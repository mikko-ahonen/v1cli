"""Tests for CLI commands."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from v1cli.api.models import DeliveryGroup, Feature, Member, Project, Story, Task
from v1cli.cli import cli
from v1cli.config.settings import ProjectBookmark, Settings, reset_settings


@pytest.fixture
def runner() -> CliRunner:
    """Create a CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_storage(tmp_path: Path):
    """Set up mock storage with temp directory."""
    with patch("v1cli.config.settings.Path.home", return_value=tmp_path):
        reset_settings()
        yield tmp_path
    reset_settings()


@pytest.fixture
def mock_client():
    """Create a mock V1Client."""
    mock = MagicMock()
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock(return_value=None)
    return mock


class TestMeCommand:
    """Tests for 'v1 me' command."""

    def test_me_success(self, runner: CliRunner, mock_storage: Path, mock_client: MagicMock) -> None:
        """me command shows user info."""
        mock_client.get_me = AsyncMock(return_value=Member(
            oid="Member:20",
            name="John Doe",
            email="john@example.com",
            username="johnd",
        ))

        with patch("v1cli.cli.V1Client", return_value=mock_client):
            result = runner.invoke(cli, ["me"])

        assert result.exit_code == 0
        assert "John Doe" in result.output
        assert "john@example.com" in result.output

    def test_me_auth_error(self, runner: CliRunner, mock_storage: Path) -> None:
        """me command handles auth error."""
        with patch("v1cli.cli.V1Client") as mock_cls:
            mock_cls.side_effect = Exception("V1_TOKEN not set")
            result = runner.invoke(cli, ["me"])

        assert result.exit_code == 1
        assert "Error" in result.output


class TestProjectsCommands:
    """Tests for project management commands."""

    def test_projects_list_empty(self, runner: CliRunner, mock_storage: Path) -> None:
        """projects list shows message when no bookmarks."""
        result = runner.invoke(cli, ["projects", "list"])

        assert result.exit_code == 0
        assert "No bookmarked projects" in result.output

    def test_projects_list_with_bookmarks(self, runner: CliRunner, mock_storage: Path) -> None:
        """projects list shows bookmarked projects."""
        # Add some bookmarks
        from v1cli.storage.local import LocalStorage
        storage = LocalStorage()
        storage.add_project_bookmark("Project A", "Epic:100")
        storage.add_project_bookmark("Project B", "Epic:200")

        result = runner.invoke(cli, ["projects", "list"])

        assert result.exit_code == 0
        assert "Project A" in result.output
        assert "Project B" in result.output
        assert "E-100" in result.output
        assert "E-200" in result.output
        # Check for project numbers
        assert "1" in result.output
        assert "2" in result.output

    def test_projects_list_shows_default(self, runner: CliRunner, mock_storage: Path) -> None:
        """projects list indicates default project."""
        from v1cli.storage.local import LocalStorage
        storage = LocalStorage()
        storage.add_project_bookmark("Default Project", "Epic:500")
        storage.set_default_project("Epic:500")

        result = runner.invoke(cli, ["projects", "list"])

        assert result.exit_code == 0
        assert "★" in result.output

    def test_projects_add(self, runner: CliRunner, mock_storage: Path, mock_client: MagicMock) -> None:
        """projects add bookmarks a project."""
        mock_client.get_project_by_number = AsyncMock(return_value=Project(
            oid="Epic:999",
            name="New Project",
            number="E-999",
        ))

        with patch("v1cli.cli.V1Client", return_value=mock_client):
            result = runner.invoke(cli, ["projects", "add", "E-999"])

        assert result.exit_code == 0
        assert "Bookmarked" in result.output

    def test_projects_add_not_found(self, runner: CliRunner, mock_storage: Path, mock_client: MagicMock) -> None:
        """projects add handles project not found."""
        mock_client.get_project_by_number = AsyncMock(return_value=None)

        with patch("v1cli.cli.V1Client", return_value=mock_client):
            result = runner.invoke(cli, ["projects", "add", "E-99999"])

        assert result.exit_code == 1
        assert "not found" in result.output

    def test_projects_rm_by_project_number(self, runner: CliRunner, mock_storage: Path) -> None:
        """projects rm removes by project number."""
        from v1cli.storage.local import LocalStorage
        storage = LocalStorage()
        storage.add_project_bookmark("First", "Epic:100")
        storage.add_project_bookmark("Second", "Epic:200")

        result = runner.invoke(cli, ["projects", "rm", "1"])

        assert result.exit_code == 0
        assert "Removed" in result.output
        assert "First" in result.output

    def test_projects_rm_by_v1_number(self, runner: CliRunner, mock_storage: Path) -> None:
        """projects rm removes by V1 number."""
        from v1cli.storage.local import LocalStorage
        storage = LocalStorage()
        storage.add_project_bookmark("Test", "Epic:300")

        result = runner.invoke(cli, ["projects", "rm", "E-300"])

        assert result.exit_code == 0
        assert "Removed" in result.output

    def test_projects_rm_not_found(self, runner: CliRunner, mock_storage: Path) -> None:
        """projects rm handles not found."""
        result = runner.invoke(cli, ["projects", "rm", "Nonexistent"])

        assert result.exit_code == 0
        assert "not found" in result.output

    def test_projects_default(self, runner: CliRunner, mock_storage: Path) -> None:
        """projects default sets default from bookmarks."""
        from v1cli.storage.local import LocalStorage
        storage = LocalStorage()
        storage.add_project_bookmark("My Project", "Epic:400")

        result = runner.invoke(cli, ["projects", "default", "1"])

        assert result.exit_code == 0
        assert "Default project set" in result.output

        # Verify it's set
        assert storage.get_default_project_oid() == "Epic:400"

    def test_projects_default_auto_bookmark(
        self, runner: CliRunner, mock_storage: Path, mock_client: MagicMock
    ) -> None:
        """projects default auto-bookmarks if not found."""
        mock_client.get_project_by_number = AsyncMock(return_value=Project(
            oid="Epic:600",
            name="Auto Project",
            number="E-600",
        ))

        with patch("v1cli.cli.V1Client", return_value=mock_client):
            result = runner.invoke(cli, ["projects", "default", "E-600"])

        assert result.exit_code == 0
        assert "Bookmarked and set as default" in result.output


