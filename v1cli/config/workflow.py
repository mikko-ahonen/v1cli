"""Opinionated workflow configuration.

This module defines the hardcoded workflow statuses used by v1cli.
The actual VersionOne status OIDs are discovered during setup and stored locally.
"""

from enum import Enum


class StoryStatus(str, Enum):
    """Story workflow statuses (opinionated 5-stage workflow)."""

    BACKLOG = "backlog"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    DONE = "done"

    @classmethod
    def from_string(cls, value: str) -> "StoryStatus":
        """Parse a status from user input."""
        normalized = value.lower().replace(" ", "_").replace("-", "_")
        # Handle common aliases
        aliases = {
            "progress": cls.IN_PROGRESS,
            "inprogress": cls.IN_PROGRESS,
            "wip": cls.IN_PROGRESS,
            "todo": cls.BACKLOG,
            "new": cls.BACKLOG,
            "complete": cls.DONE,
            "completed": cls.DONE,
            "finished": cls.DONE,
        }
        if normalized in aliases:
            return aliases[normalized]
        return cls(normalized)


class TaskStatus(str, Enum):
    """Task workflow statuses (simple 3-stage)."""

    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"


# Valid transitions between story statuses
STORY_TRANSITIONS: dict[StoryStatus, list[StoryStatus]] = {
    StoryStatus.BACKLOG: [StoryStatus.READY],
    StoryStatus.READY: [StoryStatus.BACKLOG, StoryStatus.IN_PROGRESS],
    StoryStatus.IN_PROGRESS: [StoryStatus.READY, StoryStatus.REVIEW],
    StoryStatus.REVIEW: [StoryStatus.IN_PROGRESS, StoryStatus.DONE],
    StoryStatus.DONE: [StoryStatus.REVIEW],
}


def get_valid_transitions(current: StoryStatus) -> list[StoryStatus]:
    """Get valid status transitions from current status."""
    return STORY_TRANSITIONS.get(current, [])


def can_transition(from_status: StoryStatus, to_status: StoryStatus) -> bool:
    """Check if a status transition is valid."""
    return to_status in get_valid_transitions(from_status)


# Display configuration
STATUS_ICONS: dict[StoryStatus, str] = {
    StoryStatus.BACKLOG: "○",
    StoryStatus.READY: "◔",
    StoryStatus.IN_PROGRESS: "●",
    StoryStatus.REVIEW: "◐",
    StoryStatus.DONE: "✓",
}

STATUS_COLORS: dict[StoryStatus, str] = {
    StoryStatus.BACKLOG: "dim",
    StoryStatus.READY: "cyan",
    StoryStatus.IN_PROGRESS: "yellow",
    StoryStatus.REVIEW: "magenta",
    StoryStatus.DONE: "green",
}
