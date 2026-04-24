from __future__ import annotations

import json
from typing import Any


class AgriDataMixin:
    def upsert_field_crop_cycle(self, record: dict[str, Any]) -> None:
        existing = self.fetch_one(
            """
            SELECT id
            FROM field_crop_cycles
            WHERE field_id = ? AND crop_code = ? AND planting_date = ?
            """,
            (
                str(record["field_id"]),
                str(record["crop_code"]),
                record.get("planting_date"),
            ),
        )
        params = (
            str(record["field_id"]),
            str(record["crop_code"]),
            self._to_int(record.get("year")),
            record.get("season"),
            record.get("planting_date"),
            record.get("harvest_date"),
            self._to_float(record.get("area_mu")),
            self._to_float(record.get("expected_yield_kg")),
            self._to_float(record.get("actual_yield_kg")),
            record.get("status"),
            record.get("source"),
            record.get("notes"),
        )
        with self._lock:
            if existing is None:
                self._connection.execute(
                    """
                    INSERT INTO field_crop_cycles (
                      field_id, crop_code, year, season, planting_date, harvest_date,
                      area_mu, expected_yield_kg, actual_yield_kg, status, source, notes
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    params,
                )
            else:
                self._connection.execute(
                    """
                    UPDATE field_crop_cycles
                    SET year = ?, season = ?, harvest_date = ?, area_mu = ?,
                        expected_yield_kg = ?, actual_yield_kg = ?, status = ?,
                        source = ?, notes = ?
                    WHERE id = ?
                    """,
                    (
                        self._to_int(record.get("year")),
                        record.get("season"),
                        record.get("harvest_date"),
                        self._to_float(record.get("area_mu")),
                        self._to_float(record.get("expected_yield_kg")),
                        self._to_float(record.get("actual_yield_kg")),
                        record.get("status"),
                        record.get("source"),
                        record.get("notes"),
                        int(existing["id"]),
                    ),
                )
            self._connection.commit()

    def upsert_soil_record(self, record: dict[str, Any]) -> None:
        existing = self.fetch_one(
            """
            SELECT id
            FROM soil_records
            WHERE field_id = ? AND sample_date = ? AND depth_cm = ?
            """,
            (
                str(record["field_id"]),
                record.get("sample_date"),
                self._to_int(record.get("depth_cm")),
            ),
        )
        params = (
            str(record["field_id"]),
            record.get("sample_date"),
            self._to_int(record.get("depth_cm")),
            self._to_float(record.get("ph")),
            self._to_float(record.get("organic_matter_gkg")),
            self._to_float(record.get("alkali_hydrolyzable_nitrogen_mgkg")),
            self._to_float(record.get("available_phosphorus_mgkg")),
            self._to_float(record.get("available_potassium_mgkg")),
            self._to_float(record.get("moisture_percent")),
            self._to_float(record.get("salinity_gkg")),
            record.get("texture"),
            record.get("source"),
            json.dumps(record.get("raw_payload", {}), ensure_ascii=False),
        )
        with self._lock:
            if existing is None:
                self._connection.execute(
                    """
                    INSERT INTO soil_records (
                      field_id, sample_date, depth_cm, ph, organic_matter_gkg,
                      alkali_hydrolyzable_nitrogen_mgkg, available_phosphorus_mgkg,
                      available_potassium_mgkg, moisture_percent, salinity_gkg,
                      texture, source, raw_payload
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    params,
                )
            else:
                self._connection.execute(
                    """
                    UPDATE soil_records
                    SET ph = ?, organic_matter_gkg = ?, alkali_hydrolyzable_nitrogen_mgkg = ?,
                        available_phosphorus_mgkg = ?, available_potassium_mgkg = ?,
                        moisture_percent = ?, salinity_gkg = ?, texture = ?,
                        source = ?, raw_payload = ?
                    WHERE id = ?
                    """,
                    (
                        self._to_float(record.get("ph")),
                        self._to_float(record.get("organic_matter_gkg")),
                        self._to_float(record.get("alkali_hydrolyzable_nitrogen_mgkg")),
                        self._to_float(record.get("available_phosphorus_mgkg")),
                        self._to_float(record.get("available_potassium_mgkg")),
                        self._to_float(record.get("moisture_percent")),
                        self._to_float(record.get("salinity_gkg")),
                        record.get("texture"),
                        record.get("source"),
                        json.dumps(record.get("raw_payload", {}), ensure_ascii=False),
                        int(existing["id"]),
                    ),
                )
            self._connection.commit()

    def upsert_weather_station(self, record: dict[str, Any]) -> None:
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO weather_stations (
                  station_code, station_name, province, city, county,
                  latitude, longitude, elevation_m, source_id, notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(station_code) DO UPDATE SET
                  station_name = excluded.station_name,
                  province = excluded.province,
                  city = excluded.city,
                  county = excluded.county,
                  latitude = excluded.latitude,
                  longitude = excluded.longitude,
                  elevation_m = excluded.elevation_m,
                  source_id = excluded.source_id,
                  notes = excluded.notes
                """,
                (
                    record["station_code"],
                    record["station_name"],
                    record.get("province"),
                    record.get("city"),
                    record.get("county"),
                    record.get("latitude"),
                    record.get("longitude"),
                    record.get("elevation_m"),
                    record.get("source_id"),
                    record.get("notes"),
                ),
            )
            self._connection.commit()

    def upsert_weather_history_daily(self, record: dict[str, Any]) -> None:
        field_id = record.get("field_id")
        if field_id is None:
            existing = self.fetch_one(
                """
                SELECT id
                FROM weather_history_daily
                WHERE field_id IS NULL
                  AND station_code = ?
                  AND observation_date = ?
                """,
                (
                    record.get("station_code"),
                    record["observation_date"],
                ),
            )
        else:
            existing = self.fetch_one(
                """
                SELECT id
                FROM weather_history_daily
                WHERE field_id = ?
                  AND station_code = ?
                  AND observation_date = ?
                """,
                (
                    str(field_id),
                    record.get("station_code"),
                    record["observation_date"],
                ),
            )
        params = (
            str(field_id) if field_id is not None else None,
            record.get("station_code"),
            record.get("station_name"),
            record["observation_date"],
            record.get("weather_summary"),
            record.get("temperature_avg_c"),
            record.get("temperature_min_c"),
            record.get("temperature_max_c"),
            record.get("humidity_avg_percent"),
            record.get("precipitation_mm"),
            record.get("wind_speed_avg_mps"),
            record.get("wind_direction"),
            record.get("sunshine_hours"),
            record.get("source"),
            json.dumps(record.get("raw_payload", {}), ensure_ascii=False),
        )
        with self._lock:
            if existing is None:
                self._connection.execute(
                    """
                    INSERT INTO weather_history_daily (
                      field_id, station_code, station_name, observation_date, weather_summary,
                      temperature_avg_c, temperature_min_c, temperature_max_c,
                      humidity_avg_percent, precipitation_mm, wind_speed_avg_mps,
                      wind_direction, sunshine_hours, source, raw_payload
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    params,
                )
            else:
                self._connection.execute(
                    """
                    UPDATE weather_history_daily
                    SET field_id = ?, station_name = ?, weather_summary = ?, temperature_avg_c = ?,
                        temperature_min_c = ?, temperature_max_c = ?, humidity_avg_percent = ?,
                        precipitation_mm = ?, wind_speed_avg_mps = ?, wind_direction = ?,
                        sunshine_hours = ?, source = ?, raw_payload = ?
                    WHERE id = ?
                    """,
                    (
                        record.get("field_id"),
                        record.get("station_name"),
                        record.get("weather_summary"),
                        record.get("temperature_avg_c"),
                        record.get("temperature_min_c"),
                        record.get("temperature_max_c"),
                        record.get("humidity_avg_percent"),
                        record.get("precipitation_mm"),
                        record.get("wind_speed_avg_mps"),
                        record.get("wind_direction"),
                        record.get("sunshine_hours"),
                        record.get("source"),
                        json.dumps(record.get("raw_payload", {}), ensure_ascii=False),
                        int(existing["id"]),
                    ),
                )
            self._connection.commit()

    def upsert_spray_record(self, record: dict[str, Any]) -> None:
        request_id = record.get("request_id")
        drone_task_id = record.get("drone_task_id")
        if request_id:
            self._ensure_task(str(request_id))

        if request_id:
            existing = self.fetch_one(
                """
                SELECT id
                FROM spray_records
                WHERE request_id = ?
                """,
                (str(request_id),),
            )
        elif drone_task_id:
            existing = self.fetch_one(
                """
                SELECT id
                FROM spray_records
                WHERE drone_task_id = ?
                """,
                (str(drone_task_id),),
            )
        else:
            existing = self.fetch_one(
                """
                SELECT id
                FROM spray_records
                WHERE field_id = ? AND spray_date = ?
                """,
                (
                    str(record["field_id"]),
                    record["spray_date"],
                ),
            )

        weather_snapshot = record.get("weather_snapshot")
        if isinstance(weather_snapshot, (dict, list)):
            weather_snapshot = json.dumps(weather_snapshot, ensure_ascii=False)

        params = (
            str(request_id) if request_id else None,
            str(record["field_id"]),
            self._to_int(record.get("crop_cycle_id")),
            str(drone_task_id) if drone_task_id else None,
            record.get("pesticide_id"),
            record["spray_date"],
            record.get("operator_name"),
            self._to_float(record.get("spray_area_mu")),
            self._to_float(record.get("dosage_per_mu")),
            self._to_float(record.get("total_dosage")),
            record.get("dilution_ratio"),
            self._to_float(record.get("spray_rate_lpm")),
            self._to_float(record.get("flight_height_m")),
            self._to_float(record.get("flight_speed_mps")),
            weather_snapshot,
            record.get("result_status"),
            record.get("source"),
            record.get("notes"),
        )
        with self._lock:
            if existing is None:
                self._connection.execute(
                    """
                    INSERT INTO spray_records (
                      request_id, field_id, crop_cycle_id, drone_task_id, pesticide_id,
                      spray_date, operator_name, spray_area_mu, dosage_per_mu,
                      total_dosage, dilution_ratio, spray_rate_lpm, flight_height_m,
                      flight_speed_mps, weather_snapshot, result_status, source, notes
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    params,
                )
            else:
                self._connection.execute(
                    """
                    UPDATE spray_records
                    SET request_id = ?, field_id = ?, crop_cycle_id = ?, drone_task_id = ?,
                        pesticide_id = ?, spray_date = ?, operator_name = ?, spray_area_mu = ?,
                        dosage_per_mu = ?, total_dosage = ?, dilution_ratio = ?,
                        spray_rate_lpm = ?, flight_height_m = ?, flight_speed_mps = ?,
                        weather_snapshot = ?, result_status = ?, source = ?, notes = ?
                    WHERE id = ?
                    """,
                    (*params, int(existing["id"])),
                )
            self._connection.commit()

    def fetch_decision_support_context(
        self,
        *,
        field_id: str,
        crop_name: str | None = None,
        pest_types: list[str] | None = None,
        weather_history_limit: int = 5,
        pesticide_limit: int = 5,
    ) -> dict[str, Any]:
        field_row = self.fetch_one(
            """
            SELECT field_id, field_name, province, city, county, area_mu, soil_type, irrigation_type
            FROM fields
            WHERE field_id = ?
            """,
            (field_id,),
        )
        if field_row is None:
            return {}

        soil_row = self.fetch_one(
            """
            SELECT sample_date, depth_cm, ph, organic_matter_gkg, alkali_hydrolyzable_nitrogen_mgkg,
                   available_phosphorus_mgkg, available_potassium_mgkg, moisture_percent,
                   salinity_gkg, texture
            FROM soil_records
            WHERE field_id = ?
            ORDER BY COALESCE(sample_date, '') DESC, id DESC
            LIMIT 1
            """,
            (field_id,),
        )
        weather_rows = self.fetch_all(
            """
            SELECT observation_date, weather_summary, temperature_avg_c, temperature_min_c,
                   temperature_max_c, humidity_avg_percent, precipitation_mm,
                   wind_speed_avg_mps, wind_direction, sunshine_hours
            FROM weather_history_daily
            WHERE field_id = ?
            ORDER BY observation_date DESC, id DESC
            LIMIT ?
            """,
            (field_id, max(1, int(weather_history_limit))),
        )

        pesticide_rows: list[dict[str, Any]] = []
        normalized_pest_types = [item for item in (pest_types or []) if item]
        if crop_name or normalized_pest_types:
            filters: list[str] = []
            params: list[Any] = []
            if crop_name:
                filters.append("LOWER(COALESCE(target_crops, '')) LIKE ?")
                params.append(f"%{crop_name.lower()}%")
            if normalized_pest_types:
                pest_filters = []
                for pest_type in normalized_pest_types:
                    pest_filters.append("LOWER(COALESCE(target_pests, '')) LIKE ?")
                    params.append(f"%{pest_type.lower()}%")
                filters.append(f"({' OR '.join(pest_filters)})")
            pesticide_rows = self.fetch_all(
                f"""
                SELECT pesticide_id, product_name, active_ingredient, formulation, toxicity,
                       manufacturer, target_crops, target_pests, dilution_guidance
                FROM pesticide_catalog
                WHERE {' AND '.join(filters)}
                ORDER BY product_name ASC
                LIMIT ?
                """,
                (*params, max(1, int(pesticide_limit))),
            )

        return {
            "source": "sqlite",
            "field_profile": {
                "field_id": str(field_row["field_id"]),
                "field_name": field_row.get("field_name"),
                "province": field_row.get("province"),
                "city": field_row.get("city"),
                "county": field_row.get("county"),
                "area_mu": self._to_float(field_row.get("area_mu")),
                "soil_type": field_row.get("soil_type"),
                "irrigation_type": field_row.get("irrigation_type"),
                "crop_name": crop_name,
            },
            "latest_soil_record": soil_row or {},
            "recent_weather_history": weather_rows,
            "candidate_pesticides": [
                {
                    **row,
                    "target_crops": self._parse_json_value(
                        row.get("target_crops"),
                        default=row.get("target_crops"),
                    ),
                    "target_pests": self._parse_json_value(
                        row.get("target_pests"),
                        default=row.get("target_pests"),
                    ),
                    "raw_match_keywords": {
                        "crop_name": crop_name,
                        "pest_types": normalized_pest_types,
                    },
                }
                for row in pesticide_rows
            ],
        }
