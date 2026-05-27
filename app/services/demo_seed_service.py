"""Seed a deterministic presentation task for demo and smoke checks."""

from __future__ import annotations

from typing import Any

from app.deps import iso_utc_offset
from app.services import workflow_service
from modules.infra.event_bus import FileEventBus
from modules.infra.sqlite_store import SqliteStore, utc_now_iso


DEMO_REQUEST_ID = "demo-fixed-consultation"
DEMO_FIELD_ID = "px4-sitl-demo"


def _demo_field() -> dict[str, Any]:
    configured = workflow_service.get_px4_demo_field()
    return {
        "field_id": configured.get("field_id", DEMO_FIELD_ID),
        "field_code": configured.get("field_code", "PX4-DEMO"),
        "field_name": configured.get("name", "PX4 SITL 小麦作业田"),
        "province": "河南省",
        "city": "郑州市",
        "county": "中原区",
        "latitude": 34.7472,
        "longitude": 113.6249,
        "area_mu": configured.get("area_mu", 12.0),
        "geofence": configured.get("geofence", []),
        "soil_type": "壤土",
        "irrigation_type": "喷灌",
        "source": "demo_seed",
        "notes": "比赛演示固定地块",
    }


def _decision() -> dict[str, Any]:
    return {
        "用药": {
            "农药名称": "吡虫啉",
            "浓度": "10%",
            "配比": "1000-1500倍液",
            "总量": "1.2 L",
            "安全提示": ["佩戴防护装备", "避开强风和高温时段"],
        },
        "农事建议": ["施药后 3-5 天复查虫口密度", "注意轮换不同作用机制药剂"],
    }


def _rag_context() -> dict[str, Any]:
    return {
        "decision_path": "multi_agent",
        "confidence": 0.86,
        "agreement": "majority",
        "crop_name": "冬小麦",
        "pest_types": ["aphid"],
        "pesticides": [
            {
                "content": "吡虫啉登记用于防治小麦蚜虫，低毒，适合虫口密度上升期使用。",
                "score": 0.91,
                "metadata": {"source": "demo_seed", "pesticide": "吡虫啉"},
            }
        ],
        "knowledge": [
            {
                "content": "小麦蚜虫防治应结合虫口密度、天气和作物生育期综合判断。",
                "score": 0.88,
                "metadata": {"source": "demo_seed"},
            }
        ],
        "consultation_detail": {
            "active_count": 3,
            "failed_roles": [],
            "vote_distribution": {"吡虫啉": 0.67, "噻虫嗪": 0.33},
            "experts": {
                "entomologist": {"name": "昆虫学家", "weight": 0.4, "农药名称": "吡虫啉", "总量": "1.2 L"},
                "agronomist": {"name": "农学家", "weight": 0.35, "农药名称": "吡虫啉", "总量": "1.1 L"},
                "pesticide_specialist": {"name": "植保专家", "weight": 0.25, "农药名称": "噻虫嗪", "总量": "1.0 L"},
            },
        },
    }


def _compliance() -> dict[str, Any]:
    return {
        "status": "passed",
        "score": 92,
        "summary": "吡虫啉来源、作物、防治对象、毒性和天气约束均通过演示复核",
        "checks": [
            {
                "rule": "source_match",
                "name": "来源验证",
                "status": "passed",
                "message": "吡虫啉来自 RAG 农药候选",
                "evidence": [{"source": "demo_seed", "title": "演示农药知识库", "matched_fields": ["农药名称"]}],
            },
            {
                "rule": "weather_risk",
                "name": "天气约束",
                "status": "passed",
                "message": "当前天气条件未触发施药风险",
                "evidence": [{"source": "weather_api", "title": "实时气象", "matched_fields": ["wind_speed", "humidity"]}],
            },
        ],
        "blocking_reasons": [],
        "warnings": [],
        "execution_policy": {"takeoff_mode": "auto", "reason": "演示链路合规通过，允许自动执行"},
        "alternatives": [{"pesticide": "噻虫嗪", "reason": "专家少数备选方案", "score": 78}],
    }


def _detections() -> list[dict[str, Any]]:
    return [
        {"pest_type": "aphid", "confidence": 0.92, "position": {"x1": 112, "y1": 96, "x2": 184, "y2": 172}},
        {"pest_type": "aphid", "confidence": 0.88, "position": {"x1": 264, "y1": 132, "x2": 338, "y2": 210}},
    ]


def _density_grid() -> list[dict[str, Any]]:
    """Simulated variable-rate density grid with realistic gradient distribution."""
    geofence = [
        [8.545275, 47.397586],
        [8.545913, 47.397586],
        [8.545913, 47.397898],
        [8.545275, 47.397898],
    ]
    min_lon, max_lon = geofence[0][0], geofence[1][0]
    min_lat, max_lat = geofence[0][1], geofence[2][1]
    lon_span = max_lon - min_lon
    lat_span = max_lat - min_lat
    rows, cols = 8, 10
    cell_lon = lon_span / cols
    cell_lat = lat_span / rows

    # Density pattern: hot spot in center-right, medium ring, low edges
    pattern = [
        [0.0,  0.0,  0.0,  0.05, 0.1,  0.05, 0.0,  0.0,  0.0,  0.0 ],
        [0.0,  0.05, 0.15, 0.3,  0.4,  0.35, 0.2,  0.1,  0.05, 0.0 ],
        [0.05, 0.2,  0.4,  0.65, 0.85, 0.7,  0.45, 0.25, 0.1,  0.0 ],
        [0.1,  0.3,  0.6,  0.9,  1.0,  0.92, 0.55, 0.3,  0.15, 0.05],
        [0.05, 0.25, 0.5,  0.75, 0.88, 0.8,  0.5,  0.2,  0.1,  0.0 ],
        [0.0,  0.15, 0.35, 0.5,  0.6,  0.55, 0.35, 0.15, 0.05, 0.0 ],
        [0.0,  0.05, 0.15, 0.25, 0.3,  0.28, 0.18, 0.1,  0.0,  0.0 ],
        [0.0,  0.0,  0.05, 0.1,  0.15, 0.12, 0.08, 0.05, 0.0,  0.0 ],
    ]

    cells = []
    for r in range(rows):
        for c in range(cols):
            d = round(pattern[r][c], 4)
            lon1 = min_lon + c * cell_lon
            lon2 = lon1 + cell_lon
            lat1 = min_lat + r * cell_lat
            lat2 = lat1 + cell_lat
            cells.append({
                "row": r, "col": c, "density": d,
                "bounds": [
                    [round(lon1, 7), round(lat1, 7)],
                    [round(lon2, 7), round(lat2, 7)],
                ],
            })
    return cells


