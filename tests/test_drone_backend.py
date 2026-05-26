"""Tests for the drone backend abstraction layer."""

from __future__ import annotations

import pytest

from modules.drone.backends import BACKEND_REGISTRY, resolve_backend
from modules.drone.backends.base import DroneBackend
from modules.drone.backends.px4_backend import PX4Backend


def build_config(backend: str = "px4") -> dict:
    return {
        "execution": {"backend": backend},
        "network": {"ip_whitelist": []},
        "flight_constraints": {},
        "px4": {"prefer_demo_field": False},
    }


def test_backend_registry_contains_px4():
    assert "px4" in BACKEND_REGISTRY
    assert BACKEND_REGISTRY["px4"] is PX4Backend


def test_backend_registry_contains_dji_osdk():
    assert "dji_osdk" in BACKEND_REGISTRY


def test_px4_backend_is_drone_backend():
    backend = PX4Backend(build_config())
    assert isinstance(backend, DroneBackend)


@pytest.mark.asyncio
async def test_px4_backend_connect_disconnect():
    backend = PX4Backend(build_config())
    await backend.connect()
    await backend.disconnect()


def test_resolve_backend_px4():
    backend = resolve_backend("px4", build_config())
    assert isinstance(backend, PX4Backend)


def test_resolve_backend_unknown_falls_back_to_px4():
    backend = resolve_backend("unknown_backend", build_config())
    assert isinstance(backend, PX4Backend)


def test_resolve_backend_dji_osdk():
    from modules.drone.backends.dji_osdk import DJIOSDKBackend
    backend = resolve_backend("dji_osdk", build_config("dji_osdk"))
    assert isinstance(backend, DJIOSDKBackend)
