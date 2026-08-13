from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def test_runtime_scripts_use_migrated_infra_imports() -> None:
    # run.sh embeds python snippets that must use migrated infra paths
    run_content = (ROOT_DIR / "scripts" / "run.sh").read_text(encoding="utf-8")
    assert "from modules.common import ensure_runtime_dirs" not in run_content
    assert "from modules.event_bus import FileEventBus" not in run_content
    assert "from modules.infra.common import ensure_runtime_dirs" in run_content

    # demo.sh is a pure-bash seeding script: no python imports at all
    demo_content = (ROOT_DIR / "scripts" / "demo.sh").read_text(encoding="utf-8")
    assert "from modules.common" not in demo_content
    assert "from modules.infra.common" not in demo_content
    assert "seed_demo_stages.py" in demo_content


def test_python_demo_utilities_use_migrated_infra_imports() -> None:
    script_paths = [
        ROOT_DIR / "scripts" / "demo_smoke.py",
        ROOT_DIR / "scripts" / "demo_doctor.py",
    ]

    for script_path in script_paths:
        content = script_path.read_text(encoding="utf-8")
        assert "from modules.common" not in content
        assert "from modules.event_bus" not in content
        assert "from modules.infra." in content
