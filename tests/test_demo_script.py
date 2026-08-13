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

    assert 'PX4_EXECUTION_MODE="${PX4_EXECUTION_MODE:-animated_demo}"' in content
    assert 'DRONE_BACKEND="${DRONE_BACKEND:-px4}"' in content
    assert 'MUYE_TAKEOFF_MODE="${MUYE_TAKEOFF_MODE:-manual}"' in content
    assert '--real-chain' not in content
    assert '--with-yolo-api' not in content
    assert '--skip-inject' not in content


def test_demo_script_uses_mock_external_services() -> None:
    content = DEMO_SH.read_text(encoding="utf-8")

    assert 'QWEATHER_USE_MOCK="${QWEATHER_USE_MOCK:-true}"' in content
    assert 'QWEN_USE_MOCK="${QWEN_USE_MOCK:-true}"' in content
    assert 'MUYE_MULTI_AGENT_ENABLED="${MUYE_MULTI_AGENT_ENABLED:-false}"' in content
    assert 'MUYE_ROUTER_ENABLED="${MUYE_ROUTER_ENABLED:-false}"' in content


def test_demo_script_waits_for_manual_takeoff_confirmation() -> None:
    content = DEMO_SH.read_text(encoding="utf-8")

    assert "确认起飞" in content
    assert '请在前端点击「确认起飞」，系统自动执行喷洒' in content


def test_demo_script_cleans_old_state_before_start() -> None:
    content = DEMO_SH.read_text(encoding="utf-8")

    assert 'SEED_SCRIPT="${ROOT_DIR}/scripts/seed_demo_stages.py"' in content
    assert 'seed_stage "patrol"' in content


def test_demo_script_parses_documented_arguments() -> None:
    content = DEMO_SH.read_text(encoding="utf-8")

    # AGENTS.md / demo-pipeline.md 承诺的参数必须真实存在
    assert 'while [[ $# -gt 0 ]]' in content
    assert "--mode virtual|px4" in content
    assert "--takeoff manual|auto" in content
    assert "--api-port <端口>" in content
    assert "--frontend-port <端口>" in content
    assert 'MODE="$2"' in content
    assert 'CLI_TAKEOFF="$2"' in content
    assert 'CLI_API_PORT="$2"' in content
    assert 'CLI_FRONTEND_PORT="$2"' in content
    assert 'API_PORT="${CLI_API_PORT:-${MUYE_API_PORT:-18000}}"' in content
    assert 'FRONTEND_PORT="${CLI_FRONTEND_PORT:-${MUYE_FRONTEND_PORT:-5173}}"' in content


def test_demo_script_respects_exported_scenario_env() -> None:
    content = DEMO_SH.read_text(encoding="utf-8")

    # demo_scenario.sh 导出的场景变量必须保留：
    # 环境文件只用 override=false 填充未设置项，默认值用 ${VAR:-default} 补位
    assert 'load_env_file "$API_KEYS_FILE" false' in content
    assert 'load_env_file "$DEMO_ENV_FILE" false' in content
    assert 'RAG_ENABLED="${RAG_ENABLED:-false}"' in content
    assert 'QWEATHER_MOCK_HUMIDITY="${QWEATHER_MOCK_HUMIDITY:-61}"' in content


def test_demo_script_preflights_ports_before_starting() -> None:
    content = DEMO_SH.read_text(encoding="utf-8")

    assert "port_in_use" in content
    assert "require_free_port" in content
    assert "/dev/tcp/127.0.0.1" in content
    assert 'require_free_port "$API_PORT" "后端 API"' in content
    assert 'require_free_port "$FRONTEND_PORT" "前端"' in content


def test_demo_script_px4_mode_starts_sitl_best_effort() -> None:
    content = DEMO_SH.read_text(encoding="utf-8")

    assert 'if [[ "$MODE" == "px4" ]]' in content
    assert '/drone/start-px4-demo' in content
    assert "PX4 SITL 启动失败（可能未安装 ~/PX4-Autopilot）" in content
