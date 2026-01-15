"""Local storage utilities."""

from pathlib import Path

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
