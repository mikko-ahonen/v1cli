"""CLI commands for v1cli."""

import asyncio
import csv
import json
from typing import Any

import click
from rich.console import Console
from rich.table import Table
from rich.tree import Tree

from v1cli.api.client import V1APIError, V1Client
from v1cli.config.auth import AuthError
from v1cli.config.defaults import get_default_project_query_config
from v1cli.config.settings import ProjectQueryConfig, get_settings, save_settings
from v1cli.config.workflow import STATUS_COLORS, STATUS_ICONS, StoryStatus
from v1cli.display import build_table_from_config
from v1cli.storage.local import LocalStorage

console = Console()
storage = LocalStorage()


def run_async(coro: Any) -> Any:
    """Run an async coroutine synchronously."""
    return asyncio.run(coro)


def handle_errors(func: Any) -> Any:
    """Decorator to handle common errors gracefully."""

    @click.pass_context
    def wrapper(ctx: click.Context, *args: Any, **kwargs: Any) -> Any:
        try:
            return ctx.invoke(func, *args, **kwargs)
        except AuthError as e:
            console.print(f"[red]Authentication error:[/red] {e}")
            raise SystemExit(1)
        except V1APIError as e:
            console.print(f"[red]API error:[/red] {e}")
            raise SystemExit(1)
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            raise SystemExit(1)

    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


@click.group()
@click.version_option(package_name="v1cli")
def cli() -> None:
    """V1CLI - An opinionated CLI for VersionOne.

    Get started by setting environment variables:

        export V1_URL='https://www7.v1host.com/YourInstance'

        export V1_TOKEN='your-api-token'

    Then run 'v1 setup' to configure status mappings.
    """
    pass


# =============================================================================
# Authentication & Setup Commands
# =============================================================================


@cli.command()
@handle_errors
def me() -> None:
    """Show current user info and cache member OID."""

    async def _me() -> None:
        async with V1Client() as client:
            member = await client.get_me()
            storage.cache_member(member.oid, member.name)

            console.print(f"[green]Logged in as:[/green] {member.name}")
            console.print(f"[dim]Email:[/dim] {member.email or 'N/A'}")
            console.print(f"[dim]Username:[/dim] {member.username or 'N/A'}")
            console.print(f"[dim]OID:[/dim] {member.oid}")
            console.print(f"\n[dim]Member info cached to ~/.v1cli/config.toml[/dim]")

    run_async(_me())


@cli.command()
@handle_errors
def setup() -> None:
    """Interactive setup to discover and map V1 status OIDs."""

    async def _setup() -> None:
        console.print("[bold]V1CLI Setup[/bold]\n")

        async with V1Client() as client:
            # Get current user
            console.print("Connecting to VersionOne...")
            member = await client.get_me()
            storage.cache_member(member.oid, member.name)
            console.print(f"[green]Found user:[/green] {member.name} ({member.oid})\n")

            # Discover statuses
            console.print("Discovering story statuses...")
            statuses = await client.get_story_statuses()

            if not statuses:
                console.print("[yellow]No story statuses found.[/yellow]")
                return

            console.print(f"Found {len(statuses)} statuses:\n")
            for i, status in enumerate(statuses, 1):
                console.print(f"  {i}. {status.name} ({status.oid})")

            console.print()

            # Map statuses
            settings = get_settings()
            workflow_statuses = [
                ("BACKLOG", "backlog"),
                ("READY", "ready"),
                ("IN_PROGRESS", "in_progress"),
                ("REVIEW", "review"),
                ("DONE", "done"),
            ]

            for display_name, attr_name in workflow_statuses:
                while True:
                    choice = click.prompt(
                        f"Map to {display_name}",
                        type=int,
                        default=0,
                    )
                    if choice == 0:
                        console.print(f"  [dim]Skipped {display_name}[/dim]")
                        break
                    if 1 <= choice <= len(statuses):
                        selected = statuses[choice - 1]
                        setattr(settings.status_mapping, attr_name, selected.oid)
                        console.print(f"  [green]{display_name} → {selected.name}[/green]")
                        break
                    console.print(f"  [red]Invalid choice. Enter 1-{len(statuses)} or 0 to skip.[/red]")

            save_settings(settings)
            console.print(f"\n[green]Configuration saved to ~/.v1cli/config.toml[/green]")

    run_async(_setup())


@cli.command()
@click.argument("asset_type", default="Epic")
@click.option("--filter", "-f", "filter_text", help="Filter attributes by name (case-insensitive)")
@handle_errors
def schema(asset_type: str, filter_text: str | None) -> None:
    """Show available attributes for an asset type.

    Common asset types: Epic, Story, Task, Member, StoryStatus

    Example: v1 schema Epic --filter estimate
    """

    async def _schema() -> None:
        async with V1Client() as client:
            console.print(f"[bold]Schema for {asset_type}[/bold]\n")

            try:
                attributes = await client.get_asset_attributes(asset_type)
            except Exception as e:
                console.print(f"[red]Failed to get schema:[/red] {e}")
                console.print("[dim]Common asset types: Epic, Story, Task, Member, StoryStatus[/dim]")
                raise SystemExit(1)

            if filter_text:
                filter_lower = filter_text.lower()
                attributes = [a for a in attributes if filter_lower in a["name"].lower()]

            if not attributes:
                console.print("[yellow]No attributes found.[/yellow]")
                return

            table = Table()
            table.add_column("Attribute", style="cyan")
            table.add_column("Type")
            table.add_column("Flags", style="dim")
            table.add_column("Related To", style="magenta")

            for attr in attributes:
                flags = []
                if attr["is_required"]:
                    flags.append("required")
                if attr["is_readonly"]:
                    flags.append("readonly")
                if attr["is_multi_value"]:
                    flags.append("multi")

                table.add_row(
                    attr["name"],
                    attr["type"],
                    ", ".join(flags) if flags else "-",
                    attr["related_asset"] or "-",
                )

            console.print(table)
            console.print(f"\n[dim]Total: {len(attributes)} attributes[/dim]")

    run_async(_schema())


# =============================================================================
# Project Commands
# =============================================================================


