"""Default query configurations for asset types.

These are "safe" defaults that should work on most V1 instances.
Fields that may not exist on all instances (like Type, PercentDone, Estimate on Epic)
are excluded from defaults.
"""

from v1cli.config.settings import AssetQueryConfig, ColumnConfig, ProjectQueryConfig


# Delivery Groups (Epics with Category='Delivery Group')
DEFAULT_DELIVERY_GROUP_SELECT = [
    "Name",
    "Number",
    "Status.Name",
    "PlannedStart",
    "PlannedEnd",
]

DEFAULT_DELIVERY_GROUP_FILTERS = [
    "Category.Name='Delivery Group'",
]

DEFAULT_DELIVERY_GROUP_COLUMNS = [
    ColumnConfig(field="Number", label="Number", style="cyan"),
    ColumnConfig(field="Name", label="Name", max_width=40),
    ColumnConfig(field="Status.Name", label="Status"),
    ColumnConfig(field="PlannedStart", label="Start", format="date"),
    ColumnConfig(field="PlannedEnd", label="End", format="date"),
]


# Features (Epics with Category != 'Delivery Group')
DEFAULT_FEATURE_SELECT = [
    "Number",
    "Name",
    "Description",
    "Status.Name",
    "Status",
    "Scope.Name",
    "Scope",
    "Super.Name",
]

DEFAULT_FEATURE_FILTERS = [
    "Category.Name!='Delivery Group'",
]

DEFAULT_FEATURE_COLUMNS = [
    ColumnConfig(field="Number", label="Number", style="cyan"),
    ColumnConfig(field="Name", label="Name", max_width=50),
    ColumnConfig(field="Status.Name", label="Status"),
    ColumnConfig(field="Scope.Name", label="Project", style="dim"),
]


# Stories
DEFAULT_STORY_SELECT = [
    "Number",
    "Name",
    "Description",
    "Status.Name",
    "Status",
    "Scope.Name",
    "Scope",
    "Owners.Name",
    "Owners",
    "Super.Name",
    "Super",
    "Estimate",
]

DEFAULT_STORY_FILTERS: list[str] = []

DEFAULT_STORY_COLUMNS = [
    ColumnConfig(field="Number", label="Number", style="cyan"),
    ColumnConfig(field="Status.Name", label="Status"),
    ColumnConfig(field="Name", label="Name", max_width=40),
    ColumnConfig(field="Estimate", label="Pts", justify="right", format="points"),
    ColumnConfig(field="Scope.Name", label="Project", style="dim"),
]


# Tasks
DEFAULT_TASK_SELECT = [
    "Number",
    "Name",
    "Parent",
    "Parent.Number",
    "Status.Name",
    "Status",
    "Owners.Name",
    "ToDo",
    "Actuals",
]

DEFAULT_TASK_FILTERS: list[str] = []

DEFAULT_TASK_COLUMNS = [
    ColumnConfig(field="Number", label="Number", style="cyan"),
    ColumnConfig(field="Name", label="Name", max_width=40),
    ColumnConfig(field="Status.Name", label="Status"),
    ColumnConfig(field="Actuals", label="Done", justify="right", format="hours"),
    ColumnConfig(field="ToDo", label="Todo", justify="right", format="hours"),
]


def get_default_delivery_group_config() -> AssetQueryConfig:
    """Get default configuration for delivery groups."""
    return AssetQueryConfig(
        select=DEFAULT_DELIVERY_GROUP_SELECT.copy(),
        filters=DEFAULT_DELIVERY_GROUP_FILTERS.copy(),
        sort=["PlannedStart", "Name"],
        columns=[c.model_copy() for c in DEFAULT_DELIVERY_GROUP_COLUMNS],
    )


def get_default_feature_config() -> AssetQueryConfig:
    """Get default configuration for features."""
    return AssetQueryConfig(
        select=DEFAULT_FEATURE_SELECT.copy(),
        filters=DEFAULT_FEATURE_FILTERS.copy(),
        sort=["-ChangeDateUTC"],
        columns=[c.model_copy() for c in DEFAULT_FEATURE_COLUMNS],
    )


def get_default_story_config() -> AssetQueryConfig:
    """Get default configuration for stories."""
    return AssetQueryConfig(
        select=DEFAULT_STORY_SELECT.copy(),
        filters=DEFAULT_STORY_FILTERS.copy(),
        sort=["-ChangeDateUTC"],
        columns=[c.model_copy() for c in DEFAULT_STORY_COLUMNS],
    )


def get_default_task_config() -> AssetQueryConfig:
    """Get default configuration for tasks."""
    return AssetQueryConfig(
        select=DEFAULT_TASK_SELECT.copy(),
        filters=DEFAULT_TASK_FILTERS.copy(),
        sort=["Order"],
        columns=[c.model_copy() for c in DEFAULT_TASK_COLUMNS],
    )


def get_default_project_query_config() -> ProjectQueryConfig:
    """Get a ProjectQueryConfig with all defaults."""
    return ProjectQueryConfig(
        delivery_groups=get_default_delivery_group_config(),
        features=get_default_feature_config(),
        stories=get_default_story_config(),
        tasks=get_default_task_config(),
    )
