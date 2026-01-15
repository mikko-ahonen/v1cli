"""Display utilities for rendering tables from configuration."""

from typing import Any

from rich.table import Table

from v1cli.config.settings import AssetQueryConfig, ColumnConfig


def get_nested_field(item: dict[str, Any], field: str) -> Any:
    """Get a potentially nested field value from a dict.

    Handles fields like "Status.Name" by traversing the dict structure.
    Also handles V1 API response patterns like {"_oid": "...", "Name": "..."}.
    """
    if "." not in field:
        return item.get(field)

    # Try the dotted key first (V1 API often returns "Status.Name" as a key)
    if field in item:
        return item[field]

    # Otherwise traverse the structure
    parts = field.split(".")
    value = item
    for part in parts:
        if value is None:
            return None
        if isinstance(value, dict):
            value = value.get(part)
        else:
            return None
    return value


def format_value(value: Any, format_type: str | None, max_width: int | None) -> str:
    """Format a value for display based on format type.

    Args:
        value: The raw value
        format_type: One of: "date", "percent", "points", "hours", or None
        max_width: Maximum width for text truncation
    """
    if value is None:
        return "-"

    # Handle list values (e.g., Owners.Name)
    if isinstance(value, list):
        if not value:
            return "-"
        value = ", ".join(str(v) for v in value)

    # Apply format type
    if format_type == "date":
        # Truncate datetime to just date portion
        value = str(value)[:10] if value else "-"
    elif format_type == "percent":
        try:
            value = f"{int(float(value) * 100)}%"
        except (ValueError, TypeError):
            value = "-"
    elif format_type == "points":
        try:
            value = str(int(float(value)))
        except (ValueError, TypeError):
            value = "-"
    elif format_type == "hours":
        try:
            value = f"{float(value):.1f}h"
        except (ValueError, TypeError):
            value = "-"
    else:
        value = str(value)

    # Apply max width truncation
    if max_width and len(value) > max_width:
        value = value[: max_width - 3] + "..."

    return value


def build_table_from_config(
    title: str,
    items: list[dict[str, Any]],
    config: AssetQueryConfig,
) -> Table:
    """Build a Rich Table from asset query configuration.

    Args:
        title: Table title
        items: List of item dictionaries from API
        config: Asset query configuration with column definitions

    Returns:
        A Rich Table ready for display
    """
    table = Table(title=title)

    columns = config.columns
    if not columns:
        # If no column config, create basic columns from select fields
        columns = [ColumnConfig(field=f) for f in config.select]

    # Add columns to table
    for col in columns:
        table.add_column(
            col.label or col.field,
            style=col.style,
            no_wrap=col.max_width is None,
            justify=col.justify,  # type: ignore
        )

    # Add rows
    for item in items:
        row = []
        for col in columns:
            value = get_nested_field(item, col.field)
            formatted = format_value(value, col.format, col.max_width)
            row.append(formatted)
        table.add_row(*row)

    return table


def build_table_from_models(
    title: str,
    items: list[Any],
    config: AssetQueryConfig,
) -> Table:
    """Build a Rich Table from Pydantic models using column configuration.

    This version works with Pydantic model instances rather than raw dicts.

    Args:
        title: Table title
        items: List of Pydantic model instances
        config: Asset query configuration with column definitions

    Returns:
        A Rich Table ready for display
    """
    table = Table(title=title)

    columns = config.columns
    if not columns:
        columns = [ColumnConfig(field=f) for f in config.select]

    # Add columns to table
    for col in columns:
        table.add_column(
            col.label or col.field,
            style=col.style,
            no_wrap=col.max_width is None,
            justify=col.justify,  # type: ignore
        )

    # Add rows
    for item in items:
        row = []
        for col in columns:
            # Convert dotted field to attribute access
            # e.g., "Status.Name" -> check for status_name or status attribute
            field = col.field
            value = None

            # Try direct attribute (converting dots to underscores)
            attr_name = field.replace(".", "_").lower()
            if hasattr(item, attr_name):
                value = getattr(item, attr_name)
            else:
                # Try common field name mappings
                field_mappings = {
                    "Status.Name": ["status", "status_display"],
                    "Scope.Name": ["scope_name"],
                    "Super.Name": ["parent_name"],
                    "Owners.Name": ["owners"],
                    "Parent.Number": ["parent_number"],
                }
                for mapped in field_mappings.get(field, []):
                    if hasattr(item, mapped):
                        value = getattr(item, mapped)
                        break

                # Last resort: try the field name as-is (lowercase)
                if value is None:
                    simple_name = field.split(".")[-1].lower()
                    if hasattr(item, simple_name):
                        value = getattr(item, simple_name)

            formatted = format_value(value, col.format, col.max_width)
            row.append(formatted)
        table.add_row(*row)

    return table