def _list_projects(show_all: bool, output_file: str | None, output_format: str) -> None:
    """List projects (helper function)."""

    async def _projects() -> None:
        async with V1Client() as client:
            if show_all:
                # Fetch all Implementation projects from API
                project_list = await client.get_projects(include_all_statuses=False)
            else:
                # Show only bookmarked projects
                bookmarks = storage.settings.bookmarks
                if not bookmarks:
                    console.print("[yellow]No bookmarked projects.[/yellow]")
                    console.print("[dim]Use 'v1 projects add <number>' to bookmark a project.[/dim]")
                    console.print("[dim]Use 'v1 projects all' to list all projects.[/dim]")
                    return

                # Fetch details for bookmarked projects
                project_list = []
                for bookmark in bookmarks:
                    project = await client.get_project_by_number(bookmark.oid.split(":")[-1]) if ":" in bookmark.oid else None
                    if not project:
                        # Try fetching by OID directly
                        results = await client._query(
                            "Epic",
                            select=["Name", "Number", "Category.Name", "Super.Name", "Status.Name"],
                            filter_=[f"ID='{bookmark.oid}'"],
                        )
                        if results:
                            item = results[0]
                            from v1cli.api.models import Project
                            project = Project(
                                oid=item["_oid"],
                                name=item.get("Name", bookmark.name),
                                number=item.get("Number", ""),
                                category=item.get("Category.Name"),
                                parent_name=item.get("Super.Name"),
                                status=item.get("Status.Name"),
                            )
                    if project:
                        project_list.append(project)

            if not project_list:
                console.print("[yellow]No projects found.[/yellow]")
                return

            # Handle file output
            if output_file:
                _write_projects_to_file(project_list, output_file, output_format)
                console.print(f"[green]Wrote {len(project_list)} projects to {output_file}[/green]")
                return

            # Console output
            title = "All Projects (Implementation)" if show_all else "Bookmarked Projects"
            table = Table(title=title)
            table.add_column("Number", style="cyan", no_wrap=True)
            table.add_column("Name")
            table.add_column("Status", style="magenta")
            table.add_column("Parent", style="dim")
            if show_all:
                table.add_column("★", style="green", no_wrap=True)

            bookmarked_oids = set(storage.get_bookmarked_project_oids())
            default_oid = storage.get_default_project_oid()

            for project in project_list:
                bookmark_marker = ""
                if project.oid in bookmarked_oids:
                    bookmark_marker = "★"
                    if project.oid == default_oid:
                        bookmark_marker = "★ def"
                row = [
                    project.number,
                    project.name,
                    project.status or "-",
                    project.parent_name or "-",
                ]
                if show_all:
                    row.append(bookmark_marker)
                table.add_row(*row)

            console.print(table)
            console.print(f"\n[dim]Total: {len(project_list)} projects[/dim]")

    run_async(_projects())


@cli.group(name="projects")
def projects_group() -> None:
    """List and manage projects."""
    pass


@projects_group.command(name="list")
@handle_errors
def projects_list() -> None:
    """List bookmarked projects."""
    bookmarks = storage.settings.bookmarks
    if not bookmarks:
        console.print("[yellow]No bookmarked projects.[/yellow]")
        console.print("[dim]Use 'v1 projects add <number>' to bookmark a project.[/dim]")
        return

    default_oid = storage.get_default_project_oid()

    table = Table(title="Bookmarked Projects")
    table.add_column("#", style="bold yellow", no_wrap=True, justify="right")
    table.add_column("V1 Number", style="cyan", no_wrap=True)
    table.add_column("Name")
    table.add_column("Default", style="green", no_wrap=True)

    for idx, bookmark in enumerate(bookmarks, start=1):
        # Extract V1 number from OID (e.g., "Epic:1234" -> "E-1234")
        v1_number = ""
        if ":" in bookmark.oid:
            num = bookmark.oid.split(":")[-1]
            v1_number = f"E-{num}"
        is_default = "★" if bookmark.oid == default_oid else ""
        table.add_row(str(idx), v1_number, bookmark.name, is_default)

    console.print(table)
    console.print(f"\n[dim]Total: {len(bookmarks)} bookmarks[/dim]")
    console.print("[dim]Use project # (1, 2, ...) as shorthand in commands[/dim]")


@projects_group.command(name="all")
@click.option("--output", "-o", "output_file", type=click.Path(), help="Write output to file")
@click.option("--format", "-f", "output_format", type=click.Choice(["table", "csv", "json"]), default="table", help="Output format")
@handle_errors
def projects_all(output_file: str | None, output_format: str) -> None:
    """List all projects (from API)."""
    _list_projects(show_all=True, output_file=output_file, output_format=output_format)


@projects_group.command(name="add")
@click.argument("identifier")
@handle_errors
def projects_add(identifier: str) -> None:
    """Bookmark a project.

    IDENTIFIER can be: V1 number (E-nnnnn), OID (Epic:nnnnn), or name.
    """

    async def _add() -> None:
        async with V1Client() as client:
            # Check if identifier looks like a number or OID
            is_number = (
                identifier.upper().startswith("E-") or
                identifier.replace("-", "").isdigit() or
                _is_oid_token(identifier)
            )

            if is_number:
                project = await client.get_project_by_number(identifier)
            else:
                project = await client.get_project_by_name(identifier)

            if not project:
                console.print(f"[red]Project not found:[/red] {identifier}")
                raise SystemExit(1)

            storage.add_project_bookmark(project.name, project.oid)
            console.print(f"[green]Bookmarked:[/green] {project.number} - {project.name}")

    run_async(_add())


@projects_group.command(name="rm")
@click.argument("identifier")
@handle_errors
def projects_rm(identifier: str) -> None:
    """Remove a project bookmark.

    IDENTIFIER can be: project # (1-99), V1 number (E-nnnnn), or OID (Epic:nnnnn).
    """
    result = storage.remove_project_bookmark(identifier)
    if result:
        name, oid = result
        console.print(f"[green]Removed bookmark:[/green] {name} ({oid})")
    else:
        console.print(f"[yellow]Bookmark not found:[/yellow] {identifier}")


