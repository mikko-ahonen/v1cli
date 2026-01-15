"""Tests for VersionOne API client."""

import pytest
from httpx import Response
from pytest_httpx import HTTPXMock

from v1cli.api.client import V1APIError, V1Client
from v1cli.api.models import DeliveryGroup, Feature, Member, Project, Story, Task


# Test base URL and token
TEST_URL = "https://v1test.example.com"
TEST_TOKEN = "test-token-123"


@pytest.fixture
def client() -> V1Client:
    """Create a test client."""
    return V1Client(base_url=TEST_URL, token=TEST_TOKEN)


class TestV1ClientContext:
    """Tests for client context management."""

    async def test_context_manager(self, client: V1Client) -> None:
        """Client works as async context manager."""
        async with client as c:
            assert c._client is not None
        assert client._client is None

    async def test_client_property_outside_context(self, client: V1Client) -> None:
        """Accessing client property outside context raises error."""
        with pytest.raises(RuntimeError, match="must be used as async context manager"):
            _ = client.client


class TestV1ClientGetMe:
    """Tests for get_me method."""

    async def test_get_me_success(self, client: V1Client, httpx_mock: HTTPXMock) -> None:
        """get_me returns current user info."""
        httpx_mock.add_response(
            url=f"{TEST_URL}/query.v1",
            json=[[{
                "_oid": "Member:20",
                "Name": "John Doe",
                "Email": "john@example.com",
                "Username": "johnd",
            }]],
        )

        async with client:
            member = await client.get_me()

        assert member.oid == "Member:20"
        assert member.name == "John Doe"
        assert member.email == "john@example.com"
        assert member.username == "johnd"

    async def test_get_me_not_found(self, client: V1Client, httpx_mock: HTTPXMock) -> None:
        """get_me raises error when member not found."""
        httpx_mock.add_response(url=f"{TEST_URL}/query.v1", json=[[]])

        async with client:
            with pytest.raises(V1APIError, match="Could not find current user"):
                await client.get_me()


class TestV1ClientStories:
    """Tests for story-related methods."""

    async def test_get_stories(self, client: V1Client, httpx_mock: HTTPXMock) -> None:
        """get_stories returns stories under a parent."""
        httpx_mock.add_response(
            url=f"{TEST_URL}/query.v1",
            json=[[
                {
                    "_oid": "Story:100",
                    "Number": "S-100",
                    "Name": "First Story",
                    "Description": "Description 1",
                    "Status.Name": "In Progress",
                    "Status": {"_oid": "StoryStatus:135"},
                    "Scope.Name": "Test Project",
                    "Scope": {"_oid": "Scope:1"},
                    "Owners.Name": ["John Doe"],
                    "Owners": [{"_oid": "Member:20"}],
                    "Super.Name": "Parent Feature",
                    "Super": {"_oid": "Epic:50"},
                    "Estimate": 5.0,
                },
                {
                    "_oid": "Story:101",
                    "Number": "S-101",
                    "Name": "Second Story",
                    "Status.Name": "Ready",
                    "Scope.Name": "Test Project",
                    "Scope": {"_oid": "Scope:1"},
                },
            ]],
        )

        async with client:
            stories = await client.get_stories("Epic:50")

        assert len(stories) == 2
        assert stories[0].oid == "Story:100"
        assert stories[0].number == "S-100"
        assert stories[0].name == "First Story"
        assert stories[0].status == "In Progress"
        assert stories[0].estimate == 5.0
        assert stories[1].oid == "Story:101"

    async def test_get_story_by_number(self, client: V1Client, httpx_mock: HTTPXMock) -> None:
        """get_story_by_number returns story by display number."""
        httpx_mock.add_response(
            url=f"{TEST_URL}/query.v1",
            json=[[{
                "_oid": "Story:500",
                "Number": "S-500",
                "Name": "Test Story",
                "Status.Name": "Done",
                "Status": {"_oid": "StoryStatus:136"},
                "Scope.Name": "Project",
                "Scope": {"_oid": "Scope:1"},
                "Owners.Name": [],
                "Owners": [],
            }]],
        )

        async with client:
            story = await client.get_story_by_number("S-500")

        assert story is not None
        assert story.oid == "Story:500"
        assert story.number == "S-500"

    async def test_get_story_by_oid_token(self, client: V1Client, httpx_mock: HTTPXMock) -> None:
        """get_story_by_number works with OID token."""
        httpx_mock.add_response(
            url=f"{TEST_URL}/query.v1",
            json=[[{
                "_oid": "Story:600",
                "Number": "S-600",
                "Name": "Test Story",
                "Scope.Name": "Project",
                "Scope": {"_oid": "Scope:1"},
            }]],
        )

        async with client:
            story = await client.get_story_by_number("Story:600")

        assert story is not None
        assert story.oid == "Story:600"

    async def test_get_story_not_found(self, client: V1Client, httpx_mock: HTTPXMock) -> None:
        """get_story_by_number returns None when not found."""
        httpx_mock.add_response(url=f"{TEST_URL}/query.v1", json=[[]])

        async with client:
            story = await client.get_story_by_number("S-99999")

        assert story is None

    async def test_get_my_stories(self, client: V1Client, httpx_mock: HTTPXMock) -> None:
        """get_my_stories returns stories assigned to current user."""
        # Only need stories query - uses Owners.IsSelf='true' filter
        httpx_mock.add_response(
            url=f"{TEST_URL}/query.v1",
            json=[[{
                "_oid": "Story:200",
                "Number": "S-200",
                "Name": "My Story",
                "Scope.Name": "Project",
                "Scope": {"_oid": "Scope:1"},
            }]],
        )

        async with client:
            stories = await client.get_my_stories()

        assert len(stories) == 1
        assert stories[0].oid == "Story:200"

    async def test_create_story(self, client: V1Client, httpx_mock: HTTPXMock) -> None:
        """create_story creates a new story."""
        httpx_mock.add_response(
            url=f"{TEST_URL}/api/asset",
            json={"oid": "Story:999"},
        )

        async with client:
            oid = await client.create_story(
                name="New Story",
                project_oid="Scope:1",
                feature_oid="Epic:100",
                estimate=3.0,
                description="Test description",
            )

        assert oid == "Story:999"

    async def test_update_story_status(self, client: V1Client, httpx_mock: HTTPXMock) -> None:
        """update_story_status updates the status."""
        httpx_mock.add_response(url=f"{TEST_URL}/api/asset", json={})

        async with client:
            result = await client.update_story_status("Story:100", "StoryStatus:135")

        assert result is True


