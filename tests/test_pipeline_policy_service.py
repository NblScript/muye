from __future__ import annotations

from app.services.pipeline_policy_service import resolve_policy_takeoff_mode, resolve_runtime_takeoff_mode


def test_policy_takeoff_mode_prefers_execution_policy() -> None:
    compliance = {
        "status": "passed",
        "execution_policy": {"takeoff_mode": "manual"},
    }

    assert resolve_policy_takeoff_mode(compliance) == "manual"


def test_policy_takeoff_mode_falls_back_from_compliance_status() -> None:
    assert resolve_policy_takeoff_mode({"status": "blocked"}) == "blocked"
    assert resolve_policy_takeoff_mode({"status": "warning"}) == "manual"
    assert resolve_policy_takeoff_mode({"status": "passed"}) == "auto"
    assert resolve_policy_takeoff_mode({}) == "auto"


def test_runtime_takeoff_mode_forces_manual_when_policy_warns() -> None:
    takeoff_mode, forced_manual, warnings = resolve_runtime_takeoff_mode(
        configured_takeoff_mode="auto",
        policy_takeoff_mode="manual",
        compliance={"warnings": ["wind_high"]},
    )

    assert takeoff_mode == "manual"
    assert forced_manual is True
    assert warnings == ["wind_high"]


def test_runtime_takeoff_mode_keeps_configured_mode_when_policy_allows() -> None:
    takeoff_mode, forced_manual, warnings = resolve_runtime_takeoff_mode(
        configured_takeoff_mode="manual",
        policy_takeoff_mode="auto",
        compliance={"warnings": ["ignored"]},
    )

    assert takeoff_mode == "manual"
    assert forced_manual is False
    assert warnings == []
