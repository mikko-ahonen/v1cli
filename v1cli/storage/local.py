"""Local storage utilities."""

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from v1cli.api.models import TimeEntry
from v1cli.config.settings import (
    Settings,
    get_config_dir,
    get_settings,
    save_settings,
)


class LocalStorage:
    """Manage local storage for v1cli."""

    def __init__(self) -> None:
        self._config_dir = get_config_dir()

    @property
    def config_dir(self) -> Path:
        """Get the configuration directory."""
        return self._config_dir

    @property
    def settings(self) -> Settings:
        """Get current settings."""
        return get_settings()

    def save(self, settings: Settings) -> None:
        """Save settings to disk."""
        save_settings(settings)

    def cache_member(self, oid: str, name: str) -> None:
        """Cache the current member information."""
        settings = self.settings
        settings.member_oid = oid
        settings.member_name = name
        self.save(settings)

    def get_cached_member_oid(self) -> str | None:
        """Get the cached member OID."""
        return self.settings.member_oid

    def add_project_bookmark(self, name: str, oid: str) -> None:
        """Add a project bookmark."""
        settings = self.settings
        settings.add_bookmark(name, oid)
        self.save(settings)

    def remove_project_bookmark(self, identifier: str) -> tuple[str, str] | None:
        """Remove a project bookmark by name or number.

        Returns:
            Tuple of (name, oid) if removed, None if not found.
        """
        settings = self.settings
        removed = settings.remove_bookmark(identifier)
        if removed:
            self.save(settings)
            return (removed.name, removed.oid)
        return None

    def set_default_project(self, oid: str) -> None:
        """Set the default project."""
        settings = self.settings
        settings.default_project = oid
        self.save(settings)

    def get_default_project_oid(self) -> str | None:
        """Get the default project OID."""
        return self.settings.default_project

    def get_bookmarked_project_oids(self) -> list[str]:
        """Get all bookmarked project OIDs."""
        return [b.oid for b in self.settings.bookmarks]

    def cache_features(self, features: list[tuple[str, str]]) -> None:
        """Cache the last features list (number, oid pairs)."""
        import json
        cache_file = self._config_dir / "features_cache.json"
        cache_file.write_text(json.dumps(features))

    def get_cached_feature(self, index: int) -> tuple[str, str] | None:
        """Get a cached feature by 1-based index. Returns (number, oid) or None."""
        import json
        cache_file = self._config_dir / "features_cache.json"
        if not cache_file.exists():
            return None
        try:
            features = json.loads(cache_file.read_text())
            if 1 <= index <= len(features):
                return tuple(features[index - 1])
        except (json.JSONDecodeError, IndexError):
            pass
        return None

    def cache_stories(self, stories: list[tuple[str, str]]) -> None:
        """Cache the last stories list (number, oid pairs)."""
        import json
        cache_file = self._config_dir / "stories_cache.json"
        cache_file.write_text(json.dumps(stories))

    def get_cached_story(self, index: int) -> tuple[str, str] | None:
        """Get a cached story by 1-based index. Returns (number, oid) or None."""
        cache_file = self._config_dir / "stories_cache.json"
        if not cache_file.exists():
            return None
        try:
            stories = json.loads(cache_file.read_text())
            if 1 <= index <= len(stories):
                return tuple(stories[index - 1])
        except (json.JSONDecodeError, IndexError):
            pass
        return None

    # Time tracking methods

    def _get_time_entries_file(self) -> Path:
        """Get path to time entries storage file."""
        return self._config_dir / "time_entries.json"

    def load_time_entries(self) -> list[TimeEntry]:
        """Load all time entries from local storage."""
        cache_file = self._get_time_entries_file()
        if not cache_file.exists():
            return []
        try:
            data = json.loads(cache_file.read_text())
            return [TimeEntry.model_validate(e) for e in data.get("entries", [])]
        except (json.JSONDecodeError, ValueError):
            return []

    def save_time_entries(self, entries: list[TimeEntry]) -> None:
        """Save time entries to local storage."""
        cache_file = self._get_time_entries_file()
        data = {"entries": [e.model_dump() for e in entries], "version": 1}
        cache_file.write_text(json.dumps(data, indent=2))

    def add_time_entry(
        self,
        hours: float,
        description: str,
        story_oid: str,
        story_number: str,
        project_oid: str = "",
        remaining: float | None = None,
        date: str | None = None,
    ) -> TimeEntry:
        """Add a new time entry and return it."""
        entries = self.load_time_entries()
        entry_date = date or datetime.now(timezone.utc).date().isoformat()
        entry = TimeEntry(
            id=str(uuid4()),
            hours=hours,
            description=description,
            remaining=remaining,
            date=entry_date,
            story_oid=story_oid,
            story_number=story_number,
            project_oid=project_oid,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        entries.append(entry)
        self.save_time_entries(entries)
        return entry

    def get_unsynced_entries(self) -> list[TimeEntry]:
        """Get all unsynced time entries."""
        return [e for e in self.load_time_entries() if not e.synced]

    def mark_entry_synced(self, entry_id: str, actual_oid: str) -> bool:
        """Mark an entry as synced with its V1 Actual OID."""
        entries = self.load_time_entries()
        for entry in entries:
            if entry.id == entry_id:
                entry.synced = True
                entry.synced_at = datetime.now(timezone.utc).isoformat()
                entry.actual_oid = actual_oid
                self.save_time_entries(entries)
                return True
        return False

    def move_entry(self, entry_id: str, new_story_oid: str, new_story_number: str) -> bool:
        """Move an unsynced entry to a different story."""
        entries = self.load_time_entries()
        for entry in entries:
            if entry.id == entry_id:
                if entry.synced:
                    return False  # Cannot move synced entries
                entry.story_oid = new_story_oid
                entry.story_number = new_story_number
                self.save_time_entries(entries)
                return True
        return False

    def delete_entry(self, entry_id: str) -> bool:
        """Delete an unsynced time entry."""
        entries = self.load_time_entries()
        for i, entry in enumerate(entries):
            if entry.id == entry_id:
                if entry.synced:
                    return False  # Cannot delete synced entries
                entries.pop(i)
                self.save_time_entries(entries)
                return True
        return False

    def get_entry_by_index(self, index: int) -> TimeEntry | None:
        """Get a time entry by 1-based index from unsynced entries."""
        unsynced = self.get_unsynced_entries()
        if 1 <= index <= len(unsynced):
            return unsynced[index - 1]
        return None

    def set_current_story(self, story_oid: str, story_number: str) -> None:
        """Set the current story for time tracking."""
        settings = self.settings
        settings.current_story_oid = story_oid
        settings.current_story_number = story_number
        self.save(settings)

    def get_current_story(self) -> tuple[str, str] | None:
        """Get current story (oid, number) or None."""
        settings = self.settings
        if settings.current_story_oid and settings.current_story_number:
            return (settings.current_story_oid, settings.current_story_number)
        return None
