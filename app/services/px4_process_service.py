"""PX4 SITL process helpers shared by drone routes and health checks."""

from __future__ import annotations

import fcntl
import json
import os
import socket
import subprocess
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from modules.infra.common import DATA_DIR, ensure_runtime_dirs


PX4_DEFAULT_DIR = Path.home() / "PX4-Autopilot"
PX4_LOG_DIR = DATA_DIR / "logs"
PX4_PID_FILE = DATA_DIR / "runtime" / "px4.pid"
PX4_MAVSDK_PORT = 14540
PX4_SIMULATOR_PORT = 14580
PX4_MAVLINK_PORT = 18570
PX4_READY_TIMEOUT = 90
PX4_DEMO_HOME_LAT = "47.397742"
PX4_DEMO_HOME_LON = "8.545594"
PX4_DEMO_HOME_ALT = "0"


class RotatingLogFile:
    """File-like wrapper that truncates and rewinds when size limit is reached."""

    def __init__(self, path: Path, max_bytes: int = 4 * 1024 * 1024 * 1024):
        self._path = path
        self._max_bytes = max_bytes
        self._file = open(path, "w")
        self._size = 0

    def write(self, data: str) -> int:
        n = self._file.write(data)
        self._size += n
        if self._size >= self._max_bytes:
            self._file.close()
            self._file = open(self._path, "w")
            self._size = 0
        return n

    def flush(self) -> None:
        self._file.flush()

    def fileno(self) -> int:
        return self._file.fileno()

    def close(self) -> None:
        self._file.close()


class Px4StartRequest(BaseModel):
    px4_dir: str | None = None
    world: str | None = None
    skip_px4: bool = False


class Px4StatusResponse(BaseModel):
    running: bool
    ready: bool
    pid: int | None = None
    world: str | None = None
    source: str | None = None


def ensure_pid_dir() -> None:
    ensure_runtime_dirs()
    PX4_PID_FILE.parent.mkdir(parents=True, exist_ok=True)


def write_pid_file(pid: int, world: str, source: str) -> None:
    ensure_pid_dir()
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


def read_pid_file() -> dict[str, Any] | None:
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


def clear_pid_file() -> None:
    try:
        PX4_PID_FILE.unlink()
    except FileNotFoundError:
        pass


def is_process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def is_port_open(port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(timeout)
            sock.bind(("", port))
            return False
    except OSError:
        return True


def build_gz_resource_path(px4_dir: Path, existing_value: str = "") -> str:
    """Build a Gazebo resource path compatible with PX4's nested model repo layout."""
    candidates = [
        px4_dir / "Tools" / "simulation" / "gz" / "models" / "models",
        px4_dir / "Tools" / "simulation" / "gz" / "models" / "worlds",
        px4_dir / "Tools" / "simulation" / "gz" / "models",
        px4_dir / "Tools" / "simulation" / "gz" / "worlds",
    ]
    merged: list[str] = []
    for value in [str(path) for path in candidates] + existing_value.split(":"):
        normalized = value.strip()
        if normalized and normalized not in merged:
            merged.append(normalized)
    return ":".join(merged)


def read_proc_exe(pid: int) -> str | None:
    try:
        return os.readlink(f"/proc/{pid}/exe")
    except OSError:
        return None


def read_proc_cmdline(pid: int) -> str:
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return ""
    return raw.replace(b"\x00", b" ").decode("utf-8", errors="ignore").strip()


def is_px4_process(pid: int, px4_dir: Path | None = None) -> bool:
    exe = read_proc_exe(pid)
    expected_exe = str(px4_dir / "build" / "px4_sitl_default" / "bin" / "px4") if px4_dir else None

    if exe:
        if expected_exe and exe == expected_exe:
            return True
        if Path(exe).name == "px4" and "px4_sitl_default" in exe:
            return True

    cmdline = read_proc_cmdline(pid)
    if expected_exe and expected_exe in cmdline:
        return True
    return "px4_sitl_default/bin/px4" in cmdline


def find_running_px4_pid(px4_dir: Path | None = None) -> int | None:
    pids: list[int] = []
    try:
        proc_entries = sorted(Path("/proc").iterdir(), key=lambda entry: entry.name, reverse=True)
    except OSError:
        return None

    for entry in proc_entries:
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        if is_px4_process(pid, px4_dir=px4_dir):
            pids.append(pid)
    return pids[0] if pids else None


def adopt_existing_px4(*, px4_dir: Path, world: str) -> dict[str, Any] | None:
    """Adopt an already-running PX4 SITL instance when the PID file is stale or missing."""
    if not is_port_open(PX4_SIMULATOR_PORT) or not is_port_open(PX4_MAVLINK_PORT):
        return None

    pid = find_running_px4_pid(px4_dir=px4_dir)
    if pid is None:
        return None

    write_pid_file(pid, world, "detected")
    return {
        "status": "already_running",
        "pid": str(pid),
        "world": world,
        "source": "detected",
        "ready": True,
    }


def find_px4_pgid() -> int | None:
    """Find PX4 SITL process group via PID file."""
    info = read_pid_file()
    if info is None:
        return None
    pid = info["pid"]
    if not is_process_alive(pid):
        return None
    try:
        return os.getpgid(pid)
    except (ProcessLookupError, PermissionError):
        return None


def kill_px4_process(pid: int) -> None:
    """Kill PX4 process group."""
    try:
        pgid = os.getpgid(pid)
        os.killpg(pgid, 15)
    except (ProcessLookupError, PermissionError):
        pass

    for _ in range(20):
        if not is_process_alive(pid):
            break
        time.sleep(0.5)

    if is_process_alive(pid):
        try:
            pgid = os.getpgid(pid)
            os.killpg(pgid, 9)
        except (ProcessLookupError, PermissionError):
            pass