def _spray_schedule() -> list[float]:
    """Spray rates per lane matching the density pattern — higher density = higher rate."""
    return [0.9, 1.2, 1.8, 2.7, 2.4, 1.8, 1.2, 0.9, 0.9, 0.9, 0.9]


def seed_demo_state(
    *,
    store: SqliteStore | None = None,
    event_bus: FileEventBus | None = None,
    clear_existing: bool = False,
) -> dict[str, Any]:
    """Seed SQLite and the file event bus with one complete deterministic task."""
    store = store or workflow_service.get_sqlite_store()
    event_bus = event_bus or FileEventBus()
    field = _demo_field()
    field_id = str(field["field_id"])
    decision = _decision()
    weather = {
        "summary": "晴，微风，适宜施药",
        "temperature": 24,
        "humidity": 61,
        "wind_speed": 3.2,
        "precipitation": 0,
    }
    instruction = {
        "source": "system_planner_variable_rate",
        "field_id": field_id,
        "field_name": field["field_name"],
        "crop_name": "冬小麦",
        "飞行路径": workflow_service.get_px4_demo_field().get("explicit_route", []),
        "覆盖区域": {"coordinates": field.get("geofence", [])},
        "高度": 5,
        "速度": 4.5,
        "喷洒速率": "1.8 L/min",
        "density_grid": _density_grid(),
        "spray_schedule": _spray_schedule(),
    }

    if clear_existing:
        store.clear_runtime_task_data()
        event_bus.clear()

    store.upsert_field(field)
    store.upsert_crop_catalog_record(
        {
            "crop_code": "winter_wheat",
            "crop_name": "冬小麦",
            "category": "粮食作物",
            "source": "demo_seed",
        }
    )
    store.upsert_field_crop_cycle(
        {
            "field_id": field_id,
            "crop_code": "winter_wheat",
            "year": 2026,
            "season": "春季",
            "planting_date": "2025-10-15",
            "harvest_date": "2026-06-05",
            "area_mu": field.get("area_mu"),
            "status": "growing",
            "source": "demo_seed",
        }
    )
    store.mark_task_started(DEMO_REQUEST_ID, "data/samples/aphids_01.jpg", field_id)
    store.replace_detections(DEMO_REQUEST_ID, _detections())
    store.add_weather_snapshot(DEMO_REQUEST_ID, weather)
    store.add_decision(DEMO_REQUEST_ID, decision)
    store.upsert_spray_record(
        {
            "request_id": DEMO_REQUEST_ID,
            "field_id": field_id,
            "drone_task_id": "px4-demo-seeded",
            "spray_date": utc_now_iso(),
            "spray_area_mu": field.get("area_mu"),
            "total_dosage": 1.2,
            "dilution_ratio": "1000-1500倍液",
            "spray_rate_lpm": 1.8,
            "flight_height_m": 5,
            "flight_speed_mps": 4.5,
            "weather_snapshot": weather,
            "result_status": "in_progress",
            "source": "demo_seed",
            "notes": "固定演示任务",
        }
    )
    store.add_drone_mission_update(
        DEMO_REQUEST_ID,
        task_id="px4-demo-seeded",
        status="spraying",
        message="固定演示任务正在执行喷洒路径",
        progress=72,
        current_waypoint_index=3,
        instruction=instruction,
        medication=decision["用药"],
    )

    event_bus.publish(
        request_id=DEMO_REQUEST_ID,
        stage="upload",
        status="completed",
        message="演示图片已注入",
        payload={"image_path": "data/samples/aphids_01.jpg"},
    )
    event_bus.publish(
        request_id=DEMO_REQUEST_ID,
        stage="yolo",
        status="completed",
        message="YOLO 识别到小麦蚜虫",
        payload={"detections": _detections()},
    )
    event_bus.publish(
        request_id=DEMO_REQUEST_ID,
        stage="weather",
        status="completed",
        message="天气条件适宜施药",
        payload={"weather": weather},
    )
    event_bus.publish(
        request_id=DEMO_REQUEST_ID,
        stage="decision",
        status="completed",
        message="多智能体会诊完成，合规检查通过",
        payload={"decision": decision, "rag_context": _rag_context(), "compliance": _compliance()},
    )
    event_bus.publish(
        request_id=DEMO_REQUEST_ID,
        stage="drone",
        status="spraying",
        message="固定演示任务正在执行喷洒路径",
        payload={
            "task_id": "px4-demo-seeded",
            "progress": 72,
            "current_waypoint_index": 3,
            "instruction": instruction,
            "medication": decision["用药"],
        },
    )

    return {
        "status": "ok",
        "request_id": DEMO_REQUEST_ID,
        "seeded_at": iso_utc_offset(0),
    }
