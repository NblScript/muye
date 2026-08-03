"""Seed a deterministic presentation task for demo and smoke checks."""

from __future__ import annotations

import math
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
        {"pest_type": "麦长管蛜", "confidence": 0.94, "position": {"x1": 810, "y1": 130, "x2": 862, "y2": 184}},
        {"pest_type": "麦长管蛜", "confidence": 0.91, "position": {"x1": 744, "y1": 166, "x2": 796, "y2": 220}},
        {"pest_type": "麦长管蛜", "confidence": 0.87, "position": {"x1": 900, "y1": 194, "x2": 946, "y2": 246}},
        {"pest_type": "麦长管蛜", "confidence": 0.79, "position": {"x1": 838, "y1": 248, "x2": 884, "y2": 296}},
        {"pest_type": "麦二叉蛜", "confidence": 0.86, "position": {"x1": 356, "y1": 468, "x2": 410, "y2": 524}},
        {"pest_type": "麦二叉蛜", "confidence": 0.82, "position": {"x1": 432, "y1": 510, "x2": 480, "y2": 560}},
        {"pest_type": "麦二叉蛜", "confidence": 0.72, "position": {"x1": 500, "y1": 440, "x2": 544, "y2": 486}},
        {"pest_type": "蓟马", "confidence": 0.74, "position": {"x1": 82, "y1": 286, "x2": 126, "y2": 332}},
        {"pest_type": "蓟马", "confidence": 0.64, "position": {"x1": 70, "y1": 214, "x2": 108, "y2": 254}},
        {"pest_type": "麦长管蛜", "confidence": 0.77, "position": {"x1": 1038, "y1": 526, "x2": 1084, "y2": 574}},
        {"pest_type": "aphid", "confidence": 0.92, "position": {"x1": 112, "y1": 96, "x2": 184, "y2": 172}},
        {"pest_type": "aphid", "confidence": 0.88, "position": {"x1": 264, "y1": 132, "x2": 338, "y2": 210}},
    ]


def _density_grid() -> list[dict[str, Any]]:
    """Build a deterministic, irregular insect-density survey surface."""
    geofence = _demo_field().get("geofence") or [
        [8.545275, 47.397586],
        [8.545913, 47.397586],
        [8.545913, 47.397898],
        [8.545275, 47.397898],
    ]
    min_lon = min(float(point[0]) for point in geofence)
    max_lon = max(float(point[0]) for point in geofence)
    min_lat = min(float(point[1]) for point in geofence)
    max_lat = max(float(point[1]) for point in geofence)
    lon_span = max_lon - min_lon
    lat_span = max_lat - min_lat
    rows, cols = 18, 28
    cell_lon = lon_span / cols
    cell_lat = lat_span / rows

    def patch(x: float, y: float, cx: float, cy: float, sx: float, sy: float, weight: float, angle: float) -> float:
        dx, dy = x - cx, y - cy
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        rx = cos_a * dx + sin_a * dy
        ry = -sin_a * dx + cos_a * dy
        return weight * math.exp(-0.5 * ((rx / sx) ** 2 + (ry / sy) ** 2))

    raw_grid: list[list[float]] = []
    for row in range(rows):
        values: list[float] = []
        for col in range(cols):
            x = (col + 0.5) / cols
            y = (row + 0.5) / rows
            density = (
                patch(x, y, 0.68, 0.28, 0.155, 0.070, 0.96, -0.22)
                + patch(x, y, 0.35, 0.69, 0.125, 0.105, 0.70, 0.38)
                + patch(x, y, 0.055, 0.43, 0.045, 0.190, 0.48, -0.05)
                + patch(x, y, 0.84, 0.76, 0.055, 0.045, 0.38, 0.18)
                + patch(x, y, 0.53, 0.49, 0.24, 0.055, 0.20, 0.08)
            )
            density -= patch(x, y, 0.61, 0.29, 0.048, 0.033, 0.27, 0.0)
            density -= patch(x, y, 0.31, 0.66, 0.040, 0.052, 0.18, 0.0)
            lane_factor = (1.03, 0.91, 0.97, 1.00)[row % 4]
            pseudo = math.sin((row + 1) * 12.9898 + (col + 1) * 78.233) * 43758.5453
            noise = (pseudo - math.floor(pseudo) - 0.5) * 0.10 * min(1.0, density * 3.2 + 0.12)
            density = max(0.0, density * lane_factor + noise)
            values.append(0.0 if density < 0.042 else density)
        raw_grid.append(values)

    peak = max(max(row) for row in raw_grid) or 1.0
    pattern = [[round(value / peak, 4) for value in row] for row in raw_grid]

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
    """Spray rates per lane matching the irregular density survey."""
    return [1.2, 1.5, 2.1, 2.5, 2.2, 1.4, 1.1, 1.7, 2.3, 1.8, 1.0]


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
    detections = _detections()
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
        "density_metadata": {
            "source": "demo_seed",
            "density_kind": "synthetic_relative_surface",
            "coordinate_space": "virtual_field_normalized",
            "projection": "synthetic_demo_surface",
            "normalization": "max_cell_weight",
            "grid_rows": 18,
            "grid_cols": 28,
            "detection_count": len(detections),
            "accepted_detection_count": len(detections),
            "rejected_detection_count": 0,
            "is_simulated": True,
        },
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
    store.replace_detections(DEMO_REQUEST_ID, detections)
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
        payload={"detections": detections},
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