class TestMineCommand:
    """Tests for 'v1 mine' command."""

    def test_mine_no_stories(self, runner: CliRunner, mock_storage: Path, mock_client: MagicMock) -> None:
        """mine shows message when no stories assigned."""
        mock_client.get_my_stories = AsyncMock(return_value=[])

        with patch("v1cli.cli.V1Client", return_value=mock_client):
            result = runner.invoke(cli, ["mine"])

        assert result.exit_code == 0
        assert "No stories assigned" in result.output

    def test_mine_with_stories(self, runner: CliRunner, mock_storage: Path, mock_client: MagicMock) -> None:
        """mine shows assigned stories."""
        mock_client.get_my_stories = AsyncMock(return_value=[
            Story(
                oid="Story:100",
                number="S-100",
                name="Test Story",
                status="In Progress",
                scope_name="Test Project",
            ),
        ])

        with patch("v1cli.cli.V1Client", return_value=mock_client):
            result = runner.invoke(cli, ["mine"])

        assert result.exit_code == 0
        assert "S-100" in result.output
        assert "Test Story" in result.output


class TestStoriesCommand:
    """Tests for 'v1 stories' command."""

    def test_stories_under_feature(
        self, runner: CliRunner, mock_storage: Path, mock_client: MagicMock
    ) -> None:
        """stories lists stories under a feature."""
        mock_client.get_feature_by_number = AsyncMock(return_value=Feature(
            oid="Epic:50",
            number="E-50",
            name="Parent Feature",
        ))
        mock_client.get_stories = AsyncMock(return_value=[
            Story(oid="Story:1", number="S-1", name="Child Story", scope_name="Project"),
        ])

        with patch("v1cli.cli.V1Client", return_value=mock_client):
            result = runner.invoke(cli, ["stories", "E-50"])

        assert result.exit_code == 0
        assert "S-1" in result.output
        assert "Child Story" in result.output

    def test_stories_feature_not_found(
        self, runner: CliRunner, mock_storage: Path, mock_client: MagicMock
    ) -> None:
        """stories handles feature not found."""
        mock_client.get_feature_by_number = AsyncMock(return_value=None)

        with patch("v1cli.cli.V1Client", return_value=mock_client):
            result = runner.invoke(cli, ["stories", "E-99999"])

        assert result.exit_code == 1
        assert "not found" in result.output


