#!/usr/bin/env python3
"""最简测试：MAVKSDK 能否控制 PX4 SITL。"""

import asyncio
import sys

async def main():
    from mavsdk import System

    addr = "udpin://0.0.0.0:14540"
    print(f"1. 连接 PX4: {addr}")
    drone = System()
    await drone.connect(system_address=addr)

    # 等连接
    async for state in drone.core.connection_state():
        if state.is_connected:
            print("   ✓ 已连接")
            break

    # 等定位
    print("2. 等待定位...")
    async for h in drone.telemetry.health():
        if h.is_global_position_ok or h.is_home_position_ok:
            print("   ✓ 定位就绪")
            break

    # 读取当前位置
    print("3. 读取当前位置...")
    pos = await drone.telemetry.position().__anext__()
    print(f"   当前: lat={pos.latitude_deg:.6f} lon={pos.longitude_deg:.6f} alt={pos.relative_altitude_m:.1f}m")

    # Arm
    print("4. Arm...")
    try:
        await drone.action.arm()
        print("   ✓ 已解锁")
    except Exception as e:
        print(f"   ✗ Arm 失败: {e}")
        return

    # 设置起飞高度
    target_alt = 3.0
    print(f"5. 设置起飞高度: {target_alt}m")
    try:
        await drone.action.set_takeoff_altitude(target_alt)
        print("   ✓ 已设置")
    except Exception as e:
        print(f"   设置失败: {e}")

    # Takeoff
    print("6. Takeoff...")
    try:
        await asyncio.wait_for(drone.action.takeoff(), timeout=10)
        print("   ✓ takeoff 调用完成")
    except asyncio.TimeoutError:
        print("   ⚠ takeoff 超时(10s)，继续监控...")
    except Exception as e:
        print(f"   ⚠ takeoff 异常: {e}")

    # 监控高度 30 秒
    print(f"7. 监控高度 30 秒 (目标 {target_alt}m)...")
    deadline = asyncio.get_event_loop().time() + 30
    async for pos in drone.telemetry.position():
        alt = pos.relative_altitude_m
        print(f"   高度: {alt:.1f}m  lat={pos.latitude_deg:.6f} lon={pos.longitude_deg:.6f}")
        if alt >= target_alt - 1.0:
            print(f"   ✓ 到达目标高度!")
            break
        if asyncio.get_event_loop().time() > deadline:
            print(f"   ⚠ 30秒超时, 当前 {alt:.1f}m")
            break

    # 读取飞行模式
    print("8. 读取飞行模式...")
    try:
        async for mode in drone.telemetry.flight_mode():
            print(f"   飞行模式: {mode}")
            break
    except Exception as e:
        print(f"   读取失败: {e}")

    # 尝试 goto
    target_lat = pos.latitude_deg + 0.0001  # ~11m
    target_lon = pos.longitude_deg
    print(f"9. goto_location: lat={target_lat:.6f} lon={target_lon:.6f} alt={target_alt}m")
    try:
        await drone.action.goto_location(target_lat, target_lon, target_alt, 0)
        print("   ✓ goto 调用成功")
    except Exception as e:
        print(f"   ✗ goto 失败: {e}")

    # 监控位置 20 秒
    print("10. 监控位置 20 秒...")
    deadline = asyncio.get_event_loop().time() + 20
    async for pos in drone.telemetry.position():
        print(f"    pos: alt={pos.relative_altitude_m:.1f} lat={pos.latitude_deg:.6f} lon={pos.longitude_deg:.6f}")
        if asyncio.get_event_loop().time() > deadline:
            break

    print("\n测试完成。")

if __name__ == "__main__":
    asyncio.run(main())
