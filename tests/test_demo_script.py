from __future__ import annotations

from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEMO_SH = ROOT_DIR / "scripts" / "demo.sh"


def test_demo_script_uses_strict_readiness_checks() -> None:
    content = DEMO_SH.read_text(encoding="utf-8")

    assert 'curl -fsS "$url"' in content
    assert 'curl -s "$url"' not in content
    assert 'http://127.0.0.1:${API_PORT}/live' in content
    assert 'wait_for_url' in content


def test_demo_script_seeds_stages_in_order() -> None:
    content = DEMO_SH.read_text(encoding="utf-8")

    assert 'seed_stage "patrol" "播种巡检数据"' in content
    assert 'seed_stage "detect" "播种检测数据"' in content
    assert 'seed_stage "decide" "播种决策数据"' in content
    assert '--stage clear' in content


def test_demo_script_is_animation_demo_not_real_chain() -> None:
    content = DEMO_SH.read_text(encoding="utf-8")

    assert 'PX4_EXECUTION_MODE="animated_demo"' in content
    assert 'DRONE_BACKEND="px4"' in content
    assert 'MUYE_TAKEOFF_MODE="manual"' in content
    assert '--real-chain' not in content
    assert '--with-yolo-api' not in content
    assert '--skip-inject' not in content


def test_demo_script_uses_mock_external_services() -> None:
    content = DEMO_SH.read_text(encoding="utf-8")

    assert 'QWEATHER_USE_MOCK="true"' in content
    assert 'QWEN_USE_MOCK="true"' in content
    assert 'MUYE_MULTI_AGENT_ENABLED="false"' in content
    assert 'MUYE_ROUTER_ENABLED="false"' in content


def test_demo_script_waits_for_manual_takeoff_confirmation() -> None:
    content = DEMO_SH.read_text(encoding="utf-8")

    assert "确认起飞" in content
    assert '请在前端点击「确认起飞」，系统自动执行喷洒' in content


def test_demo_script_cleans_old_state_before_start() -> None:
    content = DEMO_SH.read_text(encoding="utf-8")

    assert 'SEED_SCRIPT="${ROOT_DIR}/scripts/seed_demo_stages.py"' in content
    assert 'seed_stage "patrol"' in content
