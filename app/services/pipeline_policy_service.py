"""Helpers for resolving pipeline execution policy from compliance output."""

from __future__ import annotations

from typing import Any


def resolve_policy_takeoff_mode(compliance: dict[str, Any] | None) -> str:
    """Resolve takeoff mode requested by compliance result."""
    compliance = compliance or {}
    execution_policy = compliance.get("execution_policy") or {}
    if isinstance(execution_policy, dict):
        policy_takeoff = str(execution_policy.get("takeoff_mode") or "").strip().lower()
        if policy_takeoff:
            return policy_takeoff

    compliance_status = str(compliance.get("status") or "").strip().lower()
    if compliance_status == "blocked":
        return "blocked"
    if compliance_status == "warning":
        return "manual"
    return "auto"


def resolve_runtime_takeoff_mode(
    *,
    configured_takeoff_mode: str,
    policy_takeoff_mode: str,
    compliance: dict[str, Any] | None,
) -> tuple[str, bool, list[Any]]:
    """Resolve effective takeoff mode and whether compliance forced manual confirmation."""
    takeoff_mode = str(configured_takeoff_mode or "auto").strip().lower()
    if str(policy_takeoff_mode or "").strip().lower() != "manual":
        return takeoff_mode, False, []

    warnings = (compliance or {}).get("warnings") or []
    if not isinstance(warnings, list):
        warnings = [warnings]
    return "manual", True, warnings
