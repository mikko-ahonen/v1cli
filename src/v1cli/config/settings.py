"""Configuration settings management."""

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from v1cli.config.workflow import StoryStatus


class StatusMapping(BaseModel):
    """Mapping between workflow statuses and V1 status OIDs."""

    backlog: str | None = None
    ready: str | None = None
    in_progress: str | None = None
    review: str | None = None
    done: str | None = None

    def get_oid(self, status: StoryStatus) -> str | None:
        """Get the V1 OID for a workflow status."""
        return getattr(self, status.value, None)

    def get_status(self, oid: str) -> StoryStatus | None:
        """Get the workflow status for a V1 OID."""
        for status in StoryStatus:
            if getattr(self, status.value) == oid:
                return status
        return None

    def is_configured(self) -> bool:
        """Check if status mapping has been configured."""
        return any(
            [self.backlog, self.ready, self.in_progress, self.review, self.done]
        )


class ProjectBookmark(BaseModel):
    """A bookmarked project."""

    name: str
    oid: str


class Settings(BaseModel):
    """Application settings stored locally."""

    # Cached user info
    member_oid: str | None = Field(default=None, description="Current user's member OID")
    member_name: str | None = Field(default=None, description="Current user's display name")

    # Project bookmarks
    bookmarks: list[ProjectBookmark] = Field(default_factory=list)
    default_project: str | None = Field(default=None, description="Default project OID")

    # Status mapping (discovered during setup)
    status_mapping: StatusMapping = Field(default_factory=StatusMapping)

    def get_bookmark(self, name: str) -> ProjectBookmark | None:
        """Find a bookmark by name (case-insensitive)."""
        name_lower = name.lower()
        for bookmark in self.bookmarks:
            if bookmark.name.lower() == name_lower:
                return bookmark
        return None

    def add_bookmark(self, name: str, oid: str) -> None:
        """Add or update a project bookmark."""
        existing = self.get_bookmark(name)
        if existing:
            existing.oid = oid
        else:
            self.bookmarks.append(ProjectBookmark(name=name, oid=oid))

    def remove_bookmark(self, name: str) -> bool:
        """Remove a project bookmark. Returns True if removed."""
        name_lower = name.lower()
        for i, bookmark in enumerate(self.bookmarks):
            if bookmark.name.lower() == name_lower:
                self.bookmarks.pop(i)
                if self.default_project == bookmark.oid:
                    self.default_project = None
                return True
        return False


# Global settings instance (lazy loaded)
_settings: Settings | None = None
_settings_path: Path | None = None


def get_config_dir() -> Path:
    """Get the configuration directory, creating it if needed."""
    config_dir = Path.home() / ".v1cli"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_settings_path() -> Path:
    """Get the path to the settings file."""
    return get_config_dir() / "config.toml"


def get_settings() -> Settings:
    """Load settings from disk, or return defaults."""
    global _settings, _settings_path

    settings_path = get_settings_path()

    # Return cached settings if path hasn't changed
    if _settings is not None and _settings_path == settings_path:
        return _settings

    _settings_path = settings_path

    if settings_path.exists():
        import tomllib

        with open(settings_path, "rb") as f:
            data = tomllib.load(f)
        _settings = Settings.model_validate(data)
    else:
        _settings = Settings()

    return _settings


def save_settings(settings: Settings) -> None:
    """Save settings to disk."""
    global _settings

    import tomli_w

    settings_path = get_settings_path()
    data = settings.model_dump(exclude_none=True)

    with open(settings_path, "wb") as f:
        tomli_w.dump(data, f)

    _settings = settings


def reset_settings() -> None:
    """Reset cached settings (useful for testing)."""
    global _settings, _settings_path
    _settings = None
    _settings_path = None
