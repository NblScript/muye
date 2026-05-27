from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def test_runtime_scripts_use_migrated_infra_imports() -> None:
    script_paths = [
        ROOT_DIR / "scripts" / "demo.sh",
        ROOT_DIR / "scripts" / "run.sh",
    ]

    for script_path in script_paths:
        content = script_path.read_text(encoding="utf-8")
        assert "from modules.common import ensure_runtime_dirs" not in content
        assert "from modules.event_bus import FileEventBus" not in content
        assert "from modules.infra.common import ensure_runtime_dirs" in content


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
