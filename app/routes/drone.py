"""Drone control endpoints."""

from __future__ import annotations

import asyncio
import fcntl
import json
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException

import app.deps as deps
from app.services import px4_process_service as px4_process
from modules.infra.common import DATA_DIR

logger = logging.getLogger(__name__)

RotatingLogFile = px4_process.RotatingLogFile
Px4StartRequest = px4_process.Px4StartRequest
Px4StatusResponse = px4_process.Px4StatusResponse
PX4_DEFAULT_DIR = px4_process.PX4_DEFAULT_DIR
PX4_LOG_DIR = px4_process.PX4_LOG_DIR
PX4_PID_FILE = px4_process.PX4_PID_FILE
PX4_MAVSDK_PORT = px4_process.PX4_MAVSDK_PORT
PX4_SIMULATOR_PORT = px4_process.PX4_SIMULATOR_PORT
PX4_MAVLINK_PORT = px4_process.PX4_MAVLINK_PORT
PX4_READY_TIMEOUT = px4_process.PX4_READY_TIMEOUT
PX4_DEMO_HOME_LAT = px4_process.PX4_DEMO_HOME_LAT
PX4_DEMO_HOME_LON = px4_process.PX4_DEMO_HOME_LON
PX4_DEMO_HOME_ALT = px4_process.PX4_DEMO_HOME_ALT
_ensure_pid_dir = px4_process.ensure_pid_dir
_write_pid_file = px4_process.write_pid_file
_read_pid_file = px4_process.read_pid_file
_clear_pid_file = px4_process.clear_pid_file
_is_process_alive = px4_process.is_process_alive
_is_port_open = px4_process.is_port_open
_build_gz_resource_path = px4_process.build_gz_resource_path
_read_proc_exe = px4_process.read_proc_exe
_read_proc_cmdline = px4_process.read_proc_cmdline
_is_px4_process = px4_process.is_px4_process
_find_running_px4_pid = px4_process.find_running_px4_pid


def _ensure_pid_dir() -> None:
    px4_process.ensure_runtime_dirs()
    PX4_PID_FILE.parent.mkdir(parents=True, exist_ok=True)


