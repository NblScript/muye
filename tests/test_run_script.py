from __future__ import annotations

from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
RUN_SH = ROOT_DIR / "scripts" / "run.sh"


def test_run_script_defaults_to_loopback_api_host() -> None:
    content = RUN_SH.read_text(encoding="utf-8")

    assert 'API_HOST="${MUYE_API_HOST:-127.0.0.1}"' in content
    assert '--host "$API_HOST"' in content
    assert 'http://${API_HOST}:${API_PORT}/live' in content
    assert 'http://${API_HOST}:${API_PORT}/health' in content


def test_run_script_requires_explicit_force_arm() -> None:
    content = RUN_SH.read_text(encoding="utf-8")

    assert 'export PX4_ALLOW_FORCE_ARM="${PX4_ALLOW_FORCE_ARM:-false}"' in content
    assert 'PX4_ALLOW_FORCE_ARM="${PX4_ALLOW_FORCE_ARM:-true}"' not in content


def test_run_script_uses_strict_curl_readiness_checks() -> None:
    content = RUN_SH.read_text(encoding="utf-8")

    assert 'curl -fsS "$url"' in content
    assert 'curl -s "$url"' not in content


def test_run_script_requires_production_env_unless_explicitly_allowed() -> None:
    content = RUN_SH.read_text(encoding="utf-8")

    assert 'ALLOW_DEFAULT_ENV="false"' in content
    assert '--allow-default-env' in content
    assert '缺少 .env.production' in content
    assert 'exit 1' in content


def test_run_script_defaults_production_px4_to_real_execution() -> None:
    content = RUN_SH.read_text(encoding="utf-8")

    assert 'export PX4_EXECUTION_MODE="${PX4_EXECUTION_MODE:-real}"' in content
    assert 'PX4_EXECUTION_MODE="${PX4_EXECUTION_MODE:-sitl}"' not in content
    assert 'PX4_EXECUTION_MODE="${PX4_EXECUTION_MODE:-animated_demo}"' in content
    assert 'echo "  起飞模式:   $MUYE_TAKEOFF_MODE"' in content


def test_run_script_requires_configured_yolo_model() -> None:
    content = RUN_SH.read_text(encoding="utf-8")

    assert 'YOLO_MODEL_PATH="${YOLO_LOCAL_MODEL_PATH:-models/best.pt}"' in content
    assert 'print_error "YOLO 模型不存在: $YOLO_MODEL_PATH"' in content
    assert "--with-yolo-api 需要可用的本地模型" in content


def test_run_script_preflights_ports_before_starting() -> None:
    content = RUN_SH.read_text(encoding="utf-8")

    assert "port_in_use" in content
    assert "require_free_port" in content
    assert "/dev/tcp/127.0.0.1" in content
    assert 'require_free_port "$API_PORT" "前端 API"' in content
    assert 'require_free_port "$FRONTEND_PORT" "前端"' in content
    assert 'require_free_port "8010" "内嵌 YOLO API"' in content