@projects_group.command(name="default")
@click.argument("identifier")
@handle_errors
def projects_default(identifier: str) -> None:
    """Set the default project.

    IDENTIFIER can be: project # (1-99), V1 number (E-nnnnn), or OID (Epic:nnnnn).
    """

    async def _default() -> None:
        settings = get_settings()

        # First try to find in existing bookmarks
        bookmark = settings.get_bookmark(identifier)
        if bookmark:
            storage.set_default_project(bookmark.oid)
            console.print(f"[green]Default project set:[/green] {bookmark.name}")
            return

        # Check if it's a number format - if so, fetch and auto-bookmark
        is_number = (
            identifier.upper().startswith("E-") or
            identifier.replace("-", "").isdigit()
        )

        if is_number:
            async with V1Client() as client:
                project = await client.get_project_by_number(identifier)
                if project:
                    storage.add_project_bookmark(project.name, project.oid)
                    storage.set_default_project(project.oid)
                    console.print(f"[green]Bookmarked and set as default:[/green] {project.number} - {project.name}")
                    return

        console.print(f"[red]Project not found:[/red] {identifier}")
        console.print("[dim]Use 'v1 projects add <number>' to bookmark a project first.[/dim]")
        raise SystemExit(1)

    run_async(_default())


@projects_group.command(name="configure")
@click.argument("identifier", required=False)
@click.option("--auto-detect", "-a", is_flag=True, help="Auto-detect available fields from V1 schema")
@click.option("--reset", "-r", is_flag=True, help="Reset to default configuration")
@click.option("--show", "-s", is_flag=True, help="Show current configuration")
@handle_errors
def projects_configure(
    identifier: str | None,
    auto_detect: bool,
    reset: bool,
    show: bool,
) -> None:
    """Configure query settings for a project.

    Auto-detects available fields from your V1 instance to avoid
    errors with custom schemas.

    Examples:

        v1 projects configure --auto-detect     # Configure default project

        v1 projects configure 1 --auto-detect   # Configure project #1

        v1 projects configure E-1234 --show     # Show config for E-1234

        v1 projects configure --reset           # Reset to defaults
    """

    async def _configure() -> None:
        from v1cli.config.schema_detector import auto_detect_project_config

        settings = get_settings()

        # Resolve project
        if identifier:
            bookmark = settings.get_bookmark(identifier)
            if not bookmark:
                console.print(f"[red]Project not found:[/red] {identifier}")
                console.print("[dim]Use 'v1 projects add <number>' to bookmark first.[/dim]")
                raise SystemExit(1)
        else:
            # Use default project
            default_oid = settings.default_project
            if not default_oid:
                console.print("[red]No project specified and no default set.[/red]")
                console.print("[dim]Use 'v1 projects configure <identifier>' or set a default first.[/dim]")
                raise SystemExit(1)
            bookmark = next(
                (b for b in settings.bookmarks if b.oid == default_oid), None
            )
            if not bookmark:
                console.print("[red]Default project not found in bookmarks.[/red]")
                raise SystemExit(1)

        if show:
            _show_project_config(bookmark)
            return

        if reset:
            bookmark.query_config = None
            save_settings(settings)
            console.print(f"[green]Reset configuration for {bookmark.name}[/green]")
            console.print("[dim]Project will use default query settings.[/dim]")
            return

        if auto_detect:
            console.print(f"[bold]Detecting schema for {bookmark.name}...[/bold]")
            async with V1Client() as client:
                config = await auto_detect_project_config(client)
                bookmark.query_config = config
                save_settings(settings)

                console.print(f"[green]Configuration saved![/green]")
                console.print(f"  Delivery Groups: {len(config.delivery_groups.select)} fields")
                console.print(f"  Features: {len(config.features.select)} fields")
                console.print(f"  Stories: {len(config.stories.select)} fields")
                console.print(f"  Tasks: {len(config.tasks.select)} fields")
                console.print(f"\n[dim]Run 'v1 projects configure --show' to see details.[/dim]")
            return

        # Default action: show current config or prompt for auto-detect
        if bookmark.query_config and bookmark.query_config.is_configured():
            _show_project_config(bookmark)
        else:
            console.print(f"[yellow]No custom configuration for {bookmark.name}[/yellow]")
            console.print("[dim]Use --auto-detect to configure based on your V1 schema.[/dim]")

    run_async(_configure())


def _show_project_config(bookmark: Any) -> None:
    """Display current query configuration for a project."""
    from v1cli.config.settings import ProjectBookmark

    console.print(f"\n[bold]Query Configuration: {bookmark.name}[/bold]")

    if not bookmark.query_config or not bookmark.query_config.is_configured():
        console.print("[yellow]Using default configuration[/yellow]")
        return

    config = bookmark.query_config
    console.print(f"[dim]Last detected: {config.last_detected or 'Never'}[/dim]\n")

    for name, asset_config in [
        ("Delivery Groups", config.delivery_groups),
        ("Features", config.features),
        ("Stories", config.stories),
        ("Tasks", config.tasks),
    ]:
        console.print(f"[cyan]{name}[/cyan]")
        if asset_config.select:
            console.print(f"  Select: {', '.join(asset_config.select)}")
        else:
            console.print("  Select: [dim](default)[/dim]")
        if asset_config.filters:
            console.print(f"  Filters: {', '.join(asset_config.filters)}")
        if asset_config.columns:
            col_names = [c.label or c.field for c in asset_config.columns]
            console.print(f"  Columns: {', '.join(col_names)}")
        console.print()


# =============================================================================
# Story Listing Commands
# =============================================================================


@cli.command()
@click.option("--all", "-a", "include_done", is_flag=True, help="Include completed stories")
@click.option("--format", "-f", "output_format", type=click.Choice(["table", "json"]), default="table", help="Output format")
@handle_errors
def mine(include_done: bool, output_format: str) -> None:
    """List stories assigned to me."""

    async def _mine() -> None:
        project_oids = storage.get_bookmarked_project_oids() or None

        async with V1Client() as client:
            stories = await client.get_my_stories(
                project_oids=project_oids,
                include_done=include_done,
            )

            if not stories:
                if output_format == "json":
                    console.print("[]")
                else:
                    console.print("[yellow]No stories assigned to you.[/yellow]")
                return

            if output_format == "json":
                data = [s.model_dump() for s in stories]
                console.print(json.dumps(data, indent=2))
                return

            _print_stories_table(stories, title="My Stories")

    run_async(_mine())


