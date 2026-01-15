"""Projects browser screen."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Label, Static

from v1cli.api.client import V1Client
from v1cli.api.models import Project
from v1cli.storage.local import LocalStorage


class ProjectsScreen(Screen):
    """Screen for browsing and bookmarking projects."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back", show=True),
        Binding("b", "toggle_bookmark", "Bookmark", show=True),
        Binding("d", "set_default", "Set Default", show=True),
        Binding("enter", "view_stories", "View Stories", show=True),
        Binding("r", "refresh", "Refresh", show=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.projects: list[Project] = []
        self.storage = LocalStorage()

    def compose(self) -> ComposeResult:
        """Compose the projects layout."""
        yield Vertical(
            Label("PROJECTS", classes="title"),
            DataTable(id="project-table", cursor_type="row"),
            Static("", id="status-bar"),
        )

    def on_mount(self) -> None:
        """Set up table and load projects."""
        table = self.query_one("#project-table", DataTable)
        table.add_columns("Name", "OID", "Bookmarked")
        self.refresh_data()

    def refresh_data(self) -> None:
        """Load projects from API."""
        self.run_worker(self._load_projects())

    async def _load_projects(self) -> None:
        """Async worker to load projects."""
        table = self.query_one("#project-table", DataTable)
        status_bar = self.query_one("#status-bar", Static)

        status_bar.update("Loading...")
        table.clear()

        try:
            async with V1Client() as client:
                self.projects = await client.get_projects()

            bookmarked_oids = set(self.storage.get_bookmarked_project_oids())
            default_oid = self.storage.get_default_project_oid()

            for project in self.projects:
                bookmark_marker = ""
                if project.oid in bookmarked_oids:
                    bookmark_marker = "*"
                    if project.oid == default_oid:
                        bookmark_marker = "* (default)"

                table.add_row(
                    project.name,
                    project.oid,
                    bookmark_marker,
                    key=project.oid,
                )

            status_bar.update(f"{len(self.projects)} projects")

        except Exception as e:
            status_bar.update(f"Error: {e}")

    def _get_selected_project(self) -> Project | None:
        """Get currently selected project."""
        table = self.query_one("#project-table", DataTable)
        if table.cursor_row is not None and table.cursor_row < len(self.projects):
            return self.projects[table.cursor_row]
        return None

    def action_toggle_bookmark(self) -> None:
        """Toggle bookmark for selected project."""
        project = self._get_selected_project()
        if not project:
            return

        bookmarked_oids = set(self.storage.get_bookmarked_project_oids())

        if project.oid in bookmarked_oids:
            self.storage.remove_project_bookmark(project.name)
            self.notify(f"Removed bookmark: {project.name}")
        else:
            self.storage.add_project_bookmark(project.name, project.oid)
            self.notify(f"Bookmarked: {project.name}")

        self.refresh_data()

    def action_set_default(self) -> None:
        """Set selected project as default."""
        project = self._get_selected_project()
        if not project:
            return

        # Ensure it's bookmarked first
        bookmarked_oids = set(self.storage.get_bookmarked_project_oids())
        if project.oid not in bookmarked_oids:
            self.storage.add_project_bookmark(project.name, project.oid)

        self.storage.set_default_project(project.oid)
        self.notify(f"Default project: {project.name}")
        self.refresh_data()

    def action_view_stories(self) -> None:
        """View stories in selected project."""
        project = self._get_selected_project()
        if project:
            from v1cli.tui.screens.dashboard import DashboardScreen

            # For now, just go back to dashboard
            # A future enhancement could filter by project
            self.notify(f"Use CLI: v1 stories -p '{project.name}'")

    def action_refresh(self) -> None:
        """Refresh project list."""
        self.refresh_data()