class TestV1ClientFeatures:
    """Tests for feature-related methods."""

    async def test_get_features(self, client: V1Client, httpx_mock: HTTPXMock) -> None:
        """get_features returns features under a parent."""
        httpx_mock.add_response(
            url=f"{TEST_URL}/query.v1",
            json=[[
                {
                    "_oid": "Epic:100",
                    "Number": "E-100",
                    "Name": "Feature A",
                    "Type.Name": "Feature",
                    "Scope.Name": "Project",
                    "Scope": {"_oid": "Scope:1"},
                    "Status.Name": "Active",
                },
            ]],
        )

        async with client:
            features = await client.get_features("Epic:50")

        assert len(features) == 1
        assert features[0].oid == "Epic:100"
        assert features[0].name == "Feature A"

    async def test_get_feature_by_number(self, client: V1Client, httpx_mock: HTTPXMock) -> None:
        """get_feature_by_number returns feature by display number."""
        httpx_mock.add_response(
            url=f"{TEST_URL}/query.v1",
            json=[[{
                "_oid": "Epic:200",
                "Number": "E-200",
                "Name": "Test Feature",
                "Type.Name": "Feature",
                "Scope.Name": "Project",
                "Scope": {"_oid": "Scope:1"},
            }]],
        )

        async with client:
            feature = await client.get_feature_by_number("E-200")

        assert feature is not None
        assert feature.oid == "Epic:200"

    async def test_get_feature_by_oid_token(self, client: V1Client, httpx_mock: HTTPXMock) -> None:
        """get_feature_by_number works with OID token."""
        httpx_mock.add_response(
            url=f"{TEST_URL}/query.v1",
            json=[[{
                "_oid": "Epic:300",
                "Number": "E-300",
                "Name": "Test Feature",
                "Scope.Name": "Project",
                "Scope": {"_oid": "Scope:1"},
            }]],
        )

        async with client:
            feature = await client.get_feature_by_number("Epic:300")

        assert feature is not None
        assert feature.oid == "Epic:300"

    async def test_create_feature(self, client: V1Client, httpx_mock: HTTPXMock) -> None:
        """create_feature creates a new feature."""
        httpx_mock.add_response(
            url=f"{TEST_URL}/api/asset",
            json={"oid": "Epic:888"},
        )

        async with client:
            oid = await client.create_feature(
                name="New Feature",
                parent_oid="Epic:50",
                description="Test",
            )

        assert oid == "Epic:888"