@cli.command()
@click.argument("parent_number", required=False)
@click.option("--project", "-p", "project_id", help="Project # (1-99), V1 number (E-nnn), or OID")
@click.option("--all", "-a", "include_done", is_flag=True, help="Include completed stories")
@click.option("--format", "-f", "output_format", type=click.Choice(["table", "json"]), default="table", help="Output format")
@handle_errors
def stories(parent_number: str | None, project_id: str | None, include_done: bool, output_format: str) -> None:
    """List stories under a feature, story, or entire project.

    \b
    Examples:
        v1 stories              # All stories under default project
        v1 stories -p 1         # All stories under project #1
        v1 stories 3            # Stories under feature #3 from last 'v1 features'
        v1 stories E-123        # Stories under feature E-123
        v1 stories S-456        # Sub-stories under story S-456
        v1 stories -f json      # Output as JSON
    """

    async def _stories() -> None:
        async with V1Client() as client:
            story_list: list[Any] = []
            title = "Stories"

            # If a specific parent is given, use that
            if parent_number:
                # Check if it's a row number from cached features list
                if parent_number.isdigit():
                    cached = storage.get_cached_feature(int(parent_number))
                    if cached:
                        feature_number, feature_oid = cached
                        parent = await client.get_feature_by_number(feature_number)
                        if parent:
                            parent_oid = parent.oid
                            title = f"Stories under {parent.number}: {parent.name}"
                        else:
                            console.print(f"[red]Cached feature not found:[/red] {feature_number}")
                            raise SystemExit(1)
                    else:
                        console.print(f"[red]No cached feature at row {parent_number}. Run 'v1 features' first.[/red]")
                        raise SystemExit(1)
                # Try as Feature (E-xxx or Epic:xxx)
                elif parent_number.upper().startswith("E-") or (
                    ":" in parent_number and parent_number.split(":")[0].lower() == "epic"
                ):
                    parent = await client.get_feature_by_number(parent_number)
                    if not parent:
                        console.print(f"[red]Feature not found:[/red] {parent_number}")
                        raise SystemExit(1)
                    parent_oid = parent.oid
                    title = f"Stories under {parent.number}: {parent.name}"
                else:
                    # Try as Story (S-xxx or Story:xxx)
                    parent = await client.get_story_by_number(parent_number)
                    if not parent:
                        console.print(f"[red]Story not found:[/red] {parent_number}")
                        raise SystemExit(1)
                    parent_oid = parent.oid
                    title = f"Stories under {parent.number}: {parent.name}"

                story_list = await client.get_stories(parent_oid, include_done=include_done)
            else:
                # No parent given - get all stories under the project
                project_oid = await _resolve_project_oid_async(project_id, client)
                if not project_oid:
                    return

                # Collect all features (direct + under delivery groups)
                all_features = await client.get_features(project_oid, include_done=include_done)
                delivery_groups = await client.get_delivery_groups(project_oid, include_done=include_done)
                for dg in delivery_groups:
                    dg_features = await client.get_features(dg.oid, include_done=include_done)
                    all_features.extend(dg_features)

                # Get stories under all features
                for feature in all_features:
                    feature_stories = await client.get_stories(feature.oid, include_done=include_done)
                    story_list.extend(feature_stories)

                title = "All Stories"

            if not story_list:
                if output_format == "json":
                    console.print("[]")
                else:
                    console.print("[yellow]No stories found.[/yellow]")
                return

            if output_format == "json":
                data = [s.model_dump() for s in story_list]
                console.print(json.dumps(data, indent=2))
                return

            _print_stories_table(story_list, title=title)

    run_async(_stories())


@cli.command()
@click.argument("number")
@handle_errors
def story(number: str) -> None:
    """Show story details."""

    async def _story() -> None:
        async with V1Client() as client:
            s = await client.get_story_by_number(number)
            if not s:
                console.print(f"[red]Story not found:[/red] {number}")
                raise SystemExit(1)

            settings = get_settings()
            status_enum = None
            if s.status_oid:
                status_enum = settings.status_mapping.get_status(s.status_oid)

            icon = STATUS_ICONS.get(status_enum, "○") if status_enum else "○"
            color = STATUS_COLORS.get(status_enum, "white") if status_enum else "white"

            console.print(f"\n[bold]{s.number}:[/bold] {s.name}")
            console.print(f"[{color}]{icon} {s.status_display}[/{color}]")
            console.print()
            console.print(f"[dim]Project:[/dim] {s.scope_name}")
            if s.parent_name:
                console.print(f"[dim]Feature:[/dim] {s.parent_name}")
            console.print(f"[dim]Owners:[/dim] {', '.join(s.owners) or 'None'}")
            if s.estimate:
                console.print(f"[dim]Estimate:[/dim] {s.estimate} pts")
            console.print(f"[dim]OID:[/dim] {s.oid}")

            if s.description:
                console.print(f"\n[bold]Description[/bold]")
                console.print(s.description[:500])
                if len(s.description) > 500:
                    console.print("[dim]...(truncated)[/dim]")

            # Show tasks
            tasks = await client.get_tasks(s.oid)
            if tasks:
                console.print(f"\n[bold]Tasks ({len(tasks)})[/bold]")
                for task in tasks:
                    done_marker = "[x]" if task.is_done else "[ ]"
                    hours = ""
                    if task.todo is not None or task.done is not None:
                        hours = f" ({task.done or 0}h done, {task.todo or 0}h todo)"
                    console.print(f"  {done_marker} {task.name}{hours}")

    run_async(_story())


# =============================================================================
# Story Action Commands
# =============================================================================


