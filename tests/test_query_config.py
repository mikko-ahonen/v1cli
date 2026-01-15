"""Tests for query configuration models and utilities."""

import pytest

from v1cli.config.settings import (
    AssetQueryConfig,
    ColumnConfig,
    ProjectBookmark,
    ProjectQueryConfig,
)
from v1cli.config.defaults import (
    DEFAULT_DELIVERY_GROUP_COLUMNS,
    DEFAULT_DELIVERY_GROUP_SELECT,
    DEFAULT_FEATURE_SELECT,
    DEFAULT_STORY_SELECT,
    DEFAULT_TASK_SELECT,
    get_default_delivery_group_config,
    get_default_feature_config,
    get_default_project_query_config,
    get_default_story_config,
    get_default_task_config,
)
from v1cli.display import (
    build_table_from_config,
    format_value,
    get_nested_field,
)


class TestColumnConfig:
    """Tests for ColumnConfig model."""

    def test_create_minimal(self):
        col = ColumnConfig(field="Name")
        assert col.field == "Name"
        assert col.label is None
        assert col.style is None
        assert col.max_width is None
        assert col.format is None
        assert col.justify == "left"

    def test_create_full(self):
        col = ColumnConfig(
            field="Status.Name",
            label="Status",
            style="cyan",
            max_width=20,
            format="date",
            justify="right",
        )
        assert col.field == "Status.Name"
        assert col.label == "Status"
        assert col.style == "cyan"
        assert col.max_width == 20
        assert col.format == "date"
        assert col.justify == "right"

    def test_serialization(self):
        col = ColumnConfig(field="Name", label="Title", style="bold")
        data = col.model_dump()
        assert data["field"] == "Name"
        assert data["label"] == "Title"
        restored = ColumnConfig.model_validate(data)
        assert restored.field == col.field
        assert restored.label == col.label


class TestAssetQueryConfig:
    """Tests for AssetQueryConfig model."""

    def test_create_empty(self):
        config = AssetQueryConfig()
        assert config.select == []
        assert config.filters == []
        assert config.sort == []
        assert config.columns == []
        assert not config.is_configured()

    def test_create_with_fields(self):
        config = AssetQueryConfig(
            select=["Name", "Number", "Status.Name"],
            filters=["Status.Name!='Done'"],
            sort=["-ChangeDateUTC"],
            columns=[ColumnConfig(field="Name", label="Title")],
        )
        assert len(config.select) == 3
        assert len(config.filters) == 1
        assert len(config.sort) == 1
        assert len(config.columns) == 1
        assert config.is_configured()

    def test_is_configured_with_select_only(self):
        config = AssetQueryConfig(select=["Name"])
        assert config.is_configured()

    def test_serialization_roundtrip(self):
        config = AssetQueryConfig(
            select=["Name", "Number"],
            filters=["Status.Name='Active'"],
            sort=["Name"],
            columns=[
                ColumnConfig(field="Name", label="Title"),
                ColumnConfig(field="Number", style="cyan"),
            ],
        )
        data = config.model_dump()
        restored = AssetQueryConfig.model_validate(data)
        assert restored.select == config.select
        assert restored.filters == config.filters
        assert len(restored.columns) == 2


class TestProjectQueryConfig:
    """Tests for ProjectQueryConfig model."""

    def test_create_empty(self):
        config = ProjectQueryConfig()
        assert config.version == 1
        assert config.last_detected is None
        assert not config.delivery_groups.is_configured()
        assert not config.features.is_configured()
        assert not config.stories.is_configured()
        assert not config.tasks.is_configured()
        assert not config.is_configured()

    def test_create_with_one_asset_configured(self):
        config = ProjectQueryConfig(
            stories=AssetQueryConfig(select=["Name", "Number"])
        )
        assert config.stories.is_configured()
        assert not config.features.is_configured()
        assert config.is_configured()

    def test_last_detected_timestamp(self):
        config = ProjectQueryConfig(last_detected="2025-01-15T10:30:00Z")
        assert config.last_detected == "2025-01-15T10:30:00Z"

    def test_serialization_roundtrip(self):
        config = ProjectQueryConfig(
            version=1,
            last_detected="2025-01-15T10:30:00Z",
            stories=AssetQueryConfig(
                select=["Name", "Number"],
                columns=[ColumnConfig(field="Name")],
            ),
        )
        data = config.model_dump()
        restored = ProjectQueryConfig.model_validate(data)
        assert restored.version == 1
        assert restored.last_detected == config.last_detected
        assert restored.stories.select == ["Name", "Number"]


