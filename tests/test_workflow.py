"""Tests for workflow configuration."""

import pytest

from v1cli.config.workflow import (
    StoryStatus,
    can_transition,
    get_valid_transitions,
)


class TestStoryStatus:
    """Tests for StoryStatus enum."""

    def test_from_string_direct(self) -> None:
        """Test parsing direct status names."""
        assert StoryStatus.from_string("backlog") == StoryStatus.BACKLOG
        assert StoryStatus.from_string("ready") == StoryStatus.READY
        assert StoryStatus.from_string("in_progress") == StoryStatus.IN_PROGRESS
        assert StoryStatus.from_string("review") == StoryStatus.REVIEW
        assert StoryStatus.from_string("done") == StoryStatus.DONE

    def test_from_string_aliases(self) -> None:
        """Test parsing status aliases."""
        assert StoryStatus.from_string("progress") == StoryStatus.IN_PROGRESS
        assert StoryStatus.from_string("wip") == StoryStatus.IN_PROGRESS
        assert StoryStatus.from_string("todo") == StoryStatus.BACKLOG
        assert StoryStatus.from_string("complete") == StoryStatus.DONE
        assert StoryStatus.from_string("completed") == StoryStatus.DONE

    def test_from_string_case_insensitive(self) -> None:
        """Test case insensitivity."""
        assert StoryStatus.from_string("BACKLOG") == StoryStatus.BACKLOG
        assert StoryStatus.from_string("In_Progress") == StoryStatus.IN_PROGRESS
        assert StoryStatus.from_string("DONE") == StoryStatus.DONE


class TestTransitions:
    """Tests for status transitions."""

    def test_backlog_transitions(self) -> None:
        """Backlog can only move to Ready."""
        valid = get_valid_transitions(StoryStatus.BACKLOG)
        assert valid == [StoryStatus.READY]

    def test_ready_transitions(self) -> None:
        """Ready can move to Backlog or In Progress."""
        valid = get_valid_transitions(StoryStatus.READY)
        assert StoryStatus.BACKLOG in valid
        assert StoryStatus.IN_PROGRESS in valid
        assert len(valid) == 2

    def test_in_progress_transitions(self) -> None:
        """In Progress can move to Ready or Review."""
        valid = get_valid_transitions(StoryStatus.IN_PROGRESS)
        assert StoryStatus.READY in valid
        assert StoryStatus.REVIEW in valid
        assert len(valid) == 2

    def test_review_transitions(self) -> None:
        """Review can move to In Progress or Done."""
        valid = get_valid_transitions(StoryStatus.REVIEW)
        assert StoryStatus.IN_PROGRESS in valid
        assert StoryStatus.DONE in valid
        assert len(valid) == 2

    def test_done_transitions(self) -> None:
        """Done can only move back to Review."""
        valid = get_valid_transitions(StoryStatus.DONE)
        assert valid == [StoryStatus.REVIEW]

    def test_can_transition_valid(self) -> None:
        """Test valid transitions."""
        assert can_transition(StoryStatus.BACKLOG, StoryStatus.READY)
        assert can_transition(StoryStatus.READY, StoryStatus.IN_PROGRESS)
        assert can_transition(StoryStatus.IN_PROGRESS, StoryStatus.REVIEW)
        assert can_transition(StoryStatus.REVIEW, StoryStatus.DONE)

    def test_can_transition_invalid(self) -> None:
        """Test invalid transitions."""
        assert not can_transition(StoryStatus.BACKLOG, StoryStatus.DONE)
        assert not can_transition(StoryStatus.BACKLOG, StoryStatus.IN_PROGRESS)
        assert not can_transition(StoryStatus.DONE, StoryStatus.BACKLOG)
