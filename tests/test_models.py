"""Tests for data models."""

import pytest

from v1cli.api.models import (
    DeliveryGroup,
    Feature,
    Member,
    Project,
    ProjectBookmark,
    StatusInfo,
    Story,
    Task,
)


class TestMember:
    """Tests for Member model."""

    def test_create_member_required_fields(self) -> None:
        """Create member with required fields only."""
        member = Member(oid="Member:20", name="John Doe")

        assert member.oid == "Member:20"
        assert member.name == "John Doe"
        assert member.email is None
        assert member.username is None

    def test_create_member_all_fields(self) -> None:
        """Create member with all fields."""
        member = Member(
            oid="Member:30",
            name="Jane Smith",
            email="jane@example.com",
            username="janes",
        )

        assert member.oid == "Member:30"
        assert member.name == "Jane Smith"
        assert member.email == "jane@example.com"
        assert member.username == "janes"

    def test_member_default_name(self) -> None:
        """Member name defaults to empty string."""
        member = Member(oid="Member:40")
        assert member.name == ""


class TestProject:
    """Tests for Project model."""

    def test_create_project_required_fields(self) -> None:
        """Create project with required fields."""
        project = Project(oid="Epic:1000", name="Test Project")

        assert project.oid == "Epic:1000"
        assert project.name == "Test Project"
        assert project.number == ""
        assert project.description is None
        assert project.category is None

    def test_create_project_all_fields(self) -> None:
        """Create project with all fields."""
        project = Project(
            oid="Epic:2000",
            name="Full Project",
            description="A detailed description",
            number="E-2000",
            category="Business Epic",
            scope_name="Parent Scope",
            parent_name="Parent Project",
            status="Active",
        )

        assert project.oid == "Epic:2000"
        assert project.number == "E-2000"
        assert project.category == "Business Epic"
        assert project.status == "Active"


class TestProjectBookmark:
    """Tests for ProjectBookmark model."""

    def test_create_bookmark(self) -> None:
        """Create a simple bookmark."""
        bookmark = ProjectBookmark(name="My Project", oid="Epic:100")

        assert bookmark.name == "My Project"
        assert bookmark.oid == "Epic:100"

    def test_bookmark_equality(self) -> None:
        """Bookmarks with same values are equal."""
        b1 = ProjectBookmark(name="Project", oid="Epic:100")
        b2 = ProjectBookmark(name="Project", oid="Epic:100")

        assert b1 == b2


class TestStory:
    """Tests for Story model."""

    def test_create_story_required_fields(self) -> None:
        """Create story with required fields."""
        story = Story(
            oid="Story:100",
            number="S-100",
            name="Test Story",
        )

        assert story.oid == "Story:100"
        assert story.number == "S-100"
        assert story.name == "Test Story"
        assert story.description == ""
        assert story.status is None
        assert story.owners == []
        assert story.estimate is None

    def test_create_story_all_fields(self) -> None:
        """Create story with all fields."""
        story = Story(
            oid="Story:200",
            number="S-200",
            name="Full Story",
            description="Story description",
            status="In Progress",
            status_oid="StoryStatus:135",
            scope_name="Project",
            scope_oid="Scope:1",
            owners=["Alice", "Bob"],
            owner_oids=["Member:1", "Member:2"],
            parent_name="Parent Feature",
            parent_oid="Epic:50",
            estimate=5.0,
        )

        assert story.oid == "Story:200"
        assert story.status == "In Progress"
        assert story.status_oid == "StoryStatus:135"
        assert len(story.owners) == 2
        assert story.estimate == 5.0

    def test_status_display_with_status(self) -> None:
        """status_display returns status when set."""
        story = Story(
            oid="Story:1",
            number="S-1",
            name="Test",
            status="In Progress",
        )
        assert story.status_display == "In Progress"

    def test_status_display_without_status(self) -> None:
        """status_display returns 'None' when not set."""
        story = Story(
            oid="Story:1",
            number="S-1",
            name="Test",
        )
        assert story.status_display == "None"

    def test_status_display_empty_string(self) -> None:
        """status_display returns 'None' for empty string."""
        story = Story(
            oid="Story:1",
            number="S-1",
            name="Test",
            status="",
        )
        assert story.status_display == "None"


class TestFeature:
    """Tests for Feature model."""

    def test_create_feature_required_fields(self) -> None:
        """Create feature with required fields."""
        feature = Feature(
            oid="Epic:100",
            number="E-100",
            name="Test Feature",
        )

        assert feature.oid == "Epic:100"
        assert feature.number == "E-100"
        assert feature.name == "Test Feature"
        assert feature.description is None
        assert feature.status is None

    def test_create_feature_all_fields(self) -> None:
        """Create feature with all fields."""
        feature = Feature(
            oid="Epic:200",
            number="E-200",
            name="Full Feature",
            description="Feature description",
            scope_name="Project",
            scope_oid="Scope:1",
            parent_name="Parent Group",
            status="Active",
            status_oid="EpicStatus:10",
        )

        assert feature.oid == "Epic:200"
        assert feature.description == "Feature description"
        assert feature.scope_name == "Project"
        assert feature.status == "Active"