class TestV1ClientProjects:
    """Tests for project-related methods."""

    async def test_get_projects(self, client: V1Client, httpx_mock: HTTPXMock) -> None:
        """get_projects returns all projects."""
        httpx_mock.add_response(
            url=f"{TEST_URL}/query.v1",
            json=[[
                {
                    "_oid": "Epic:1000",
                    "Number": "E-1000",
                    "Name": "Backend Project",
                    "Category.Name": "Business Epic",
                    "Status.Name": "Active",
                },
                {
                    "_oid": "Epic:2000",
                    "Number": "E-2000",
                    "Name": "Frontend Project",
                    "Category.Name": "Business Epic",
                    "Status.Name": "Active",
                },
            ]],
        )

        async with client:
            projects = await client.get_projects()

        assert len(projects) == 2
        assert projects[0].oid == "Epic:1000"
        assert projects[0].name == "Backend Project"

    async def test_get_project_by_number(self, client: V1Client, httpx_mock: HTTPXMock) -> None:
        """get_project_by_number returns project by display number."""
        httpx_mock.add_response(
            url=f"{TEST_URL}/query.v1",
            json=[[{
                "_oid": "Epic:5000",
                "Number": "E-5000",
                "Name": "Test Project",
                "Category.Name": "Business Epic",
            }]],
        )

        async with client:
            project = await client.get_project_by_number("E-5000")

        assert project is not None
        assert project.oid == "Epic:5000"

    async def test_get_project_by_oid_token(self, client: V1Client, httpx_mock: HTTPXMock) -> None:
        """get_project_by_number works with OID token."""
        httpx_mock.add_response(
            url=f"{TEST_URL}/query.v1",
            json=[[{
                "_oid": "Epic:6000",
                "Number": "E-6000",
                "Name": "Test Project",
            }]],
        )

        async with client:
            project = await client.get_project_by_number("Epic:6000")

        assert project is not None
        assert project.oid == "Epic:6000"

    async def test_get_project_by_name(self, client: V1Client, httpx_mock: HTTPXMock) -> None:
        """get_project_by_name returns project by name."""
        httpx_mock.add_response(
            url=f"{TEST_URL}/query.v1",
            json=[[{
                "_oid": "Epic:7000",
                "Number": "E-7000",
                "Name": "My Project",
            }]],
        )

        async with client:
            project = await client.get_project_by_name("My Project")

        assert project is not None
        assert project.oid == "Epic:7000"


class TestV1ClientTasks:
    """Tests for task-related methods."""

    async def test_get_tasks(self, client: V1Client, httpx_mock: HTTPXMock) -> None:
        """get_tasks returns tasks for a story."""
        httpx_mock.add_response(
            url=f"{TEST_URL}/query.v1",
            json=[[
                {
                    "_oid": "Task:100",
                    "Number": "TK-100",
                    "Name": "Task One",
                    "Parent": {"_oid": "Story:50"},
                    "Parent.Number": "S-50",
                    "Status.Name": "In Progress",
                    "Status": {"_oid": "TaskStatus:10"},
                    "Owners.Name": ["Alice"],
                    "ToDo": 2.0,
                    "Actuals": 1.5,
                },
                {
                    "_oid": "Task:101",
                    "Number": "TK-101",
                    "Name": "Task Two",
                    "Parent": {"_oid": "Story:50"},
                    "Status.Name": "Done",
                },
            ]],
        )

        async with client:
            tasks = await client.get_tasks("Story:50")

        assert len(tasks) == 2
        assert tasks[0].oid == "Task:100"
        assert tasks[0].number == "TK-100"
        assert tasks[0].todo == 2.0
        assert tasks[0].done == 1.5
        assert tasks[1].oid == "Task:101"
        assert tasks[1].is_done is True

    async def test_get_task_by_identifier_number(
        self, client: V1Client, httpx_mock: HTTPXMock
    ) -> None:
        """get_task_by_identifier works with TK-xxx format."""
        httpx_mock.add_response(
            url=f"{TEST_URL}/query.v1",
            json=[[{
                "_oid": "Task:200",
                "Number": "TK-200",
                "Name": "Test Task",
                "Parent": {"_oid": "Story:100"},
            }]],
        )

        async with client:
            task = await client.get_task_by_identifier("TK-200")

        assert task is not None
        assert task.oid == "Task:200"

    async def test_get_task_by_identifier_oid(
        self, client: V1Client, httpx_mock: HTTPXMock
    ) -> None:
        """get_task_by_identifier works with OID token."""
        httpx_mock.add_response(
            url=f"{TEST_URL}/query.v1",
            json=[[{
                "_oid": "Task:300",
                "Number": "TK-300",
                "Name": "Test Task",
                "Parent": {"_oid": "Story:100"},
            }]],
        )

        async with client:
            task = await client.get_task_by_identifier("Task:300")

        assert task is not None
        assert task.oid == "Task:300"

    async def test_create_task(self, client: V1Client, httpx_mock: HTTPXMock) -> None:
        """create_task creates a new task."""
        httpx_mock.add_response(
            url=f"{TEST_URL}/api/asset",
            json={"oid": "Task:777"},
        )

        async with client:
            oid = await client.create_task(
                name="New Task",
                story_oid="Story:100",
                estimate=4.0,
            )

        assert oid == "Task:777"

    async def test_complete_task(self, client: V1Client, httpx_mock: HTTPXMock) -> None:
        """complete_task marks task as done."""
        httpx_mock.add_response(url=f"{TEST_URL}/api/asset", json={})

        async with client:
            result = await client.complete_task("Task:100")

        assert result is True