class TestStoryCommand:
    """Tests for 'v1 story' command."""

    def test_story_command_exists(self, runner: CliRunner) -> None:
        """story command group is registered."""
        result = runner.invoke(cli, ["story", "--help"])
        # The story group should show help
        assert result.exit_code == 0
        assert "create" in result.output.lower()

    def test_story_create_help(self, runner: CliRunner) -> None:
        """story create subcommand has help."""
        result = runner.invoke(cli, ["story", "create", "--help"])
        assert result.exit_code == 0
        assert "NAME" in result.output


class TestStatusCommand:
    """Tests for 'v1 status' command."""

    def test_status_change(
        self, runner: CliRunner, mock_storage: Path, mock_client: MagicMock
    ) -> None:
        """status changes story status."""
        # Set up status mapping
        from v1cli.config.settings import get_settings, save_settings, StatusMapping
        settings = get_settings()
        settings.status_mapping = StatusMapping(
            backlog="StoryStatus:100",
            ready="StoryStatus:101",
            in_progress="StoryStatus:102",
            review="StoryStatus:103",
            done="StoryStatus:104",
        )
        save_settings(settings)

        mock_client.get_story_by_number = AsyncMock(return_value=Story(
            oid="Story:100",
            number="S-100",
            name="Test",
            scope_name="Project",
        ))
        mock_client.update_story_status = AsyncMock(return_value=True)

        with patch("v1cli.cli.V1Client", return_value=mock_client):
            result = runner.invoke(cli, ["status", "S-100", "progress"])

        assert result.exit_code == 0
        assert "Updated" in result.output

    def test_status_not_configured(self, runner: CliRunner, mock_storage: Path) -> None:
        """status shows error when not configured."""
        result = runner.invoke(cli, ["status", "S-100", "progress"])

        assert result.exit_code == 1
        assert "not configured" in result.output

    def test_status_invalid(self, runner: CliRunner, mock_storage: Path) -> None:
        """status handles invalid status."""
        # Set up status mapping
        from v1cli.config.settings import get_settings, save_settings, StatusMapping
        settings = get_settings()
        settings.status_mapping = StatusMapping(in_progress="StoryStatus:102")
        save_settings(settings)

        result = runner.invoke(cli, ["status", "S-100", "invalid"])

        assert result.exit_code == 1
        assert "Invalid status" in result.output


class TestTasksCommand:
    """Tests for 'v1 tasks' command."""

    def test_tasks_list(
        self, runner: CliRunner, mock_storage: Path, mock_client: MagicMock
    ) -> None:
        """tasks lists tasks for a story."""
        mock_client.get_story_by_number = AsyncMock(return_value=Story(
            oid="Story:100",
            number="S-100",
            name="Test Story",
            scope_name="Project",
        ))
        mock_client.get_tasks = AsyncMock(return_value=[
            Task(
                oid="Task:1",
                number="TK-1",
                name="First Task",
                parent_oid="Story:100",
                status="Done",
            ),
            Task(
                oid="Task:2",
                number="TK-2",
                name="Second Task",
                parent_oid="Story:100",
                status="In Progress",
                todo=3.0,
                done=1.0,
            ),
        ])

        with patch("v1cli.cli.V1Client", return_value=mock_client):
            result = runner.invoke(cli, ["tasks", "S-100"])

        assert result.exit_code == 0
        assert "TK-1" in result.output
        assert "First Task" in result.output
        assert "TK-2" in result.output

    def test_tasks_no_tasks(
        self, runner: CliRunner, mock_storage: Path, mock_client: MagicMock
    ) -> None:
        """tasks shows message when no tasks."""
        mock_client.get_story_by_number = AsyncMock(return_value=Story(
            oid="Story:100",
            number="S-100",
            name="Test Story",
            scope_name="Project",
        ))
        mock_client.get_tasks = AsyncMock(return_value=[])

        with patch("v1cli.cli.V1Client", return_value=mock_client):
            result = runner.invoke(cli, ["tasks", "S-100"])

        assert result.exit_code == 0
        assert "No tasks" in result.output


