"""Tests for configuration settings."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from v1cli.config.settings import (
    ProjectBookmark,
    Settings,
    StatusMapping,
    get_config_dir,
    get_settings,
    get_settings_path,
    reset_settings,
    save_settings,
)
from v1cli.config.workflow import StoryStatus


class TestStatusMapping:
    """Tests for StatusMapping."""

    def test_default_not_configured(self) -> None:
        """Default mapping is not configured."""
        mapping = StatusMapping()
        assert not mapping.is_configured()

    def test_is_configured_with_one_status(self) -> None:
        """Mapping is configured if any status is set."""
        mapping = StatusMapping(backlog="StoryStatus:100")
        assert mapping.is_configured()

    def test_is_configured_with_all_statuses(self) -> None:
        """Mapping is configured with all statuses."""
        mapping = StatusMapping(
            backlog="StoryStatus:100",
            ready="StoryStatus:101",
            in_progress="StoryStatus:102",
            review="StoryStatus:103",
            done="StoryStatus:104",
        )
        assert mapping.is_configured()

    def test_get_oid(self) -> None:
        """Test getting OID for a status."""
        mapping = StatusMapping(
            backlog="StoryStatus:100",
            in_progress="StoryStatus:102",
        )
        assert mapping.get_oid(StoryStatus.BACKLOG) == "StoryStatus:100"
        assert mapping.get_oid(StoryStatus.IN_PROGRESS) == "StoryStatus:102"
        assert mapping.get_oid(StoryStatus.READY) is None

    def test_get_status(self) -> None:
        """Test getting status for an OID."""
        mapping = StatusMapping(
            backlog="StoryStatus:100",
            in_progress="StoryStatus:102",
        )
        assert mapping.get_status("StoryStatus:100") == StoryStatus.BACKLOG
        assert mapping.get_status("StoryStatus:102") == StoryStatus.IN_PROGRESS
        assert mapping.get_status("StoryStatus:999") is None


class TestProjectBookmark:
    """Tests for ProjectBookmark model."""

    def test_create_bookmark(self) -> None:
        """Test creating a bookmark."""
        bookmark = ProjectBookmark(name="Test Project", oid="Epic:1234")
        assert bookmark.name == "Test Project"
        assert bookmark.oid == "Epic:1234"


class TestSettingsGetBookmark:
    """Tests for Settings.get_bookmark() method."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.settings = Settings(
            bookmarks=[
                ProjectBookmark(name="First Project", oid="Epic:100"),
                ProjectBookmark(name="Second Project", oid="Epic:200"),
                ProjectBookmark(name="Third Project", oid="Epic:300"),
            ]
        )

    # Project number tests (1-99)
    def test_get_bookmark_by_project_number_1(self) -> None:
        """Get first bookmark by project number 1."""
        result = self.settings.get_bookmark("1")
        assert result is not None
        assert result.name == "First Project"
        assert result.oid == "Epic:100"

    def test_get_bookmark_by_project_number_2(self) -> None:
        """Get second bookmark by project number 2."""
        result = self.settings.get_bookmark("2")
        assert result is not None
        assert result.name == "Second Project"

    def test_get_bookmark_by_project_number_3(self) -> None:
        """Get third bookmark by project number 3."""
        result = self.settings.get_bookmark("3")
        assert result is not None
        assert result.name == "Third Project"

    def test_get_bookmark_by_project_number_out_of_range(self) -> None:
        """Project number beyond bookmark count returns None."""
        result = self.settings.get_bookmark("4")
        assert result is None

    def test_get_bookmark_by_project_number_zero(self) -> None:
        """Project number 0 returns None (1-indexed)."""
        result = self.settings.get_bookmark("0")
        assert result is None

    def test_get_bookmark_by_project_number_large(self) -> None:
        """Large project number (>99) is not treated as index."""
        # This should fall through to V1 number matching
        result = self.settings.get_bookmark("100")
        assert result is not None  # Matches Epic:100 OID
        assert result.name == "First Project"

    # OID token tests
    def test_get_bookmark_by_oid_exact(self) -> None:
        """Get bookmark by exact OID token."""
        result = self.settings.get_bookmark("Epic:200")
        assert result is not None
        assert result.name == "Second Project"

    def test_get_bookmark_by_oid_case_insensitive(self) -> None:
        """OID matching is case-insensitive."""
        result = self.settings.get_bookmark("epic:200")
        assert result is not None
        assert result.name == "Second Project"

    def test_get_bookmark_by_oid_not_found(self) -> None:
        """Non-existent OID returns None."""
        result = self.settings.get_bookmark("Epic:999")
        assert result is None

    # V1 number tests (E-xxx)
    def test_get_bookmark_by_v1_number(self) -> None:
        """Get bookmark by V1 display number."""
        result = self.settings.get_bookmark("E-100")
        assert result is not None
        assert result.name == "First Project"

    def test_get_bookmark_by_v1_number_lowercase(self) -> None:
        """V1 number is case-insensitive."""
        result = self.settings.get_bookmark("e-200")
        assert result is not None
        assert result.name == "Second Project"

    def test_get_bookmark_by_v1_number_with_leading_zeros(self) -> None:
        """V1 number with leading zeros."""
        result = self.settings.get_bookmark("E-0100")
        assert result is not None
        assert result.name == "First Project"

    def test_get_bookmark_by_v1_number_not_found(self) -> None:
        """Non-existent V1 number returns None."""
        result = self.settings.get_bookmark("E-999")
        assert result is None

    # Name tests
    def test_get_bookmark_by_name_exact(self) -> None:
        """Get bookmark by exact name."""
        result = self.settings.get_bookmark("First Project")
        assert result is not None
        assert result.oid == "Epic:100"

    def test_get_bookmark_by_name_case_insensitive(self) -> None:
        """Name matching is case-insensitive."""
        result = self.settings.get_bookmark("first project")
        assert result is not None
        assert result.oid == "Epic:100"

    def test_get_bookmark_by_name_not_found(self) -> None:
        """Non-existent name returns None."""
        result = self.settings.get_bookmark("Nonexistent Project")
        assert result is None

    # Empty bookmarks
    def test_get_bookmark_empty_list(self) -> None:
        """Empty bookmarks list returns None for any query."""
        settings = Settings(bookmarks=[])
        assert settings.get_bookmark("1") is None
        assert settings.get_bookmark("Epic:100") is None
        assert settings.get_bookmark("E-100") is None
        assert settings.get_bookmark("Test") is None


