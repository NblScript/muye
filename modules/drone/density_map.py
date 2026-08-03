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
        if grid_rows <= 0 or grid_cols <= 0:
            raise ValueError("grid dimensions must be positive")

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
        if self.lon_span <= 0 or self.lat_span <= 0:
            raise ValueError("geofence must span both longitude and latitude")

        self._grid: list[list[float]] = [
            [0.0] * grid_cols for _ in range(grid_rows)
        ]
        self._max_weight = 0.0
        self.total_detections = 0
        self.accepted_detections = 0
        self.rejected_detections = 0

    def add_detections(
        self,
        detections: list[dict[str, Any]],
        *,
        image_width: int | None = None,
        image_height: int | None = None,
    ) -> None:
        for det in detections:
            self.total_detections += 1
            pos = det.get("position") or det.get("bbox") or {}
            try:
                confidence = float(det.get("confidence", 0.5))
            except (TypeError, ValueError):
                self.rejected_detections += 1
                continue
            if not math.isfinite(confidence) or confidence <= 0:
                self.rejected_detections += 1
                continue
            confidence = min(confidence, 1.0)

            nx, ny = self._normalize_position(pos, image_width, image_height)
            if nx is None or ny is None:
                self.rejected_detections += 1
                continue

            col = min(int(nx * self.grid_cols), self.grid_cols - 1)
            row = min(int(ny * self.grid_rows), self.grid_rows - 1)
            self._grid[row][col] += confidence
            self._max_weight = max(self._max_weight, self._grid[row][col])
            self.accepted_detections += 1

    @property
    def has_data(self) -> bool:
        return self.accepted_detections > 0 and self._max_weight > 0

    def metadata(self) -> dict[str, Any]:
        return {
            "source": "yolo_bbox",
            "density_kind": "relative_detection_weight",
            "coordinate_space": "image_normalized",
            "projection": "image_frame_to_geofence_bbox",
            "normalization": "max_cell_weight",
            "grid_rows": self.grid_rows,
            "grid_cols": self.grid_cols,
            "detection_count": self.total_detections,
            "accepted_detection_count": self.accepted_detections,
            "rejected_detection_count": self.rejected_detections,
            "is_simulated": False,
        }

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
                # Image rows start at the top. Map row 0 to the northern edge
                # of the field bounding box so the heat surface is not flipped.
                lat1 = self.max_lat - (r + 1) * cell_lat
                lat2 = self.max_lat - r * cell_lat
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
            return self._validate_normalized(pos[0], pos[1])

        if not isinstance(pos, dict):
            return None, None

        coordinate_space = str(pos.get("coordinate_space") or "").strip().lower()
        width = image_width or self._positive_num(pos.get("image_width"))
        height = image_height or self._positive_num(pos.get("image_height"))

        if "x" in pos and "y" in pos:
            return self._normalize_xy(
                self._num(pos.get("x")),
                self._num(pos.get("y")),
                coordinate_space=coordinate_space,
                image_width=width,
                image_height=height,
            )

        x1 = self._num(pos.get("x1"))
        y1 = self._num(pos.get("y1"))
        x2 = self._num(pos.get("x2"))
        y2 = self._num(pos.get("y2"))

        if x1 is None or y1 is None or x2 is None or y2 is None:
            cx = self._num(pos.get("cx"))
            cy = self._num(pos.get("cy"))
            if cx is None:
                cx = self._num(pos.get("x"))
            if cy is None:
                cy = self._num(pos.get("y"))
            if cx is not None and cy is not None:
                return self._normalize_xy(
                    cx,
                    cy,
                    coordinate_space=coordinate_space,
                    image_width=width,
                    image_height=height,
                )
            return None, None

        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2

        return self._normalize_xy(
            cx,
            cy,
            coordinate_space=coordinate_space,
            image_width=width,
            image_height=height,
            bbox_values=(x1, y1, x2, y2),
        )

    def _normalize_xy(
        self,
        x: float | None,
        y: float | None,
        *,
        coordinate_space: str,
        image_width: float | None,
        image_height: float | None,
        bbox_values: tuple[float, float, float, float] | None = None,
    ) -> tuple[float | None, float | None]:
        if x is None or y is None:
            return None, None

        normalized_spaces = {"normalized", "image_normalized", "xyxyn", "xywhn"}
        pixel_spaces = {"pixel", "pixels", "image_pixel", "xyxy", "xywh"}
        values = bbox_values or (x, y)
        values_are_normalized = all(math.isfinite(value) and 0 <= value <= 1 for value in values)

        if coordinate_space in normalized_spaces or (not coordinate_space and values_are_normalized):
            return self._validate_normalized(x, y)

        if coordinate_space and coordinate_space not in pixel_spaces:
            return None, None
        if image_width is None or image_height is None:
            return None, None
        return self._validate_normalized(x / image_width, y / image_height)

    @staticmethod
    def _validate_normalized(x: Any, y: Any) -> tuple[float | None, float | None]:
        try:
            nx = float(x)
            ny = float(y)
        except (TypeError, ValueError):
            return None, None
        if not math.isfinite(nx) or not math.isfinite(ny):
            return None, None
        if not (0 <= nx <= 1 and 0 <= ny <= 1):
            return None, None
        return nx, ny

    @staticmethod
    def _num(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _positive_num(cls, value: Any) -> float | None:
        number = cls._num(value)
        if number is None or not math.isfinite(number) or number <= 0:
            return None
        return number

    @staticmethod
    def _clamp(value: float, value_range: list[float]) -> float:
        return max(float(value_range[0]), min(float(value_range[1]), value))