class TestTaskDoneCommand:
    """Tests for 'v1 task done' command."""

    def test_task_done(
        self, runner: CliRunner, mock_storage: Path, mock_client: MagicMock
    ) -> None:
        """task done marks task as complete."""
        mock_client.get_task_by_identifier = AsyncMock(return_value=Task(
            oid="Task:100",
            number="TK-100",
            name="Test Task",
            parent_oid="Story:50",
        ))
        mock_client.complete_task = AsyncMock(return_value=True)

        with patch("v1cli.cli.V1Client", return_value=mock_client):
            result = runner.invoke(cli, ["task", "done", "TK-100"])

        assert result.exit_code == 0
        assert "done" in result.output.lower()

    def test_task_done_by_oid(
        self, runner: CliRunner, mock_storage: Path, mock_client: MagicMock
    ) -> None:
        """task done works with OID token."""
        mock_client.get_task_by_identifier = AsyncMock(return_value=Task(
            oid="Task:200",
            number="TK-200",
            name="Test Task",
            parent_oid="Story:50",
        ))
        mock_client.complete_task = AsyncMock(return_value=True)

        with patch("v1cli.cli.V1Client", return_value=mock_client):
            result = runner.invoke(cli, ["task", "done", "Task:200"])

        assert result.exit_code == 0


class TestFeaturesCommand:
    """Tests for 'v1 features' command."""

    def test_features_list(
        self, runner: CliRunner, mock_storage: Path, mock_client: MagicMock
    ) -> None:
        """features lists features under a project."""
        # Set up default project
        from v1cli.storage.local import LocalStorage
        storage = LocalStorage()
        storage.add_project_bookmark("Test", "Epic:1000")
        storage.set_default_project("Epic:1000")

        mock_client.get_features = AsyncMock(return_value=[
            Feature(
                oid="Epic:100",
                number="E-100",
                name="Feature A",
                scope_name="Test",
            ),
        ])

        with patch("v1cli.cli.V1Client", return_value=mock_client):
            result = runner.invoke(cli, ["features"])

        assert result.exit_code == 0
        assert "E-100" in result.output
        assert "Feature A" in result.output

    def test_features_no_default(self, runner: CliRunner, mock_storage: Path) -> None:
        """features shows error when no default project."""
        # Test without any default project set - should fail before API call
        # Use env vars to provide auth but no default project
        result = runner.invoke(cli, ["features"], env={
            "V1_URL": "https://test.example.com",
            "V1_TOKEN": "test-token",
        })

        # Should exit with error because no project specified
        assert result.exit_code == 1
        assert "No project specified" in result.output or "no default" in result.output.lower()


class TestStoryCreateCommand:
    """Tests for 'v1 story create' command."""

    def test_story_create(
        self, runner: CliRunner, mock_storage: Path, mock_client: MagicMock
    ) -> None:
        """story create creates a new story."""
        from v1cli.storage.local import LocalStorage
        storage = LocalStorage()
        storage.add_project_bookmark("Test", "Epic:1000")
        storage.set_default_project("Epic:1000")

        mock_client.create_story = AsyncMock(return_value="Story:999")

        with patch("v1cli.cli.V1Client", return_value=mock_client):
            result = runner.invoke(cli, ["story", "create", "New Story", "-s", "3"])

        assert result.exit_code == 0
        assert "Created" in result.output
        assert "Story:999" in result.output

    def test_story_create_with_feature(
        self, runner: CliRunner, mock_storage: Path, mock_client: MagicMock
    ) -> None:
        """story create with feature parent."""
        from v1cli.storage.local import LocalStorage
        storage = LocalStorage()
        storage.add_project_bookmark("Test", "Epic:1000")
        storage.set_default_project("Epic:1000")

        mock_client.get_feature_by_number = AsyncMock(return_value=Feature(
            oid="Epic:100",
            number="E-100",
            name="Parent",
        ))
        mock_client.create_story = AsyncMock(return_value="Story:888")

        with patch("v1cli.cli.V1Client", return_value=mock_client):
            result = runner.invoke(cli, ["story", "create", "New Story", "-e", "E-100"])

        assert result.exit_code == 0
        assert "Created" in result.output


class TestHelpMessages:
    """Tests for CLI help messages."""

    def test_main_help(self, runner: CliRunner) -> None:
        """Main help is displayed."""
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "V1CLI" in result.output

    def test_projects_help(self, runner: CliRunner) -> None:
        """projects help mentions project numbers."""
        result = runner.invoke(cli, ["projects", "--help"])

        assert result.exit_code == 0
        assert "projects" in result.output.lower()

    def test_projects_rm_help(self, runner: CliRunner) -> None:
        """projects rm help shows identifier options."""
        result = runner.invoke(cli, ["projects", "rm", "--help"])

        assert result.exit_code == 0
        assert "1-99" in result.output
        assert "E-nnnnn" in result.output
        assert "Epic:nnnnn" in result.output

    def test_roadmap_help(self, runner: CliRunner) -> None:
        """roadmap help shows project option."""
        result = runner.invoke(cli, ["roadmap", "--help"])

        assert result.exit_code == 0
        assert "Project #" in result.output

    def test_tree_help(self, runner: CliRunner) -> None:
        """tree help shows depth options."""
        result = runner.invoke(cli, ["tree", "--help"])

        assert result.exit_code == 0
        assert "depth" in result.output.lower()
        assert "deliveries" in result.output
        assert "features" in result.output
        assert "stories" in result.output
        assert "tasks" in result.output


