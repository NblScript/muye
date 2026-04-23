from __future__ import annotations

from typing import Any, Protocol

from modules.infra.sqlite_store import SqliteStore


class DecisionContextProvider(Protocol):
    def build_context(
        self,
        *,
        request_id: str,
        pest_detections: list[dict[str, Any]],
        weather_data: dict[str, Any],
        field_context: dict[str, Any],
    ) -> dict[str, Any]:
        """Build optional structured context for the decision engine."""


class SqliteDecisionContextProvider:
    """Optional SQLite-backed context enricher for later decision upgrades."""

    def __init__(
        self,
        sqlite_store: SqliteStore,
        *,
        weather_history_limit: int = 5,
        pesticide_limit: int = 5,
    ) -> None:
        self.sqlite_store = sqlite_store
        self.weather_history_limit = weather_history_limit
        self.pesticide_limit = pesticide_limit

    def build_context(
        self,
        *,
        request_id: str,
        pest_detections: list[dict[str, Any]],
        weather_data: dict[str, Any],
        field_context: dict[str, Any],
    ) -> dict[str, Any]:
        del request_id, weather_data

        field_id = str(field_context.get("field_id") or "").strip()
        if not field_id:
            return {}

        crop_cycle = field_context.get("crop_cycle") or {}
        crop_name = crop_cycle.get("crop_name")
        pest_types = [
            pest_type
            for pest_type in {
                str(item.get("pest_type") or "").strip()
                for item in pest_detections
            }
            if pest_type
        ]
        return self.sqlite_store.fetch_decision_support_context(
            field_id=field_id,
            crop_name=str(crop_name).strip() if crop_name else None,
            pest_types=pest_types,
            weather_history_limit=self.weather_history_limit,
            pesticide_limit=self.pesticide_limit,
        )
