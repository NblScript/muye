from __future__ import annotations

import json
from typing import Any


class FieldMixin:
    def upsert_field(self, record: dict[str, Any]) -> None:
        geofence = record.get("geofence")
        if isinstance(geofence, (list, dict)):
            geofence = json.dumps(geofence, ensure_ascii=False)

        area_mu = self._to_float(record.get("area_mu"))
        area_hectare = self._to_float(record.get("area_hectare"))
        if area_hectare is None and area_mu is not None:
            area_hectare = round(area_mu * 0.0666667, 4)

        with self._lock:
            self._connection.execute(
                """
                INSERT INTO fields (
                  field_id, field_code, field_name, owner_user_id, province, city, county,
                  township, village, latitude, longitude, area_mu, area_hectare,
                  geofence, soil_type, irrigation_type, source, notes, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(field_id) DO UPDATE SET
                  field_code = excluded.field_code,
                  field_name = excluded.field_name,
                  owner_user_id = excluded.owner_user_id,
                  province = excluded.province,
                  city = excluded.city,
                  county = excluded.county,
                  township = excluded.township,
                  village = excluded.village,
                  latitude = excluded.latitude,
                  longitude = excluded.longitude,
                  area_mu = excluded.area_mu,
                  area_hectare = excluded.area_hectare,
                  geofence = excluded.geofence,
                  soil_type = excluded.soil_type,
                  irrigation_type = excluded.irrigation_type,
                  source = excluded.source,
                  notes = excluded.notes,
                  updated_at = excluded.updated_at
                """,
                (
                    str(record["field_id"]),
                    record.get("field_code"),
                    record["field_name"],
                    record.get("owner_user_id"),
                    record.get("province"),
                    record.get("city"),
                    record.get("county"),
                    record.get("township"),
                    record.get("village"),
                    self._to_float(record.get("latitude")),
                    self._to_float(record.get("longitude")),
                    area_mu,
                    area_hectare,
                    geofence,
                    record.get("soil_type"),
                    record.get("irrigation_type"),
                    record.get("source"),
                    record.get("notes"),
                    record.get("created_at"),
                    record.get("updated_at"),
                ),
            )
            self._connection.commit()

    def fetch_field_context(self, field_id: str | None = None) -> dict[str, Any] | None:
        if field_id:
            field_row = self.fetch_one(
                """
                SELECT *
                FROM fields
                WHERE field_id = ?
                """,
                (field_id,),
            )
        else:
            field_count_row = self.fetch_one("SELECT COUNT(*) AS total FROM fields")
            field_count = int(field_count_row["total"]) if field_count_row else 0
            if field_count == 0:
                return None
            if field_count > 1:
                raise RuntimeError("检测到多个地块，请显式设置 MUYE_ACTIVE_FIELD_ID")
            field_row = self.fetch_one(
                """
                SELECT *
                FROM fields
                ORDER BY city ASC, field_name ASC
                LIMIT 1
                """
            )

        if field_row is None:
            return None

        latitude = self._to_float(field_row.get("latitude"))
        longitude = self._to_float(field_row.get("longitude"))
        area_mu = self._to_float(field_row.get("area_mu"))
        geofence = self._parse_json_value(field_row.get("geofence"), default=[])
        if not geofence and latitude is not None and longitude is not None:
            geofence = self._derive_square_geofence(latitude, longitude, area_mu or 30.0)

        crop_cycle = self.fetch_one(
            """
            SELECT
              field_crop_cycles.id,
              field_crop_cycles.field_id,
              field_crop_cycles.crop_code,
              field_crop_cycles.year,
              field_crop_cycles.season,
              field_crop_cycles.planting_date,
              field_crop_cycles.harvest_date,
              field_crop_cycles.area_mu,
              field_crop_cycles.status,
              crop_catalog.crop_name,
              crop_catalog.category,
              crop_catalog.growth_cycle_days,
              crop_catalog.water_demand_coefficient
            FROM field_crop_cycles
            LEFT JOIN crop_catalog
              ON crop_catalog.crop_code = field_crop_cycles.crop_code
            WHERE field_crop_cycles.field_id = ?
            ORDER BY
              CASE field_crop_cycles.status
                WHEN 'growing' THEN 0
                WHEN 'planted' THEN 1
                WHEN 'planned' THEN 2
                ELSE 3
              END,
              COALESCE(field_crop_cycles.harvest_date, field_crop_cycles.planting_date) DESC
            LIMIT 1
            """,
            (str(field_row["field_id"]),),
        )

        weather_location = (
            (f"{longitude},{latitude}" if longitude is not None and latitude is not None else None)
            or field_row.get("city")
            or field_row.get("county")
        )

        return {
            "field_id": str(field_row["field_id"]),
            "name": field_row.get("field_name"),
            "weather_location": weather_location,
            "area_mu": area_mu,
            "soil_type": field_row.get("soil_type"),
            "geofence": geofence,
            "location": {
                "province": field_row.get("province"),
                "city": field_row.get("city"),
                "county": field_row.get("county"),
                "latitude": latitude,
                "longitude": longitude,
            },
            "crop_cycle": crop_cycle,
        }

    def find_nearest_field_id(
        self,
        *,
        latitude: float | None,
        longitude: float | None,
        city: str | None = None,
        county: str | None = None,
    ) -> str | None:
        if latitude is None or longitude is None:
            return None

        filters = ["latitude IS NOT NULL", "longitude IS NOT NULL"]
        params: list[Any] = []
        if county:
            filters.append("county = ?")
            params.append(county)
        elif city:
            filters.append("city = ?")
            params.append(city)

        rows = self.fetch_all(
            f"""
            SELECT field_id, latitude, longitude
            FROM fields
            WHERE {' AND '.join(filters)}
            """,
            tuple(params),
        )
        if not rows and city and county:
            rows = self.fetch_all(
                """
                SELECT field_id, latitude, longitude
                FROM fields
                WHERE latitude IS NOT NULL AND longitude IS NOT NULL AND city = ?
                """,
                (city,),
            )
        if not rows:
            rows = self.fetch_all(
                """
                SELECT field_id, latitude, longitude
                FROM fields
                WHERE latitude IS NOT NULL AND longitude IS NOT NULL
                """
            )
        if not rows:
            return None

        nearest = min(
            rows,
            key=lambda row: self._distance_sq(
                latitude,
                longitude,
                self._to_float(row.get("latitude")) or latitude,
                self._to_float(row.get("longitude")) or longitude,
            ),
        )
        return str(nearest["field_id"])

    def count_fields(self) -> int:
        row = self.fetch_one("SELECT COUNT(*) AS total FROM fields")
        return int(row["total"]) if row else 0

    def field_exists(self, field_id: str) -> bool:
        row = self.fetch_one("SELECT 1 FROM fields WHERE field_id = ?", (field_id,))
        return row is not None

    def get_field_source(self, field_id: str) -> str | None:
        row = self.fetch_one("SELECT source FROM fields WHERE field_id = ?", (field_id,))
        return row["source"] if row else None

    def count_non_fallback_fields(self) -> int:
        row = self.fetch_one(
            "SELECT COUNT(*) AS total FROM fields WHERE source IS NULL OR source != 'drone_config_fallback'"
        )
        return int(row["total"]) if row else 0

    def get_first_non_fallback_field_id(self) -> str | None:
        row = self.fetch_one(
            "SELECT field_id FROM fields WHERE source IS NULL OR source != 'drone_config_fallback' ORDER BY city ASC, field_name ASC LIMIT 1"
        )
        return row["field_id"] if row else None

    def field_has_non_fallback_source(self) -> bool:
        row = self.fetch_one(
            "SELECT 1 FROM fields WHERE source IS NULL OR source != 'drone_config_fallback' LIMIT 1"
        )
        return row is not None