@cli.command()
@click.argument("number")
@click.argument("new_status")
@handle_errors
def status(number: str, new_status: str) -> None:
    """Change story status (backlog/ready/progress/review/done)."""

    async def _status() -> None:
        settings = get_settings()
        if not settings.status_mapping.is_configured():
            console.print("[red]Status mapping not configured.[/red]")
            console.print("Run 'v1 setup' first to map your V1 statuses.")
            raise SystemExit(1)

        try:
            target_status = StoryStatus.from_string(new_status)
        except ValueError:
            console.print(f"[red]Invalid status:[/red] {new_status}")
            console.print("Valid statuses: backlog, ready, progress, review, done")
            raise SystemExit(1)

        status_oid = settings.status_mapping.get_oid(target_status)
        if not status_oid:
            console.print(f"[red]Status not mapped:[/red] {target_status.value}")
            console.print("Run 'v1 setup' to configure this status.")
            raise SystemExit(1)

        async with V1Client() as client:
            s = await client.get_story_by_number(number)
            if not s:
                console.print(f"[red]Story not found:[/red] {number}")
                raise SystemExit(1)

            await client.update_story_status(s.oid, status_oid)

            icon = STATUS_ICONS.get(target_status, "○")
            color = STATUS_COLORS.get(target_status, "white")
            console.print(f"[green]Updated {s.number}:[/green] [{color}]{icon} {target_status.value}[/{color}]")

    run_async(_status())


@cli.command()
@click.argument("number")
@handle_errors
def take(number: str) -> None:
    """Assign a story to myself."""

    async def _take() -> None:
        member_oid = storage.get_cached_member_oid()
        if not member_oid:
            console.print("[red]Member OID not cached.[/red]")
            console.print("Run 'v1 me' first.")
            raise SystemExit(1)

        async with V1Client() as client:
            s = await client.get_story_by_number(number)
            if not s:
                console.print(f"[red]Story not found:[/red] {number}")
                raise SystemExit(1)

            await client.assign_story_to_me(s.oid, member_oid)
            console.print(f"[green]Assigned {s.number} to you[/green]")

    run_async(_take())


# =============================================================================
# Feature Commands
# =============================================================================


@cli.command()
@click.option("--project", "-p", "project_name", help="Project # (1-99), V1 number (E-nnn), or name")
@click.option("--all", "-a", "include_done", is_flag=True, help="Include closed delivery groups")
@click.option("--output", "-o", "output_file", type=click.Path(), help="Write output to file")
@click.option("--format", "-f", "output_format", type=click.Choice(["table", "csv", "json"]), default="table", help="Output format")
@handle_errors
def roadmap(project_name: str | None, include_done: bool, output_file: str | None, output_format: str) -> None:
    """List delivery groups (roadmap) for a project."""

    async def _roadmap() -> None:
        async with V1Client() as client:
            project_oid, query_config = await _resolve_project_with_config(project_name, client)

            # Use config-based query
            dg_config = query_config.delivery_groups
            results = await client.query_with_config(
                asset_type="Epic",
                parent_oid=project_oid,
                parent_field="Super",
                config_select=dg_config.select,
                config_filters=dg_config.filters,
                config_sort=dg_config.sort,
                include_done=include_done,
            )

            if not results:
                console.print("[yellow]No delivery groups found.[/yellow]")
                return

            # Handle file output (use raw results)
            if output_file:
                _write_results_to_file(results, output_file, output_format)
                console.print(f"[green]Wrote {len(results)} delivery groups to {output_file}[/green]")
                return

            # Build table from configuration
            table = build_table_from_config(
                "Roadmap (Delivery Groups)",
                results,
                dg_config,
            )

            console.print(table)
            console.print(f"\n[dim]Total: {len(results)} delivery groups[/dim]")

    run_async(_roadmap())


@cli.command()
@click.option("--parent", "-p", "parent_id", help="Parent: project # (1-99), V1 number (E-nnn), or OID")
@click.option("--all", "-a", "include_done", is_flag=True, help="Include closed features")
@click.option("--format", "-f", "output_format", type=click.Choice(["table", "json"]), default="table", help="Output format")
@handle_errors
def features(parent_id: str | None, include_done: bool, output_format: str) -> None:
    """List features under a Delivery Group or Project.

    When parent is a Project, shows features under all Delivery Groups.
    """

    async def _features() -> None:
        async with V1Client() as client:
            parent_oid = await _resolve_project_oid_async(parent_id, client)
            if not parent_oid:
                return

            # Get features directly under the parent
            feature_list = await client.get_features(parent_oid, include_done=include_done)

            # Also get features under any Delivery Groups (for project-level queries)
            delivery_groups = await client.get_delivery_groups(parent_oid, include_done=include_done)
            for dg in delivery_groups:
                dg_features = await client.get_features(dg.oid, include_done=include_done)
                feature_list.extend(dg_features)

            if not feature_list:
                if output_format == "json":
                    console.print("[]")
                else:
                    console.print("[yellow]No features found.[/yellow]")
                return

            # Cache features for later reference by row number
            storage.cache_features([(f.number, f.oid) for f in feature_list])

            if output_format == "json":
                data = [f.model_dump() for f in feature_list]
                console.print(json.dumps(data, indent=2))
                return

            table = Table(title="Features")
            table.add_column("#", style="dim", justify="right")
            table.add_column("Number", style="cyan")
            table.add_column("Name")
            table.add_column("Status")
            table.add_column("Parent", style="dim")

            for idx, feature in enumerate(feature_list, 1):
                table.add_row(
                    str(idx),
                    feature.number,
                    feature.name,
                    feature.status or "-",
                    feature.parent_name or feature.scope_name,
                )

            console.print(table)

    run_async(_features())


@cli.group(name="feature")
def feature_group() -> None:
    """Manage features."""
    pass


@feature_group.command(name="create")
@click.argument("name")
@click.option("--parent", "-p", "parent_id", help="Parent: project # (1-99), V1 number (E-nnn), or OID")
@click.option("--description", "-d", "description", default="", help="Feature description")
@handle_errors
def feature_create(name: str, parent_id: str | None, description: str) -> None:
    """Create a new feature."""

    async def _create() -> None:
        async with V1Client() as client:
            parent_oid = await _resolve_project_oid_async(parent_id, client)
            if not parent_oid:
                return

            oid = await client.create_feature(name, parent_oid, description)
            console.print(f"[green]Created feature:[/green] {oid}")
            console.print(f"  Name: {name}")

    run_async(_create())


