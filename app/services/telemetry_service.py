"""Compatibility shim — TelemetryService moved to modules.infra.telemetry."""

from __future__ import annotations

from modules.infra.telemetry import (
    TelemetryBuffer,
    TelemetryService,
    get_telemetry_service,
)

__all__ = ["TelemetryBuffer", "TelemetryService", "get_telemetry_service"]
