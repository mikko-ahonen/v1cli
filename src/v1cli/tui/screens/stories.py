"""Story detail and status modal screens."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import Label, OptionList, Static
from textual.widgets.option_list import Option

from v1cli.api.client import V1Client
from v1cli.api.models import Story, Task
from v1cli.config.settings import get_settings
from v1cli.config.workflow import (
    STATUS_ICONS,
    StoryStatus,
    get_valid_transitions,
)


class StoryDetailScreen(Screen):
    """Screen showing story details."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back", show=True),
        Binding("s", "change_status", "Status", show=True),
        Binding("t", "view_tasks", "Tasks", show=True),
    ]

    def __init__(self, story: Story) -> None:
        super().__init__()
        self.story = story
        self.tasks: list[Task] = []
        self.settings = get_settings()

    def compose(self) -> ComposeResult:
        """Compose the story detail layout."""
        status_enum = None
        if self.story.status_oid:
            status_enum = self.settings.status_mapping.get_status(self.story.status_oid)
        icon = STATUS_ICONS.get(status_enum, "○") if status_enum else "○"

        yield Vertical(
            Label(f"{self.story.number}: {self.story.name}", classes="title"),
            Static(f"{icon} {self.story.status_display}"),
            Static(""),
            Static(f"Project: {self.story.scope_name}", classes="label"),
            Static(
                f"Feature: {self.story.parent_name or 'None'}", classes="label"
            ) if self.story.parent_name else Static(""),
            Static(f"Owners: {', '.join(self.story.owners) or 'None'}", classes="label"),
            Static(
                f"Estimate: {self.story.estimate} pts" if self.story.estimate else "Estimate: -",
                classes="label",
            ),
            Static(""),
            Label("DESCRIPTION", classes="title"),
            Static(self.story.description[:500] if self.story.description else "(No description)"),
            Static(""),
            Label("TASKS", classes="title"),
            Static("", id="tasks-content"),
            id="story-detail",
        )

    def on_mount(self) -> None:
        """Load tasks when mounted."""
        self.run_worker(self._load_tasks())

    async def _load_tasks(self) -> None:
        """Load tasks for this story."""
        tasks_widget = self.query_one("#tasks-content", Static)

        try:
            async with V1Client() as client:
                self.tasks = await client.get_tasks(self.story.oid)

            if not self.tasks:
                tasks_widget.update("(No tasks)")
                return

            lines = []
            for task in self.tasks:
                marker = "[x]" if task.is_done else "[ ]"
                hours = ""
                if task.todo is not None or task.done is not None:
                    hours = f" ({task.done or 0}h done, {task.todo or 0}h todo)"
                lines.append(f"{marker} {task.name}{hours}")

            tasks_widget.update("\n".join(lines))

        except Exception as e:
            tasks_widget.update(f"Error loading tasks: {e}")

    def action_change_status(self) -> None:
        """Change story status."""
        self.app.push_screen(StatusModal(self.story), self._on_status_changed)

    def _on_status_changed(self, changed: bool) -> None:
        """Handle status change."""
        if changed:
            self.app.pop_screen()  # Go back to refresh

    def action_view_tasks(self) -> None:
        """View tasks screen."""
        from v1cli.tui.screens.tasks import TasksScreen

        self.app.push_screen(TasksScreen(self.story))


class StatusModal(ModalScreen[bool]):
    """Modal for changing story status."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
    ]

    def __init__(self, story: Story) -> None:
        super().__init__()
        self.story = story
        self.settings = get_settings()
        self.current_status: StoryStatus | None = None
        self.valid_targets: list[StoryStatus] = []

        # Determine current status and valid transitions
        if story.status_oid:
            self.current_status = self.settings.status_mapping.get_status(story.status_oid)

        if self.current_status:
            self.valid_targets = get_valid_transitions(self.current_status)

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        current_icon = STATUS_ICONS.get(self.current_status, "○") if self.current_status else "○"
        current_name = self.current_status.value if self.current_status else "Unknown"

        options = []
        for status in self.valid_targets:
            icon = STATUS_ICONS.get(status, "○")
            options.append(Option(f"{icon} {status.value}", id=status.value))

        with Vertical(id="status-modal"):
            yield Label(f"Change Status: {self.story.number}", classes="modal-title")
            yield Static(f"Current: {current_icon} {current_name}")
            yield Static("")
            if options:
                yield Label("Move to:")
                yield OptionList(*options, id="status-options")
            else:
                yield Static("No valid transitions from current status")

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle status selection."""
        selected_value = event.option.id
        if selected_value:
            self.run_worker(self._update_status(selected_value))

    async def _update_status(self, status_value: str) -> None:
        """Update the story status."""
        try:
            target_status = StoryStatus(status_value)
            status_oid = self.settings.status_mapping.get_oid(target_status)

            if not status_oid:
                self.notify(f"Status {status_value} not configured", severity="error")
                return

            async with V1Client() as client:
                await client.update_story_status(self.story.oid, status_oid)

            self.notify(f"Updated to {target_status.value}")
            self.dismiss(True)

        except Exception as e:
            self.notify(f"Error: {e}", severity="error")

    def action_cancel(self) -> None:
        """Cancel and close modal."""
        self.dismiss(False)
