"""Tests for FieldContextResolver."""
from __future__ import annotations

import os
from unittest import mock

import pytest

from modules.drone.field_context_resolver import FieldContextResolver


class TestFieldContextResolver:
    """Tests for FieldContextResolver class."""

    @pytest.fixture
    def mock_store(self):
        """Create a mock SqliteStore."""
        return mock.Mock()

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger."""
        return mock.Mock()

    @pytest.fixture
    def basic_drone_config(self):
        """Create a basic drone_config."""
        return {
            "execution": {"backend": "simulated"},
            "px4": {},
            "field": {},
        }

    def test_resolve_returns_px4_demo_field_when_configured(self, mock_store, mock_logger, basic_drone_config):
        """Test that PX4 demo field is returned when configured."""
        basic_drone_config["execution"]["backend"] = "px4"
        basic_drone_config["px4"] = {
            "prefer_demo_field": True,
            "demo_field": {
                "field_id": "px4-demo",
                "name": "PX4 Demo Field",
                "geofence": [
                    {"latitude": 47.0, "longitude": 8.0},
                    {"latitude": 47.01, "longitude": 8.0},
                    {"latitude": 47.01, "longitude": 8.01},
                ],
            },
        }
        mock_store.count_fields.return_value = 0
        mock_store.field_exists.return_value = False

        resolver = FieldContextResolver(mock_store, basic_drone_config, mock_logger)
        result = resolver.resolve()

        assert result["field_id"] == "px4-demo"
        assert result["name"] == "PX4 Demo Field"
        mock_store.upsert_field.assert_called_once()

    def test_resolve_px4_demo_raises_on_invalid_geofence(self, mock_store, mock_logger, basic_drone_config):
        """Test that PX4 demo field raises error when geofence is invalid."""
        basic_drone_config["execution"]["backend"] = "px4"
        basic_drone_config["px4"] = {
            "prefer_demo_field": True,
            "demo_field": {
                "field_id": "px4-demo",
                "geofence": [{"latitude": 47.0, "longitude": 8.0}],
            },
        }

        resolver = FieldContextResolver(mock_store, basic_drone_config, mock_logger)
        with pytest.raises(RuntimeError, match="缺少有效 geofence"):
            resolver.resolve()

    def test_resolve_with_preferred_field_id(self, mock_store, mock_logger, basic_drone_config):
        """Test that preferred field_id is returned when it exists."""
        mock_store.count_fields.return_value = 1
        mock_store.fetch_field_context.return_value = {
            "field_id": "test-field",
            "name": "Test Field",
        }
        mock_store.get_field_source.return_value = "user_import"

        resolver = FieldContextResolver(mock_store, basic_drone_config, mock_logger)
        result = resolver.resolve(field_id="test-field")

        assert result["field_id"] == "test-field"
        mock_store.fetch_field_context.assert_called_once_with(field_id="test-field")

    def test_resolve_raises_when_preferred_field_not_found(self, mock_store, mock_logger, basic_drone_config):
        """Test that resolver raises when preferred field_id doesn't exist."""
        mock_store.count_fields.return_value = 1
        mock_store.fetch_field_context.return_value = None

        resolver = FieldContextResolver(mock_store, basic_drone_config, mock_logger)
        with pytest.raises(RuntimeError, match="指定地块不存在"):
            resolver.resolve(field_id="nonexistent")

    def test_resolve_uses_env_field_id(self, mock_store, mock_logger, basic_drone_config):
        """Test that MUYE_ACTIVE_FIELD_ID env var is used."""
        mock_store.count_fields.return_value = 1
        mock_store.fetch_field_context.return_value = {
            "field_id": "env-field",
            "name": "Env Field",
        }
        mock_store.get_field_source.return_value = "user_import"

        with mock.patch.dict(os.environ, {"MUYE_ACTIVE_FIELD_ID": "env-field"}):
            resolver = FieldContextResolver(mock_store, basic_drone_config, mock_logger)
            result = resolver.resolve()

        assert result["field_id"] == "env-field"

    def test_resolve_uses_config_field_id_as_fallback(self, mock_store, mock_logger, basic_drone_config):
        """Test that config field_id is used as fallback."""
        basic_drone_config["field"] = {"field_id": "config-field"}
        mock_store.count_fields.return_value = 1
        mock_store.fetch_field_context.return_value = {
            "field_id": "config-field",
            "name": "Config Field",
        }
        mock_store.get_field_source.return_value = "user_import"

        resolver = FieldContextResolver(mock_store, basic_drone_config, mock_logger)
        result = resolver.resolve()

        assert result["field_id"] == "config-field"

    def test_resolve_finds_single_non_fallback_field(self, mock_store, mock_logger, basic_drone_config):
        """Test that resolver finds a single non-fallback field."""
        mock_store.count_fields.return_value = 1
        mock_store.count_non_fallback_fields.return_value = 1
        mock_store.get_first_non_fallback_field_id.return_value = "real-field"
        mock_store.fetch_field_context.return_value = {
            "field_id": "real-field",
            "name": "Real Field",
        }

        resolver = FieldContextResolver(mock_store, basic_drone_config, mock_logger)
        result = resolver.resolve()

        assert result["field_id"] == "real-field"

    def test_resolve_raises_on_multiple_non_fallback_fields(self, mock_store, mock_logger, basic_drone_config):
        """Test that resolver raises when there are multiple non-fallback fields."""
        mock_store.count_fields.return_value = 5
        mock_store.count_non_fallback_fields.return_value = 3

        resolver = FieldContextResolver(mock_store, basic_drone_config, mock_logger)
        with pytest.raises(RuntimeError, match="检测到多个地块"):
            resolver.resolve()

    def test_resolve_falls_back_to_config_field_context(self, mock_store, mock_logger, basic_drone_config):
        """Test that resolver falls back to config field context when no fields exist."""
        basic_drone_config["field"] = {
            "field_id": "fallback-field",
            "name": "Fallback Field",
            "location": {"city": "Test City"},
        }
        mock_store.count_fields.return_value = 0
        mock_store.count_non_fallback_fields.return_value = 0
        mock_store.fetch_field_context.return_value = None
        mock_store.field_exists.return_value = False

        resolver = FieldContextResolver(mock_store, basic_drone_config, mock_logger)
        result = resolver.resolve()

        assert result["field_id"] == "fallback-field"
        assert result["name"] == "Fallback Field"
        mock_store.upsert_field.assert_called_once()

    def test_seed_if_needed_seeds_field(self, mock_store, mock_logger, basic_drone_config):
        """Test that seed_if_needed seeds a field when it doesn't exist."""
        mock_store.field_exists.return_value = False
        mock_store.count_fields.return_value = 0

        resolver = FieldContextResolver(mock_store, basic_drone_config, mock_logger)
        resolver.seed_if_needed(
            {
                "field_id": "new-field",
                "name": "New Field",
                "location": {"city": "Test City"},
            },
            source="test",
            notes="Test notes",
        )

        mock_store.upsert_field.assert_called_once()
        call_args = mock_store.upsert_field.call_args[0][0]
        assert call_args["field_id"] == "new-field"
        assert call_args["source"] == "test"

    def test_seed_if_needed_skips_existing_field(self, mock_store, mock_logger, basic_drone_config):
        """Test that seed_if_needed skips when field already exists."""
        mock_store.field_exists.return_value = True

        resolver = FieldContextResolver(mock_store, basic_drone_config, mock_logger)
        resolver.seed_if_needed(
            {"field_id": "existing-field", "name": "Existing"},
            source="test",
            notes="Test",
        )

        mock_store.upsert_field.assert_not_called()

    def test_seed_if_needed_skip_if_any_field_exists(self, mock_store, mock_logger, basic_drone_config):
        """Test that seed_if_needed respects skip_if_any_field_exists."""
        mock_store.field_exists.return_value = False
        mock_store.count_fields.return_value = 5

        resolver = FieldContextResolver(mock_store, basic_drone_config, mock_logger)
        resolver.seed_if_needed(
            {"field_id": "new-field", "name": "New"},
            source="test",
            notes="Test",
            skip_if_any_field_exists=True,
        )

        mock_store.upsert_field.assert_not_called()

    def test_seed_if_needed_handles_exception(self, mock_store, mock_logger, basic_drone_config):
        """Test that seed_if_needed handles exceptions gracefully."""
        mock_store.field_exists.return_value = False
        mock_store.count_fields.return_value = 0
        mock_store.upsert_field.side_effect = Exception("DB error")

        resolver = FieldContextResolver(mock_store, basic_drone_config, mock_logger)
        # Should not raise
        resolver.seed_if_needed(
            {"field_id": "new-field", "name": "New"},
            source="test",
            notes="Test",
        )

        mock_logger.warning.assert_called_once()

    def test_should_ignore_config_fallback_field_returns_false_for_non_fallback(self, mock_store, mock_logger, basic_drone_config):
        """Test that fallback field is not ignored when source is not fallback."""
        mock_store.get_field_source.return_value = "user_import"
        mock_store.field_has_non_fallback_source.return_value = True

        resolver = FieldContextResolver(mock_store, basic_drone_config, mock_logger)
        result = resolver._should_ignore_config_fallback_field("some-field")

        assert result is False

    def test_should_ignore_config_fallback_field_returns_true_for_fallback_with_real_fields(self, mock_store, mock_logger, basic_drone_config):
        """Test that fallback field is ignored when real fields exist."""
        mock_store.get_field_source.return_value = "drone_config_fallback"
        mock_store.field_has_non_fallback_source.return_value = True

        resolver = FieldContextResolver(mock_store, basic_drone_config, mock_logger)
        result = resolver._should_ignore_config_fallback_field("fallback-field")

        assert result is True
