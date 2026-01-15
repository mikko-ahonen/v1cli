"""CLI commands for v1cli."""

import asyncio
import csv
import json
from typing import Any

import click
from rich.console import Console
from rich.table import Table

from v1cli.api.client import V1APIError, V1Client
from v1cli.config.auth import AuthError
from v1cli.config.settings import get_settings, save_settings
from v1cli.config.workflow import STATUS_COLORS, STATUS_ICONS, StoryStatus
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
                    project.name[:50] + ("..." if len(project.name) > 50 else ""),
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
    table.add_column("Number", style="cyan", no_wrap=True)
    table.add_column("Name")
    table.add_column("Default", style="green", no_wrap=True)

    for bookmark in bookmarks:
        # Extract number from OID (e.g., "Epic:1234" -> "E-1234")
        number = ""
        if ":" in bookmark.oid:
            num = bookmark.oid.split(":")[-1]
            number = f"E-{num}"
        is_default = "★" if bookmark.oid == default_oid else ""
        table.add_row(number, bookmark.name, is_default)

    console.print(table)
    console.print(f"\n[dim]Total: {len(bookmarks)} bookmarks[/dim]")


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
    """Bookmark a project by number (E-nnnnn) or OID."""

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
    """Remove a project bookmark by number (E-nnnnn) or OID."""
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
    """Set the default project by name or number (E-xxx)."""

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


# =============================================================================
# Story Listing Commands
# =============================================================================


@cli.command()
@click.option("--all", "-a", "include_done", is_flag=True, help="Include completed stories")
@handle_errors
def mine(include_done: bool) -> None:
    """List stories assigned to me."""

    async def _mine() -> None:
        project_oids = storage.get_bookmarked_project_oids() or None

        async with V1Client() as client:
            stories = await client.get_my_stories(
                project_oids=project_oids,
                include_done=include_done,
            )

            if not stories:
                console.print("[yellow]No stories assigned to you.[/yellow]")
                return

            _print_stories_table(stories, title="My Stories")

    run_async(_mine())


@cli.command()
@click.argument("parent_number")
@click.option("--all", "-a", "include_done", is_flag=True, help="Include completed stories")
@handle_errors
def stories(parent_number: str, include_done: bool) -> None:
    """List stories under a feature (E-nnnnn) or story (S-nnnnn)."""

    async def _stories() -> None:
        async with V1Client() as client:
            # Try as Feature first (E-xxx or Epic:xxx)
            if parent_number.upper().startswith("E-") or (
                ":" in parent_number and parent_number.split(":")[0].lower() == "epic"
            ):
                parent = await client.get_feature_by_number(parent_number)
                if not parent:
                    console.print(f"[red]Feature not found:[/red] {parent_number}")
                    raise SystemExit(1)
                parent_oid = parent.oid
                parent_display = f"{parent.number}: {parent.name}"
            else:
                # Try as Story (S-xxx or Story:xxx)
                parent = await client.get_story_by_number(parent_number)
                if not parent:
                    console.print(f"[red]Story not found:[/red] {parent_number}")
                    raise SystemExit(1)
                parent_oid = parent.oid
                parent_display = f"{parent.number}: {parent.name}"

            story_list = await client.get_stories(parent_oid, include_done=include_done)

            if not story_list:
                console.print(f"[yellow]No stories under {parent_display}[/yellow]")
                return

            _print_stories_table(story_list, title=f"Stories under {parent_display}")

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
@click.option("--project", "-p", "project_name", help="Project name or number")
@click.option("--all", "-a", "include_done", is_flag=True, help="Include closed delivery groups")
@click.option("--output", "-o", "output_file", type=click.Path(), help="Write output to file")
@click.option("--format", "-f", "output_format", type=click.Choice(["table", "csv", "json"]), default="table", help="Output format")
@handle_errors
def roadmap(project_name: str | None, include_done: bool, output_file: str | None, output_format: str) -> None:
    """List delivery groups (roadmap) for a project."""

    async def _roadmap() -> None:
        async with V1Client() as client:
            project_oid = await _resolve_project_oid_async(project_name, client)
            if not project_oid:
                return

            deliveries = await client.get_delivery_groups(project_oid, include_done=include_done)

            if not deliveries:
                console.print("[yellow]No delivery groups found.[/yellow]")
                return

            # Handle file output
            if output_file:
                _write_deliveries_to_file(deliveries, output_file, output_format)
                console.print(f"[green]Wrote {len(deliveries)} delivery groups to {output_file}[/green]")
                return

            table = Table(title="Roadmap (Delivery Groups)")
            table.add_column("Number", style="cyan", no_wrap=True)
            table.add_column("Name")
            table.add_column("Type", style="dim")
            table.add_column("Status")
            table.add_column("Begin", no_wrap=True)
            table.add_column("End", no_wrap=True)
            table.add_column("Progress", justify="right")
            table.add_column("Pts", justify="right")

            for d in deliveries:
                # Format dates (remove time portion if present)
                begin = (d.planned_start or "")[:10] if d.planned_start else "-"
                end = (d.planned_end or "")[:10] if d.planned_end else "-"
                # Format progress as percentage
                progress = f"{int(d.progress * 100)}%" if d.progress is not None else "-"
                # Format estimate
                estimate = str(int(d.estimate)) if d.estimate is not None else "-"

                table.add_row(
                    d.number,
                    d.name[:40] + ("..." if len(d.name) > 40 else ""),
                    d.delivery_type or "-",
                    d.status or "-",
                    begin,
                    end,
                    progress,
                    estimate,
                )

            console.print(table)
            console.print(f"\n[dim]Total: {len(deliveries)} delivery groups[/dim]")

    run_async(_roadmap())


