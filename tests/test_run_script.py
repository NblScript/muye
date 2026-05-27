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