class TestTreeCommand:
    """Tests for 'v1 tree' command."""

    def test_tree_with_deliveries(
        self, runner: CliRunner, mock_storage: Path, mock_client: MagicMock
    ) -> None:
        """tree shows project hierarchy."""
        from v1cli.storage.local import LocalStorage
        storage = LocalStorage()
        storage.add_project_bookmark("Test Project", "Epic:1000")
        storage.set_default_project("Epic:1000")

        mock_client.get_project_by_number = AsyncMock(return_value=Project(
            oid="Epic:1000",
            number="E-1000",
            name="Test Project",
        ))
        mock_client.get_delivery_groups = AsyncMock(return_value=[
            DeliveryGroup(
                oid="Epic:100",
                number="E-100",
                name="Q1 Release",
                status="In Progress",
            ),
        ])
        mock_client.get_features = AsyncMock(return_value=[
            Feature(
                oid="Epic:200",
                number="E-200",
                name="Feature A",
                status="Active",
            ),
        ])
        mock_client.get_stories = AsyncMock(return_value=[
            Story(
                oid="Story:300",
                number="S-300",
                name="Story 1",
                scope_name="Test",
                estimate=5.0,
            ),
        ])

        with patch("v1cli.cli.V1Client", return_value=mock_client):
            result = runner.invoke(cli, ["tree", "--depth", "stories"])

        assert result.exit_code == 0
        assert "Test Project" in result.output
        assert "E-100" in result.output
        assert "Q1 Release" in result.output
        assert "E-200" in result.output
        assert "Feature A" in result.output
        assert "S-300" in result.output
        assert "Story 1" in result.output

    def test_tree_deliveries_only(
        self, runner: CliRunner, mock_storage: Path, mock_client: MagicMock
    ) -> None:
        """tree --depth deliveries shows only delivery groups."""
        from v1cli.storage.local import LocalStorage
        storage = LocalStorage()
        storage.add_project_bookmark("Test", "Epic:1000")
        storage.set_default_project("Epic:1000")

        mock_client.get_project_by_number = AsyncMock(return_value=Project(
            oid="Epic:1000",
            number="E-1000",
            name="Test Project",
        ))
        mock_client.get_delivery_groups = AsyncMock(return_value=[
            DeliveryGroup(
                oid="Epic:100",
                number="E-100",
                name="Q1 Release",
            ),
        ])
        mock_client.get_features = AsyncMock(return_value=[])

        with patch("v1cli.cli.V1Client", return_value=mock_client):
            result = runner.invoke(cli, ["tree", "--depth", "deliveries"])

        assert result.exit_code == 0
        assert "E-100" in result.output
        # Features should not be fetched when depth is deliveries
        mock_client.get_stories.assert_not_called()

    def test_tree_no_items(
        self, runner: CliRunner, mock_storage: Path, mock_client: MagicMock
    ) -> None:
        """tree shows message when no items."""
        from v1cli.storage.local import LocalStorage
        storage = LocalStorage()
        storage.add_project_bookmark("Empty", "Epic:1000")
        storage.set_default_project("Epic:1000")

        mock_client.get_project_by_number = AsyncMock(return_value=Project(
            oid="Epic:1000",
            number="E-1000",
            name="Empty Project",
        ))
        mock_client.get_delivery_groups = AsyncMock(return_value=[])
        mock_client.get_features = AsyncMock(return_value=[])

        with patch("v1cli.cli.V1Client", return_value=mock_client):
            result = runner.invoke(cli, ["tree"])

        assert result.exit_code == 0
        assert "No items found" in result.output

    def test_tree_no_default_project(
        self, runner: CliRunner, mock_storage: Path, mock_client: MagicMock
    ) -> None:
        """tree errors without default project."""
        with patch("v1cli.cli.V1Client", return_value=mock_client):
            result = runner.invoke(cli, ["tree"])

        assert result.exit_code == 1
        assert "No project specified" in result.output