# =============================================================================
# Story Creation Commands
# =============================================================================


@cli.group(name="story", invoke_without_command=True)
@click.pass_context
def story_group(ctx: click.Context) -> None:
    """Manage stories."""
    # If no subcommand, this is `v1 story <number>` - redirect
    pass


@story_group.command(name="create")
@click.argument("name")
@click.option("--project", "-p", "project_name", help="Project # (1-99), V1 number (E-nnn), or name")
@click.option("--feature", "-e", "feature_number", help="Parent feature number (e.g., E-100)")
@click.option("--estimate", "-s", type=float, help="Story points estimate")
@click.option("--description", "-d", "description", default="", help="Story description")
@handle_errors
def story_create(
    name: str,
    project_name: str | None,
    feature_number: str | None,
    estimate: float | None,
    description: str,
) -> None:
    """Create a new story."""

    async def _create() -> None:
        async with V1Client() as client:
            project_oid = await _resolve_project_oid_async(project_name, client)
            if not project_oid:
                return

            feature_oid = None
            if feature_number:
                feature = await client.get_feature_by_number(feature_number)
                if not feature:
                    console.print(f"[red]Feature not found:[/red] {feature_number}")
                    raise SystemExit(1)
                feature_oid = feature.oid

            oid = await client.create_story(
                name=name,
                project_oid=project_oid,
                feature_oid=feature_oid,
                estimate=estimate,
                description=description,
            )
            console.print(f"[green]Created story:[/green] {oid}")
            console.print(f"  Name: {name}")
            if feature_number:
                console.print(f"  Feature: {feature_number}")
            if estimate:
                console.print(f"  Estimate: {estimate} pts")

    run_async(_create())


# =============================================================================
# Task Commands
# =============================================================================


@cli.command()
@click.argument("story_number")
@click.option("--format", "-f", "output_format", type=click.Choice(["table", "json"]), default="table", help="Output format")
@handle_errors
def tasks(story_number: str, output_format: str) -> None:
    """List tasks for a story.

    \b
    Examples:
        v1 tasks 3         # Tasks for story #3 from last 'v1 stories'
        v1 tasks S-123     # Tasks for story S-123
    """

    async def _tasks() -> None:
        async with V1Client() as client:
            # Check if it's a row number from cached stories list
            if story_number.isdigit():
                cached = storage.get_cached_story(int(story_number))
                if cached:
                    cached_number, cached_oid = cached
                    s = await client.get_story_by_number(cached_number)
                else:
                    console.print(f"[red]No cached story at row {story_number}. Run 'v1 stories' first.[/red]")
                    raise SystemExit(1)
            else:
                s = await client.get_story_by_number(story_number)

            if not s:
                console.print(f"[red]Story not found:[/red] {story_number}")
                raise SystemExit(1)

            task_list = await client.get_tasks(s.oid)

            if not task_list:
                if output_format == "json":
                    console.print("[]")
                else:
                    console.print(f"[yellow]No tasks for {story_number}[/yellow]")
                return

            if output_format == "json":
                data = [t.model_dump() for t in task_list]
                console.print(json.dumps(data, indent=2))
                return

            console.print(f"[bold]Tasks for {s.number}: {s.name}[/bold]\n")

            for task in task_list:
                done_marker = "[green]✓[/green]" if task.is_done else "[ ]"
                hours = ""
                if task.todo is not None or task.done is not None:
                    hours = f" [dim]({task.done or 0}h done, {task.todo or 0}h todo)[/dim]"
                owners = f" [dim]({', '.join(task.owners)})[/dim]" if task.owners else ""
                task_num = f"[cyan]{task.number}[/cyan] " if task.number else ""
                console.print(f"  {done_marker} {task_num}{task.name}{hours}{owners}")

    run_async(_tasks())


@cli.group(name="task")
def task_group() -> None:
    """Manage tasks."""
    pass


@task_group.command(name="create")
@click.argument("story_number")
@click.argument("name")
@click.option("--estimate", "-e", type=float, help="Hours estimate")
@handle_errors
def task_create(story_number: str, name: str, estimate: float | None) -> None:
    """Create a task for a story."""

    async def _create() -> None:
        async with V1Client() as client:
            s = await client.get_story_by_number(story_number)
            if not s:
                console.print(f"[red]Story not found:[/red] {story_number}")
                raise SystemExit(1)

            oid = await client.create_task(name, s.oid, estimate)
            console.print(f"[green]Created task:[/green] {oid}")
            console.print(f"  Name: {name}")
            console.print(f"  Story: {s.number}")
            if estimate:
                console.print(f"  Estimate: {estimate}h")

    run_async(_create())


@task_group.command(name="done")
@click.argument("identifier")
@handle_errors
def task_done(identifier: str) -> None:
    """Mark a task as done (TK-nnnnn or Task:nnnnn)."""

    async def _done() -> None:
        async with V1Client() as client:
            task = await client.get_task_by_identifier(identifier)
            if not task:
                console.print(f"[red]Task not found:[/red] {identifier}")
                raise SystemExit(1)

            await client.complete_task(task.oid)
            display = task.number or task.oid
            console.print(f"[green]Marked task as done:[/green] {display} - {task.name}")

    run_async(_done())


# =============================================================================
# Tree Command
# =============================================================================