class TestV1ClientDeliveryGroups:
    """Tests for delivery group methods."""

    async def test_get_delivery_groups(self, client: V1Client, httpx_mock: HTTPXMock) -> None:
        """get_delivery_groups returns delivery groups for a project."""
        httpx_mock.add_response(
            url=f"{TEST_URL}/query.v1",
            json=[[
                {
                    "_oid": "Epic:500",
                    "Number": "E-500",
                    "Name": "Q1 Release",
                    "Status.Name": "In Progress",
                    "Type.Name": "Release",
                    "PlannedStart": "2024-01-01",
                    "PlannedEnd": "2024-03-31",
                    "PercentDone": 0.5,
                    "Estimate": 100.0,
                },
            ]],
        )

        async with client:
            groups = await client.get_delivery_groups("Epic:1000")

        assert len(groups) == 1
        assert groups[0].oid == "Epic:500"
        assert groups[0].name == "Q1 Release"
        assert groups[0].delivery_type == "Release"
        assert groups[0].planned_start == "2024-01-01"
        assert groups[0].planned_end == "2024-03-31"
        assert groups[0].progress == 0.5
        assert groups[0].estimate == 100.0


class TestV1ClientStatuses:
    """Tests for status-related methods."""

    async def test_get_story_statuses(self, client: V1Client, httpx_mock: HTTPXMock) -> None:
        """get_story_statuses returns available statuses."""
        httpx_mock.add_response(
            url=f"{TEST_URL}/query.v1",
            json=[[
                {"_oid": "StoryStatus:133", "Name": "None"},
                {"_oid": "StoryStatus:134", "Name": "Future"},
                {"_oid": "StoryStatus:135", "Name": "In Progress"},
                {"_oid": "StoryStatus:136", "Name": "Done"},
            ]],
        )

        async with client:
            statuses = await client.get_story_statuses()

        assert len(statuses) == 4
        assert statuses[0].oid == "StoryStatus:133"
        assert statuses[0].name == "None"
        assert statuses[2].name == "In Progress"


class TestV1ClientErrorHandling:
    """Tests for error handling."""

    async def test_401_unauthorized(self, client: V1Client, httpx_mock: HTTPXMock) -> None:
        """401 response raises authentication error."""
        httpx_mock.add_response(url=f"{TEST_URL}/query.v1", status_code=401)

        async with client:
            with pytest.raises(V1APIError, match="Authentication failed"):
                await client.get_me()

    async def test_403_forbidden(self, client: V1Client, httpx_mock: HTTPXMock) -> None:
        """403 response raises API error."""
        httpx_mock.add_response(
            url=f"{TEST_URL}/query.v1",
            status_code=403,
            json={"message": "Access denied"},
        )

        async with client:
            with pytest.raises(V1APIError, match="Access denied"):
                await client.get_me()

    async def test_404_not_found(self, client: V1Client, httpx_mock: HTTPXMock) -> None:
        """404 response raises not found error."""
        httpx_mock.add_response(url=f"{TEST_URL}/query.v1", status_code=404)

        async with client:
            with pytest.raises(V1APIError, match="not found"):
                await client.get_me()

    async def test_500_server_error(self, client: V1Client, httpx_mock: HTTPXMock) -> None:
        """500 response raises server error."""
        httpx_mock.add_response(url=f"{TEST_URL}/query.v1", status_code=500)

        async with client:
            with pytest.raises(V1APIError) as exc_info:
                await client.get_me()
            assert exc_info.value.status_code == 500

    async def test_error_response_body(self, client: V1Client, httpx_mock: HTTPXMock) -> None:
        """Error response body is included in exception."""
        httpx_mock.add_response(
            url=f"{TEST_URL}/query.v1",
            status_code=400,
            json={"message": "Invalid query syntax"},
        )

        async with client:
            with pytest.raises(V1APIError, match="Invalid query syntax"):
                await client.get_me()
