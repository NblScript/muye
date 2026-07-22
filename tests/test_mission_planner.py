from __future__ import annotations

from modules.drone.mission_planner import MissionPlanner


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


def test_mission_planner_uses_presentation_profile_for_visible_demo_route() -> None:
    planner = build_planner()
    geofence = [
        [8.545541, 47.397707],
        [8.545647, 47.397707],
        [8.545647, 47.397777],
        [8.545541, 47.397777],
    ]

    default_plan = planner.plan_spray_mission(
        field_context={
            "field_id": "px4-sitl-demo",
            "name": "PX4 SITL 展示地块",
            "area_mu": 2.0,
            "geofence": geofence,
            "crop_cycle": {"crop_name": "SITL 测试作物"},
        },
        current_weather={"wind_speed": 3.3},
    )
    presentation_plan = planner.plan_spray_mission(
        field_context={
            "field_id": "px4-sitl-demo",
            "name": "PX4 SITL 展示地块",
            "area_mu": 2.0,
            "geofence": geofence,
            "presentation_profile": {
                "target_speed_mps": 1.0,
                "lane_spacing_m": 2.0,
                "acceptance_radius_m": 0.15,
                "waypoint_loiter_time_s": 0.0,
                "fly_through": False,
                "turn_mode": "in_place",
                "turn_loiter_time_s": 0.8,
            },
            "crop_cycle": {"crop_name": "SITL 测试作物"},
        },
        current_weather={"wind_speed": 3.3},
    )

    assert default_plan["速度"] > presentation_plan["速度"]
    assert presentation_plan["速度"] == 1.0
    assert len(presentation_plan["飞行路径"]) > len(default_plan["飞行路径"])
    assert presentation_plan["航点控制"] == {
        "接受半径": 0.15,
        "到点停留秒数": 0.0,
        "飞越航点": False,
        "转弯模式": "in_place",
        "转弯停留秒数": 0.8,
    }


def test_mission_planner_prefers_explicit_demo_route_over_generated_sweep() -> None:
    planner = build_planner()
    geofence = [
        [8.545541, 47.397707],
        [8.545647, 47.397707],
        [8.545647, 47.397777],
        [8.545541, 47.397777],
    ]
    explicit_route = [
        [8.545541, 47.397711],
        [8.545647, 47.397711],
        [8.545647, 47.397719],
        [8.545541, 47.397719],
        [8.545541, 47.397727],
        [8.545647, 47.397727],
    ]

    plan = planner.plan_spray_mission(
        field_context={
            "field_id": "px4-sitl-demo",
            "name": "PX4 SITL 展示地块",
            "area_mu": 0.12,
            "geofence": geofence,
            "explicit_route": explicit_route,
            "presentation_profile": {
                "target_speed_mps": 1.0,
                "lane_spacing_m": 2.0,
            },
            "crop_cycle": {"crop_name": "SITL 测试作物"},
        },
        current_weather={"wind_speed": 3.3},
    )

    assert plan["飞行路径"] == explicit_route
