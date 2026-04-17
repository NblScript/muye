from __future__ import annotations

import json
import sqlite3

from modules.sqlite_store import SqliteStore
from scripts.generate_henan_field_crop_seed_csv import generate_seed_csvs
from scripts.generate_henan_soil_seed_csv import generate_soil_seed_csv
from scripts.import_henan_field_crop_seed_csv import import_henan_field_crop_seed_csv
from scripts.import_henan_reference_data import import_henan_reference_data
from scripts.import_henan_soil_records_csv import import_henan_soil_records_csv
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
        store.upsert_field(
            {
                "field_id": "henan-zz-001",
                "field_code": "HN-001",
                "field_name": "郑州示范田1号",
                "province": "河南省",
                "city": "郑州市",
                "county": "中牟县",
                "latitude": 34.7467,
                "longitude": 113.6241,
                "area_mu": 66,
                "geofence": [[113.61, 34.73], [113.63, 34.73], [113.63, 34.75], [113.61, 34.75]],
            }
        )
        store.mark_task_queued("req-a", "/tmp/a.jpg", field_id="henan-zz-001")
        store.mark_task_started("req-a", "/tmp/a.jpg", field_id="henan-zz-001")
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
            instruction={"飞行路径": [[113.6241, 34.7467], [113.6257, 34.7479]]},
            medication={"农药名称": "吡虫啉"},
        )
        store.upsert_spray_record(
            {
                "request_id": "req-a",
                "field_id": "henan-zz-001",
                "drone_task_id": "vd-req-a",
                "spray_date": "2026-04-16T01:00:00Z",
                "spray_area_mu": 66,
                "dosage_per_mu": 0.5,
                "total_dosage": 33,
                "dilution_ratio": "1:800",
                "spray_rate_lpm": 1.8,
                "flight_height_m": 3.0,
                "flight_speed_mps": 4.2,
                "result_status": "completed",
            }
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
    assert completed_tasks[0]["field"]["field_name"] == "郑州示范田1号"
    assert completed_tasks[0]["field"]["area_mu"] == 66
    assert len(completed_tasks[0]["field"]["geofence"]) == 4
    assert completed_tasks[0]["spray_summary"]["spray_area_mu"] == 66
    assert completed_tasks[0]["spray_summary"]["total_dosage"] == 33
    assert completed_tasks[0]["spray_summary"]["result_status"] == "completed"
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


def test_sqlite_store_upsert_spray_record_updates_existing_row_by_request_id(tmp_path) -> None:
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
        store.upsert_crop_catalog_record(
            {
                "crop_code": "winter_wheat",
                "crop_name": "冬小麦",
                "category": "grain",
            }
        )
        store.upsert_field_crop_cycle(
            {
                "field_id": "henan-zz-001",
                "crop_code": "winter_wheat",
                "year": 2025,
                "season": "winter",
                "planting_date": "2025-10-01",
                "harvest_date": "2026-06-05",
                "area_mu": 66,
                "status": "growing",
            }
        )
        cycle_row = store.fetch_one(
            """
            SELECT id
            FROM field_crop_cycles
            WHERE field_id = ? AND crop_code = ?
            """,
            ("henan-zz-001", "winter_wheat"),
        )
        assert cycle_row is not None

        store.mark_task_queued("req-spray-1", "/tmp/sample.jpg", field_id="henan-zz-001")
        store.upsert_spray_record(
            {
                "request_id": "req-spray-1",
                "field_id": "henan-zz-001",
                "crop_cycle_id": cycle_row["id"],
                "drone_task_id": "sim-req-spray-1",
                "spray_date": "2026-04-16T00:00:00Z",
                "spray_area_mu": 66,
                "dosage_per_mu": 0.02,
                "total_dosage": 1.32,
                "dilution_ratio": "1:1000",
                "spray_rate_lpm": 1.1,
                "flight_height_m": 3.2,
                "flight_speed_mps": 2.8,
                "weather_snapshot": {"summary": "多云"},
                "result_status": "completed",
                "source": "main_pipeline",
                "notes": "第一次写入",
            }
        )
        store.upsert_spray_record(
            {
                "request_id": "req-spray-1",
                "field_id": "henan-zz-001",
                "crop_cycle_id": cycle_row["id"],
                "drone_task_id": "sim-req-spray-1-updated",
                "spray_date": "2026-04-16T00:00:00Z",
                "spray_area_mu": 68,
                "dosage_per_mu": 0.03,
                "total_dosage": 2.04,
                "dilution_ratio": "1:800",
                "spray_rate_lpm": 1.3,
                "flight_height_m": 3.5,
                "flight_speed_mps": 2.6,
                "weather_snapshot": {"summary": "晴"},
                "result_status": "completed",
                "source": "main_pipeline",
                "notes": "第二次更新",
            }
        )
        spray_rows = store.fetch_all(
            """
            SELECT request_id, drone_task_id, spray_area_mu, total_dosage, dilution_ratio,
                   spray_rate_lpm, flight_height_m, flight_speed_mps, weather_snapshot, notes
            FROM spray_records
            WHERE request_id = ?
            """,
            ("req-spray-1",),
        )
    finally:
        store.close()

    assert len(spray_rows) == 1
    assert spray_rows[0]["drone_task_id"] == "sim-req-spray-1-updated"
    assert spray_rows[0]["spray_area_mu"] == 68
    assert spray_rows[0]["total_dosage"] == 2.04
    assert spray_rows[0]["dilution_ratio"] == "1:800"
    assert spray_rows[0]["spray_rate_lpm"] == 1.3
    assert spray_rows[0]["flight_height_m"] == 3.5
    assert spray_rows[0]["flight_speed_mps"] == 2.6
    assert json.loads(spray_rows[0]["weather_snapshot"])["summary"] == "晴"
    assert spray_rows[0]["notes"] == "第二次更新"


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


def test_sqlite_store_supports_pesticide_catalog_upserts(tmp_path) -> None:
    db_path = tmp_path / "muye.db"
    store = SqliteStore(db_path)
    try:
        store.upsert_pesticide_catalog_record(
            {
                "pesticide_id": "seed-imidacloprid",
                "registration_no": "SEED-PD-IMI-001",
                "product_name": "吡虫啉",
                "active_ingredient": "吡虫啉",
                "formulation": "10% 可湿性粉剂",
                "toxicity": "低毒",
                "manufacturer": "牧野示例目录",
                "target_crops": ["冬小麦", "夏玉米"],
                "target_pests": ["蚜虫", "飞虱"],
                "dilution_guidance": "1000-1500倍液",
                "source": "henan_pesticide_catalog_seed",
                "raw_payload": {"kind": "seed"},
            }
        )
        store.upsert_pesticide_catalog_record(
            {
                "pesticide_id": "seed-imidacloprid",
                "registration_no": "SEED-PD-IMI-001",
                "product_name": "吡虫啉",
                "active_ingredient": "吡虫啉",
                "formulation": "10% 可湿性粉剂",
                "toxicity": "低毒",
                "manufacturer": "更新后的目录",
                "target_crops": ["冬小麦"],
                "target_pests": ["蚜虫"],
                "dilution_guidance": "1200倍液",
                "source": "henan_pesticide_catalog_seed",
                "raw_payload": {"kind": "seed_updated"},
            }
        )
        pesticide_row = store.fetch_one(
            """
            SELECT product_name, manufacturer, target_crops, target_pests, dilution_guidance, raw_payload
            FROM pesticide_catalog
            WHERE pesticide_id = ?
            """,
            ("seed-imidacloprid",),
        )
    finally:
        store.close()

    assert pesticide_row is not None
    assert pesticide_row["product_name"] == "吡虫啉"
    assert pesticide_row["manufacturer"] == "更新后的目录"
    assert json.loads(pesticide_row["target_crops"]) == ["冬小麦"]
    assert json.loads(pesticide_row["target_pests"]) == ["蚜虫"]
    assert pesticide_row["dilution_guidance"] == "1200倍液"
    assert json.loads(pesticide_row["raw_payload"])["kind"] == "seed_updated"


def test_sqlite_store_supports_soil_record_upserts(tmp_path) -> None:
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
        store.upsert_soil_record(
            {
                "field_id": "henan-zz-001",
                "sample_date": "2025-03-18",
                "depth_cm": 20,
                "ph": 6.8,
                "organic_matter_gkg": 18.6,
                "alkali_hydrolyzable_nitrogen_mgkg": 92.4,
                "available_phosphorus_mgkg": 24.8,
                "available_potassium_mgkg": 128.5,
                "moisture_percent": 22.1,
                "salinity_gkg": 0.9,
                "texture": "壤土",
                "source": "henan_soil_records_seed",
                "raw_payload": {"kind": "seed"},
            }
        )
        store.upsert_soil_record(
            {
                "field_id": "henan-zz-001",
                "sample_date": "2025-03-18",
                "depth_cm": 20,
                "ph": 6.9,
                "organic_matter_gkg": 19.0,
                "alkali_hydrolyzable_nitrogen_mgkg": 93.1,
                "available_phosphorus_mgkg": 25.2,
                "available_potassium_mgkg": 129.8,
                "moisture_percent": 22.6,
                "salinity_gkg": 1.0,
                "texture": "壤土",
                "source": "henan_soil_records_seed",
                "raw_payload": {"kind": "seed_updated"},
            }
        )
        soil_rows = store.fetch_all(
            """
            SELECT field_id, sample_date, depth_cm, ph, organic_matter_gkg, raw_payload
            FROM soil_records
            WHERE field_id = ?
            """,
            ("henan-zz-001",),
        )
    finally:
        store.close()

    assert len(soil_rows) == 1
    assert soil_rows[0]["ph"] == 6.9
    assert soil_rows[0]["organic_matter_gkg"] == 19.0
    assert json.loads(soil_rows[0]["raw_payload"])["kind"] == "seed_updated"


def test_import_henan_reference_data_seeds_sources_and_indicators(tmp_path) -> None:
    db_path = tmp_path / "muye.db"
    summary = import_henan_reference_data(db_path)

    store = SqliteStore(db_path)
    try:
        source_count = store.fetch_one("SELECT COUNT(*) AS total FROM data_sources")
        indicator_count = store.fetch_one("SELECT COUNT(*) AS total FROM agri_statistical_indicators")
        pesticide_count = store.fetch_one("SELECT COUNT(*) AS total FROM pesticide_catalog")
        sample_indicator = store.fetch_one(
            """
            SELECT indicator_name, value, unit, source_id, source_excerpt
            FROM agri_statistical_indicators
            WHERE indicator_code = ?
            """,
            ("grain_output_10k_tons",),
        )
        sample_pesticide = store.fetch_one(
            """
            SELECT product_name, source, target_crops, target_pests
            FROM pesticide_catalog
            WHERE pesticide_id = ?
            """,
            ("seed-imidacloprid",),
        )
    finally:
        store.close()

    assert summary["sources"] >= 5
    assert summary["agri_statistical_indicators"] >= 20
    assert summary["pesticide_catalog"] >= 4
    assert source_count is not None
    assert source_count["total"] == summary["sources"]
    assert indicator_count is not None
    assert indicator_count["total"] == summary["agri_statistical_indicators"]
    assert pesticide_count is not None
    assert pesticide_count["total"] == summary["pesticide_catalog"]
    assert sample_indicator is not None
    assert sample_indicator["indicator_name"] == "粮食产量"
    assert sample_indicator["value"] == 6719.37
    assert sample_indicator["unit"] == "万吨"
    assert sample_indicator["source_id"] == "henan_stat_bulletin_2024"
    assert "6719.37万吨" in sample_indicator["source_excerpt"]
    assert sample_pesticide is not None
    assert sample_pesticide["product_name"] == "吡虫啉"
    assert sample_pesticide["source"] == "henan_pesticide_catalog_seed"
    assert "冬小麦" in json.loads(sample_pesticide["target_crops"])
    assert "蚜虫" in json.loads(sample_pesticide["target_pests"])


def test_import_henan_soil_records_csv_imports_rows(tmp_path) -> None:
    seed_dir = tmp_path / "henan_seed"
    generate_seed_csvs(seed_dir)
    soil_csv = tmp_path / "soil_records.csv"
    generate_soil_seed_csv(soil_csv, fields_csv=seed_dir / "fields.csv")
    db_path = tmp_path / "muye.db"

    import_henan_field_crop_seed_csv(seed_dir, db_path)
    summary = import_henan_soil_records_csv(soil_csv, db_path)

    store = SqliteStore(db_path)
    try:
        soil_count = store.fetch_one("SELECT COUNT(*) AS total FROM soil_records")
        sample_row = store.fetch_one(
            """
            SELECT field_id, sample_date, depth_cm, ph, texture, source
            FROM soil_records
            WHERE field_id = ?
            """,
            ("henan-zz-001",),
        )
    finally:
        store.close()

    assert summary["soil_records"] >= 5
    assert soil_count is not None
    assert soil_count["total"] == summary["soil_records"]
    assert sample_row is not None
    assert sample_row["field_id"] == "henan-zz-001"
    assert sample_row["sample_date"] == "2025-03-18"
    assert sample_row["depth_cm"] == 20
    assert sample_row["source"] == "henan_soil_records_seed"
    assert sample_row["texture"]



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
