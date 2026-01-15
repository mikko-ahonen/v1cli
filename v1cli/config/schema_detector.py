"""Schema detection for VersionOne instances.

Uses the V1 meta API to discover which fields are available,
then generates query configurations that only use valid fields.
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from v1cli.config.defaults import (
    DEFAULT_DELIVERY_GROUP_COLUMNS,
    DEFAULT_DELIVERY_GROUP_FILTERS,
    DEFAULT_DELIVERY_GROUP_SELECT,
    DEFAULT_FEATURE_COLUMNS,
    DEFAULT_FEATURE_FILTERS,
    DEFAULT_FEATURE_SELECT,
    DEFAULT_STORY_COLUMNS,
    DEFAULT_STORY_FILTERS,
    DEFAULT_STORY_SELECT,
    DEFAULT_TASK_COLUMNS,
    DEFAULT_TASK_FILTERS,
    DEFAULT_TASK_SELECT,
)
from v1cli.config.settings import AssetQueryConfig, ColumnConfig, ProjectQueryConfig

if TYPE_CHECKING:
    from v1cli.api.client import V1Client


async def get_available_attributes(client: "V1Client", asset_type: str) -> set[str]:
    """Get the set of available attribute names for an asset type."""
    try:
        attributes = await client.get_asset_attributes(asset_type)
        return {attr["name"] for attr in attributes}
    except Exception:
        # On error, return empty set (will use defaults)
        return set()


def filter_valid_fields(
    desired_fields: list[str],
    available_attrs: set[str],
) -> list[str]:
    """Filter a list of fields to only those that exist.

    For relation fields like "Status.Name", checks that the base attribute exists.
    """
    valid_fields = []
    for field in desired_fields:
        # Extract base attribute (e.g., "Status" from "Status.Name")
        base_field = field.split(".")[0]
        if base_field in available_attrs:
            valid_fields.append(field)
    return valid_fields


def filter_valid_columns(
    desired_columns: list[ColumnConfig],
    available_attrs: set[str],
) -> list[ColumnConfig]:
    """Filter columns to only those with valid fields."""
    valid_columns = []
    for col in desired_columns:
        base_field = col.field.split(".")[0]
        if base_field in available_attrs:
            valid_columns.append(col.model_copy())
    return valid_columns


async def detect_asset_config(
    client: "V1Client",
    asset_type: str,
    default_select: list[str],
    default_filters: list[str],
    default_columns: list[ColumnConfig],
    default_sort: list[str],
) -> AssetQueryConfig:
    """Detect available fields and create an optimized query config for an asset type."""
    available = await get_available_attributes(client, asset_type)

    if not available:
        # Couldn't get schema, return defaults (may fail on query)
        return AssetQueryConfig(
            select=default_select.copy(),
            filters=default_filters.copy(),
            sort=default_sort.copy(),
            columns=[c.model_copy() for c in default_columns],
        )

    # Filter to only available fields
    valid_select = filter_valid_fields(default_select, available)
    valid_columns = filter_valid_columns(default_columns, available)
    valid_sort = filter_valid_fields(default_sort, available)

    return AssetQueryConfig(
        select=valid_select,
        filters=default_filters.copy(),  # Filters are kept as-is
        sort=valid_sort,
        columns=valid_columns,
    )


async def auto_detect_project_config(client: "V1Client") -> ProjectQueryConfig:
    """Detect available fields and create optimized query config for a project.

    Queries the V1 meta API to discover which fields exist, then generates
    configurations that only include valid fields.
    """
    config = ProjectQueryConfig(
        last_detected=datetime.now(timezone.utc).isoformat(),
    )

    # Detect for Epic (used for delivery groups and features)
    config.delivery_groups = await detect_asset_config(
        client,
        "Epic",
        DEFAULT_DELIVERY_GROUP_SELECT,
        DEFAULT_DELIVERY_GROUP_FILTERS,
        DEFAULT_DELIVERY_GROUP_COLUMNS,
        ["PlannedStart", "Name"],
    )

    config.features = await detect_asset_config(
        client,
        "Epic",
        DEFAULT_FEATURE_SELECT,
        DEFAULT_FEATURE_FILTERS,
        DEFAULT_FEATURE_COLUMNS,
        ["-ChangeDateUTC"],
    )

    # Detect for Story
    config.stories = await detect_asset_config(
        client,
        "Story",
        DEFAULT_STORY_SELECT,
        DEFAULT_STORY_FILTERS,
        DEFAULT_STORY_COLUMNS,
        ["-ChangeDateUTC"],
    )

    # Detect for Task
    config.tasks = await detect_asset_config(
        client,
        "Task",
        DEFAULT_TASK_SELECT,
        DEFAULT_TASK_FILTERS,
        DEFAULT_TASK_COLUMNS,
        ["Order"],
    )

    return config
