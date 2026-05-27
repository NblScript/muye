from __future__ import annotations

import json
from pathlib import Path

from app.services import px4_process_service as service


def test_px4_service_pid_file_round_trip(monkeypatch, tmp_path: Path) -> None:
    pid_file = tmp_path / "px4.pid"
    monkeypatch.setattr(service, "PX4_PID_FILE", pid_file)

    service.write_pid_file(12345, "muye_world", "api")

    payload = service.read_pid_file()
    assert payload is not None
    assert payload["pid"] == 12345
    assert payload["world"] == "muye_world"
    assert payload["source"] == "api"

    service.clear_pid_file()
    assert service.read_pid_file() is None


def test_px4_service_rejects_invalid_pid_file(monkeypatch, tmp_path: Path) -> None:
    pid_file = tmp_path / "px4.pid"
    pid_file.write_text(json.dumps({"pid": "not-int"}), encoding="utf-8")
    monkeypatch.setattr(service, "PX4_PID_FILE", pid_file)

    assert service.read_pid_file() is None


def test_px4_service_builds_unique_gazebo_resource_path(tmp_path: Path) -> None:
    px4_dir = tmp_path / "PX4-Autopilot"
    path = service.build_gz_resource_path(px4_dir, f"{px4_dir}/Tools/simulation/gz/models:/custom")

    parts = path.split(":")
    assert str(px4_dir / "Tools" / "simulation" / "gz" / "models") in parts
    assert "/custom" in parts
    assert len(parts) == len(set(parts))
