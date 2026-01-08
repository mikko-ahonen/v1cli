"""Main Textual TUI application."""

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header

from v1cli.tui.screens.dashboard import DashboardScreen


class V1App(App):
    """V1CLI TUI Application."""

    TITLE = "V1CLI"
    SUB_TITLE = "VersionOne CLI"
    CSS_PATH = None

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("d", "dashboard", "Dashboard", show=True),
        Binding("p", "projects", "Projects", show=True),
        Binding("r", "refresh", "Refresh", show=True),
    ]

    CSS = """
    Screen {
        background: $surface;
    }

    #story-list {
        height: 1fr;
        border: solid $primary;
        padding: 1;
    }

    .story-row {
        height: 1;
        padding: 0 1;
    }

    .story-row:hover {
        background: $boost;
    }

    .story-row.selected {
        background: $accent;
    }

    .status-backlog { color: $text-muted; }
    .status-ready { color: cyan; }
    .status-in_progress { color: yellow; }
    .status-review { color: magenta; }
    .status-done { color: green; }

    #detail-panel {
        width: 40%;
        border: solid $primary;
        padding: 1;
    }

    .label {
        color: $text-muted;
    }

    .title {
        text-style: bold;
    }

    #status-modal {
        align: center middle;
    }

    #status-modal > Vertical {
        width: 40;
        height: auto;
        border: solid $primary;
        background: $surface;
        padding: 1 2;
    }

    .modal-title {
        text-style: bold;
        margin-bottom: 1;
    }

    OptionList {
        height: auto;
        max-height: 10;
    }

    DataTable {
        height: 1fr;
    }

    DataTable > .datatable--header {
        text-style: bold;
        background: $primary;
    }

    DataTable > .datatable--cursor {
        background: $accent;
    }

    #loading {
        width: 100%;
        height: 100%;
        align: center middle;
    }

    #error-message {
        color: red;
        padding: 1;
    }

    .task-done {
        color: green;
    }

    .task-pending {
        color: $text-muted;
    }
    """

    def compose(self) -> ComposeResult:
        """Compose the app layout."""
        yield Header()
        yield Footer()

    def on_mount(self) -> None:
        """Handle app mount."""
        self.push_screen(DashboardScreen())

    def action_dashboard(self) -> None:
        """Show dashboard screen."""
        self.push_screen(DashboardScreen())

    def action_projects(self) -> None:
        """Show projects screen."""
        from v1cli.tui.screens.projects import ProjectsScreen

        self.push_screen(ProjectsScreen())

    def action_refresh(self) -> None:
        """Refresh current screen."""
        if hasattr(self.screen, "refresh_data"):
            self.screen.refresh_data()


if __name__ == "__main__":
    app = V1App()
    app.run()