@cli.command()
@click.option("--project", "-p", "project_id", help="Project # (1-99), V1 number (E-nnn), or OID")
@click.option("--depth", "-d", type=click.Choice(["deliveries", "features", "stories", "tasks"]), default="stories", help="Tree depth")
@click.option("--all", "-a", "include_done", is_flag=True, help="Include closed items")
@click.option("--types", "-t", "show_types", is_flag=True, help="Show asset types (Epic, Story, Task)")
@handle_errors
def tree(project_id: str | None, depth: str, include_done: bool, show_types: bool) -> None:
    """Show project hierarchy as a tree.

    Displays the full structure: Project → Delivery Groups → Features → Stories → Tasks
    """

    async def _tree() -> None:
        async with V1Client() as client:
            project_oid = await _resolve_project_oid_async(project_id, client)
            if not project_oid:
                return

            # Get project name for the root
            project = await client.get_project_by_number(project_oid)
            project_name = project.name if project else project_oid

            # Create tree root
            root_label = f"[bold cyan]{project_name}[/bold cyan]"
            if show_types:
                root_label = f"[dim]Scope:[/dim] {root_label}"
            root = Tree(root_label)

            # Get delivery groups
            deliveries = await client.get_delivery_groups(project_oid, include_done=include_done)

            # Also get features directly under the project (not under a delivery group)
            direct_features = await client.get_features(project_oid, include_done=include_done)

            if not deliveries and not direct_features:
                console.print(f"[yellow]No items found under project.[/yellow]")
                return

            # Add delivery groups
            for dg in deliveries:
                dg_label = f"[bold magenta]{dg.number}[/bold magenta] {dg.name}"
                if show_types:
                    category_info = f" ({dg.category})" if dg.category else ""
                    dg_label = f"[dim]Epic{category_info}:[/dim] {dg_label}"
                if dg.status:
                    dg_label += f" [dim]({dg.status})[/dim]"
                dg_branch = root.add(dg_label)

                if depth in ["features", "stories", "tasks"]:
                    # Get features under this delivery group
                    features = await client.get_features(dg.oid, include_done=include_done)
                    await _add_features_to_tree(dg_branch, features, depth, include_done, client, show_types)

            # Add features directly under project (not under a delivery group)
            if direct_features:
                await _add_features_to_tree(root, direct_features, depth, include_done, client, show_types)

            console.print(root)

    async def _add_features_to_tree(
        parent_branch: Tree,
        features: list[Any],
        depth: str,
        include_done: bool,
        client: V1Client,
        show_types: bool,
    ) -> None:
        """Add features and their children to the tree."""
        for feature in features:
            f_label = f"[cyan]{feature.number}[/cyan] {feature.name}"
            if show_types:
                category_info = f" ({feature.category})" if feature.category else ""
                f_label = f"[dim]Epic{category_info}:[/dim] {f_label}"
            if feature.status:
                f_label += f" [dim]({feature.status})[/dim]"
            f_branch = parent_branch.add(f_label)

            if depth in ["stories", "tasks"]:
                # Get stories under this feature
                stories = await client.get_stories(feature.oid, include_done=include_done)
                for story in stories:
                    settings = get_settings()
                    status_enum = None
                    if story.status_oid:
                        status_enum = settings.status_mapping.get_status(story.status_oid)

                    icon = STATUS_ICONS.get(status_enum, "○") if status_enum else "○"
                    color = STATUS_COLORS.get(status_enum, "white") if status_enum else "white"

                    s_label = f"[green]{story.number}[/green] {story.name}"
                    if show_types:
                        s_label = f"[dim]Story:[/dim] {s_label}"
                    s_label += f" [{color}]{icon}[/{color}]"
                    if story.estimate:
                        s_label += f" [dim]{int(story.estimate)}pts[/dim]"

                    s_branch = f_branch.add(s_label)

                    if depth == "tasks":
                        # Get tasks under this story
                        tasks = await client.get_tasks(story.oid)
                        for task in tasks:
                            done_marker = "[green]✓[/green]" if task.is_done else "[ ]"
                            t_label = f"{done_marker} {task.name}"
                            if task.number:
                                t_label = f"[dim]{task.number}[/dim] {t_label}"
                            if show_types:
                                t_label = f"[dim]Task:[/dim] {t_label}"
                            s_branch.add(t_label)

    run_async(_tree())


# =============================================================================
# TUI Command
# =============================================================================


@cli.command()
@handle_errors
def tui() -> None:
    """Launch interactive TUI dashboard."""
    from v1cli.tui.app import V1App

    app = V1App()
    app.run()


# =============================================================================
# Helper Functions
# =============================================================================


def _is_oid_token(identifier: str) -> bool:
    """Check if identifier is an OID token (e.g., 'Epic:1234', 'Story:5678')."""
    if ":" not in identifier:
        return False
    parts = identifier.split(":", 1)
    return parts[0].isalpha() and parts[1].isdigit()


async def _resolve_project_oid_async(project_identifier: str | None, client: V1Client) -> str:
    """Resolve a project OID from name, number, OID token, or default."""
    if project_identifier:
        # Check if it's already an OID token
        if _is_oid_token(project_identifier):
            return project_identifier

        settings = get_settings()

        # Check bookmarks by name, number, or OID
        bookmark = settings.get_bookmark(project_identifier)
        if bookmark:
            return bookmark.oid

        # Check if it looks like a number (E-xxx)
        is_number = (
            project_identifier.upper().startswith("E-") or
            project_identifier.replace("-", "").isdigit()
        )

        if is_number:
            # Try to fetch by number
            project = await client.get_project_by_number(project_identifier)
            if project:
                return project.oid

        console.print(f"[red]Project not found:[/red] {project_identifier}")
        console.print("Use 'v1 projects add <number>' to bookmark a project.")
        raise SystemExit(1)

    default_oid = storage.get_default_project_oid()
    if default_oid:
        return default_oid

    console.print("[red]No project specified and no default set.[/red]")
    console.print("Use --project/-p or set a default with 'v1 projects default <number>'")
    raise SystemExit(1)


async def _resolve_project_with_config(
    project_identifier: str | None, client: V1Client
) -> tuple[str, ProjectQueryConfig]:
    """Resolve project OID and return its query configuration.

    Returns:
        Tuple of (project_oid, query_config). The query_config is either
        the project's custom config or the defaults.
    """
    project_oid = await _resolve_project_oid_async(project_identifier, client)

    settings = get_settings()
    # Find bookmark for this project
    bookmark = next(
        (b for b in settings.bookmarks if b.oid == project_oid),
        None
    )

    if bookmark and bookmark.query_config and bookmark.query_config.is_configured():
        return project_oid, bookmark.query_config

    return project_oid, get_default_project_query_config()