class TestProjectBookmarkWithQueryConfig:
    """Tests for ProjectBookmark with query_config."""

    def test_bookmark_without_config(self):
        bookmark = ProjectBookmark(name="My Project", oid="Epic:1234")
        assert bookmark.query_config is None

    def test_bookmark_with_config(self):
        config = ProjectQueryConfig(
            stories=AssetQueryConfig(select=["Name"])
        )
        bookmark = ProjectBookmark(
            name="My Project",
            oid="Epic:1234",
            query_config=config,
        )
        assert bookmark.query_config is not None
        assert bookmark.query_config.stories.is_configured()

    def test_bookmark_serialization_with_config(self):
        config = ProjectQueryConfig(
            last_detected="2025-01-15T10:30:00Z",
            delivery_groups=AssetQueryConfig(
                select=["Name", "Number"],
                columns=[ColumnConfig(field="Name", label="Title")],
            ),
        )
        bookmark = ProjectBookmark(
            name="My Project",
            oid="Epic:1234",
            query_config=config,
        )
        data = bookmark.model_dump()
        restored = ProjectBookmark.model_validate(data)
        assert restored.query_config is not None
        assert restored.query_config.delivery_groups.select == ["Name", "Number"]


class TestDefaults:
    """Tests for default configuration functions."""

    def test_default_delivery_group_select(self):
        assert "Name" in DEFAULT_DELIVERY_GROUP_SELECT
        assert "Number" in DEFAULT_DELIVERY_GROUP_SELECT
        assert "Status.Name" in DEFAULT_DELIVERY_GROUP_SELECT

    def test_default_delivery_group_columns(self):
        assert len(DEFAULT_DELIVERY_GROUP_COLUMNS) > 0
        fields = [c.field for c in DEFAULT_DELIVERY_GROUP_COLUMNS]
        assert "Number" in fields
        assert "Name" in fields

    def test_default_feature_select(self):
        assert "Name" in DEFAULT_FEATURE_SELECT
        assert "Number" in DEFAULT_FEATURE_SELECT

    def test_default_story_select(self):
        assert "Name" in DEFAULT_STORY_SELECT
        assert "Number" in DEFAULT_STORY_SELECT
        assert "Estimate" in DEFAULT_STORY_SELECT

    def test_default_task_select(self):
        assert "Name" in DEFAULT_TASK_SELECT
        assert "Number" in DEFAULT_TASK_SELECT
        assert "ToDo" in DEFAULT_TASK_SELECT
        assert "Actuals" in DEFAULT_TASK_SELECT

    def test_get_default_delivery_group_config(self):
        config = get_default_delivery_group_config()
        assert config.is_configured()
        assert len(config.select) > 0
        assert len(config.columns) > 0

    def test_get_default_feature_config(self):
        config = get_default_feature_config()
        assert config.is_configured()
        assert "-ChangeDateUTC" in config.sort

    def test_get_default_story_config(self):
        config = get_default_story_config()
        assert config.is_configured()
        assert "Estimate" in config.select

    def test_get_default_task_config(self):
        config = get_default_task_config()
        assert config.is_configured()
        assert "Order" in config.sort

    def test_get_default_project_query_config(self):
        config = get_default_project_query_config()
        assert config.is_configured()
        assert config.delivery_groups.is_configured()
        assert config.features.is_configured()
        assert config.stories.is_configured()
        assert config.tasks.is_configured()

    def test_default_configs_are_independent(self):
        config1 = get_default_story_config()
        config2 = get_default_story_config()
        config1.select.append("CustomField")
        assert "CustomField" not in config2.select


class TestGetNestedField:
    """Tests for get_nested_field function."""

    def test_simple_field(self):
        item = {"Name": "Test Story", "Number": "S-123"}
        assert get_nested_field(item, "Name") == "Test Story"
        assert get_nested_field(item, "Number") == "S-123"

    def test_dotted_field_as_key(self):
        item = {"Status.Name": "In Progress", "Name": "Test"}
        assert get_nested_field(item, "Status.Name") == "In Progress"

    def test_nested_traversal(self):
        item = {"Status": {"Name": "Done", "Order": 5}}
        assert get_nested_field(item, "Status.Name") == "Done"
        assert get_nested_field(item, "Status.Order") == 5

    def test_missing_field(self):
        item = {"Name": "Test"}
        assert get_nested_field(item, "Missing") is None

    def test_missing_nested_field(self):
        item = {"Status": {"Name": "Done"}}
        assert get_nested_field(item, "Status.Missing") is None

    def test_none_intermediate(self):
        item = {"Status": None}
        assert get_nested_field(item, "Status.Name") is None

    def test_deep_nesting(self):
        item = {"A": {"B": {"C": "value"}}}
        assert get_nested_field(item, "A.B.C") == "value"