def _write_pid_file(pid: int, world: str, source: str) -> None:
    _ensure_pid_dir()
    with PX4_PID_FILE.open("w", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.write(
            json.dumps(
                {"pid": pid, "world": world, "source": source, "ts": time.time()},
                ensure_ascii=False,
            )
        )
        handle.flush()
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _read_pid_file() -> dict[str, Any] | None:
    if not PX4_PID_FILE.exists():
        return None
    try:
        with PX4_PID_FILE.open("r", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
            content = handle.read()
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        data = json.loads(content)
        pid = data.get("pid")
        if not isinstance(pid, int):
            return None
        return data
    except (OSError, json.JSONDecodeError, ValueError):
        return None


def _clear_pid_file() -> None:
    try:
        PX4_PID_FILE.unlink()
    except FileNotFoundError:
        pass


def _adopt_existing_px4(*, px4_dir: Path, world: str) -> dict[str, Any] | None:
    """Adopt an already-running PX4 SITL instance when the PID file is stale or missing."""
    if not _is_port_open(PX4_SIMULATOR_PORT) or not _is_port_open(PX4_MAVLINK_PORT):
        return None

    pid = _find_running_px4_pid(px4_dir=px4_dir)
    if pid is None:
        return None

    _write_pid_file(pid, world, "detected")
    return {
        "status": "already_running",
        "pid": str(pid),
        "world": world,
        "source": "detected",
        "ready": True,
    }


def _find_px4_pgid() -> int | None:
    """Find PX4 SITL process group via PID file."""
    info = _read_pid_file()
    if info is None:
        return None
    pid = info["pid"]
    if not _is_process_alive(pid):
        return None
    try:
        return os.getpgid(pid)
    except (ProcessLookupError, PermissionError):
        return None


def _kill_px4_process(pid: int) -> None:
    """Kill PX4 process group."""
    try:
        pgid = os.getpgid(pid)
        os.killpg(pgid, 15)
    except (ProcessLookupError, PermissionError):
        pass

    for _ in range(20):
        if not _is_process_alive(pid):
            break
        time.sleep(0.5)

    if _is_process_alive(pid):
        try:
            pgid = os.getpgid(pid)
            os.killpg(pgid, 9)
        except (ProcessLookupError, PermissionError):
            pass


async def ensure_px4_ready(request: Px4StartRequest | None = None) -> dict[str, Any]:
    """Ensure PX4 SITL is running and ready for MAVSDK connection."""
    request = request or Px4StartRequest()
    if request.skip_px4:
        return {"status": "skipped"}

    existing = _read_pid_file()
    px4_running = existing is not None and _is_process_alive(existing["pid"])

    if px4_running:
        if not _is_port_open(PX4_MAVLINK_PORT):
            raise HTTPException(status_code=503, detail="px4_not_ready")
        return {
            "status": "already_running",
            "pid": str(existing["pid"]),
            "world": existing.get("world", "unknown"),
            "source": existing.get("source", "unknown"),
            "ready": True,
        }

    start_result = await start_px4_demo(request)
    if start_result.get("status") not in ("started", "already_running"):
        raise HTTPException(status_code=500, detail="PX4 启动失败")
    return start_result


async def confirm_drone_takeoff() -> dict[str, Any]:
    """Confirm drone takeoff and ensure PX4 is ready if needed."""
    if deps.is_takeoff_confirmed():
        return {"status": "already_confirmed"}

    pending_request_id = deps.get_pending_takeoff_request_id()
    event = deps.takeoff_confirmation_event
    if event is None and pending_request_id is None:
        raise HTTPException(status_code=503, detail="takeoff_not_initialized")

    px4_info = await ensure_px4_ready()
    deps.mark_takeoff_confirmed()
    return {"status": "confirmed", "px4": px4_info}


async def start_px4_demo(request: Px4StartRequest) -> dict[str, Any]:
    """Start PX4 SITL + Gazebo for demo."""
    if request.skip_px4:
        return {"status": "skipped"}

    # Check if PX4 is already running (via PID file, covers script-started instances)
    existing = _read_pid_file()
    if existing is not None and _is_process_alive(existing["pid"]):
        return {
            "status": "already_running",
            "pid": str(existing["pid"]),
            "world": existing.get("world", "unknown"),
            "source": existing.get("source", "unknown"),
        }

    # Clean stale PID file
    _clear_pid_file()

    px4_dir = Path(request.px4_dir) if request.px4_dir else PX4_DEFAULT_DIR
    if not px4_dir.exists():
        raise HTTPException(status_code=400, detail=f"PX4 directory not found: {px4_dir}")

    makefile = px4_dir / "Makefile"
    if not makefile.exists():
        raise HTTPException(status_code=400, detail=f"PX4 Makefile not found: {makefile}")

    # Determine Gazebo world
    world = request.world
    if not world:
        gz_worlds = px4_dir / "Tools" / "simulation" / "gz" / "worlds"
        if gz_worlds.exists():
            for f in gz_worlds.iterdir():
                if "muye" in f.name.lower():
                    world = f.stem
                    break
        if not world:
            world = "default"

    adopted = _adopt_existing_px4(px4_dir=px4_dir, world=world)
    if adopted is not None:
        return adopted

    # Clean proxy env
    env = os.environ.copy()
    for key in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY",
                "all_proxy", "ALL_PROXY"):
        env.pop(key, None)

    env["PX4_GZ_WORLD"] = world
    env["PX4_SIM_SPEED_FACTOR"] = "1"
    env["PX4_HOME_LAT"] = PX4_DEMO_HOME_LAT
    env["PX4_HOME_LON"] = PX4_DEMO_HOME_LON
    env["PX4_HOME_ALT"] = PX4_DEMO_HOME_ALT

    env["GZ_SIM_RESOURCE_PATH"] = _build_gz_resource_path(
        px4_dir,
        env.get("GZ_SIM_RESOURCE_PATH", ""),
    )

    # Log file
    PX4_LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = PX4_LOG_DIR / "px4-sitl-demo.log"

    logger.info("Starting PX4 SITL: dir=%s world=%s", px4_dir, world)

    try:
        proc = subprocess.Popen(
            ["make", "px4_sitl", "gz_x500"],
            cwd=str(px4_dir),
            env=env,
            stdout=RotatingLogFile(log_path),
            stderr=subprocess.STDOUT,
            preexec_fn=os.setsid,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=f"Failed to start PX4: {e}")

    # Write PID file immediately
    _write_pid_file(proc.pid, world, "api")

    # Wait for MAVLink port to become available (PX4 binds 18570, not 14540)
    deadline = time.monotonic() + PX4_READY_TIMEOUT
    ready = False
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            adopted = _adopt_existing_px4(px4_dir=px4_dir, world=world)
            if adopted is not None:
                return adopted
            _clear_pid_file()
            raise HTTPException(
                status_code=500,
                detail=f"PX4 exited immediately (code {proc.returncode}). Check log: {log_path}",
            )
        if _is_port_open(PX4_MAVLINK_PORT):
            ready = True
            break
        await asyncio.sleep(1)

    if not ready:
        _kill_px4_process(proc.pid)
        _clear_pid_file()
        raise HTTPException(
            status_code=504,
            detail=f"PX4 MAVLink port {PX4_MAVLINK_PORT} not ready after {PX4_READY_TIMEOUT}s. Check log: {log_path}",
        )

    return {
        "status": "started",
        "pid": str(proc.pid),
        "world": world,
        "log": str(log_path),
        "ready": ready,
    }


async def stop_px4_demo() -> dict[str, str]:
    """Stop PX4 SITL process."""
    info = _read_pid_file()

    if info is None:
        return {"status": "not_running"}

    pid = info["pid"]
    source = info.get("source", "unknown")

    if not _is_process_alive(pid):
        _clear_pid_file()
        return {"status": "not_running"}

    _kill_px4_process(pid)
    _clear_pid_file()
    return {"status": "stopped", "pid": str(pid), "source": source}


async def get_px4_status() -> Px4StatusResponse:
    """Get PX4 SITL status — reads shared PID file, checks process + port."""
    info = _read_pid_file()

    if info is None:
        adopted = _adopt_existing_px4(px4_dir=PX4_DEFAULT_DIR, world="unknown")
        if adopted is None:
            return Px4StatusResponse(running=False, ready=False, pid=None, world=None, source=None)
        return Px4StatusResponse(
            running=True,
            ready=True,
            pid=int(adopted["pid"]),
            world=str(adopted["world"]),
            source=str(adopted["source"]),
        )

    pid = info["pid"]
    world = info.get("world")
    source = info.get("source")

    if not _is_process_alive(pid):
        adopted = _adopt_existing_px4(
            px4_dir=PX4_DEFAULT_DIR,
            world=str(world or "unknown"),
        )
        if adopted is not None:
            return Px4StatusResponse(
                running=True,
                ready=True,
                pid=int(adopted["pid"]),
                world=str(adopted["world"]),
                source=str(adopted["source"]),
            )
        _clear_pid_file()
        return Px4StatusResponse(running=False, ready=False, pid=None, world=world, source=source)

    ready = _is_port_open(PX4_MAVLINK_PORT)
    return Px4StatusResponse(running=True, ready=ready, pid=pid, world=world, source=source)


# DJI 无人机端点 — 全局后端实例
_dji_backend = None


def _load_drone_config() -> dict[str, Any]:
    config_path = Path(__file__).resolve().parent.parent.parent / "config" / "drone_config.json"
    if config_path.exists():
        return json.loads(config_path.read_text(encoding="utf-8"))
    return {}


def _get_dji_backend():
    global _dji_backend
    if _dji_backend is None:
        from modules.drone.backends.dji_osdk import DJIOSDKBackend
        drone_config = _load_drone_config()
        _dji_backend = DJIOSDKBackend(drone_config)
    return _dji_backend


async def get_dji_status() -> Any:
    backend = _get_dji_backend()
    return await backend.get_status()


async def get_dji_telemetry() -> Any:
    backend = _get_dji_backend()
    return await backend.get_telemetry()


async def connect_dji() -> Any:
    backend = _get_dji_backend()
    await backend.connect()
    return {"status": "connected", **(await backend.get_status())}


async def disconnect_dji() -> Any:
    backend = _get_dji_backend()
    await backend.disconnect()
    return {"status": "disconnected"}


async def get_density_map(request_id: str) -> Any:
    from modules.infra.sqlite_store import SqliteStore

    db_path = Path(os.getenv("MUYE_SQLITE_PATH", str(DATA_DIR / "muye.db")))
    store = SqliteStore(db_path)
    try:
        row = store.fetch_one(
            "SELECT drone_instruction FROM tasks WHERE request_id = ?",
            (request_id,),
        )
    finally:
        store.close()

    if not row or not row.get("drone_instruction"):
        raise HTTPException(status_code=404, detail="任务不存在或无无人机指令")

    instruction = row["drone_instruction"]
    if isinstance(instruction, str):
        instruction = json.loads(instruction)

    density_grid = instruction.get("density_grid") or []
    spray_schedule = instruction.get("spray_schedule") or []

    if not density_grid:
        raise HTTPException(status_code=404, detail="该任务无密度图数据")

    return {
        "request_id": request_id,
        "grid_rows": max(c["row"] for c in density_grid) + 1 if density_grid else 0,
        "grid_cols": max(c["col"] for c in density_grid) + 1 if density_grid else 0,
        "cells": density_grid,
        "spray_schedule": spray_schedule,
    }


def register_drone_routes(app: FastAPI) -> None:
    """Register drone routes."""
    app.post("/drone/confirm-takeoff")(confirm_drone_takeoff)
    app.post("/api/drone/confirm-takeoff", include_in_schema=False)(confirm_drone_takeoff)
    app.post("/drone/start-px4-demo")(start_px4_demo)
    app.post("/api/drone/start-px4-demo", include_in_schema=False)(start_px4_demo)
    app.post("/drone/stop-px4-demo")(stop_px4_demo)
    app.post("/api/drone/stop-px4-demo", include_in_schema=False)(stop_px4_demo)
    app.get("/drone/px4-status")(get_px4_status)
    app.get("/api/drone/px4-status", include_in_schema=False)(get_px4_status)

    # DJI 无人机端点
    app.get("/drone/dji/status")(get_dji_status)
    app.get("/api/drone/dji/status", include_in_schema=False)(get_dji_status)
    app.get("/drone/dji/telemetry")(get_dji_telemetry)
    app.get("/api/drone/dji/telemetry", include_in_schema=False)(get_dji_telemetry)
    app.post("/drone/dji/connect")(connect_dji)
    app.post("/api/drone/dji/connect", include_in_schema=False)(connect_dji)
    app.post("/drone/dji/disconnect")(disconnect_dji)
    app.post("/api/drone/dji/disconnect", include_in_schema=False)(disconnect_dji)

    # 密度图端点
    app.get("/drone/density-map")(get_density_map)
    app.get("/api/drone/density-map", include_in_schema=False)(get_density_map)
