from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def test_runtime_scripts_use_migrated_infra_imports() -> None:
    script_paths = [
        ROOT_DIR / "scripts" / "start_demo.sh",
        ROOT_DIR / "scripts" / "start_px4_visual_demo.sh",
        ROOT_DIR / "scripts" / "run_px4_demo.sh",
    ]

    for script_path in script_paths:
        content = script_path.read_text(encoding="utf-8")
        assert "from modules.common import ensure_runtime_dirs" not in content
        assert "from modules.event_bus import FileEventBus" not in content
        assert "from modules.infra.common import ensure_runtime_dirs" in content
        assert "from modules.infra.event_bus import FileEventBus" in content
