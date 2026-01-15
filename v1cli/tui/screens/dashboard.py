"""Dashboard screen showing user's stories."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Label, Static

from v1cli.api.client import V1Client
from v1cli.api.models import Story
from v1cli.config.settings import get_settings
from v1cli.config.workflow import STATUS_ICONS, StoryStatus
from v1cli.storage.local import LocalStorage


class DashboardScreen(Screen):
    """Main dashboard showing user's assigned stories."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back", show=True),
        Binding("enter", "view_story", "View", show=True),
        Binding("s", "change_status", "Status", show=True),
        Binding("t", "view_tasks", "Tasks", show=True),
        Binding("n", "new_story", "New Story", show=True),
        Binding("r", "refresh", "Refresh", show=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.stories: list[Story] = []
        self.storage = LocalStorage()
        self.settings = get_settings()

    def compose(self) -> ComposeResult:
        """Compose the dashboard layout."""
        yield Vertical(
            Label("MY STORIES", classes="title"),
            Container(
                DataTable(id="story-table", cursor_type="row"),
                id="story-list",
            ),
            Static("", id="status-bar"),
        )

    def on_mount(self) -> None:
        """Handle screen mount."""
        table = self.query_one("#story-table", DataTable)
        table.add_columns("Number", "Status", "Name", "Pts", "Project")
        self.refresh_data()

    def refresh_data(self) -> None:
        """Load stories from API."""
        self.run_worker(self._load_stories(), exclusive=True)

    async def _load_stories(self) -> None:
        """Async worker to load stories."""
        table = self.query_one("#story-table", DataTable)
        status_bar = self.query_one("#status-bar", Static)

        status_bar.update("Loading...")
        table.clear()

        try:
            project_oids = self.storage.get_bookmarked_project_oids() or None

            async with V1Client() as client:
                self.stories = await client.get_my_stories(
                    project_oids=project_oids,
                    include_done=False,
                )

            for story in self.stories:
                status_enum = None
                if story.status_oid:
                    status_enum = self.settings.status_mapping.get_status(story.status_oid)

                icon = STATUS_ICONS.get(status_enum, "○") if status_enum else "○"
                status_text = f"{icon} {story.status_display}"

                pts = str(int(story.estimate)) if story.estimate else "-"
                name = story.name[:40] + ("..." if len(story.name) > 40 else "")

                table.add_row(
                    story.number,
                    status_text,
                    name,
                    pts,
                    story.scope_name,
                    key=story.oid,
                )

            status_bar.update(f"{len(self.stories)} stories")

        except Exception as e:
            status_bar.update(f"Error: {e}")

    def _get_selected_story(self) -> Story | None:
        """Get the currently selected story."""
        table = self.query_one("#story-table", DataTable)
        if table.cursor_row is not None and table.cursor_row < len(self.stories):
            return self.stories[table.cursor_row]
        return None

    def action_view_story(self) -> None:
        """View selected story details."""
        story = self._get_selected_story()
        if story:
            from v1cli.tui.screens.stories import StoryDetailScreen

            self.app.push_screen(StoryDetailScreen(story))

    def action_change_status(self) -> None:
        """Change status of selected story."""
        story = self._get_selected_story()
        if story:
            from v1cli.tui.screens.stories import StatusModal

            self.app.push_screen(StatusModal(story), self._on_status_changed)

    def _on_status_changed(self, changed: bool) -> None:
        """Handle status change result."""
        if changed:
            self.refresh_data()

    def action_view_tasks(self) -> None:
        """View tasks for selected story."""
        story = self._get_selected_story()
        if story:
            from v1cli.tui.screens.tasks import TasksScreen

            self.app.push_screen(TasksScreen(story))

    def action_new_story(self) -> None:
        """Create a new story."""
        self.notify("Use CLI: v1 story create <name>", title="Create Story")

    def action_refresh(self) -> None:
        """Refresh the story list."""
        self.refresh_data()
