"""Tests for data models."""

import pytest

from v1cli.api.models import Story, Task


class TestStory:
    """Tests for Story model."""

    def test_status_display_with_status(self) -> None:
        """Test status_display with a status set."""
        story = Story(
            oid="Story:1",
            number="S-1",
            name="Test",
            status="In Progress",
        )
        assert story.status_display == "In Progress"

    def test_status_display_without_status(self) -> None:
        """Test status_display without a status."""
        story = Story(
            oid="Story:1",
            number="S-1",
            name="Test",
        )
        assert story.status_display == "None"


class TestTask:
    """Tests for Task model."""

    def test_is_done_true(self) -> None:
        """Test is_done when task is completed."""
        task = Task(
            oid="Task:1",
            name="Test",
            parent_oid="Story:1",
            status="Done",
        )
        assert task.is_done is True

    def test_is_done_false(self) -> None:
        """Test is_done when task is not completed."""
        task = Task(
            oid="Task:1",
            name="Test",
            parent_oid="Story:1",
            status="In Progress",
        )
        assert task.is_done is False

    def test_is_done_no_status(self) -> None:
        """Test is_done when status is None."""
        task = Task(
            oid="Task:1",
            name="Test",
            parent_oid="Story:1",
        )
        assert task.is_done is False
