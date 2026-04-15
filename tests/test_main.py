from __future__ import annotations

import asyncio
import json
import os

from main import MuyeApplication, _build_local_yolo_urls, _resolve_loopback_host


def test_resolve_loopback_host() -> None:
    assert _resolve_loopback_host("0.0.0.0") == "127.0.0.1"
    assert _resolve_loopback_host("::") == "127.0.0.1"
    assert _resolve_loopback_host("192.168.1.20") == "192.168.1.20"


def test_build_local_yolo_urls() -> None:
    detect_url, health_url = _build_local_yolo_urls("0.0.0.0", 8010)

    assert detect_url == "http://127.0.0.1:8010/detect"
    assert health_url == "http://127.0.0.1:8010/health"


def test_main_reads_qwen_mock_flag(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("QWEN_USE_MOCK", "true")
    monkeypatch.setenv("MUYE_SQLITE_PATH", str(tmp_path / "muye.db"))
    app = MuyeApplication()
    try:
        assert app.decision_engine.use_mock is True
    finally:
        import asyncio

        asyncio.run(app.shutdown())
    os.environ.pop("QWEN_USE_MOCK", None)


def test_main_pipeline_writes_sqlite_records(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("MUYE_SQLITE_PATH", str(tmp_path / "muye.db"))

    app = MuyeApplication()
    image_path = tmp_path / "sample.jpg"
    image_path.write_bytes(b"\xff\xd8\xff\xd9")

    detections = [
        {
            "pest_type": "aphid",
            "confidence": 0.94,
            "position": {"x1": 1, "y1": 2, "x2": 3, "y2": 4},
        }
    ]
    weather = {
        "temperature": 26.5,
        "humidity": 61,
        "summary": "多云",
        "wind_direction": "东南风",
        "wind_scale_text": "2",
        "wind_speed": 3.3,
    }
    decision = {
        "用药": {
            "农药名称": "吡虫啉",
            "浓度": "1000倍",
            "配比": "1:1000",
            "总量": "1L",
            "安全提示": ["佩戴防护装备"],
        },
        "农事建议": ["优先处理高风险区"],
    }
    mission_result = {"status": "simulated", "task_id": "sim-req-1", "accepted": True}

    async def fake_detect_pests(*args, **kwargs):
        return detections

    async def fake_generate_decision(*args, **kwargs):
        return {
            "weather": weather,
            "decision": decision,
            "structured_input_text": "stub",
        }

    async def fake_execute_spray_mission(*args, **kwargs):
        return mission_result

    monkeypatch.setattr(app.image_processor, "detect_pests", fake_detect_pests)
    monkeypatch.setattr(app.decision_engine, "generate_decision", fake_generate_decision)
    monkeypatch.setattr(app.drone_controller, "execute_spray_mission", fake_execute_spray_mission)

    async def run_pipeline() -> tuple[str, dict[str, object] | None]:
        await app.enqueue_image(image_path)
        request_id, queued_image, field_context = app.queue.get_nowait()
        queued_task = app.sqlite_store.fetch_one(
            "SELECT request_id, field_id, image_path, status FROM tasks WHERE request_id = ?",
            (request_id,),
        )
        try:
            await app._process_image(request_id, queued_image, field_context, worker_id=1)
            return request_id, queued_task
        finally:
            app.pending_images.discard(str(queued_image.resolve()))
            app.queue.task_done()

    try:
        request_id, queued_task = asyncio.run(run_pipeline())
        task = app.sqlite_store.fetch_one(
            "SELECT request_id, field_id, image_path, status, start_time, end_time FROM tasks WHERE request_id = ?",
            (request_id,),
        )
        detection_rows = app.sqlite_store.fetch_all(
            "SELECT label, confidence, bbox FROM detections WHERE request_id = ?",
            (request_id,),
        )
        weather_row = app.sqlite_store.fetch_one(
            "SELECT weather_data FROM weather_snapshots WHERE request_id = ?",
            (request_id,),
        )
        decision_row = app.sqlite_store.fetch_one(
            "SELECT decision_text FROM decisions WHERE request_id = ?",
            (request_id,),
        )
    finally:
        asyncio.run(app.shutdown())

    assert queued_task is not None
    assert queued_task["status"] == "queued"
    assert queued_task["image_path"] == str(image_path)
    assert queued_task["field_id"] == "henan-zz-001"

    assert task is not None
    assert task["request_id"] == request_id
    assert task["status"] == "completed"
    assert task["image_path"] == str(image_path)
    assert task["field_id"] == "henan-zz-001"
    assert task["start_time"] is not None
    assert task["end_time"] is not None

    assert len(detection_rows) == 1
    assert detection_rows[0]["label"] == "aphid"
    assert detection_rows[0]["confidence"] == 0.94
    assert json.loads(detection_rows[0]["bbox"]) == {"x1": 1, "y1": 2, "x2": 3, "y2": 4}

    assert weather_row is not None
    assert json.loads(weather_row["weather_data"])["summary"] == "多云"

    assert decision_row is not None
    assert json.loads(decision_row["decision_text"])["用药"]["农药名称"] == "吡虫啉"


def test_main_prefers_sqlite_field_context_over_static_config(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("MUYE_SQLITE_PATH", str(tmp_path / "muye.db"))
    monkeypatch.setenv("MUYE_ACTIVE_FIELD_ID", "henan-zz-001")

    app = MuyeApplication()
    try:
        app.sqlite_store.upsert_field(
            {
                "field_id": "henan-zz-001",
                "field_code": "HN-001",
                "field_name": "郑州示范田1号",
                "owner_user_id": "user_a",
                "province": "河南省",
                "city": "郑州",
                "county": "中原区",
                "latitude": 34.74,
                "longitude": 113.62,
                "area_mu": 66,
                "geofence": [[113.61, 34.73], [113.63, 34.73], [113.63, 34.75], [113.61, 34.75]],
                "soil_type": "潮土",
            }
        )
        app.sqlite_store.upsert_crop_catalog_record(
            {
                "crop_code": "winter_wheat",
                "crop_name": "冬小麦",
                "category": "grain",
                "growth_cycle_days": 240,
                "water_demand_coefficient": 1.0,
            }
        )
        app.sqlite_store.upsert_field_crop_cycle(
            {
                "field_id": "henan-zz-001",
                "crop_code": "winter_wheat",
                "year": 2025,
                "season": "winter",
                "planting_date": "2025-10-10",
                "harvest_date": "2026-06-05",
                "area_mu": 66,
                "status": "growing",
            }
        )

        field_context = app._resolve_runtime_field_context()
    finally:
        asyncio.run(app.shutdown())

    assert field_context["field_id"] == "henan-zz-001"
    assert field_context["location"]["city"] == "郑州"
    assert field_context["crop_cycle"]["crop_name"] == "冬小麦"


def test_main_rejects_ambiguous_field_context_without_explicit_selection(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("MUYE_SQLITE_PATH", str(tmp_path / "muye.db"))
    monkeypatch.delenv("MUYE_ACTIVE_FIELD_ID", raising=False)

    app = MuyeApplication()
    try:
        app.drone_config["field"]["field_id"] = None
        app.sqlite_store.upsert_field(
            {
                "field_id": "henan-zz-001",
                "field_code": "HN-001",
                "field_name": "郑州示范田1号",
                "province": "河南省",
                "city": "郑州",
                "county": "中原区",
                "latitude": 34.74,
                "longitude": 113.62,
            }
        )
        app.sqlite_store.upsert_field(
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

        try:
            app._resolve_runtime_field_context()
            assert False, "expected ambiguous field context to raise"
        except RuntimeError as exc:
            assert "MUYE_ACTIVE_FIELD_ID" in str(exc)
    finally:
        asyncio.run(app.shutdown())