class TestSettingsAddBookmark:
    """Tests for Settings.add_bookmark() method."""

    def test_add_new_bookmark(self) -> None:
        """Add a new bookmark."""
        settings = Settings()
        settings.add_bookmark("New Project", "Epic:500")

        assert len(settings.bookmarks) == 1
        assert settings.bookmarks[0].name == "New Project"
        assert settings.bookmarks[0].oid == "Epic:500"

    def test_add_multiple_bookmarks(self) -> None:
        """Add multiple bookmarks."""
        settings = Settings()
        settings.add_bookmark("Project A", "Epic:100")
        settings.add_bookmark("Project B", "Epic:200")

        assert len(settings.bookmarks) == 2

    def test_update_existing_bookmark(self) -> None:
        """Adding bookmark with existing name updates the OID."""
        settings = Settings(
            bookmarks=[ProjectBookmark(name="Existing", oid="Epic:100")]
        )
        settings.add_bookmark("Existing", "Epic:999")

        assert len(settings.bookmarks) == 1
        assert settings.bookmarks[0].oid == "Epic:999"


class TestSettingsRemoveBookmark:
    """Tests for Settings.remove_bookmark() method."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.settings = Settings(
            bookmarks=[
                ProjectBookmark(name="First", oid="Epic:100"),
                ProjectBookmark(name="Second", oid="Epic:200"),
            ],
            default_project="Epic:100",
        )

    def test_remove_by_name(self) -> None:
        """Remove bookmark by name."""
        removed = self.settings.remove_bookmark("First")

        assert removed is not None
        assert removed.name == "First"
        assert len(self.settings.bookmarks) == 1

    def test_remove_by_v1_number(self) -> None:
        """Remove bookmark by V1 number."""
        removed = self.settings.remove_bookmark("E-200")

        assert removed is not None
        assert removed.name == "Second"
        assert len(self.settings.bookmarks) == 1

    def test_remove_by_project_number(self) -> None:
        """Remove bookmark by project number."""
        removed = self.settings.remove_bookmark("1")

        assert removed is not None
        assert removed.name == "First"
        assert len(self.settings.bookmarks) == 1

    def test_remove_clears_default_if_match(self) -> None:
        """Removing default project clears the default."""
        self.settings.remove_bookmark("First")

        assert self.settings.default_project is None

    def test_remove_preserves_default_if_different(self) -> None:
        """Removing non-default project preserves the default."""
        self.settings.remove_bookmark("Second")

        assert self.settings.default_project == "Epic:100"

    def test_remove_not_found(self) -> None:
        """Removing non-existent bookmark returns None."""
        removed = self.settings.remove_bookmark("Nonexistent")

        assert removed is None
        assert len(self.settings.bookmarks) == 2


class TestSettingsPersistence:
    """Tests for settings file loading and saving."""

    def test_get_config_dir_creates_directory(self) -> None:
        """get_config_dir creates the directory if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("v1cli.config.settings.Path.home", return_value=Path(tmpdir)):
                reset_settings()
                config_dir = get_config_dir()

                assert config_dir.exists()
                assert config_dir == Path(tmpdir) / ".v1cli"

    def test_settings_path(self) -> None:
        """get_settings_path returns correct path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("v1cli.config.settings.Path.home", return_value=Path(tmpdir)):
                reset_settings()
                path = get_settings_path()

                assert path == Path(tmpdir) / ".v1cli" / "config.toml"

    def test_get_settings_default(self) -> None:
        """get_settings returns default settings when file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("v1cli.config.settings.Path.home", return_value=Path(tmpdir)):
                reset_settings()
                settings = get_settings()

                assert settings.member_oid is None
                assert settings.bookmarks == []
                assert settings.default_project is None

    def test_save_and_load_settings(self) -> None:
        """Settings can be saved and loaded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("v1cli.config.settings.Path.home", return_value=Path(tmpdir)):
                reset_settings()

                # Create and save settings
                settings = Settings(
                    member_oid="Member:20",
                    member_name="Test User",
                    bookmarks=[
                        ProjectBookmark(name="Project A", oid="Epic:100"),
                    ],
                    default_project="Epic:100",
                )
                save_settings(settings)

                # Reset cache and reload
                reset_settings()
                loaded = get_settings()

                assert loaded.member_oid == "Member:20"
                assert loaded.member_name == "Test User"
                assert len(loaded.bookmarks) == 1
                assert loaded.bookmarks[0].name == "Project A"
                assert loaded.default_project == "Epic:100"

    def test_save_settings_with_status_mapping(self) -> None:
        """Settings with status mapping can be saved and loaded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("v1cli.config.settings.Path.home", return_value=Path(tmpdir)):
                reset_settings()

                settings = Settings(
                    status_mapping=StatusMapping(
                        backlog="StoryStatus:100",
                        ready="StoryStatus:101",
                        in_progress="StoryStatus:102",
                        review="StoryStatus:103",
                        done="StoryStatus:104",
                    )
                )
                save_settings(settings)

                reset_settings()
                loaded = get_settings()

                assert loaded.status_mapping.is_configured()
                assert loaded.status_mapping.backlog == "StoryStatus:100"
                assert loaded.status_mapping.done == "StoryStatus:104"

    def test_settings_caching(self) -> None:
        """Settings are cached after first load."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("v1cli.config.settings.Path.home", return_value=Path(tmpdir)):
                reset_settings()

                settings1 = get_settings()
                settings2 = get_settings()

                # Should be same object (cached)
                assert settings1 is settings2
