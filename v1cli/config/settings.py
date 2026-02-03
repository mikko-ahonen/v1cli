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


class ColumnConfig(BaseModel):
    """Configuration for a single display column."""

    field: str  # API field name (e.g., "Status.Name")
    label: str | None = None  # Display label (defaults to field name)
    style: str | None = None  # Rich style (e.g., "cyan", "bold")
    max_width: int | None = None  # Truncate text to this width
    format: str | None = None  # Format type: "date", "percent", "points"
    justify: str = "left"  # "left", "right", "center"


class AssetQueryConfig(BaseModel):
    """Query and display configuration for an asset type."""

    select: list[str] = Field(default_factory=list)  # Fields to query from API
    filters: list[str] = Field(default_factory=list)  # Filter conditions
    sort: list[str] = Field(default_factory=list)  # Sort order
    columns: list[ColumnConfig] = Field(default_factory=list)  # Display columns

    def is_configured(self) -> bool:
        """Check if this asset config has been set up."""
        return bool(self.select)


class ProjectQueryConfig(BaseModel):
    """Query configurations for all asset types in a project."""

    version: int = Field(default=1, description="Config schema version")
    last_detected: str | None = Field(default=None, description="ISO timestamp of last auto-detection")

    delivery_groups: AssetQueryConfig = Field(default_factory=AssetQueryConfig)
    features: AssetQueryConfig = Field(default_factory=AssetQueryConfig)
    stories: AssetQueryConfig = Field(default_factory=AssetQueryConfig)
    tasks: AssetQueryConfig = Field(default_factory=AssetQueryConfig)

    def is_configured(self) -> bool:
        """Check if any query config has been set."""
        return (
            self.delivery_groups.is_configured()
            or self.features.is_configured()
            or self.stories.is_configured()
            or self.tasks.is_configured()
        )


class ProjectBookmark(BaseModel):
    """A bookmarked project with optional query configuration."""

    name: str
    oid: str
    query_config: ProjectQueryConfig | None = Field(
        default=None, description="Custom query configurations for this project"
    )


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

    # Current story for time tracking
    current_story_oid: str | None = Field(default=None, description="Current story OID for time tracking")
    current_story_number: str | None = Field(default=None, description="Current story display number")

    def get_bookmark(self, identifier: str) -> ProjectBookmark | None:
        """Find a bookmark by name, project number, V1 number, or OID.

        Args:
            identifier: One of:
                - Project number (1-99): Simple index into bookmarks list
                - V1 number (e.g., "E-1234"): VersionOne display number
                - OID (e.g., "Epic:1234"): VersionOne internal identifier
                - Name: Project name (case-insensitive)
        """
        identifier_lower = identifier.lower()

        # Check if it's a simple project number (1-99) - index into bookmarks
        if identifier.isdigit():
            proj_num = int(identifier)
            if 1 <= proj_num <= 99 and proj_num <= len(self.bookmarks):
                return self.bookmarks[proj_num - 1]
            # If number > 99, try to match as V1 number against OID
            num = identifier.lstrip("0") or "0"
            for bookmark in self.bookmarks:
                oid_num = bookmark.oid.split(":")[-1] if ":" in bookmark.oid else ""
                if oid_num == num:
                    return bookmark

        # Check if it's an OID token (e.g., "Epic:1234", "Story:5678")
        if ":" in identifier and identifier.split(":")[0].isalpha():
            for bookmark in self.bookmarks:
                if bookmark.oid.lower() == identifier_lower:
                    return bookmark
            return None

        # Check if it looks like a V1 number (E-xxx)
        if identifier_lower.startswith("e-"):
            num = identifier_lower.replace("e-", "").lstrip("0") or "0"
            for bookmark in self.bookmarks:
                # OID format is "Epic:1234"
                oid_num = bookmark.oid.split(":")[-1] if ":" in bookmark.oid else ""
                if oid_num == num:
                    return bookmark

        # Match by name
        for bookmark in self.bookmarks:
            if bookmark.name.lower() == identifier_lower:
                return bookmark
        return None

    def add_bookmark(self, name: str, oid: str) -> None:
        """Add or update a project bookmark."""
        existing = self.get_bookmark(name)
        if existing:
            existing.oid = oid
        else:
            self.bookmarks.append(ProjectBookmark(name=name, oid=oid))

    def remove_bookmark(self, identifier: str) -> ProjectBookmark | None:
        """Remove a project bookmark by name or number.

        Args:
            identifier: Project name or number (e.g., "E-1234" or "1234")

        Returns:
            The removed bookmark, or None if not found.
        """
        bookmark = self.get_bookmark(identifier)
        if bookmark:
            self.bookmarks.remove(bookmark)
            if self.default_project == bookmark.oid:
                self.default_project = None
            return bookmark
        return None


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
