"""地块上下文解析器 - 从 MuyeApplication 拆分"""
from __future__ import annotations

import logging
import os
from typing import Any

from modules.infra.sqlite_store import SqliteStore


class FieldContextResolver:
    """
    负责解析运行时地块上下文。
    职责：从 SqliteStore 加载地块信息，合并 drone_config 默认配置，必要时 seed 默认地块。
    """

    def __init__(
        self,
        sqlite_store: SqliteStore,
        drone_config: dict[str, Any],
        logger: logging.Logger | None = None,
    ) -> None:
        self.store = sqlite_store
        self.drone_config = drone_config
        self.logger = logger or logging.getLogger(__name__)

    def resolve(self, field_id: str | None = None) -> dict[str, Any]:
        """解析地块上下文，field_id 为 None 时自动选择"""
        if self._should_use_px4_demo_field():
            return self._build_px4_demo_field_context()

        configured_field_id = str(self.drone_config.get("field", {}).get("field_id") or "").strip() or None
        env_field_id = os.getenv("MUYE_ACTIVE_FIELD_ID")
        preferred_field_id = field_id or env_field_id or configured_field_id
        field_count = self.store.count_fields()

        if preferred_field_id:
            field_context = self.store.fetch_field_context(field_id=preferred_field_id)
            if field_context:
                if env_field_id or field_id or not self._should_ignore_config_fallback_field(preferred_field_id):
                    return field_context
            elif env_field_id or field_id or field_count > 0:
                raise RuntimeError(f"指定地块不存在: {preferred_field_id}")

        real_field_context = self._resolve_non_fallback_field_context()
        if real_field_context:
            return real_field_context

        field_context = self.store.fetch_field_context()
        if field_context:
            return field_context

        return self._build_config_field_context()

    def seed_if_needed(
        self,
        field_context: dict[str, Any],
        *,
        source: str,
        notes: str,
        skip_if_any_field_exists: bool = False,
    ) -> None:
        """如地块不存在则写入数据库"""
        field_id = str(field_context.get("field_id") or "").strip()
        if not field_id:
            return

        if self.store.field_exists(field_id):
            return

        if skip_if_any_field_exists:
            if self.store.count_fields() > 0:
                return

        location = field_context.get("location", {})
        try:
            self.store.upsert_field(
                {
                    "field_id": field_id,
                    "field_code": field_id.upper(),
                    "field_name": field_context.get("name") or field_id,
                    "province": location.get("province"),
                    "city": location.get("city"),
                    "county": location.get("county"),
                    "latitude": location.get("latitude"),
                    "longitude": location.get("longitude"),
                    "area_mu": field_context.get("area_mu"),
                    "geofence": field_context.get("geofence"),
                    "soil_type": field_context.get("soil_type"),
                    "source": source,
                    "notes": notes,
                }
            )
        except Exception as exc:
            self.logger.warning(
                "配置地块回写 SQLite 失败: field_id=%s, error=%s",
                field_id,
                exc,
            )

    def _should_use_px4_demo_field(self) -> bool:
        execution = self.drone_config.get("execution", {})
        px4_config = self.drone_config.get("px4", {})
        return execution.get("backend") == "px4" and bool(px4_config.get("prefer_demo_field", False))

    def _build_px4_demo_field_context(self) -> dict[str, Any]:
        px4_config = self.drone_config.get("px4", {})
        demo_field = px4_config.get("demo_field") or {}
        location = demo_field.get("location", {})
        geofence = demo_field.get("geofence", [])
        if len(geofence) < 3:
            raise RuntimeError("PX4 SITL 演示地块缺少有效 geofence 配置")

        field_context = {
            "field_id": demo_field.get("field_id", "px4-sitl-demo"),
            "name": demo_field.get("name", "PX4 SITL 演示地块"),
            "weather_location": demo_field.get("weather_location") or location.get("city") or "Zurich",
            "area_mu": demo_field.get("area_mu", 1.0),
            "soil_type": demo_field.get("soil_type", "demo"),
            "geofence": geofence,
            "explicit_route": demo_field.get("explicit_route"),
            "presentation_profile": demo_field.get("presentation_profile"),
            "location": {
                "province": location.get("province"),
                "city": location.get("city"),
                "county": location.get("county"),
                "latitude": location.get("latitude"),
                "longitude": location.get("longitude"),
            },
            "crop_cycle": demo_field.get("crop_cycle"),
        }
        self.seed_if_needed(
            field_context,
            source="px4_sitl_demo",
            notes="Auto-seeded from config/drone_config.json PX4 SITL demo field.",
        )
        return field_context

    def _build_config_field_context(self) -> dict[str, Any]:
        field = self.drone_config.get("field", {})
        location = field.get("location", {})
        field_context = {
            "field_id": field.get("field_id"),
            "name": field.get("name", "默认示范田"),
            "weather_location": field.get("weather_location") or location.get("city"),
            "area_mu": field.get("area_mu"),
            "soil_type": field.get("soil_type"),
            "geofence": field.get("geofence", []),
            "location": {
                "province": location.get("province"),
                "city": location.get("city"),
                "county": location.get("county"),
                "latitude": location.get("latitude"),
                "longitude": location.get("longitude"),
            },
            "crop_cycle": None,
        }
        self.seed_if_needed(
            field_context,
            source="drone_config_fallback",
            notes="Auto-seeded from config/drone_config.json fallback context.",
            skip_if_any_field_exists=True,
        )
        return field_context

    def _should_ignore_config_fallback_field(self, field_id: str) -> bool:
        source = self.store.get_field_source(field_id)
        if source != "drone_config_fallback":
            return False
        return self.store.field_has_non_fallback_source()

    def _resolve_non_fallback_field_context(self) -> dict[str, Any] | None:
        non_fallback_count = self.store.count_non_fallback_fields()
        if non_fallback_count == 0:
            return None
        if non_fallback_count > 1:
            raise RuntimeError("检测到多个地块，请显式设置 MUYE_ACTIVE_FIELD_ID")

        first_field_id = self.store.get_first_non_fallback_field_id()
        if first_field_id is None:
            return None
        return self.store.fetch_field_context(field_id=first_field_id)
