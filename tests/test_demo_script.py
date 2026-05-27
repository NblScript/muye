from __future__ import annotations

from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEMO_SH = ROOT_DIR / "scripts" / "demo.sh"


def test_demo_script_uses_strict_readiness_checks() -> None:
    content = DEMO_SH.read_text(encoding="utf-8")

    assert 'curl -fsS "$url"' in content
    assert 'curl -s "$url"' not in content
    assert 'http://127.0.0.1:${API_PORT}/live' in content
    assert 'http://127.0.0.1:${API_PORT}/health' in content


def test_demo_script_can_seed_fixed_consultation_state() -> None:
    content = DEMO_SH.read_text(encoding="utf-8")

    assert "真实链路演示" in content
    assert "多智能体固定演示任务" in content
    assert 'scripts/seed_demo_state.sh --keep-existing' in content


def test_demo_script_verifies_seeded_consultation_reaches_frontend_api() -> None:
    content = DEMO_SH.read_text(encoding="utf-8")

    assert 'wait_for_seeded_demo_state()' in content
    assert "consultation_detail = rag_context.get(\\\"consultation_detail\\\") or {}" in content
    assert "active_count = int(consultation_detail.get(\\\"active_count\\\") or 0)" in content
    assert 'active_count >= 3' in content


def test_demo_script_is_only_a_stable_script_not_the_real_chain() -> None:
    content = DEMO_SH.read_text(encoding="utf-8")

    assert '固定会诊任务不依赖巡检图片' in content
    assert 'MAIN_ARGS=(--drone-backend px4 --no-capture-on-startup)' in content
    assert '--real-chain' not in content
    assert '--with-yolo-api' not in content
    assert '--image' not in content
    assert '--skip-inject' not in content
    assert '投喂单张巡检图片' not in content
    assert 'wait_for_latest_status' not in content
    assert 'YOLO API' not in content


def test_demo_script_keeps_running_when_runtime_clear_hits_sqlite_constraints() -> None:
    content = DEMO_SH.read_text(encoding="utf-8")

    assert 'clear_runtime_state()' in content
    assert 'print_warn "旧运行状态清理失败' in content
    assert '不影响本轮演示继续启动' in content


def test_demo_script_surfaces_demo_doctor_command() -> None:
    content = DEMO_SH.read_text(encoding="utf-8")

    assert './scripts/demo_doctor.sh --base-url http://127.0.0.1:${API_PORT}' in content