@cli.command()
@click.option("--parent", "-p", "parent_id", help="Parent (Delivery Group or Project) E-nnnnn")
@click.option("--all", "-a", "include_done", is_flag=True, help="Include closed features")
@handle_errors
def features(parent_id: str | None, include_done: bool) -> None:
    """List features under a Delivery Group or Project."""

    async def _features() -> None:
        async with V1Client() as client:
            parent_oid = await _resolve_project_oid_async(parent_id, client)
            if not parent_oid:
                return

            feature_list = await client.get_features(parent_oid, include_done=include_done)

            if not feature_list:
                console.print("[yellow]No features found.[/yellow]")
                return

            table = Table(title="Features")
            table.add_column("Number", style="cyan")
            table.add_column("Name")
            table.add_column("Status")
            table.add_column("Project", style="dim")

            for feature in feature_list:
                table.add_row(
                    feature.number,
                    feature.name[:50] + ("..." if len(feature.name) > 50 else ""),
                    feature.status or "-",
                    feature.scope_name,
                )

            console.print(table)

    run_async(_features())


@cli.group(name="feature")
def feature_group() -> None:
    """Manage features."""
    pass


@feature_group.command(name="create")
@click.argument("name")
@click.option("--parent", "-p", "parent_id", help="Parent (Delivery Group or Project) E-nnnnn")
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
@click.option("--project", "-p", "project_name", help="Project name or number")
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
@handle_errors
def tasks(story_number: str) -> None:
    """List tasks for a story (S-nnnnn or Story:nnnnn)."""

    async def _tasks() -> None:
        async with V1Client() as client:
            s = await client.get_story_by_number(story_number)
            if not s:
                console.print(f"[red]Story not found:[/red] {story_number}")
                raise SystemExit(1)

            task_list = await client.get_tasks(s.oid)

            if not task_list:
                console.print(f"[yellow]No tasks for {story_number}[/yellow]")
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


async def _resolve_project_oid_async(project_identifier: str | None, client: V1Client) -> str | None:
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
        return None

    default_oid = storage.get_default_project_oid()
    if default_oid:
        return default_oid

    console.print("[red]No project specified and no default set.[/red]")
    console.print("Use --project/-p or set a default with 'v1 projects default <number>'")
    return None


def _resolve_project_oid(project_identifier: str | None) -> str | None:
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
        return None

    default_oid = storage.get_default_project_oid()
    if default_oid:
        return default_oid

    console.print("[red]No project specified and no default set.[/red]")
    console.print("Use --project/-p or set a default with 'v1 projects default <number>'")
    return None


def _print_stories_table(stories: list[Any], title: str = "Stories") -> None:
    """Print a formatted table of stories."""
    settings = get_settings()

    table = Table(title=title)
    table.add_column("Number", style="cyan", no_wrap=True)
    table.add_column("Status", no_wrap=True)
    table.add_column("Name")
    table.add_column("Pts", justify="right")
    table.add_column("Project", style="dim")

    for s in stories:
        status_enum = None
        if s.status_oid:
            status_enum = settings.status_mapping.get_status(s.status_oid)

        icon = STATUS_ICONS.get(status_enum, "○") if status_enum else "○"
        color = STATUS_COLORS.get(status_enum, "white") if status_enum else "white"
        status_display = f"[{color}]{icon} {s.status_display}[/{color}]"

        pts = str(int(s.estimate)) if s.estimate else "-"

        table.add_row(
            s.number,
            status_display,
            s.name[:40] + ("..." if len(s.name) > 40 else ""),
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
