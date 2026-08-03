from __future__ import annotations

from app.services.pipeline_planning_service import detection_has_bbox, plan_spray_mission


class FakePlanner:
    def __init__(self) -> None:
        self.variable_called = False

    def plan_variable_rate_mission(self, *, field_context, current_weather, density_map):
        self.variable_called = True
        return {
            "mode": "variable",
            "density_grid": [{"row": 0, "col": 0}],
            "spray_schedule": [{"lane": 1}],
        }


class FakeDroneController:
    def __init__(self) -> None:
        self.planner = FakePlanner()
        self.uniform_called = False

    def plan_spray_mission(self, *, field_context, current_weather):
        self.uniform_called = True
        return {"mode": "uniform"}


def test_detection_has_bbox_accepts_position_or_bbox_dict() -> None:
    assert detection_has_bbox([{"position": {"x1": 1, "y1": 2, "x2": 3, "y2": 4}}]) is True
    assert detection_has_bbox([{"bbox": {"x": 1, "y": 2, "w": 3, "h": 4}}]) is True
    assert detection_has_bbox([{"position": {"x1": 1}}]) is False
    assert detection_has_bbox([{"position": []}]) is False


def test_plan_spray_mission_uses_variable_rate_when_bbox_and_geofence_exist() -> None:
    controller = FakeDroneController()

    plan = plan_spray_mission(
        drone_controller=controller,
        field_context={"geofence": [[0, 0], [0, 1], [1, 1]]},
        current_weather={"wind_speed": "3.3"},
        detections=[{
            "confidence": 0.9,
            "position": {
                "x1": 100,
                "y1": 120,
                "x2": 180,
                "y2": 220,
                "coordinate_space": "image_pixel",
                "image_width": 640,
                "image_height": 480,
            },
        }],
    )

    assert plan["mode"] == "variable"
    assert controller.planner.variable_called is True
    assert controller.uniform_called is False


def test_plan_spray_mission_falls_back_to_uniform_without_bbox() -> None:
    controller = FakeDroneController()

    plan = plan_spray_mission(
        drone_controller=controller,
        field_context={"geofence": [[0, 0], [0, 1], [1, 1]]},
        current_weather={},
        detections=[{"confidence": 0.9}],
    )

    assert plan == {"mode": "uniform"}
    assert controller.uniform_called is True


def test_plan_spray_mission_rejects_ambiguous_pixel_bbox_without_image_size() -> None:
    controller = FakeDroneController()

    plan = plan_spray_mission(
        drone_controller=controller,
        field_context={"geofence": [[0, 0], [0, 1], [1, 1]]},
        current_weather={},
        detections=[{
            "confidence": 0.9,
            "position": {"x1": 100, "y1": 120, "x2": 180, "y2": 220},
        }],
    )

    assert plan == {"mode": "uniform"}
    assert controller.planner.variable_called is False
    assert controller.uniform_called is True
