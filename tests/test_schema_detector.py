"""Tests for schema detection functionality."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from v1cli.config.schema_detector import (
    filter_valid_columns,
    filter_valid_fields,
    get_available_attributes,
    detect_asset_config,
    auto_detect_project_config,
)
from v1cli.config.settings import ColumnConfig


class TestFilterValidFields:
    """Tests for filter_valid_fields function."""

    def test_all_fields_available(self):
        desired = ["Name", "Number", "Status"]
        available = {"Name", "Number", "Status", "Description"}
        result = filter_valid_fields(desired, available)
        assert result == ["Name", "Number", "Status"]

    def test_some_fields_missing(self):
        desired = ["Name", "Number", "CustomField"]
        available = {"Name", "Number", "Description"}
        result = filter_valid_fields(desired, available)
        assert result == ["Name", "Number"]
        assert "CustomField" not in result

    def test_dotted_field_base_available(self):
        desired = ["Name", "Status.Name", "Scope.Name"]
        available = {"Name", "Status", "Scope"}
        result = filter_valid_fields(desired, available)
        assert "Status.Name" in result
        assert "Scope.Name" in result

    def test_dotted_field_base_missing(self):
        desired = ["Name", "Status.Name", "Missing.Field"]
        available = {"Name", "Status"}
        result = filter_valid_fields(desired, available)
        assert "Status.Name" in result
        assert "Missing.Field" not in result

    def test_empty_desired(self):
        result = filter_valid_fields([], {"Name", "Number"})
        assert result == []

    def test_empty_available(self):
        result = filter_valid_fields(["Name", "Number"], set())
        assert result == []


class TestFilterValidColumns:
    """Tests for filter_valid_columns function."""

    def test_all_columns_valid(self):
        columns = [
            ColumnConfig(field="Name", label="Title"),
            ColumnConfig(field="Number", style="cyan"),
        ]
        available = {"Name", "Number", "Status"}
        result = filter_valid_columns(columns, available)
        assert len(result) == 2
        assert result[0].field == "Name"
        assert result[0].label == "Title"

    def test_some_columns_invalid(self):
        columns = [
            ColumnConfig(field="Name"),
            ColumnConfig(field="CustomField"),
            ColumnConfig(field="Number"),
        ]
        available = {"Name", "Number"}
        result = filter_valid_columns(columns, available)
        assert len(result) == 2
        fields = [c.field for c in result]
        assert "Name" in fields
        assert "Number" in fields
        assert "CustomField" not in fields

    def test_dotted_field_columns(self):
        columns = [
            ColumnConfig(field="Status.Name", label="Status"),
            ColumnConfig(field="Missing.Field", label="Missing"),
        ]
        available = {"Status"}
        result = filter_valid_columns(columns, available)
        assert len(result) == 1
        assert result[0].field == "Status.Name"

    def test_returns_copies(self):
        original = ColumnConfig(field="Name", label="Title")
        columns = [original]
        available = {"Name"}
        result = filter_valid_columns(columns, available)
        assert result[0] is not original
        assert result[0].field == original.field


class TestGetAvailableAttributes:
    """Tests for get_available_attributes function."""

    @pytest.mark.asyncio
    async def test_returns_attribute_names(self):
        mock_client = MagicMock()
        mock_client.get_asset_attributes = AsyncMock(
            return_value=[
                {"name": "Name"},
                {"name": "Number"},
                {"name": "Status"},
            ]
        )
        result = await get_available_attributes(mock_client, "Story")
        assert result == {"Name", "Number", "Status"}
        mock_client.get_asset_attributes.assert_called_once_with("Story")

    @pytest.mark.asyncio
    async def test_returns_empty_on_error(self):
        mock_client = MagicMock()
        mock_client.get_asset_attributes = AsyncMock(side_effect=Exception("API error"))
        result = await get_available_attributes(mock_client, "Story")
        assert result == set()


class TestDetectAssetConfig:
    """Tests for detect_asset_config function."""

    @pytest.mark.asyncio
    async def test_filters_to_available_fields(self):
        mock_client = MagicMock()
        mock_client.get_asset_attributes = AsyncMock(
            return_value=[
                {"name": "Name"},
                {"name": "Number"},
                {"name": "Status"},
            ]
        )

        default_select = ["Name", "Number", "Status.Name", "CustomField"]
        default_filters = ["Status.Name!='Done'"]
        default_columns = [
            ColumnConfig(field="Name"),
            ColumnConfig(field="Number"),
            ColumnConfig(field="CustomField"),
        ]
        default_sort = ["Name", "CustomField"]

        result = await detect_asset_config(
            mock_client,
            "Story",
            default_select,
            default_filters,
            default_columns,
            default_sort,
        )

        assert "Name" in result.select
        assert "Number" in result.select
        assert "Status.Name" in result.select
        assert "CustomField" not in result.select

        assert len(result.columns) == 2
        column_fields = [c.field for c in result.columns]
        assert "CustomField" not in column_fields

        assert "Name" in result.sort
        assert "CustomField" not in result.sort

    @pytest.mark.asyncio
    async def test_returns_defaults_on_error(self):
        mock_client = MagicMock()
        mock_client.get_asset_attributes = AsyncMock(side_effect=Exception("API error"))

        default_select = ["Name", "Number"]
        default_filters = ["Status.Name!='Done'"]
        default_columns = [ColumnConfig(field="Name")]
        default_sort = ["Name"]

        result = await detect_asset_config(
            mock_client,
            "Story",
            default_select,
            default_filters,
            default_columns,
            default_sort,
        )

        assert result.select == default_select
        assert result.filters == default_filters
        assert result.sort == default_sort


class TestAutoDetectProjectConfig:
    """Tests for auto_detect_project_config function."""

    @pytest.mark.asyncio
    async def test_creates_config_for_all_asset_types(self):
        mock_client = MagicMock()
        mock_client.get_asset_attributes = AsyncMock(
            return_value=[
                {"name": "Name"},
                {"name": "Number"},
                {"name": "Status"},
                {"name": "PlannedStart"},
                {"name": "PlannedEnd"},
                {"name": "Scope"},
                {"name": "Super"},
                {"name": "Owners"},
                {"name": "Estimate"},
                {"name": "Parent"},
                {"name": "ToDo"},
                {"name": "Actuals"},
                {"name": "Order"},
                {"name": "Category"},
                {"name": "ChangeDateUTC"},
            ]
        )

        result = await auto_detect_project_config(mock_client)

        assert result.last_detected is not None
        assert result.delivery_groups.is_configured()
        assert result.features.is_configured()
        assert result.stories.is_configured()
        assert result.tasks.is_configured()

    @pytest.mark.asyncio
    async def test_sets_last_detected_timestamp(self):
        mock_client = MagicMock()
        mock_client.get_asset_attributes = AsyncMock(return_value=[{"name": "Name"}])

        result = await auto_detect_project_config(mock_client)

        assert result.last_detected is not None
        assert "T" in result.last_detected  # ISO format
