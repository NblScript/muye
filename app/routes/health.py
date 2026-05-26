"""Health check endpoint."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from modules.infra.common import DATA_DIR, ensure_runtime_dirs
from modules.infra.sqlite_store import SqliteStore


def check_sqlite_health() -> dict[str, Any]:
    """Check SQLite health status."""
    sqlite_path = Path(os.getenv("MUYE_SQLITE_PATH", str(DATA_DIR / "muye.db")))
    store = SqliteStore(sqlite_path)
    try:
        row = store.fetch_one("SELECT 1 AS ok")
        if not row or int(row.get("ok") or 0) != 1:
            raise RuntimeError("sqlite_query_failed")
        return {"status": "ok", "path": str(sqlite_path)}
    finally:
        store.close()


def check_data_dir_health() -> dict[str, Any]:
    """Check data directory health status."""
    ensure_runtime_dirs()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    probe_fd, probe_path = tempfile.mkstemp(prefix=".health-", dir=str(DATA_DIR))
    try:
        with os.fdopen(probe_fd, "w", encoding="utf-8") as handle:
            handle.write("ok")
        Path(probe_path).unlink(missing_ok=True)
        return {"status": "ok", "path": str(DATA_DIR)}
    except Exception:
        Path(probe_path).unlink(missing_ok=True)
        raise


def check_embedded_yolo_health(runner: Any = None) -> dict[str, Any]:
    """Check embedded YOLO API health status."""
    # If no runner provided, try to get from deps
    if runner is None:
        from app.deps import get_embedded_yolo_runner
        runner = get_embedded_yolo_runner()
    
    if runner is None:
        return {"status": "skipped", "detail": "no_embedded_yolo_runner"}

    if runner.server_task is None:
        raise RuntimeError("embedded_yolo_runner_not_started")

    if runner.server_task.done():
        error = runner.server_task.exception()
        if error:
            raise RuntimeError(f"embedded_yolo_runner_exited: {error}") from error
        raise RuntimeError("embedded_yolo_runner_exited")

    return {
        "status": "ok",
        "detect_url": runner.detect_url,
        "health_url": runner.health_url,
    }


def collect_health_status(embedded_yolo_runner: Any = None) -> tuple[dict[str, Any], bool]:
    """Collect all health check statuses."""
    # If no runner provided, try to get from deps
    if embedded_yolo_runner is None:
        from app.deps import get_embedded_yolo_runner
        embedded_yolo_runner = get_embedded_yolo_runner()
    
    # Use module-level function references for monkeypatching
    # Tests can patch app.routes.health.check_sqlite_health etc.
    import app.routes.health as health_module
    
    sqlite_checker = health_module.check_sqlite_health
    data_dir_checker = health_module.check_data_dir_health
    yolo_checker = health_module.check_embedded_yolo_health

    checks: dict[str, dict[str, Any]] = {}
    failures: list[str] = []
    
    # Determine how to call the yolo checker based on its signature
    # For monkeypatched lambdas (no params), call without args
    # For our function (takes runner param), pass the runner
    try:
        import inspect
        sig = inspect.signature(yolo_checker)
        param_count = len(sig.parameters)
    except (ValueError, TypeError):
        param_count = 1  # Fallback: assume it needs the runner
    
    if param_count == 0:
        yolo_call = lambda: yolo_checker()
    else:
        yolo_call = lambda: yolo_checker(embedded_yolo_runner)
    
    for name, checker in (
        ("sqlite", sqlite_checker),
        ("data_dir", data_dir_checker),
        ("embedded_yolo", yolo_call),
    ):
        try:
            result = checker()
        except Exception as exc:
            result = {"status": "error", "detail": str(exc)}

        checks[name] = result
        if result.get("status") == "error":
            failures.append(name)

    payload: dict[str, Any] = {
        "status": "ok" if not failures else "error",
        "checks": checks,
    }
    if failures:
        payload["failures"] = failures
    return payload, not failures


async def api_health() -> Any:
    """Health check endpoint handler."""
    import app.routes.health as health_module
    payload, healthy = health_module.collect_health_status()
    if healthy:
        return payload
    return JSONResponse(status_code=503, content=payload)


async def api_slo() -> Any:
    """SLO metrics endpoint."""
    from app.slo import get_slo_metrics
    return get_slo_metrics().snapshot()


def register_health_routes(app: FastAPI) -> None:
    """Register health check and SLO routes."""
    app.get("/health", response_model=None)(api_health)
    app.get("/api/health", include_in_schema=False, response_model=None)(api_health)
    app.get("/slo", response_model=None)(api_slo)
    app.get("/api/slo", include_in_schema=False, response_model=None)(api_slo)
