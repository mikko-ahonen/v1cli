"""Pydantic models for VersionOne assets."""

from pydantic import BaseModel, Field


class Member(BaseModel):
    """A VersionOne member (user)."""

    oid: str = Field(description="Unique identifier, e.g., 'Member:20'")
    name: str = Field(default="", description="Display name")
    email: str | None = Field(default=None, description="Email address")
    username: str | None = Field(default=None, description="Login username")


class Project(BaseModel):
    """A VersionOne project (Scope)."""

    oid: str = Field(description="Unique identifier, e.g., 'Scope:1234'")
    name: str = Field(description="Project name")
    description: str = Field(default="", description="Project description")


class ProjectBookmark(BaseModel):
    """A locally stored project bookmark."""

    name: str
    oid: str


class Story(BaseModel):
    """A VersionOne story (2nd level workitem)."""

    oid: str = Field(description="Unique identifier, e.g., 'Story:1234'")
    number: str = Field(description="Display number, e.g., 'S-12345'")
    name: str = Field(description="Story title")
    description: str = Field(default="", description="Story description")
    status: str | None = Field(default=None, description="Status name")
    status_oid: str | None = Field(default=None, description="Status OID")
    scope_name: str = Field(default="", description="Project name")
    scope_oid: str = Field(default="", description="Project OID")
    owners: list[str] = Field(default_factory=list, description="Owner names")
    owner_oids: list[str] = Field(default_factory=list, description="Owner OIDs")
    parent_name: str | None = Field(default=None, description="Epic name")
    parent_oid: str | None = Field(default=None, description="Epic OID")
    estimate: float | None = Field(default=None, description="Story points estimate")

    @property
    def status_display(self) -> str:
        """Return status for display, with fallback."""
        return self.status or "None"


class Epic(BaseModel):
    """A VersionOne epic (high-level workitem)."""

    oid: str = Field(description="Unique identifier, e.g., 'Epic:100'")
    number: str = Field(description="Display number, e.g., 'E-100'")
    name: str = Field(description="Epic title")
    description: str = Field(default="", description="Epic description")
    scope_name: str = Field(default="", description="Project name")
    scope_oid: str = Field(default="", description="Project OID")
    status: str | None = Field(default=None, description="Status name")
    status_oid: str | None = Field(default=None, description="Status OID")


class Task(BaseModel):
    """A VersionOne task (sub-item of a story)."""

    oid: str = Field(description="Unique identifier, e.g., 'Task:5678'")
    name: str = Field(description="Task title")
    parent_oid: str = Field(description="Parent story OID")
    parent_number: str = Field(default="", description="Parent story number")
    status: str | None = Field(default=None, description="Status name")
    status_oid: str | None = Field(default=None, description="Status OID")
    owners: list[str] = Field(default_factory=list, description="Owner names")
    todo: float | None = Field(default=None, description="Hours remaining")
    done: float | None = Field(default=None, description="Hours completed")

    @property
    def is_done(self) -> bool:
        """Check if task is completed."""
        return self.status is not None and self.status.lower() in ("done", "completed")


class StatusInfo(BaseModel):
    """Information about a status option."""

    oid: str = Field(description="Status OID, e.g., 'StoryStatus:134'")
    name: str = Field(description="Status name, e.g., 'In Progress'")
