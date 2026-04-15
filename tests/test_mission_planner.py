from __future__ import annotations

from modules.mission_planner import MissionPlanner


def build_planner() -> MissionPlanner:
    return MissionPlanner(
        {
            "altitude_range_m": [2.0, 8.0],
            "speed_range_mps": [1.0, 6.0],
            "spray_rate_range_lpm": [0.3, 3.0],
            "max_safe_wind_speed_mps": 8.0,
        }
    )


def test_mission_planner_generates_coverage_route_not_just_polygon_vertices() -> None:
    planner = build_planner()
    geofence = [
        [113.6241, 34.7467],
        [113.6257, 34.7467],
        [113.6257, 34.7479],
        [113.6241, 34.7479],
    ]

    plan = planner.plan_spray_mission(
        field_context={
            "field_id": "henan-zz-001",
            "name": "郑州示范田1号",
            "area_mu": 68.0,
            "geofence": geofence,
            "crop_cycle": {"crop_name": "冬小麦"},
        },
        current_weather={"wind_speed": 2.5},
    )

    route = plan["飞行路径"]
    assert len(route) > len(geofence)
    assert route != geofence
    assert route[0][1] == route[1][1]
    assert route[2][1] != route[0][1]
    assert plan["覆盖区域"]["coordinates"] == geofence
    assert plan["气象限制"]["最大风速"] <= 8.0
