from __future__ import annotations

import json
from typing import Any


class CatalogMixin:
    def upsert_crop_catalog_record(self, record: dict[str, Any]) -> None:
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO crop_catalog (
                  crop_code, crop_name, category, variety, growth_cycle_days,
                  water_demand_coefficient, typical_planting_month, typical_harvest_month,
                  source, notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(crop_code) DO UPDATE SET
                  crop_name = excluded.crop_name,
                  category = excluded.category,
                  variety = excluded.variety,
                  growth_cycle_days = excluded.growth_cycle_days,
                  water_demand_coefficient = excluded.water_demand_coefficient,
                  typical_planting_month = excluded.typical_planting_month,
                  typical_harvest_month = excluded.typical_harvest_month,
                  source = excluded.source,
                  notes = excluded.notes
                """,
                (
                    str(record["crop_code"]),
                    record["crop_name"],
                    record.get("category"),
                    record.get("variety"),
                    self._to_int(record.get("growth_cycle_days")),
                    self._to_float(record.get("water_demand_coefficient")),
                    record.get("typical_planting_month"),
                    record.get("typical_harvest_month"),
                    record.get("source"),
                    record.get("notes"),
                ),
            )
            self._connection.commit()

    def upsert_pesticide_catalog_record(self, record: dict[str, Any]) -> None:
        target_crops = record.get("target_crops")
        if isinstance(target_crops, (list, dict)):
            target_crops = json.dumps(target_crops, ensure_ascii=False)

        target_pests = record.get("target_pests")
        if isinstance(target_pests, (list, dict)):
            target_pests = json.dumps(target_pests, ensure_ascii=False)

        raw_payload = record.get("raw_payload", {})
        if isinstance(raw_payload, str):
            raw_payload_text = raw_payload
        else:
            raw_payload_text = json.dumps(raw_payload, ensure_ascii=False)

        with self._lock:
            self._connection.execute(
                """
                INSERT INTO pesticide_catalog (
                  pesticide_id, registration_no, product_name, active_ingredient,
                  formulation, toxicity, manufacturer, target_crops, target_pests,
                  dilution_guidance, source, raw_payload
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(pesticide_id) DO UPDATE SET
                  registration_no = excluded.registration_no,
                  product_name = excluded.product_name,
                  active_ingredient = excluded.active_ingredient,
                  formulation = excluded.formulation,
                  toxicity = excluded.toxicity,
                  manufacturer = excluded.manufacturer,
                  target_crops = excluded.target_crops,
                  target_pests = excluded.target_pests,
                  dilution_guidance = excluded.dilution_guidance,
                  source = excluded.source,
                  raw_payload = excluded.raw_payload
                """,
                (
                    str(record["pesticide_id"]),
                    record.get("registration_no"),
                    record["product_name"],
                    record.get("active_ingredient"),
                    record.get("formulation"),
                    record.get("toxicity"),
                    record.get("manufacturer"),
                    target_crops,
                    target_pests,
                    record.get("dilution_guidance"),
                    record.get("source"),
                    raw_payload_text,
                ),
            )
            self._connection.commit()

    def resolve_pesticide_id_by_name(self, product_name: str) -> str | None:
        row = self.fetch_one(
            "SELECT pesticide_id FROM pesticide_catalog WHERE product_name = ? ORDER BY pesticide_id ASC LIMIT 1",
            (product_name,),
        )
        return row["pesticide_id"] if row else None

    def upsert_data_source(self, record: dict[str, Any]) -> None:
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO data_sources (
                  source_id, source_name, publisher, region_scope, source_type,
                  source_url, access_level, retrieval_date, license, notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id) DO UPDATE SET
                  source_name = excluded.source_name,
                  publisher = excluded.publisher,
                  region_scope = excluded.region_scope,
                  source_type = excluded.source_type,
                  source_url = excluded.source_url,
                  access_level = excluded.access_level,
                  retrieval_date = excluded.retrieval_date,
                  license = excluded.license,
                  notes = excluded.notes
                """,
                (
                    record["source_id"],
                    record["source_name"],
                    record.get("publisher"),
                    record.get("region_scope"),
                    record.get("source_type"),
                    record["source_url"],
                    record.get("access_level"),
                    record.get("retrieval_date"),
                    record.get("license"),
                    record.get("notes"),
                ),
            )
            self._connection.commit()

    def upsert_agri_statistical_indicator(self, record: dict[str, Any]) -> None:
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO agri_statistical_indicators (
                  region_level, region_name, province, city, county, year, period,
                  indicator_code, indicator_name, value, unit, source_id,
                  source_excerpt, raw_payload
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(
                  region_level, region_name, province, city, county, year, period, indicator_code
                ) DO UPDATE SET
                  indicator_name = excluded.indicator_name,
                  value = excluded.value,
                  unit = excluded.unit,
                  source_id = excluded.source_id,
                  source_excerpt = excluded.source_excerpt,
                  raw_payload = excluded.raw_payload
                """,
                (
                    record["region_level"],
                    record["region_name"],
                    record.get("province"),
                    record.get("city"),
                    record.get("county"),
                    int(record["year"]),
                    record["period"],
                    record["indicator_code"],
                    record["indicator_name"],
                    float(record["value"]),
                    record.get("unit"),
                    record.get("source_id"),
                    record.get("source_excerpt"),
                    json.dumps(record.get("raw_payload", {}), ensure_ascii=False),
                ),
            )
            self._connection.commit()
