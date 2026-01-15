"""Tests for local storage utilities."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from v1cli.config.settings import ProjectBookmark, Settings, reset_settings
from v1cli.storage.local import LocalStorage


class TestLocalStorage:
    """Tests for LocalStorage class."""

    def setup_method(self) -> None:
        """Set up a fresh storage instance for each test."""
        self.tmpdir = tempfile.mkdtemp()
        self.patcher = patch(
            "v1cli.config.settings.Path.home",
            return_value=Path(self.tmpdir)
        )
        self.patcher.start()
        reset_settings()
        self.storage = LocalStorage()

    def teardown_method(self) -> None:
        """Clean up after each test."""
        self.patcher.stop()
        reset_settings()

    def test_config_dir(self) -> None:
        """Config directory is created and accessible."""
        assert self.storage.config_dir.exists()
        assert self.storage.config_dir == Path(self.tmpdir) / ".v1cli"

    def test_settings_property(self) -> None:
        """Settings property returns current settings."""
        settings = self.storage.settings
        assert isinstance(settings, Settings)

    def test_cache_member(self) -> None:
        """cache_member stores member info."""
        self.storage.cache_member("Member:20", "John Doe")

        assert self.storage.settings.member_oid == "Member:20"
        assert self.storage.settings.member_name == "John Doe"

    def test_get_cached_member_oid(self) -> None:
        """get_cached_member_oid returns the cached OID."""
        assert self.storage.get_cached_member_oid() is None

        self.storage.cache_member("Member:30", "Jane Doe")
        assert self.storage.get_cached_member_oid() == "Member:30"

    def test_add_project_bookmark(self) -> None:
        """add_project_bookmark adds a new bookmark."""
        self.storage.add_project_bookmark("Test Project", "Epic:100")

        bookmarks = self.storage.settings.bookmarks
        assert len(bookmarks) == 1
        assert bookmarks[0].name == "Test Project"
        assert bookmarks[0].oid == "Epic:100"

    def test_add_project_bookmark_persists(self) -> None:
        """Added bookmark persists after reload."""
        self.storage.add_project_bookmark("Test Project", "Epic:100")

        # Reset cache and reload
        reset_settings()
        new_storage = LocalStorage()

        bookmarks = new_storage.settings.bookmarks
        assert len(bookmarks) == 1
        assert bookmarks[0].name == "Test Project"

    def test_remove_project_bookmark_by_name(self) -> None:
        """remove_project_bookmark removes by name."""
        self.storage.add_project_bookmark("Project A", "Epic:100")
        self.storage.add_project_bookmark("Project B", "Epic:200")

        result = self.storage.remove_project_bookmark("Project A")

        assert result == ("Project A", "Epic:100")
        assert len(self.storage.settings.bookmarks) == 1
        assert self.storage.settings.bookmarks[0].name == "Project B"

    def test_remove_project_bookmark_by_v1_number(self) -> None:
        """remove_project_bookmark removes by V1 number."""
        self.storage.add_project_bookmark("Project A", "Epic:100")

        result = self.storage.remove_project_bookmark("E-100")

        assert result == ("Project A", "Epic:100")
        assert len(self.storage.settings.bookmarks) == 0

    def test_remove_project_bookmark_by_project_number(self) -> None:
        """remove_project_bookmark removes by project number."""
        self.storage.add_project_bookmark("Project A", "Epic:100")
        self.storage.add_project_bookmark("Project B", "Epic:200")

        result = self.storage.remove_project_bookmark("2")

        assert result == ("Project B", "Epic:200")
        assert len(self.storage.settings.bookmarks) == 1

    def test_remove_project_bookmark_not_found(self) -> None:
        """remove_project_bookmark returns None when not found."""
        self.storage.add_project_bookmark("Project A", "Epic:100")

        result = self.storage.remove_project_bookmark("Nonexistent")

        assert result is None
        assert len(self.storage.settings.bookmarks) == 1

    def test_set_default_project(self) -> None:
        """set_default_project sets the default."""
        self.storage.set_default_project("Epic:100")

        assert self.storage.settings.default_project == "Epic:100"

    def test_get_default_project_oid(self) -> None:
        """get_default_project_oid returns the default OID."""
        assert self.storage.get_default_project_oid() is None

        self.storage.set_default_project("Epic:200")
        assert self.storage.get_default_project_oid() == "Epic:200"

    def test_get_bookmarked_project_oids(self) -> None:
        """get_bookmarked_project_oids returns all OIDs."""
        assert self.storage.get_bookmarked_project_oids() == []

        self.storage.add_project_bookmark("A", "Epic:100")
        self.storage.add_project_bookmark("B", "Epic:200")
        self.storage.add_project_bookmark("C", "Epic:300")

        oids = self.storage.get_bookmarked_project_oids()
        assert oids == ["Epic:100", "Epic:200", "Epic:300"]

    def test_default_project_persists(self) -> None:
        """Default project persists after reload."""
        self.storage.set_default_project("Epic:500")

        reset_settings()
        new_storage = LocalStorage()

        assert new_storage.get_default_project_oid() == "Epic:500"

    def test_remove_default_project_clears_default(self) -> None:
        """Removing the default project clears the default setting."""
        self.storage.add_project_bookmark("Default Project", "Epic:100")
        self.storage.set_default_project("Epic:100")

        self.storage.remove_project_bookmark("Default Project")

        assert self.storage.get_default_project_oid() is None


class TestLocalStorageIntegration:
    """Integration tests for LocalStorage with multiple operations."""

    def setup_method(self) -> None:
        """Set up a fresh storage instance for each test."""
        self.tmpdir = tempfile.mkdtemp()
        self.patcher = patch(
            "v1cli.config.settings.Path.home",
            return_value=Path(self.tmpdir)
        )
        self.patcher.start()
        reset_settings()
        self.storage = LocalStorage()

    def teardown_method(self) -> None:
        """Clean up after each test."""
        self.patcher.stop()
        reset_settings()

    def test_full_workflow(self) -> None:
        """Test a complete user workflow."""
        # Cache member
        self.storage.cache_member("Member:50", "Alice Smith")

        # Add projects
        self.storage.add_project_bookmark("Backend", "Epic:1000")
        self.storage.add_project_bookmark("Frontend", "Epic:2000")
        self.storage.add_project_bookmark("Infrastructure", "Epic:3000")

        # Set default
        self.storage.set_default_project("Epic:2000")

        # Verify state
        assert self.storage.get_cached_member_oid() == "Member:50"
        assert len(self.storage.settings.bookmarks) == 3
        assert self.storage.get_default_project_oid() == "Epic:2000"

        # Access by project number
        bookmark = self.storage.settings.get_bookmark("1")
        assert bookmark is not None
        assert bookmark.name == "Backend"

        bookmark = self.storage.settings.get_bookmark("3")
        assert bookmark is not None
        assert bookmark.name == "Infrastructure"

        # Remove middle project
        self.storage.remove_project_bookmark("2")

        # Project numbers shift
        assert len(self.storage.settings.bookmarks) == 2
        bookmark = self.storage.settings.get_bookmark("2")
        assert bookmark is not None
        assert bookmark.name == "Infrastructure"  # Now #2

        # Default was removed, so should be cleared
        assert self.storage.get_default_project_oid() is None

    def test_concurrent_operations(self) -> None:
        """Test multiple operations don't corrupt data."""
        # Add many bookmarks
        for i in range(10):
            self.storage.add_project_bookmark(f"Project {i}", f"Epic:{i * 100}")

        assert len(self.storage.settings.bookmarks) == 10

        # Remove by V1 number (not project number) to avoid shifting issues
        self.storage.remove_project_bookmark("E-200")
        self.storage.remove_project_bookmark("E-400")
        self.storage.remove_project_bookmark("E-600")

        assert len(self.storage.settings.bookmarks) == 7

        # Verify remaining
        oids = self.storage.get_bookmarked_project_oids()
        assert "Epic:200" not in oids
        assert "Epic:400" not in oids
        assert "Epic:600" not in oids
        assert "Epic:0" in oids
        assert "Epic:100" in oids
        assert "Epic:300" in oids
