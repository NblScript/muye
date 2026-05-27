from __future__ import annotations

from scripts.demo_doctor import build_report, format_report


def test_demo_doctor_marks_error_health_checks_as_fail() -> None:
    report = build_report(
        health={
            "status": "error",
            "checks": {
                "sqlite": {"status": "ok"},
                "ai_config": {"status": "error", "detail": "missing key"},
                "px4_runtime": {"status": "skipped"},
            },
            "failures": ["ai_config"],
        },
        slo={"api": {"success_rate": 1.0}},
        workflow={"latest_task": {"request_id": "req-1", "status": "pending_confirmation"}},
        events=[{"stage": "decision", "status": "completed"}],
        log_errors=["ERROR qwen unavailable"],
    )

    assert report["status"] == "FAIL"
    assert "ai_config" in report["failures"]
    assert report["warnings"] == ["px4_runtime"]
    assert report["latest_task"]["status"] == "pending_confirmation"


def test_demo_doctor_formats_runtime_summary() -> None:
    report = build_report(
        health={
            "status": "ok",
            "checks": {
                "runtime_config": {
                    "status": "ok",
                    "takeoff_mode": "manual",
                    "qwen_mode": "mock",
                    "weather_mode": "mock",
                }
            },
        },
        slo={},
        workflow={},
        events=[],
        log_errors=[],
    )

    output = format_report(report)

    assert "DEMO DOCTOR: PASS" in output
    assert "takeoff_mode: manual" in output
    assert "qwen_mode: mock" in output
    assert "weather_mode: mock" in output
