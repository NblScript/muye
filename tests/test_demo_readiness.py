from __future__ import annotations

from modules.infra.event_bus import FileEventBus, build_task_views, load_events
from modules.infra.sqlite_store import SqliteStore


def test_demo_readiness_reports_ready_and_degraded_items() -> None:
    from app.services.demo_readiness_service import build_demo_readiness_response

    payload = build_demo_readiness_response(
        health={
            "status": "error",
            "checks": {
                "sqlite": {"status": "ok"},
                "yolo_model": {"status": "ok", "active_model": "best"},
                "ai_config": {"status": "ok", "qwen_mode": "mock"},
                "rag_config": {"status": "error", "enabled": True},
                "weather_config": {"status": "ok", "mode": "mock"},
                "px4_runtime": {"status": "skipped", "running": False, "ready": False},
                "runtime_config": {"status": "ok", "multi_agent_enabled": True},
            },
            "failures": ["rag_config"],
        },
        workflow={
            "latest_task": {
                "request_id": "req-demo",
                "decision": {"用药": {"农药名称": "吡虫啉"}},
                "rag_context": {"consultation_detail": {"active_count": 3}},
                "drone": {"status": "spraying"},
            }
        },
        websocket_connected=True,
    )

    assert payload["status"] == "degraded"
    assert payload["summary"]["ok"] >= 5
    assert payload["checks"]["qwen"]["status"] == "ok"
    assert payload["checks"]["multi_agent"]["detail"] == "3 位专家"
    assert payload["checks"]["rag"]["status"] == "error"
    assert payload["checks"]["px4"]["status"] == "warning"
    assert payload["issues"][0]["key"] == "rag"
    assert set(payload["issues"][0]) >= {"reason", "impact", "system_action", "human_action"}


def test_seed_demo_state_generates_full_demo_task(tmp_path) -> None:
    from app.services.demo_seed_service import DEMO_REQUEST_ID, seed_demo_state

    store = SqliteStore(tmp_path / "muye.db")
    event_bus = FileEventBus(tmp_path / "demo_events.jsonl")

    result = seed_demo_state(store=store, event_bus=event_bus, clear_existing=True)

    assert result["request_id"] == DEMO_REQUEST_ID
    task_views = store.fetch_task_views(limit=1)
    assert task_views[0]["request_id"] == DEMO_REQUEST_ID
    assert task_views[0]["decision"]["用药"]["农药名称"] == "吡虫啉"

    event_tasks = build_task_views(load_events(event_bus.path))
    seeded = event_tasks[0]
    assert seeded["request_id"] == DEMO_REQUEST_ID
    assert seeded["rag_context"]["consultation_detail"]["active_count"] == 3
    assert seeded["compliance"]["status"] == "passed"
    assert seeded["drone"]["status"] == "spraying"
