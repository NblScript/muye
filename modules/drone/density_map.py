"""Density map computation for variable-rate spray optimization."""

from __future__ import annotations

import math
from typing import Any


class DensityMap:
    """Map pest detections onto a geographic grid over a field."""

    def __init__(
        self,
        geofence: list[list[float]],
        *,
        grid_rows: int = 8,
        grid_cols: int = 10,
    ) -> None:
        if len(geofence) < 3:
            raise ValueError("geofence must have at least 3 points")

        self.geofence = geofence
        self.grid_rows = grid_rows
        self.grid_cols = grid_cols

        lons = [p[0] for p in geofence]
        lats = [p[1] for p in geofence]
        self.min_lon = min(lons)
        self.max_lon = max(lons)
        self.min_lat = min(lats)
        self.max_lat = max(lats)
        self.lon_span = self.max_lon - self.min_lon
        self.lat_span = self.max_lat - self.min_lat

        self._grid: list[list[float]] = [
            [0.0] * grid_cols for _ in range(grid_rows)
        ]
        self._max_weight = 0.0

    def add_detections(
        self,
        detections: list[dict[str, Any]],
        *,
        image_width: int | None = None,
        image_height: int | None = None,
    ) -> None:
        for det in detections:
            pos = det.get("position") or det.get("bbox") or {}
            confidence = float(det.get("confidence", 0.5))

            nx, ny = self._normalize_position(pos, image_width, image_height)
            if nx is None or ny is None:
                continue

            col = min(int(nx * self.grid_cols), self.grid_cols - 1)
            row = min(int(ny * self.grid_rows), self.grid_rows - 1)
            self._grid[row][col] += confidence
            self._max_weight = max(self._max_weight, self._grid[row][col])

    def to_grid(self) -> list[list[float]]:
        if self._max_weight <= 0:
            return self._grid
        return [
            [cell / self._max_weight for cell in row]
            for row in self._grid
        ]

    def to_geo_grid(self) -> list[dict[str, Any]]:
        grid = self.to_grid()
        cells: list[dict[str, Any]] = []
        cell_lon = self.lon_span / self.grid_cols if self.grid_cols > 0 else 0
        cell_lat = self.lat_span / self.grid_rows if self.grid_rows > 0 else 0

        for r in range(self.grid_rows):
            for c in range(self.grid_cols):
                lat1 = self.min_lat + r * cell_lat
                lat2 = lat1 + cell_lat
                lon1 = self.min_lon + c * cell_lon
                lon2 = lon1 + cell_lon
                cells.append({
                    "row": r,
                    "col": c,
                    "density": round(grid[r][c], 4),
                    "bounds": [
                        [round(lon1, 7), round(lat1, 7)],
                        [round(lon2, 7), round(lat2, 7)],
                    ],
                })
        return cells

    def suggest_spray_rates(
        self,
        *,
        base_rate: float,
        rate_range: list[float],
        lane_count: int,
    ) -> list[float]:
        grid = self.to_grid()
        rates: list[float] = []
        for lane in range(lane_count):
            row_idx = min(
                int(lane * self.grid_rows / max(lane_count, 1)),
                self.grid_rows - 1,
            )
            row_density = max(grid[row_idx]) if self.grid_cols > 0 else 0.0
            if row_density >= 0.6:
                rate = base_rate * 1.5
            elif row_density >= 0.3:
                rate = base_rate
            else:
                rate = base_rate * 0.5
            rates.append(self._clamp(rate, rate_range))
        return rates

    def _normalize_position(
        self,
        pos: dict[str, Any] | list[Any],
        image_width: int | None,
        image_height: int | None,
    ) -> tuple[float | None, float | None]:
        if isinstance(pos, (list, tuple)) and len(pos) >= 2:
            return float(pos[0]), float(pos[1])

        if not isinstance(pos, dict):
            return None, None

        if "x" in pos and "y" in pos:
            return float(pos["x"]), float(pos["y"])

        x1 = self._num(pos.get("x1"))
        y1 = self._num(pos.get("y1"))
        x2 = self._num(pos.get("x2"))
        y2 = self._num(pos.get("y2"))

        if x1 is None or y1 is None or x2 is None or y2 is None:
            cx = self._num(pos.get("cx")) or self._num(pos.get("x"))
            cy = self._num(pos.get("cy")) or self._num(pos.get("y"))
            if cx is not None and cy is not None:
                if image_width and image_height:
                    return cx / image_width, cy / image_height
                return cx, cy
            return None, None

        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2

        w = image_width or self._num(pos.get("image_width")) or 1
        h = image_height or self._num(pos.get("image_height")) or 1
        if w <= 0:
            w = 1
        if h <= 0:
            h = 1

        return cx / w, cy / h

    @staticmethod
    def _num(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _clamp(value: float, value_range: list[float]) -> float:
        return max(float(value_range[0]), min(float(value_range[1]), value))
