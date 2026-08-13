from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from modules.infra.common import LOGS_DIR
from modules.infra.event_bus import load_events

ROOT_DIR = Path(__file__).resolve().parents[1]
EVENT_LOG = LOGS_DIR / "demo_events.jsonl"
SYSTEM_LOG = LOGS_DIR / "system.log"


def fetch_json(url: str, timeout: float = 2.0) -> tuple[dict[str, Any] | None, str | None]:
    try:
        with urlopen(url, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
    except URLError as exc:
        return None, str(exc)
    except OSError as exc:
        return None, str(exc)

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, f"invalid json from {url}: {exc}"
    if isinstance(payload, dict):
        return payload, None
    return None, f"unexpected json payload from {url}"


def recent_events(path: Path = EVENT_LOG, limit: int = 20) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return load_events(path)[-limit:]


def recent_log_errors(path: Path = SYSTEM_LOG, limit: int = 20) -> list[str]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    matches = [
        line
        for line in lines
        if "ERROR" in line or "Traceback" in line or "Exception" in line
    ]
    return matches[-limit:]


def build_report(
    *,
    health: dict[str, Any] | None,
    slo: dict[str, Any] | None,
    workflow: dict[str, Any] | None,
    events: list[dict[str, Any]],
    log_errors: list[str],
    fetch_errors: list[str] | None = None,
) -> dict[str, Any]:
    checks = (health or {}).get("checks") or {}
    failures = sorted(
        name
        for name, check in checks.items()
        if isinstance(check, dict) and check.get("status") == "error"
    )
    warnings = sorted(
        name
        for name, check in checks.items()
        if isinstance(check, dict) and check.get("status") == "skipped"
    )
    fetch_errors = fetch_errors or []

    status = "PASS"
    if failures or fetch_errors or not health:
        status = "FAIL"
    elif warnings or log_errors:
        status = "WARN"

    return {
        "status": status,
        "failures": failures,
        "warnings": warnings,
        "fetch_errors": fetch_errors,
        "runtime_config": checks.get("runtime_config") or {},
        "slo": slo or {},
        "latest_task": (workflow or {}).get("latest_task") or {},
        "recent_events": events[-20:],
        "recent_log_errors": log_errors[-20:],
    }


def _format_key_values(payload: dict[str, Any], keys: list[str]) -> list[str]:
    lines: list[str] = []
    for key in keys:
        if key in payload:
            lines.append(f"  {key}: {payload[key]}")
    return lines


def format_report(report: dict[str, Any]) -> str:
    lines = [f"DEMO DOCTOR: {report['status']}", ""]
    if report["fetch_errors"]:
        lines.append("Fetch errors:")
        lines.extend(f"  - {item}" for item in report["fetch_errors"])
        lines.append("")
    if report["failures"]:
        lines.append("Failed checks:")
        lines.extend(f"  - {item}" for item in report["failures"])
        lines.append("")
    if report["warnings"]:
        lines.append("Warnings:")
        lines.extend(f"  - {item}" for item in report["warnings"])
        lines.append("")

    runtime = report.get("runtime_config") or {}
    if runtime:
        lines.append("Runtime config:")
        lines.extend(
            _format_key_values(
                runtime,
                [
                    "takeoff_mode",
                    "drone_backend",
                    "px4_execution_mode",
                    "weather_mode",
                    "qwen_mode",
                    "rag_enabled",
                    "router_enabled",
                    "multi_agent_enabled",
                    "yolo_active_model",
                    "yolo_device",
                ],
            )
        )
        lines.append("")

    latest = report.get("latest_task") or {}
    if latest:
        lines.append("Latest task:")
        lines.extend(_format_key_values(latest, ["request_id", "status", "current_stage"]))
        lines.append("")

    events = report.get("recent_events") or []
    lines.append(f"Recent events: {len(events)}")
    for event in events[-5:]:
        stage = event.get("stage", "-")
        status = event.get("status", "-")
        message = event.get("message", "")
        lines.append(f"  - {stage}/{status} {message}".rstrip())
    lines.append("")

    errors = report.get("recent_log_errors") or []
    lines.append(f"Recent log errors: {len(errors)}")
    lines.extend(f"  - {item}" for item in errors[-5:])
    return "\n".join(lines)


def collect_report(api_url: str) -> dict[str, Any]:
    base = api_url.rstrip("/")
    fetch_errors: list[str] = []
    health, error = fetch_json(f"{base}/health")
    if error:
        fetch_errors.append(f"health: {error}")
    slo, error = fetch_json(f"{base}/slo")
    if error:
        fetch_errors.append(f"slo: {error}")
    workflow, error = fetch_json(f"{base}/workflow/state")
    if error:
        fetch_errors.append(f"workflow: {error}")

    return build_report(
        health=health,
        slo=slo,
        workflow=workflow,
        events=recent_events(),
        log_errors=recent_log_errors(),
        fetch_errors=fetch_errors,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="牧野演示现场诊断报告")
    parser.add_argument("--api-url", default="http://127.0.0.1:18000")
    parser.add_argument("--json", action="store_true", help="输出 JSON 报告")
    args = parser.parse_args(argv)

    report = collect_report(args.api_url)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(format_report(report))
    return 0 if report["status"] in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