def _resolve_project_oid(project_identifier: str | None) -> str:
    """Resolve a project OID from name, number, OID token, or default (sync, bookmarks only)."""
    if project_identifier:
        # Check if it's already an OID token
        if _is_oid_token(project_identifier):
            return project_identifier

        settings = get_settings()
        bookmark = settings.get_bookmark(project_identifier)
        if bookmark:
            return bookmark.oid
        console.print(f"[red]Project bookmark not found:[/red] {project_identifier}")
        console.print("Use 'v1 projects add <number>' to bookmark a project.")
        raise SystemExit(1)

    default_oid = storage.get_default_project_oid()
    if default_oid:
        return default_oid

    console.print("[red]No project specified and no default set.[/red]")
    console.print("Use --project/-p or set a default with 'v1 projects default <number>'")
    raise SystemExit(1)


def _print_stories_table(stories: list[Any], title: str = "Stories") -> None:
    """Print a formatted table of stories."""
    settings = get_settings()

    # Cache stories for later reference by row number
    storage.cache_stories([(s.number, s.oid) for s in stories])

    table = Table(title=title)
    table.add_column("#", style="dim", justify="right")
    table.add_column("Number", style="cyan", no_wrap=True)
    table.add_column("Status", no_wrap=True)
    table.add_column("Name")
    table.add_column("Pts", justify="right")
    table.add_column("Project", style="dim")

    for idx, s in enumerate(stories, 1):
        status_enum = None
        if s.status_oid:
            status_enum = settings.status_mapping.get_status(s.status_oid)

        icon = STATUS_ICONS.get(status_enum, "○") if status_enum else "○"
        color = STATUS_COLORS.get(status_enum, "white") if status_enum else "white"
        status_display = f"[{color}]{icon} {s.status_display}[/{color}]"

        pts = str(int(s.estimate)) if s.estimate else "-"

        table.add_row(
            str(idx),
            s.number,
            status_display,
            s.name,
            pts,
            s.scope_name,
        )

    console.print(table)
    console.print(f"\n[dim]Total: {len(stories)} stories[/dim]")


def _write_projects_to_file(projects: list[Any], filepath: str, fmt: str) -> None:
    """Write projects to a file in the specified format."""
    if fmt == "json":
        data = [
            {
                "oid": p.oid,
                "number": p.number,
                "name": p.name,
                "category": p.category,
                "parent": p.parent_name,
                "scope": p.scope_name,
                "description": p.description,
            }
            for p in projects
        ]
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    elif fmt == "csv":
        with open(filepath, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["OID", "Number", "Name", "Category", "Parent", "Scope"])
            for p in projects:
                writer.writerow([
                    p.oid,
                    p.number,
                    p.name,
                    p.category or "",
                    p.parent_name or "",
                    p.scope_name or "",
                ])

    else:  # table format as plain text
        lines = ["Number\tName\tCategory\tParent"]
        for p in projects:
            lines.append(f"{p.number}\t{p.name}\t{p.category or '-'}\t{p.parent_name or '-'}")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))


def _write_results_to_file(results: list[dict[str, Any]], filepath: str, fmt: str) -> None:
    """Write raw query results to a file in the specified format."""
    if fmt == "json":
        # Clean up _oid to oid
        data = []
        for item in results:
            clean_item = {"oid": item.get("_oid", "")}
            for key, value in item.items():
                if not key.startswith("_"):
                    clean_item[key] = value
            data.append(clean_item)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    elif fmt == "csv":
        if not results:
            return
        # Get all keys from first result (excluding internal keys)
        keys = ["oid"] + [k for k in results[0].keys() if not k.startswith("_")]
        with open(filepath, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(keys)
            for item in results:
                row = [item.get("_oid", "")]
                for key in keys[1:]:
                    value = item.get(key, "")
                    if isinstance(value, list):
                        value = ", ".join(str(v) for v in value)
                    row.append(value if value is not None else "")
                writer.writerow(row)

    else:  # table format as plain text
        if not results:
            return
        keys = [k for k in results[0].keys() if not k.startswith("_")]
        lines = ["\t".join(keys)]
        for item in results:
            row = []
            for key in keys:
                value = item.get(key, "-")
                if isinstance(value, list):
                    value = ", ".join(str(v) for v in value)
                row.append(str(value) if value is not None else "-")
            lines.append("\t".join(row))
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))


def _write_deliveries_to_file(deliveries: list[Any], filepath: str, fmt: str) -> None:
    """Write delivery groups to a file in the specified format."""
    if fmt == "json":
        data = [
            {
                "oid": d.oid,
                "number": d.number,
                "name": d.name,
                "type": d.delivery_type,
                "status": d.status,
                "planned_start": d.planned_start,
                "planned_end": d.planned_end,
                "progress": d.progress,
                "estimate": d.estimate,
            }
            for d in deliveries
        ]
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    elif fmt == "csv":
        with open(filepath, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["OID", "Number", "Name", "Type", "Status", "PlannedStart", "PlannedEnd", "Progress", "Estimate"])
            for d in deliveries:
                writer.writerow([
                    d.oid,
                    d.number,
                    d.name,
                    d.delivery_type or "",
                    d.status or "",
                    d.planned_start or "",
                    d.planned_end or "",
                    d.progress or "",
                    d.estimate or "",
                ])

    else:  # table format as plain text
        lines = ["Number\tName\tType\tStatus\tBegin\tEnd\tProgress\tEstimate"]
        for d in deliveries:
            begin = (d.planned_start or "")[:10] if d.planned_start else "-"
            end = (d.planned_end or "")[:10] if d.planned_end else "-"
            progress = f"{int(d.progress * 100)}%" if d.progress is not None else "-"
            estimate = str(int(d.estimate)) if d.estimate is not None else "-"
            lines.append(f"{d.number}\t{d.name}\t{d.delivery_type or '-'}\t{d.status or '-'}\t{begin}\t{end}\t{progress}\t{estimate}")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))


if __name__ == "__main__":
    cli()
