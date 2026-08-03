from __future__ import annotations

import math

from modules.drone.density_map import DensityMap

GEOFENCE = [
    [8.5454, 47.3972],
    [8.5454, 47.3982],
    [8.5464, 47.3982],
    [8.5464, 47.3972],
]


def test_density_map_add_detections_with_bbox() -> None:
    dm = DensityMap(GEOFENCE, grid_rows=4, grid_cols=4)

    detections = [
        {
            "pest_type": "aphid",
            "confidence": 0.9,
            "position": {"x1": 0, "y1": 0, "x2": 100, "y2": 100},
        },
        {
            "pest_type": "aphid",
            "confidence": 0.7,
            "position": {"x1": 300, "y1": 300, "x2": 400, "y2": 400},
        },
    ]

    dm.add_detections(detections, image_width=640, image_height=480)

    grid = dm.to_grid()
    assert len(grid) == 4
    assert len(grid[0]) == 4

    total_density = sum(sum(row) for row in grid)
    assert total_density > 0

    max_cell = max(max(row) for row in grid)
    assert max_cell == 1.0
    assert dm.has_data is True
    assert dm.accepted_detections == 2
    assert dm.rejected_detections == 0


def test_density_map_empty_detections() -> None:
    dm = DensityMap(GEOFENCE, grid_rows=4, grid_cols=4)
    dm.add_detections([], image_width=640, image_height=480)

    grid = dm.to_grid()
    assert all(cell == 0.0 for row in grid for cell in row)


def test_density_map_geo_grid() -> None:
    dm = DensityMap(GEOFENCE, grid_rows=2, grid_cols=2)
    cells = dm.to_geo_grid()

    assert len(cells) == 4
    assert cells[0]["row"] == 0
    assert cells[0]["col"] == 0
    assert cells[0]["density"] == 0.0
    assert len(cells[0]["bounds"]) == 2

    lon1, lat1 = cells[0]["bounds"][0]
    lon2, lat2 = cells[0]["bounds"][1]
    assert lon2 > lon1
    assert lat2 > lat1
    assert cells[0]["bounds"][0][1] > cells[-1]["bounds"][0][1]


def test_density_map_suggest_spray_rates() -> None:
    dm = DensityMap(GEOFENCE, grid_rows=4, grid_cols=4)

    detections = [
        {
            "pest_type": "aphid",
            "confidence": 0.95,
            "position": {"x1": 0, "y1": 0, "x2": 50, "y2": 50},
        },
        {
            "pest_type": "aphid",
            "confidence": 0.90,
            "position": {"x1": 10, "y1": 10, "x2": 60, "y2": 60},
        },
    ]
    dm.add_detections(detections, image_width=640, image_height=480)

    rates = dm.suggest_spray_rates(
        base_rate=1.0,
        rate_range=[0.3, 3.0],
        lane_count=4,
    )

    assert len(rates) == 4
    for rate in rates:
        assert 0.3 <= rate <= 3.0


def test_density_map_concentrated_detections_produce_hotspot() -> None:
    dm = DensityMap(GEOFENCE, grid_rows=4, grid_cols=4)

    detections = []
    for i in range(5):
        detections.append({
            "pest_type": "aphid",
            "confidence": 0.9,
            "position": {"x1": 10 + i, "y1": 10 + i, "x2": 30 + i, "y2": 30 + i},
        })

    dm.add_detections(detections, image_width=640, image_height=480)

    grid = dm.to_grid()
    nonzero_cells = [(r, c) for r in range(4) for c in range(4) if grid[r][c] > 0]
    assert len(nonzero_cells) <= 2
    max_cell = max(max(row) for row in grid)
    assert max_cell == 1.0


def test_density_map_reads_pixel_dimensions_from_detection_contract() -> None:
    dm = DensityMap(GEOFENCE, grid_rows=4, grid_cols=4)
    dm.add_detections([{
        "pest_type": "aphid",
        "confidence": 0.9,
        "position": {
            "x1": 480,
            "y1": 120,
            "x2": 560,
            "y2": 200,
            "coordinate_space": "image_pixel",
            "image_width": 640,
            "image_height": 480,
        },
    }])

    grid = dm.to_grid()
    assert grid[1][3] == 1.0
    assert dm.metadata() == {
        "source": "yolo_bbox",
        "density_kind": "relative_detection_weight",
        "coordinate_space": "image_normalized",
        "projection": "image_frame_to_geofence_bbox",
        "normalization": "max_cell_weight",
        "grid_rows": 4,
        "grid_cols": 4,
        "detection_count": 1,
        "accepted_detection_count": 1,
        "rejected_detection_count": 0,
        "is_simulated": False,
    }


def test_density_map_rejects_pixel_bbox_without_dimensions() -> None:
    dm = DensityMap(GEOFENCE, grid_rows=4, grid_cols=4)
    dm.add_detections([{
        "pest_type": "aphid",
        "confidence": 0.9,
        "position": {"x1": 100, "y1": 100, "x2": 150, "y2": 150},
    }])

    assert dm.has_data is False
    assert dm.accepted_detections == 0
    assert dm.rejected_detections == 1
    assert all(cell == 0 for row in dm.to_grid() for cell in row)
