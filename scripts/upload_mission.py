#!/usr/bin/env python3
"""将配置文件中的 explicit_route 上传为 PX4 Mission。

用法: python scripts/upload_mission.py [--config config/drone_config.json]
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path


async def upload(config_path: str) -> None:
    try:
        from mavsdk import System
        from mavsdk.mission import MissionItem, MissionPlan
    except ImportError:
        print("错误: 需要安装 mavsdk (pip install mavsdk)", file=sys.stderr)
        sys.exit(1)

    cfg = json.loads(Path(config_path).read_text())

    # 从 demo_field 或 field 取 explicit_route
    demo_field = cfg.get("px4", {}).get("demo_field", {})
    field = cfg.get("field", {})
    route = demo_field.get("explicit_route") or field.get("explicit_route")
    if not route or len(route) < 2:
        print("错误: 配置中没有 explicit_route 或航点不足", file=sys.stderr)
        sys.exit(1)

    px4_cfg = cfg.get("px4", {})
    addr = px4_cfg.get("system_address", "udpout://127.0.0.1:18570")
    # 确保使用正确的连接格式
    if "14540" in addr or "14580" in addr:
        addr = "udpout://127.0.0.1:18570"
    elif addr.startswith("udp://"):
        addr = addr.replace("udp://", "udpout://")

    # MissionItem 的 relative_altitude_m 是相对高度
    # PX4 SITL 高度读数有bug，设为0保持当前高度，只控制水平移动
    rel_alt = 0.0
    speed = float(demo_field.get("presentation_profile", {}).get("target_speed_mps", 4.5))
    accept_r = float(demo_field.get("presentation_profile", {}).get("acceptance_radius_m",
                     px4_cfg.get("acceptance_radius_m", 1.0)))

    print(f"连接 PX4: {addr}")
    drone = System()
    await drone.connect(system_address=addr)

    # 等待连接
    async for state in drone.core.connection_state():
        if state.is_connected:
            print("PX4 已连接")
            break

    # 等待定位
    async for health in drone.telemetry.health():
        if health.is_global_position_ok or health.is_home_position_ok:
            print("定位已就绪")
            break

    # 清除旧任务
    try:
        await drone.mission.clear_mission()
        print("已清除旧任务")
    except Exception:
        pass

    # 构建任务
    items = []
    for lon, lat in route:
        items.append(MissionItem(
            lat, lon, rel_alt, speed,
            is_fly_through=True,
            gimbal_pitch_deg=float("nan"),
            gimbal_yaw_deg=float("nan"),
            camera_action=MissionItem.CameraAction.NONE,
            loiter_time_s=0.0,
            camera_photo_interval_s=float("nan"),
            acceptance_radius_m=accept_r,
            yaw_deg=float("nan"),
            camera_photo_distance_m=float("nan"),
            vehicle_action=MissionItem.VehicleAction.NONE,
        ))

    plan = MissionPlan(items)
    await drone.mission.upload_mission(plan)
    print(f"已上传 {len(items)} 个航点, 相对高度 {rel_alt}m, 速度 {speed}m/s")

    for i, (lon, lat) in enumerate(route):
        print(f"  航点 {i+1}: lat={lat:.6f}, lon={lon:.6f}")

    print("\n航线上传完成！现在可以在前端点击'确认起飞'了。")


def main() -> None:
    parser = argparse.ArgumentParser(description="上传航线到 PX4")
    parser.add_argument("--config", default="config/drone_config.json", help="配置文件路径")
    args = parser.parse_args()
    asyncio.run(upload(args.config))


if __name__ == "__main__":
    main()