class TestFormatValue:
    """Tests for format_value function."""

    def test_none_value(self):
        assert format_value(None, None, None) == "-"

    def test_simple_string(self):
        assert format_value("Hello", None, None) == "Hello"

    def test_list_value(self):
        assert format_value(["Alice", "Bob"], None, None) == "Alice, Bob"

    def test_empty_list(self):
        assert format_value([], None, None) == "-"

    def test_date_format(self):
        assert format_value("2025-01-15T10:30:00Z", "date", None) == "2025-01-15"

    def test_date_format_short_value(self):
        assert format_value("2025-01", "date", None) == "2025-01"

    def test_percent_format(self):
        assert format_value(0.75, "percent", None) == "75%"
        assert format_value("0.5", "percent", None) == "50%"

    def test_percent_format_invalid(self):
        assert format_value("not a number", "percent", None) == "-"

    def test_points_format(self):
        assert format_value(5.0, "points", None) == "5"
        assert format_value("3.5", "points", None) == "3"

    def test_points_format_invalid(self):
        assert format_value("invalid", "points", None) == "-"

    def test_hours_format(self):
        assert format_value(2.5, "hours", None) == "2.5h"
        assert format_value("4", "hours", None) == "4.0h"

    def test_hours_format_invalid(self):
        assert format_value("not hours", "hours", None) == "-"

    def test_max_width_truncation(self):
        long_text = "This is a very long text that should be truncated"
        result = format_value(long_text, None, 20)
        assert len(result) == 20
        assert result.endswith("...")

    def test_max_width_no_truncation_needed(self):
        short_text = "Short"
        result = format_value(short_text, None, 20)
        assert result == "Short"


class TestBuildTableFromConfig:
    """Tests for build_table_from_config function."""

    def test_build_simple_table(self):
        items = [
            {"Number": "S-001", "Name": "First Story"},
            {"Number": "S-002", "Name": "Second Story"},
        ]
        config = AssetQueryConfig(
            select=["Number", "Name"],
            columns=[
                ColumnConfig(field="Number", label="ID"),
                ColumnConfig(field="Name", label="Title"),
            ],
        )
        table = build_table_from_config("Stories", items, config)
        assert table.title == "Stories"
        assert len(table.columns) == 2
        assert table.columns[0].header == "ID"
        assert table.columns[1].header == "Title"

    def test_build_table_with_nested_fields(self):
        items = [
            {"Number": "S-001", "Status.Name": "In Progress"},
        ]
        config = AssetQueryConfig(
            select=["Number", "Status.Name"],
            columns=[
                ColumnConfig(field="Number"),
                ColumnConfig(field="Status.Name", label="Status"),
            ],
        )
        table = build_table_from_config("Stories", items, config)
        assert table.columns[1].header == "Status"

    def test_build_table_uses_field_as_label(self):
        items = [{"Name": "Test"}]
        config = AssetQueryConfig(
            select=["Name"],
            columns=[ColumnConfig(field="Name")],
        )
        table = build_table_from_config("Test", items, config)
        assert table.columns[0].header == "Name"

    def test_build_table_no_columns_uses_select(self):
        items = [{"Name": "Test", "Number": "T-001"}]
        config = AssetQueryConfig(select=["Number", "Name"])
        table = build_table_from_config("Test", items, config)
        assert len(table.columns) == 2

    def test_build_table_with_formatting(self):
        items = [
            {"Number": "S-001", "Estimate": 5.0, "Done": 0.75},
        ]
        config = AssetQueryConfig(
            select=["Number", "Estimate", "Done"],
            columns=[
                ColumnConfig(field="Number"),
                ColumnConfig(field="Estimate", format="points"),
                ColumnConfig(field="Done", format="percent"),
            ],
        )
        table = build_table_from_config("Stories", items, config)
        assert len(table.columns) == 3

    def test_build_table_empty_items(self):
        config = AssetQueryConfig(
            select=["Name"],
            columns=[ColumnConfig(field="Name")],
        )
        table = build_table_from_config("Empty", [], config)
        assert table.title == "Empty"
        assert len(table.columns) == 1
        assert table.row_count == 0
