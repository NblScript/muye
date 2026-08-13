"""Health check endpoint."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from modules.infra.common import CONFIG_DIR, DATA_DIR, LOGS_DIR, ensure_runtime_dirs, load_yaml
from app.services.workflow_service import get_sqlite_store


def check_sqlite_health() -> dict[str, Any]:
    """Check SQLite health status."""
    store = get_sqlite_store()
    row = store.fetch_one("SELECT 1 AS ok")
    if not row or int(row.get("ok") or 0) != 1:
        raise RuntimeError("sqlite_query_failed")
    return {"status": "ok", "path": str(store.db_path)}


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


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _has_configured_secret(name: str) -> bool:
    value = os.getenv(name, "").strip()
    if not value:
        return False
    placeholders = ("your-", "replace-with", "在此填入")
    return not any(item in value for item in placeholders)


def check_yolo_model_health() -> dict[str, Any]:
    """Check configured local YOLO model availability without loading it."""
    if _env_bool("MUYE_CONTAINER_SMOKE", False):
        return {
            "status": "ok",
            "active_model": "container-smoke-fake",
            "model_path": None,
            "model_exists": False,
            "device": "fake",
            "available_models": [],
            "mode": "smoke_fake",
            "is_simulated": True,
        }

    config = load_yaml(CONFIG_DIR / "yolo_config.yaml")
    models = config.get("models") or {}
    active_model = str(config.get("active_model") or "")
    local_api = config.get("local_api") or {}

    if isinstance(models, dict) and active_model in models:
        profile = models[active_model] or {}
        raw_path = os.getenv("YOLO_LOCAL_MODEL_PATH") or profile.get("path")
        device = os.getenv("YOLO_LOCAL_DEVICE") or str(profile.get("device", "auto"))
    else:
        raw_path = os.getenv("YOLO_LOCAL_MODEL_PATH") or local_api.get("model_path") or "models/best.pt"
        device = os.getenv("YOLO_LOCAL_DEVICE") or str(local_api.get("device", "auto"))
        active_model = active_model or "default"

    model_path = Path(str(raw_path))
    if not model_path.is_absolute():
        model_path = CONFIG_DIR.parent / model_path

    return {
        "status": "ok" if model_path.exists() else "error",
        "active_model": active_model,
        "model_path": str(model_path),
        "model_exists": model_path.exists(),
        "device": device,
        "available_models": sorted(models.keys()) if isinstance(models, dict) else [],
    }


def check_ai_config_health() -> dict[str, Any]:
    """Report AI provider readiness from local configuration only."""
    qwen_mock = _env_bool("QWEN_USE_MOCK", False)
    multi_agent_enabled = _env_bool("MUYE_MULTI_AGENT_ENABLED", False)
    providers = {
        "qwen": qwen_mock or _has_configured_secret("QWEN_API_KEY"),
        "deepseek": _has_configured_secret("DEEPSEEK_API_KEY"),
        "xiaomi": _has_configured_secret("XIAOMI_API_KEY"),
    }
    required_ready = providers["qwen"]
    if multi_agent_enabled:
        required_ready = all(providers.values())

    return {
        "status": "ok" if required_ready else "error",
        "qwen_mode": "mock" if qwen_mock else "real",
        "multi_agent_enabled": multi_agent_enabled,
        "providers": providers,
    }


def check_weather_config_health() -> dict[str, Any]:
    """Report weather provider readiness from local configuration only."""
    use_mock = _env_bool("QWEATHER_USE_MOCK", False)
    configured = _has_configured_secret("QWEATHER_API_KEY")
    return {
        "status": "ok" if use_mock or configured else "error",
        "mode": "mock" if use_mock else "real",
        "api_key_configured": configured,
    }


def check_event_bus_health() -> dict[str, Any]:
    """Check event log path writability without mutating the event stream."""
    ensure_runtime_dirs()
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    probe_fd, probe_path = tempfile.mkstemp(prefix=".event-health-", dir=str(LOGS_DIR))
    try:
        with os.fdopen(probe_fd, "w", encoding="utf-8") as handle:
            handle.write("ok")
        Path(probe_path).unlink(missing_ok=True)
        event_path = LOGS_DIR / "demo_events.jsonl"
        return {
            "status": "ok",
            "path": str(event_path),
            "exists": event_path.exists(),
        }
    except Exception:
        Path(probe_path).unlink(missing_ok=True)
        raise


def check_pipeline_runtime_health() -> dict[str, Any]:
    """Check the optional cross-process pipeline readiness marker."""
    raw_path = os.getenv("MUYE_PIPELINE_READY_FILE", "").strip()
    if not raw_path:
        return {"status": "skipped", "detail": "pipeline_ready_file_not_configured"}
    ready_path = Path(raw_path)
    ready = ready_path.is_file()
    return {
        "status": "ok" if ready else "error",
        "ready": ready,
        "path": str(ready_path),
    }


def check_rag_config_health() -> dict[str, Any]:
    """Report RAG mode and local vector-store path state."""
    enabled = _env_bool("RAG_ENABLED", True)
    chroma_path = DATA_DIR / "chroma_db"
    return {
        "status": "ok" if (not enabled or _has_configured_secret("QWEN_API_KEY")) else "error",
        "enabled": enabled,
        "chroma_path": str(chroma_path),
        "chroma_exists": chroma_path.exists(),
    }


def check_px4_runtime_health() -> dict[str, Any]:
    """Check PX4 runtime state without starting or stopping PX4."""
    try:
        from app.services import px4_process_service

        info = px4_process_service.read_pid_file()
        if info is None:
            return {"status": "skipped", "running": False, "ready": False}

        pid = int(info["pid"])
        running = px4_process_service.is_process_alive(pid)
        ready = running and px4_process_service.is_port_open(px4_process_service.PX4_MAVLINK_PORT)
        return {
            "status": "ok" if ready else "skipped",
            "running": running,
            "ready": ready,
            "pid": pid,
            "world": info.get("world"),
            "source": info.get("source"),
        }
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


def check_runtime_config_health() -> dict[str, Any]:
    """Expose effective demo-critical runtime switches."""
    config_path = CONFIG_DIR / "drone_config.json"
    try:
        raw_config = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        raw_config = {}
    execution = raw_config.get("execution") or {}
    px4 = raw_config.get("px4") or {}
    yolo = check_yolo_model_health()
    return {
        "status": "ok",
        "takeoff_mode": os.getenv("MUYE_TAKEOFF_MODE") or os.getenv("DRONE_TAKEOFF_MODE") or execution.get("takeoff_mode", "auto"),
        "drone_backend": os.getenv("DRONE_BACKEND") or execution.get("backend", "px4"),
        "px4_execution_mode": os.getenv("PX4_EXECUTION_MODE") or px4.get("execution_mode", "animated_demo"),
        "px4_auto_start_on_spray": _env_bool(
            "PX4_AUTO_START_ON_SPRAY",
            bool(px4.get("auto_start_on_spray", True)),
        ),
        "weather_mode": "mock" if _env_bool("QWEATHER_USE_MOCK", False) else "real",
        "qwen_mode": "mock" if _env_bool("QWEN_USE_MOCK", False) else "real",
        "rag_enabled": _env_bool("RAG_ENABLED", True),
        "router_enabled": _env_bool("MUYE_ROUTER_ENABLED", False),
        "multi_agent_enabled": _env_bool("MUYE_MULTI_AGENT_ENABLED", False),
        "yolo_active_model": yolo.get("active_model"),
        "yolo_device": yolo.get("device"),
        "yolo_mode": yolo.get("mode", "real"),
        "yolo_is_simulated": bool(yolo.get("is_simulated", False)),
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
        ("yolo_model", health_module.check_yolo_model_health),
        ("ai_config", health_module.check_ai_config_health),
        ("weather_config", health_module.check_weather_config_health),
        ("event_bus", health_module.check_event_bus_health),
        ("pipeline_runtime", health_module.check_pipeline_runtime_health),
        ("rag_config", health_module.check_rag_config_health),
        ("px4_runtime", health_module.check_px4_runtime_health),
        ("runtime_config", health_module.check_runtime_config_health),
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


async def api_live() -> dict[str, str]:
    """Cheap liveness probe that does not touch external dependencies."""
    return {"status": "ok"}


async def api_slo() -> Any:
    """SLO metrics endpoint."""
    from app.slo import get_slo_metrics
    return get_slo_metrics().snapshot()


def register_health_routes(app: FastAPI) -> None:
    """Register health check and SLO routes."""
    app.get("/live", response_model=None)(api_live)
    app.get("/api/live", include_in_schema=False, response_model=None)(api_live)
    app.get("/health", response_model=None)(api_health)
    app.get("/api/health", include_in_schema=False, response_model=None)(api_health)
    app.get("/slo", response_model=None)(api_slo)
    app.get("/api/slo", include_in_schema=False, response_model=None)(api_slo)