class TestTask:
    """Tests for Task model."""

    def test_create_task_required_fields(self) -> None:
        """Create task with required fields."""
        task = Task(
            oid="Task:100",
            name="Test Task",
            parent_oid="Story:50",
        )

        assert task.oid == "Task:100"
        assert task.name == "Test Task"
        assert task.parent_oid == "Story:50"
        assert task.number == ""
        assert task.status is None
        assert task.todo is None
        assert task.done is None

    def test_create_task_all_fields(self) -> None:
        """Create task with all fields."""
        task = Task(
            oid="Task:200",
            number="TK-200",
            name="Full Task",
            parent_oid="Story:100",
            parent_number="S-100",
            status="In Progress",
            status_oid="TaskStatus:10",
            owners=["Alice"],
            todo=4.0,
            done=2.0,
        )

        assert task.oid == "Task:200"
        assert task.number == "TK-200"
        assert task.todo == 4.0
        assert task.done == 2.0

    def test_is_done_with_done_status(self) -> None:
        """is_done returns True for 'Done' status."""
        task = Task(
            oid="Task:1",
            name="Test",
            parent_oid="Story:1",
            status="Done",
        )
        assert task.is_done is True

    def test_is_done_with_completed_status(self) -> None:
        """is_done returns True for 'Completed' status."""
        task = Task(
            oid="Task:1",
            name="Test",
            parent_oid="Story:1",
            status="Completed",
        )
        assert task.is_done is True

    def test_is_done_case_insensitive(self) -> None:
        """is_done is case-insensitive."""
        task = Task(
            oid="Task:1",
            name="Test",
            parent_oid="Story:1",
            status="DONE",
        )
        assert task.is_done is True

    def test_is_done_false_in_progress(self) -> None:
        """is_done returns False for in-progress status."""
        task = Task(
            oid="Task:1",
            name="Test",
            parent_oid="Story:1",
            status="In Progress",
        )
        assert task.is_done is False

    def test_is_done_false_no_status(self) -> None:
        """is_done returns False when status is None."""
        task = Task(
            oid="Task:1",
            name="Test",
            parent_oid="Story:1",
        )
        assert task.is_done is False


class TestDeliveryGroup:
    """Tests for DeliveryGroup model."""

    def test_create_delivery_group_required_fields(self) -> None:
        """Create delivery group with required fields."""
        group = DeliveryGroup(
            oid="Epic:500",
            name="Q1 Release",
        )

        assert group.oid == "Epic:500"
        assert group.name == "Q1 Release"
        assert group.number == ""
        assert group.status is None
        assert group.delivery_type is None
        assert group.planned_start is None
        assert group.planned_end is None
        assert group.progress is None
        assert group.estimate is None

    def test_create_delivery_group_all_fields(self) -> None:
        """Create delivery group with all fields."""
        group = DeliveryGroup(
            oid="Epic:600",
            name="Q2 Release",
            number="E-600",
            status="In Progress",
            delivery_type="Release",
            planned_start="2024-04-01",
            planned_end="2024-06-30",
            progress=0.75,
            estimate=200.0,
        )

        assert group.oid == "Epic:600"
        assert group.number == "E-600"
        assert group.delivery_type == "Release"
        assert group.planned_start == "2024-04-01"
        assert group.planned_end == "2024-06-30"
        assert group.progress == 0.75
        assert group.estimate == 200.0


class TestStatusInfo:
    """Tests for StatusInfo model."""

    def test_create_status_info(self) -> None:
        """Create status info."""
        status = StatusInfo(
            oid="StoryStatus:135",
            name="In Progress",
        )

        assert status.oid == "StoryStatus:135"
        assert status.name == "In Progress"


class TestModelSerialization:
    """Tests for model serialization/deserialization."""

    def test_story_to_dict(self) -> None:
        """Story can be converted to dict."""
        story = Story(
            oid="Story:100",
            number="S-100",
            name="Test",
            status="Done",
            estimate=3.0,
        )

        data = story.model_dump()

        assert data["oid"] == "Story:100"
        assert data["number"] == "S-100"
        assert data["estimate"] == 3.0

    def test_story_from_dict(self) -> None:
        """Story can be created from dict."""
        data = {
            "oid": "Story:200",
            "number": "S-200",
            "name": "From Dict",
            "status": "Ready",
        }

        story = Story.model_validate(data)

        assert story.oid == "Story:200"
        assert story.name == "From Dict"

    def test_task_json_roundtrip(self) -> None:
        """Task survives JSON serialization roundtrip."""
        task = Task(
            oid="Task:100",
            number="TK-100",
            name="Test Task",
            parent_oid="Story:50",
            status="Done",
            todo=0.0,
            done=4.0,
        )

        json_str = task.model_dump_json()
        restored = Task.model_validate_json(json_str)

        assert restored.oid == task.oid
        assert restored.number == task.number
        assert restored.is_done == task.is_done

    def test_feature_exclude_none(self) -> None:
        """Feature can exclude None values in serialization."""
        feature = Feature(
            oid="Epic:100",
            number="E-100",
            name="Test",
        )

        data = feature.model_dump(exclude_none=True)

        assert "oid" in data
        assert "description" not in data
        assert "status" not in data


class TestModelValidation:
    """Tests for model validation."""

    def test_story_requires_oid(self) -> None:
        """Story requires oid field."""
        with pytest.raises(ValueError):
            Story(number="S-100", name="Test")  # type: ignore

    def test_story_requires_number(self) -> None:
        """Story requires number field."""
        with pytest.raises(ValueError):
            Story(oid="Story:100", name="Test")  # type: ignore

    def test_story_requires_name(self) -> None:
        """Story requires name field."""
        with pytest.raises(ValueError):
            Story(oid="Story:100", number="S-100")  # type: ignore

    def test_task_requires_parent_oid(self) -> None:
        """Task requires parent_oid field."""
        with pytest.raises(ValueError):
            Task(oid="Task:100", name="Test")  # type: ignore

    def test_member_requires_oid(self) -> None:
        """Member requires oid field."""
        with pytest.raises(ValueError):
            Member(name="Test")  # type: ignore
