from __future__ import annotations

import json
import sqlite3

from modules.sqlite_store import SqliteStore
from scripts.generate_henan_field_crop_seed_csv import generate_seed_csvs
from scripts.import_henan_field_crop_seed_csv import import_henan_field_crop_seed_csv
from scripts.import_henan_reference_data import import_henan_reference_data
from scripts.import_henan_weather_history_csv import import_henan_weather_history_csv


def test_sqlite_store_migrates_legacy_database_to_v1_1(tmp_path) -> None:
    db_path = tmp_path / "legacy.db"
    connection = sqlite3.connect(db_path)
    try:
        connection.executescript(
            """
            CREATE TABLE tasks (
              request_id TEXT PRIMARY KEY,
              image_path TEXT,
              start_time DATETIME,
              end_time DATETIME,
              status TEXT
            );

            CREATE TABLE detections (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              request_id TEXT NOT NULL,
              label TEXT,
              confidence REAL,
              bbox TEXT,
              FOREIGN KEY (request_id) REFERENCES tasks(request_id)
            );

            CREATE TABLE weather_snapshots (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              request_id TEXT NOT NULL,
              timestamp DATETIME,
              weather_data TEXT,
              FOREIGN KEY (request_id) REFERENCES tasks(request_id)
            );

            CREATE TABLE decisions (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              request_id TEXT NOT NULL,
              timestamp DATETIME,
              decision_text TEXT,
              FOREIGN KEY (request_id) REFERENCES tasks(request_id)
            );
            """
        )
        connection.execute(
            """
            INSERT INTO tasks (request_id, image_path, start_time, end_time, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("req-legacy", "/tmp/legacy.jpg", "2026-04-14T00:00:00+00:00", None, "broken-status"),
        )
        connection.execute(
            """
            INSERT INTO detections (request_id, label, confidence, bbox)
            VALUES (?, ?, ?, ?)
            """,
            ("req-legacy", "aphid", 0.95, '{"x1":1,"y1":2,"x2":3,"y2":4}'),
        )
        connection.commit()
    finally:
        connection.close()

    store = SqliteStore(db_path)
    try:
        task = store.fetch_one(
            "SELECT request_id, image_path, status FROM tasks WHERE request_id = ?",
            ("req-legacy",),
        )
        detections = store.fetch_all(
            "SELECT request_id, label FROM detections WHERE request_id = ?",
            ("req-legacy",),
        )
        task_table_sql = store.fetch_one(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'tasks'"
        )
        detection_indexes = {
            item["name"]
            for item in store.fetch_all("PRAGMA index_list('detections')")
        }
        weather_indexes = {
            item["name"]
            for item in store.fetch_all("PRAGMA index_list('weather_snapshots')")
        }
        decision_indexes = {
            item["name"]
            for item in store.fetch_all("PRAGMA index_list('decisions')")
        }
    finally:
        store.close()

    assert task is not None
    assert task["request_id"] == "req-legacy"
    assert task["image_path"] == "/tmp/legacy.jpg"
    assert task["status"] == "error"

    assert len(detections) == 1
    assert detections[0]["label"] == "aphid"

    assert task_table_sql is not None
    assert "CHECK" in task_table_sql["sql"]
    assert "queued" in task_table_sql["sql"]
    assert "error" in task_table_sql["sql"]

    assert "idx_detections_request_id" in detection_indexes
    assert "idx_weather_snapshots_request_id" in weather_indexes
    assert "idx_decisions_request_id" in decision_indexes


def test_sqlite_store_fetch_task_views_supports_structured_history_queries(tmp_path) -> None:
    db_path = tmp_path / "muye.db"
    store = SqliteStore(db_path)
    try:
        store.mark_task_queued("req-a", "/tmp/a.jpg")
        store.mark_task_started("req-a", "/tmp/a.jpg")
        store.replace_detections(
            "req-a",
            [
                {
                    "pest_type": "aphid",
                    "confidence": 0.91,
                    "position": {"x1": 1, "y1": 2, "x2": 3, "y2": 4},
                }
            ],
        )
        store.add_weather_snapshot(
            "req-a",
            {
                "temperature": 26,
                "humidity": 61,
                "summary": "多云",
                "wind_direction": "东南风",
                "wind_scale_text": "2",
                "wind_speed": 3.2,
            },
        )
        store.add_decision(
            "req-a",
            {
                "用药": {"农药名称": "吡虫啉"},
                "农事建议": ["优先处理受灾最重区域"],
            },
        )
        store.add_drone_mission_update(
            "req-a",
            task_id="vd-req-a",
            status="completed",
            message="虚拟无人机任务完成",
            progress=100,
            current_waypoint_index=1,
            instruction={"飞行路径": [[121.1, 31.1], [121.2, 31.2]]},
            medication={"农药名称": "吡虫啉"},
        )
        store.mark_task_finished("req-a", "completed")

        store.mark_task_queued("req-b", "/tmp/b.jpg")
        store.mark_task_started("req-b", "/tmp/b.jpg")
        store.replace_detections(
            "req-b",
            [
                {
                    "pest_type": "whitefly",
                    "confidence": 0.88,
                    "position": {"x1": 5, "y1": 6, "x2": 7, "y2": 8},
                }
            ],
        )
        store.mark_task_finished("req-b", "error")

        completed_tasks = store.fetch_task_views(status="completed", limit=10)
        pest_search_tasks = store.fetch_task_views(search="aphid", limit=10)
        image_search_tasks = store.fetch_task_views(search="b.jpg", limit=10)
    finally:
        store.close()

    assert len(completed_tasks) == 1
    assert completed_tasks[0]["request_id"] == "req-a"
    assert completed_tasks[0]["status"] == "completed"
    assert completed_tasks[0]["current_stage"] == "pipeline"
    assert completed_tasks[0]["weather"]["summary"] == "多云"
    assert completed_tasks[0]["decision"]["用药"]["农药名称"] == "吡虫啉"
    assert completed_tasks[0]["detections"][0]["pest_type"] == "aphid"
    assert completed_tasks[0]["drone"]["status"] == "completed"
    assert completed_tasks[0]["drone"]["task_id"] == "vd-req-a"
    assert completed_tasks[0]["drone"]["message"] == "虚拟无人机任务完成"
    assert json.dumps(completed_tasks[0]["detections"][0]["position"], ensure_ascii=False) == '{"x1": 1, "y1": 2, "x2": 3, "y2": 4}'

    assert [task["request_id"] for task in pest_search_tasks] == ["req-a"]
    assert [task["request_id"] for task in image_search_tasks] == ["req-b"]


def test_sqlite_store_creates_agriculture_data_schema_scaffold(tmp_path) -> None:
    db_path = tmp_path / "muye.db"
    store = SqliteStore(db_path)
    try:
        table_names = {
            item["name"]
            for item in store.fetch_all("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        field_columns = {
            item["name"]
            for item in store.fetch_all("PRAGMA table_info('fields')")
        }
        crop_cycle_columns = {
            item["name"]
            for item in store.fetch_all("PRAGMA table_info('field_crop_cycles')")
        }
        soil_columns = {
            item["name"]
            for item in store.fetch_all("PRAGMA table_info('soil_records')")
        }
        weather_columns = {
            item["name"]
            for item in store.fetch_all("PRAGMA table_info('weather_history_daily')")
        }
        pesticide_columns = {
            item["name"]
            for item in store.fetch_all("PRAGMA table_info('pesticide_catalog')")
        }
        spray_columns = {
            item["name"]
            for item in store.fetch_all("PRAGMA table_info('spray_records')")
        }
        source_columns = {
            item["name"]
            for item in store.fetch_all("PRAGMA table_info('data_sources')")
        }
        indicator_columns = {
            item["name"]
            for item in store.fetch_all("PRAGMA table_info('agri_statistical_indicators')")
        }
        spray_indexes = {
            item["name"]
            for item in store.fetch_all("PRAGMA index_list('spray_records')")
        }
        weather_indexes = {
            item["name"]
            for item in store.fetch_all("PRAGMA index_list('weather_history_daily')")
        }
        indicator_indexes = {
            item["name"]
            for item in store.fetch_all("PRAGMA index_list('agri_statistical_indicators')")
        }
    finally:
        store.close()

    assert "fields" in table_names
    assert "crop_catalog" in table_names
    assert "field_crop_cycles" in table_names
    assert "soil_records" in table_names
    assert "weather_history_daily" in table_names
    assert "pesticide_catalog" in table_names
    assert "spray_records" in table_names
    assert "data_sources" in table_names
    assert "agri_statistical_indicators" in table_names

    assert {"field_id", "field_name", "owner_user_id", "province", "city", "county", "geofence"} <= field_columns
    assert {"field_id", "crop_code", "year", "season", "status", "planting_date"} <= crop_cycle_columns
    assert {"field_id", "sample_date", "ph", "organic_matter_gkg", "texture"} <= soil_columns
    assert {"field_id", "station_code", "observation_date", "precipitation_mm"} <= weather_columns
    assert {"pesticide_id", "registration_no", "product_name", "target_pests"} <= pesticide_columns
    assert {"field_id", "crop_cycle_id", "pesticide_id", "spray_date", "result_status"} <= spray_columns
    assert {"source_id", "source_name", "publisher", "source_url"} <= source_columns
    assert {"year", "indicator_code", "indicator_name", "value", "source_id"} <= indicator_columns

    assert "idx_spray_records_field_date" in spray_indexes
    assert "idx_weather_history_daily_field_date" in weather_indexes
    assert "idx_agri_statistical_indicators_code" in indicator_indexes


def test_import_henan_field_crop_seed_csv_imports_and_resolves_runtime_context(tmp_path) -> None:
    seed_dir = tmp_path / "henan_seed"
    generate_seed_csvs(seed_dir)
    db_path = tmp_path / "muye.db"

    summary = import_henan_field_crop_seed_csv(seed_dir, db_path)

    store = SqliteStore(db_path)
    try:
        field_count = store.fetch_one("SELECT COUNT(*) AS total FROM fields")
        crop_count = store.fetch_one("SELECT COUNT(*) AS total FROM crop_catalog")
        cycle_count = store.fetch_one("SELECT COUNT(*) AS total FROM field_crop_cycles")
        field_context = store.fetch_field_context("henan-zz-001")
    finally:
        store.close()

    assert summary["crop_catalog"] == 2
    assert summary["fields"] >= 5
    assert summary["field_crop_cycles"] == summary["fields"] * 2
    assert field_count is not None and field_count["total"] == summary["fields"]
    assert crop_count is not None and crop_count["total"] == summary["crop_catalog"]
    assert cycle_count is not None and cycle_count["total"] == summary["field_crop_cycles"]
    assert field_context is not None
    assert field_context["location"]["province"] == "河南省"
    assert "," in field_context["weather_location"]
    assert len(field_context["geofence"]) >= 3
    assert field_context["crop_cycle"]["crop_name"] in {"冬小麦", "夏玉米"}


def test_sqlite_store_supports_multiple_field_weather_rows_for_same_station_day(tmp_path) -> None:
    db_path = tmp_path / "muye.db"
    store = SqliteStore(db_path)
    try:
        store.upsert_field(
            {
                "field_id": "henan-zz-001",
                "field_code": "HN-001",
                "field_name": "郑州示范田1号",
                "province": "河南省",
                "city": "郑州",
                "county": "中原区",
                "latitude": 34.72,
                "longitude": 113.65,
            }
        )
        store.upsert_field(
            {
                "field_id": "henan-kf-002",
                "field_code": "HN-002",
                "field_name": "开封示范田1号",
                "province": "河南省",
                "city": "开封",
                "county": "龙亭区",
                "latitude": 34.79,
                "longitude": 114.30,
            }
        )
        store.upsert_weather_history_daily(
            {
                "field_id": "henan-zz-001",
                "station_code": "57083",
                "station_name": "郑州",
                "observation_date": "2024-01-01",
                "weather_summary": "晴",
            }
        )
        store.upsert_weather_history_daily(
            {
                "field_id": "henan-kf-002",
                "station_code": "57083",
                "station_name": "郑州",
                "observation_date": "2024-01-01",
                "weather_summary": "多云",
            }
        )
        rows = store.fetch_all(
            """
            SELECT field_id, station_code, observation_date, weather_summary
            FROM weather_history_daily
            WHERE station_code = ? AND observation_date = ?
            ORDER BY field_id ASC
            """,
            ("57083", "2024-01-01"),
        )
    finally:
        store.close()

    assert len(rows) == 2
    assert rows[0]["field_id"] == "henan-kf-002"
    assert rows[1]["field_id"] == "henan-zz-001"


def test_sqlite_store_supports_source_and_indicator_upserts(tmp_path) -> None:
    db_path = tmp_path / "muye.db"
    store = SqliteStore(db_path)
    try:
        store.upsert_data_source(
            {
                "source_id": "henan-source-1",
                "source_name": "河南测试来源",
                "publisher": "测试机构",
                "region_scope": "河南省",
                "source_type": "official",
                "source_url": "https://example.com/henan",
                "access_level": "public",
                "retrieval_date": "2026-04-15",
                "license": "",
                "notes": "test",
            }
        )
        store.upsert_agri_statistical_indicator(
            {
                "region_level": "province",
                "region_name": "河南省",
                "province": "河南省",
                "city": None,
                "county": None,
                "year": 2024,
                "period": "annual",
                "indicator_code": "grain_output_10k_tons",
                "indicator_name": "粮食产量",
                "value": 6719.37,
                "unit": "万吨",
                "source_id": "henan-source-1",
                "source_excerpt": "全年全省粮食产量6719.37万吨。",
                "raw_payload": {"section": "农业"},
            }
        )
        source_row = store.fetch_one(
            "SELECT source_name, source_url FROM data_sources WHERE source_id = ?",
            ("henan-source-1",),
        )
        indicator_row = store.fetch_one(
            """
            SELECT indicator_name, value, source_id, raw_payload
            FROM agri_statistical_indicators
            WHERE indicator_code = ?
            """,
            ("grain_output_10k_tons",),
        )
    finally:
        store.close()

    assert source_row is not None
    assert source_row["source_name"] == "河南测试来源"
    assert source_row["source_url"] == "https://example.com/henan"

    assert indicator_row is not None
    assert indicator_row["indicator_name"] == "粮食产量"
    assert indicator_row["value"] == 6719.37
    assert indicator_row["source_id"] == "henan-source-1"
    assert json.loads(indicator_row["raw_payload"])["section"] == "农业"


def test_import_henan_reference_data_seeds_sources_and_indicators(tmp_path) -> None:
    db_path = tmp_path / "muye.db"
    summary = import_henan_reference_data(db_path)

    store = SqliteStore(db_path)
    try:
        source_count = store.fetch_one("SELECT COUNT(*) AS total FROM data_sources")
        indicator_count = store.fetch_one("SELECT COUNT(*) AS total FROM agri_statistical_indicators")
        sample_indicator = store.fetch_one(
            """
            SELECT indicator_name, value, unit, source_id, source_excerpt
            FROM agri_statistical_indicators
            WHERE indicator_code = ?
            """,
            ("grain_output_10k_tons",),
        )
    finally:
        store.close()

    assert summary["sources"] >= 4
    assert summary["agri_statistical_indicators"] >= 20
    assert source_count is not None
    assert source_count["total"] == summary["sources"]
    assert indicator_count is not None
    assert indicator_count["total"] == summary["agri_statistical_indicators"]
    assert sample_indicator is not None
    assert sample_indicator["indicator_name"] == "粮食产量"
    assert sample_indicator["value"] == 6719.37
    assert sample_indicator["unit"] == "万吨"
    assert sample_indicator["source_id"] == "henan_stat_bulletin_2024"
    assert "6719.37万吨" in sample_indicator["source_excerpt"]


def test_import_henan_weather_history_csv_imports_stations_and_daily_rows(tmp_path) -> None:
    db_path = tmp_path / "muye.db"
    store = SqliteStore(db_path)
    try:
        store.upsert_field(
            {
                "field_id": "henan-zz-001",
                "field_code": "HN-001",
                "field_name": "郑州示范田1号",
                "owner_user_id": "user_a",
                "province": "河南省",
                "city": "郑州市",
                "county": "中原区",
                "latitude": 34.72,
                "longitude": 113.65,
                "area_mu": 66.0,
                "geofence": [[113.64, 34.71], [113.66, 34.71], [113.66, 34.73], [113.64, 34.73]],
            }
        )
    finally:
        store.close()

    csv_path = tmp_path / "henan_weather.csv"
    csv_path.write_text(
        "\n".join(
            [
                "站号,站名,日期,省份,城市,区县,纬度,经度,海拔,平均气温,最低气温,最高气温,平均相对湿度,降水量,平均风速,风向,日照时数,天气概况",
                "57083,郑州,20240101,河南省,郑州市,中原区,34.72,113.65,110.4,1.2,-3.4,5.6,68,0.0,2.5,东北风,5.2,晴",
                "57083,郑州,20240102,河南省,郑州市,中原区,34.72,113.65,110.4,0.8,-2.0,4.3,72,1.1,2.1,东风,2.0,多云",
            ]
        ),
        encoding="utf-8",
    )

    summary = import_henan_weather_history_csv(csv_path, db_path)

    store = SqliteStore(db_path)
    try:
        station_row = store.fetch_one(
            "SELECT station_name, city, county, source_id FROM weather_stations WHERE station_code = ?",
            ("57083",),
        )
        weather_rows = store.fetch_all(
            """
            SELECT station_code, observation_date, weather_summary, temperature_avg_c,
                   precipitation_mm, source, field_id
            FROM weather_history_daily
            WHERE station_code = ?
            ORDER BY observation_date ASC
            """,
            ("57083",),
        )
    finally:
        store.close()

    assert summary["stations"] == 1
    assert summary["weather_history_daily"] == 2

    assert station_row is not None
    assert station_row["station_name"] == "郑州"
    assert station_row["city"] == "郑州市"
    assert station_row["county"] == "中原区"
    assert station_row["source_id"] == "cma_surf_cli_chn_mul_day_v3"

    assert len(weather_rows) == 2
    assert weather_rows[0]["observation_date"] == "2024-01-01"
    assert weather_rows[0]["weather_summary"] == "晴"
    assert weather_rows[0]["temperature_avg_c"] == 1.2
    assert weather_rows[0]["field_id"] == "henan-zz-001"
    assert weather_rows[1]["precipitation_mm"] == 1.1
    assert weather_rows[1]["source"] == "cma_surf_cli_chn_mul_day_v3"


def test_fetch_field_context_prefers_coordinates_for_weather_lookup(tmp_path) -> None:
    db_path = tmp_path / "muye.db"
    store = SqliteStore(db_path)
    try:
        store.upsert_field(
            {
                "field_id": "henan-zz-001",
                "field_code": "HN-001",
                "field_name": "郑州示范田1号",
                "province": "河南省",
                "city": "郑州",
                "county": "中原区",
                "latitude": 34.72,
                "longitude": 113.65,
            }
        )
        field_context = store.fetch_field_context("henan-zz-001")
    finally:
        store.close()

    assert field_context is not None
    assert field_context["weather_location"] == "113.65,34.72"
