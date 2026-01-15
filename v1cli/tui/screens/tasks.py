"""Tasks screen for viewing and managing story tasks."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Label, Static

from v1cli.api.client import V1Client
from v1cli.api.models import Story, Task


class TasksScreen(Screen):
    """Screen showing tasks for a story."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back", show=True),
        Binding("d", "mark_done", "Mark Done", show=True),
        Binding("n", "new_task", "New Task", show=True),
        Binding("r", "refresh", "Refresh", show=True),
    ]

    def __init__(self, story: Story) -> None:
        super().__init__()
        self.story = story
        self.tasks: list[Task] = []

    def compose(self) -> ComposeResult:
        """Compose the tasks layout."""
        yield Vertical(
            Label(f"Tasks for {self.story.number}: {self.story.name}", classes="title"),
            DataTable(id="task-table", cursor_type="row"),
            Static("", id="status-bar"),
        )

    def on_mount(self) -> None:
        """Set up table and load tasks."""
        table = self.query_one("#task-table", DataTable)
        table.add_columns("Status", "Name", "Done", "Todo", "Owners")
        self.refresh_data()

    def refresh_data(self) -> None:
        """Load tasks from API."""
        self.run_worker(self._load_tasks())

    async def _load_tasks(self) -> None:
        """Async worker to load tasks."""
        table = self.query_one("#task-table", DataTable)
        status_bar = self.query_one("#status-bar", Static)

        status_bar.update("Loading...")
        table.clear()

        try:
            async with V1Client() as client:
                self.tasks = await client.get_tasks(self.story.oid)

            for task in self.tasks:
                marker = "[x]" if task.is_done else "[ ]"
                done_h = f"{task.done or 0}h"
                todo_h = f"{task.todo or 0}h"
                owners = ", ".join(task.owners) if task.owners else "-"

                table.add_row(
                    marker,
                    task.name[:40] + ("..." if len(task.name) > 40 else ""),
                    done_h,
                    todo_h,
                    owners,
                    key=task.oid,
                )

            status_bar.update(f"{len(self.tasks)} tasks")

        except Exception as e:
            status_bar.update(f"Error: {e}")

    def _get_selected_task(self) -> Task | None:
        """Get currently selected task."""
        table = self.query_one("#task-table", DataTable)
        if table.cursor_row is not None and table.cursor_row < len(self.tasks):
            return self.tasks[table.cursor_row]
        return None

    def action_mark_done(self) -> None:
        """Mark selected task as done."""
        task = self._get_selected_task()
        if task:
            self.run_worker(self._complete_task(task))

    async def _complete_task(self, task: Task) -> None:
        """Complete a task."""
        status_bar = self.query_one("#status-bar", Static)

        try:
            async with V1Client() as client:
                await client.complete_task(task.oid)

            self.notify(f"Marked done: {task.name}")
            self.refresh_data()

        except Exception as e:
            status_bar.update(f"Error: {e}")

    def action_new_task(self) -> None:
        """Create a new task."""
        self.notify(
            f"Use CLI: v1 task create {self.story.number} '<name>'",
            title="Create Task",
        )

    def action_refresh(self) -> None:
        """Refresh task list."""
        self.refresh_data()
