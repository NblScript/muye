#!/usr/bin/env python
"""Staged demo seeding — seeds SQLite + EventBus one stage at a time.

Usage:
  python scripts/seed_demo_stages.py --stage clear     # Reset all demo state
  python scripts/seed_demo_stages.py --stage patrol    # Field ready, drone patrol
  python scripts/seed_demo_stages.py --stage detect    # Pest image + YOLO result
  python scripts/seed_demo_stages.py --stage decide    # Multi-agent consultation + compliance
  python scripts/seed_demo_stages.py --stage spray     # Spray execution + animation
  python scripts/seed_demo_stages.py --stage evaluate  # Re-inspection + effectiveness
  python scripts/seed_demo_stages.py --stage all       # Seed everything at once
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.deps import iso_utc_offset
from app.services import workflow_service
from modules.infra.common import load_environment
from modules.infra.event_bus import FileEventBus
from modules.infra.sqlite_store import SqliteStore, utc_now_iso

DEMO_REQUEST_ID = "demo-fixed-consultation"
DEMO_FIELD_ID = "px4-sitl-demo"


def _get_store() -> SqliteStore:
    return workflow_service.get_sqlite_store()


def _get_event_bus() -> FileEventBus:
    return FileEventBus()


def _demo_field() -> dict:
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


def _density_grid() -> list[dict]:
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

    # Deterministic survey-like distribution: wind-stretched colonies, a
    # field-edge incursion, a secondary colony and genuine low-density gaps.
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
    return [1.2, 1.5, 2.1, 2.5, 2.2, 1.4, 1.1, 1.7, 2.3, 1.8, 1.0]


def _flight_route() -> list:
    return workflow_service.get_px4_demo_field().get("explicit_route", [])


def _weather() -> dict:
    return {
        "summary": "晴，微风，适宜施药",
        "temperature": 24,
        "humidity": 61,
        "wind_speed": 3.2,
        "precipitation": 0,
    }


def _detections() -> list[dict]:
    return [
        {"pest_type": "麦长管蛜", "confidence": 0.94, "position": {"x1": 810, "y1": 130, "x2": 862, "y2": 184}},
        {"pest_type": "麦长管蛜", "confidence": 0.91, "position": {"x1": 744, "y1": 166, "x2": 796, "y2": 220}},
        {"pest_type": "麦长管蛜", "confidence": 0.87, "position": {"x1": 900, "y1": 194, "x2": 946, "y2": 246}},
        {"pest_type": "麦长管蛜", "confidence": 0.84, "position": {"x1": 674, "y1": 118, "x2": 716, "y2": 168}},
        {"pest_type": "麦长管蛜", "confidence": 0.79, "position": {"x1": 838, "y1": 248, "x2": 884, "y2": 296}},
        {"pest_type": "麦二叉蛜", "confidence": 0.86, "position": {"x1": 356, "y1": 468, "x2": 410, "y2": 524}},
        {"pest_type": "麦二叉蛜", "confidence": 0.82, "position": {"x1": 432, "y1": 510, "x2": 480, "y2": 560}},
        {"pest_type": "麦二叉蛜", "confidence": 0.76, "position": {"x1": 286, "y1": 542, "x2": 332, "y2": 590}},
        {"pest_type": "麦二叉蛜", "confidence": 0.72, "position": {"x1": 500, "y1": 440, "x2": 544, "y2": 486}},
        {"pest_type": "蓟马", "confidence": 0.74, "position": {"x1": 82, "y1": 286, "x2": 126, "y2": 332}},
        {"pest_type": "蓟马", "confidence": 0.69, "position": {"x1": 106, "y1": 380, "x2": 148, "y2": 426}},
        {"pest_type": "蓟马", "confidence": 0.64, "position": {"x1": 70, "y1": 214, "x2": 108, "y2": 254}},
        {"pest_type": "麦长管蛜", "confidence": 0.77, "position": {"x1": 1038, "y1": 526, "x2": 1084, "y2": 574}},
        {"pest_type": "麦长管蛜", "confidence": 0.68, "position": {"x1": 1094, "y1": 568, "x2": 1134, "y2": 610}},
        {"pest_type": "小麦蚜虫", "confidence": 0.92, "position": {"x1": 112, "y1": 96, "x2": 184, "y2": 172}},
    ]


def _decision() -> dict:
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


def _rag_context() -> dict:
    return {
        "decision_path": "multi_agent",
        "confidence": 0.86,
        "agreement": "majority",
        "familiarity_score": 0.72,
        "familiarity_breakdown": {
            "pesticide_match": 0.65,
            "historical_cases": 0.55,
            "crop_similarity": 0.80,
            "catalog_coverage": 0.90,
        },
        "crop_name": "冬小麦",
        "pest_types": ["aphid"],
        "pesticides": [
            {
                "content": "吡虫啉（imidacloprid），10%可湿性粉剂，登记证号PD20060001。"
                           "登记作物：小麦、水稻、棉花。防治对象：蚜虫、飞虱。"
                           "低毒，对蜜蜂高毒，花期禁用。安全间隔期14天。"
                           "推荐用量：15-20g/亩，兑水30-45L，均匀喷雾。",
                "score": 0.91,
                "metadata": {"source": "农药登记目录", "pesticide": "吡虫啉", "toxicity": "低毒", "category": "烟碱类"},
            },
            {
                "content": "噻虫嗪（thiamethoxam），25%水分散粒剂，登记证号PD20180002。"
                           "登记作物：小麦、玉米、蔬菜。防治对象：蚜虫、蓟马、粉虱。"
                           "低毒，对蜜蜂高毒，对水生生物有毒。安全间隔期21天。",
                "score": 0.85,
                "metadata": {"source": "农药登记目录", "pesticide": "噻虫嗪", "toxicity": "低毒", "category": "烟碱类"},
            },
        ],
        "historical_cases": [
            {
                "content": "2025年5月，河南省新乡市冬小麦田蚜虫防治案例。虫口密度85头/百株，"
                           "使用10%吡虫啉WP 18g/亩喷雾，3天后复查虫口降至18头/百株，杀灭率78.8%。"
                           "第7天复查降至5头/百株，总杀灭率94.1%。",
                "score": 0.82,
                "metadata": {"source": "历史防治记录", "location": "河南新乡", "date": "2025-05", "result": "达标"},
            },
        ],
        "knowledge": [
            {
                "content": "小麦蚜虫（麦蚜）是小麦产区主要害虫之一，主要有麦长管蚜和麦二叉蚜。"
                           "适宜温度为18-25°C，相对湿度60-75%。虫口密度超过500头/百株时需立即防治。"
                           "推荐药剂：吡虫啉、啶虫脒、高效氯氟氰菊酯等，注意轮换使用不同作用机制药剂。",
                "score": 0.88,
                "metadata": {"source": "农业病虫害知识库", "category": "虫害防治"},
            },
            {
                "content": "冬小麦抽穗扬花期是蚜虫防治关键窗口期。施药时应选择无风或微风天气，"
                           "上午9-11点或下午4-6点为佳。避开蜜蜂活动高峰期。喷雾要均匀，"
                           "重点喷施穗部和上部叶片。防治效果以施药后3-7天的虫口减退率为准。",
                "score": 0.84,
                "metadata": {"source": "农事操作规范", "category": "施药技术"},
            },
        ],
        "consultation_detail": {
            "active_count": 3,
            "failed_roles": [],
            "vote_distribution": {"吡虫啉": 0.67, "噻虫嗪": 0.33},
            "experts": {
                "entomologist": {
                    "name": "昆虫学家",
                    "llm_provider": "qwen-max-latest",
                    "weight": 0.4,
                    "农药名称": "吡虫啉",
                    "总量": "1.2 L",
                    "reasoning": "小麦蚜虫属于刺吸式口器害虫，吡虫啉作为烟碱类内吸性杀虫剂，"
                                 "具有良好的内吸传导性，可被作物根系和叶片吸收后传输至蚜虫取食部位。"
                                 "当前虫口密度中等，10%浓度即可达到理想防效。",
                },
                "agronomist": {
                    "name": "农学家",
                    "llm_provider": "deepseek-chat",
                    "weight": 0.35,
                    "农药名称": "吡虫啉",
                    "总量": "1.1 L",
                    "reasoning": "冬小麦正处于抽穗扬花期，是产量形成的关键阶段。吡虫啉对天敌相对安全，"
                                 "且对小麦品质无不良影响。结合当前天气条件（晴、微风、24°C），施药窗口良好。"
                                 "考虑到综合成本，推荐1.1L总量即可覆盖12亩地块。",
                },
                "pesticide_specialist": {
                    "name": "植保专家",
                    "llm_provider": "xiaomi-mimo-v2.5-pro",
                    "weight": 0.25,
                    "农药名称": "噻虫嗪",
                    "总量": "1.0 L",
                    "reasoning": "噻虫嗪是第二代烟碱类杀虫剂，与吡虫啉相比具有更高的水溶性和更长的持效期。"
                                 "考虑到蚜虫可能对吡虫啉产生一定抗性，建议使用噻虫嗪作为替代方案。"
                                 "25%水分散粒剂每亩用量更低，适合变量喷洒。",
                },
            },
        },
    }


def _compliance() -> dict:
    return {
        "status": "passed",
        "score": 92,
        "summary": "吡虫啉来源可追溯，作物与防治对象匹配，毒性等级可接受，天气条件适宜施药",
        "checks": [
            {
                "rule": "source_match",
                "name": "来源验证",
                "status": "passed",
                "message": "吡虫啉存在于 RAG 农药知识库中，来源可追溯至农药登记目录",
                "evidence": [
                    {"source": "农药登记目录", "title": "吡虫啉登记信息", "matched_fields": ["农药名称", "登记证号", "作物"]},
                ],
            },
            {
                "rule": "crop_match",
                "name": "作物匹配",
                "status": "passed",
                "message": "吡虫啉已登记用于小麦作物，防治对象包含蚜虫",
                "evidence": [
                    {"source": "农药登记目录", "title": "吡虫啉适用范围", "matched_fields": ["作物=小麦", "防治对象=蚜虫"]},
                ],
            },
            {
                "rule": "toxicity_check",
                "name": "毒性评估",
                "status": "passed",
                "message": "吡虫啉毒性等级为低毒，符合常规施药安全标准",
                "evidence": [
                    {"source": "农药登记目录", "title": "吡虫啉毒性信息", "matched_fields": ["毒性等级=低毒"]},
                ],
            },
            {
                "rule": "weather_risk",
                "name": "天气约束",
                "status": "passed",
                "message": "温度24°C、湿度61%、风速3.2m/s，均在安全施药范围内",
                "evidence": [
                    {"source": "天气API", "title": "实时气象数据", "matched_fields": ["温度", "湿度", "风速"]},
                ],
            },
            {
                "rule": "safety_warning",
                "name": "安全提示",
                "status": "warning",
                "message": "吡虫啉对蜜蜂高毒，请注意避开蜜源植物和蜜蜂活动区域",
                "evidence": [
                    {"source": "农药登记目录", "title": "吡虫啉安全提示", "matched_fields": ["蜜蜂毒性"]},
                ],
            },
        ],
        "blocking_reasons": [],
        "warnings": ["对蜜蜂高毒，需避开蜜源植物"],
        "execution_policy": {"takeoff_mode": "auto", "reason": "全部核心检查项通过，仅安全提示为警告级别，允许自动执行"},
        "alternatives": [
            {"pesticide": "噻虫嗪", "reason": "第二代烟碱类，持效期更长，专家少数备选方案", "score": 78},
            {"pesticide": "啶虫脒", "reason": "对蜜蜂毒性较低，适合蜜源植物附近地块", "score": 65},
        ],
    }


def _spray_instruction() -> dict:
    field = _demo_field()
    return {
        "source": "system_planner_variable_rate",
        "field_id": field["field_id"],
        "field_name": field["field_name"],
        "crop_name": "冬小麦",
        "飞行路径": _flight_route(),
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
            "detection_count": 16,
            "accepted_detection_count": 16,
            "rejected_detection_count": 0,
            "is_simulated": True,
        },
        "spray_schedule": _spray_schedule(),
    }


def _evaluation_data() -> dict:
    return {
        "evaluation_id": "demo-eval-001",
        "request_id": DEMO_REQUEST_ID,
        "status": "completed",
        "kill_rate": 0.94,
        "threshold": 0.90,
        "passed": True,
        "before_count": 28,
        "after_count": 2,
        "pest_types": ["aphid"],
        "method": "yolo_reinspection",
        "recommendation": "杀灭率 94%，超过阈值 90%，防治效果达标",
        "rounds": 1,
        "evaluated_at": iso_utc_offset(0),
    }


# ── Stage functions ──

def stage_clear() -> None:
    """Reset all demo runtime state."""
    store = _get_store()
    event_bus = _get_event_bus()
    # Delete from FK-referencing tables before tasks (clear_runtime_task_data misses some)
    store._connection.execute("DELETE FROM task_evaluations")
    store._connection.execute("DELETE FROM mission_iterations")
    store._connection.execute("DELETE FROM missions")
    store._connection.execute("DELETE FROM pending_actions")
    store._connection.commit()
    store.clear_runtime_task_data()
    event_bus.clear()
    print("✓ 演示状态已清空")


def stage_patrol() -> None:
    """Seed field + crop data, publish patrol event. Frontend shows drone takeoff."""
    store = _get_store()
    event_bus = _get_event_bus()
    field = _demo_field()
    field_id = field["field_id"]

    store.upsert_field(field)
    store.upsert_crop_catalog_record({
        "crop_code": "winter_wheat",
        "crop_name": "冬小麦",
        "category": "粮食作物",
        "source": "demo_seed",
    })
    store.upsert_field_crop_cycle({
        "field_id": field_id,
        "crop_code": "winter_wheat",
        "year": 2026,
        "season": "春季",
        "planting_date": "2025-10-15",
        "harvest_date": "2026-06-05",
        "area_mu": field["area_mu"],
        "status": "growing",
        "source": "demo_seed",
    })

    # Initialize task in SQLite (no image yet — image comes in stage 2: detect)
    store.mark_task_started(DEMO_REQUEST_ID, "", field_id)
    store.add_drone_mission_update(
        DEMO_REQUEST_ID,
        task_id="demo-patrol-001",
        status="patrolling",
        message="无人机正在执行巡检任务，实时回传农田画面",
        progress=25,
        current_waypoint_index=0,
        instruction={
            "source": "manual_patrol",
            "field_id": field_id,
            "field_name": field["field_name"],
            "crop_name": "冬小麦",
            "飞行路径": _flight_route(),
            "覆盖区域": {"coordinates": field.get("geofence", [])},
        },
        medication={},
    )

    event_bus.publish(
        request_id=DEMO_REQUEST_ID,
        stage="drone",
        status="patrolling",
        message="无人机起飞，开始巡检作业",
        payload={
            "task_id": "demo-patrol-001",
            "progress": 25,
            "current_waypoint_index": 0,
            "field_id": field_id,
            "field_name": field["field_name"],
        },
    )
    print("✓ 阶段1完成：无人机起飞巡检 — 前端应显示巡检状态")


def stage_detect() -> None:
    """Seed pest detection result. Frontend shows YOLO output + pest cards."""
    store = _get_store()
    event_bus = _get_event_bus()
    detections = _detections()

    store.mark_task_started(DEMO_REQUEST_ID, "data/samples/aphids_01.jpg", _demo_field()["field_id"])
    store.replace_detections(DEMO_REQUEST_ID, detections)
    store.add_drone_mission_update(
        DEMO_REQUEST_ID,
        task_id="demo-patrol-001",
        status="detecting",
        message="巡检相机识别到害虫，正在执行 YOLO 检测",
        progress=45,
        current_waypoint_index=1,
        instruction={
            "source": "manual_patrol",
            "field_id": _demo_field()["field_id"],
            "field_name": _demo_field()["field_name"],
            "crop_name": "冬小麦",
        },
        medication={},
    )

    event_bus.publish(
        request_id=DEMO_REQUEST_ID,
        stage="upload",
        status="completed",
        message="巡检图像已回传至分析平台",
        payload={"image_path": "data/samples/aphids_01.jpg"},
    )
    event_bus.publish(
        request_id=DEMO_REQUEST_ID,
        stage="yolo",
        status="completed",
        message="YOLO 检测完成：小麦蚜虫，置信度 92%",
        payload={"detections": detections},
    )
    print("✓ 阶段2完成：害虫检测 — 前端应显示 YOLO 检测结果")


def stage_decide() -> None:
    """Seed AI decision + multi-agent consultation + compliance. Frontend shows expert debate."""
    store = _get_store()
    event_bus = _get_event_bus()
    weather = _weather()
    decision = _decision()
    rag_context = _rag_context()
    compliance = _compliance()

    store.add_weather_snapshot(DEMO_REQUEST_ID, weather)
    store.add_decision(DEMO_REQUEST_ID, decision)

    event_bus.publish(
        request_id=DEMO_REQUEST_ID,
        stage="weather",
        status="completed",
        message=f"气象数据采集完成：{weather['summary']}，温度 {weather['temperature']}°C",
        payload={"weather": weather},
    )
    event_bus.publish(
        request_id=DEMO_REQUEST_ID,
        stage="decision",
        status="completed",
        message="多智能体会诊完成，3位专家达成共识：推荐使用吡虫啉",
        payload={
            "decision": decision,
            "rag_context": rag_context,
            "compliance": compliance,
        },
    )
    event_bus.publish(
        request_id=DEMO_REQUEST_ID,
        stage="compliance",
        status="passed",
        message="农药合规审核通过：来源可追溯、天气条件适宜",
        payload={"compliance": compliance},
    )

    store.add_drone_mission_update(
        DEMO_REQUEST_ID,
        task_id="demo-patrol-001",
        status="pending_confirmation",
        message="AI决策完成，等待确认起飞执行喷洒",
        progress=60,
        current_waypoint_index=1,
        instruction=_spray_instruction(),
        medication=decision["用药"],
    )

    # Must publish a drone event so EventBus task view reflects pending_confirmation.
    # Without this, merge_sqlite_tasks_with_events would keep the old "patrolling"
    # status from the stage-1 drone event.
    event_bus.publish(
        request_id=DEMO_REQUEST_ID,
        stage="drone",
        status="pending_confirmation",
        message="AI决策完成，等待确认起飞执行喷洒",
        payload={
            "task_id": "demo-patrol-001",
            "progress": 60,
            "current_waypoint_index": 1,
        },
    )
    print("✓ 阶段3完成：AI会诊决策 — 前端应显示多专家会诊 + 决策结果 + 合规通过")


def stage_spray() -> None:
    """Seed spray execution. Frontend shows spray animation + progress."""
    store = _get_store()
    event_bus = _get_event_bus()
    decision = _decision()
    weather = _weather()
    field = _demo_field()
    instruction = _spray_instruction()
    field_id = field["field_id"]

    # Update drone status to spraying
    store.add_drone_mission_update(
        DEMO_REQUEST_ID,
        task_id="demo-spray-001",
        status="spraying",
        message="无人机正在执行变量喷洒任务",
        progress=72,
        current_waypoint_index=3,
        instruction=instruction,
        medication=decision["用药"],
    )

    # Create spray record
    store.upsert_spray_record({
        "request_id": DEMO_REQUEST_ID,
        "field_id": field_id,
        "drone_task_id": "demo-spray-001",
        "spray_date": utc_now_iso(),
        "spray_area_mu": field["area_mu"],
        "total_dosage": 1.2,
        "dilution_ratio": "1000-1500倍液",
        "spray_rate_lpm": 1.8,
        "flight_height_m": 5,
        "flight_speed_mps": 4.5,
        "weather_snapshot": weather,
        "result_status": "in_progress",
        "source": "demo_seed",
        "notes": "手动操作无人机演示喷洒",
    })

    # Mark task as completed
    store.mark_task_finished(DEMO_REQUEST_ID, "completed")

    event_bus.publish(
        request_id=DEMO_REQUEST_ID,
        stage="drone",
        status="spraying",
        message="无人机喷洒执行中 — 变量喷洒，重点区域加大药量",
        payload={
            "task_id": "demo-spray-001",
            "progress": 72,
            "current_waypoint_index": 3,
            "instruction": instruction,
            "medication": decision["用药"],
        },
    )
    event_bus.publish(
        request_id=DEMO_REQUEST_ID,
        stage="pipeline",
        status="completed",
        message="喷洒任务完成，飞行路径已记录",
        payload={
            "spray_area_mu": field["area_mu"],
            "total_dosage": 1.2,
            "flight_height_m": 5,
        },
    )
    print("✓ 阶段4完成：喷洒执行 — 前端应显示喷洒动画 + 进度")


def stage_evaluate() -> None:
    """Seed re-inspection + evaluation data. Frontend shows evaluation card with kill rate."""
    store = _get_store()
    event_bus = _get_event_bus()
    evaluation = _evaluation_data()

    # Update spray record with completed status
    store.upsert_spray_record({
        "request_id": DEMO_REQUEST_ID,
        "field_id": _demo_field()["field_id"],
        "drone_task_id": "demo-spray-001",
        "spray_date": utc_now_iso(),
        "spray_area_mu": _demo_field()["area_mu"],
        "total_dosage": 1.2,
        "dilution_ratio": "1000-1500倍液",
        "spray_rate_lpm": 1.8,
        "flight_height_m": 5,
        "flight_speed_mps": 4.5,
        "weather_snapshot": _weather(),
        "result_status": "completed",
        "source": "demo_seed",
        "notes": "演示喷洒完成，已启动效果评估",
    })

    # Add re-inspection drone update
    store.add_drone_mission_update(
        DEMO_REQUEST_ID,
        task_id="demo-reinspect-001",
        status="inspecting",
        message="复检无人机正在巡检，评估防治效果",
        progress=88,
        current_waypoint_index=5,
        instruction={
            "source": "reinspection",
            "field_id": _demo_field()["field_id"],
            "field_name": _demo_field()["field_name"],
            "crop_name": "冬小麦",
            "purpose": "喷洒后复检，评估杀虫率",
        },
        medication={},
    )

    event_bus.publish(
        request_id=DEMO_REQUEST_ID,
        stage="drone",
        status="inspecting",
        message="复检无人机起飞，正在采集喷洒后农田图像",
        payload={"task_id": "demo-reinspect-001", "progress": 88},
    )
    event_bus.publish(
        request_id=DEMO_REQUEST_ID,
        stage="evaluation",
        status="completed",
        message=f"药效评估完成：杀灭率 {evaluation['kill_rate']*100:.0f}%，超过阈值 {evaluation['threshold']*100:.0f}%，防治达标",
        payload=evaluation,
    )
    print("✓ 阶段5完成：复检评估 — 前端应显示复检过程 + 杀灭率 94%")


def stage_all() -> None:
    """Seed all stages at once (for quick-start demo)."""
    stage_clear()
    stage_patrol()
    stage_detect()
    stage_decide()
    stage_spray()
    stage_evaluate()
    print("✓ 全部阶段播种完成")


STAGES = {
    "clear": stage_clear,
    "patrol": stage_patrol,
    "detect": stage_detect,
    "decide": stage_decide,
    "spray": stage_spray,
    "evaluate": stage_evaluate,
    "all": stage_all,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Staged demo seeding for muye demo script")
    parser.add_argument(
        "--stage",
        required=True,
        choices=list(STAGES.keys()),
        help="Which stage to seed",
    )
    args = parser.parse_args()

    load_environment()
    STAGES[args.stage]()
    _get_store().close()


if __name__ == "__main__":
    main()
