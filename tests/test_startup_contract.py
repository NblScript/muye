from __future__ import annotations

from pathlib import Path
import subprocess

import yaml


ROOT_DIR = Path(__file__).resolve().parents[1]


def parse_env_template(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value.strip().strip("\"'")
    return values


def test_prepare_accepts_production_option() -> None:
    result = subprocess.run(
        ["bash", "scripts/prepare.sh", "--production", "--help"],
        cwd=ROOT_DIR,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "--production" in result.stdout


def test_production_env_template_uses_real_integrations() -> None:
    values = parse_env_template(ROOT_DIR / ".env.production.example")

    assert values["YOLO_LOCAL_MODEL_PATH"] == "models/best.pt"
    assert values["QWEN_USE_MOCK"] == "false"
    assert values["QWEATHER_USE_MOCK"] == "false"
    assert values["PX4_EXECUTION_MODE"] == "real"
    assert values["PX4_ALLOW_FORCE_ARM"] == "false"


def test_compose_is_deterministic_local_integration_stack() -> None:
    compose = yaml.safe_load(
        (ROOT_DIR / "docker-compose.yml").read_text(encoding="utf-8")
    )
    backend = compose["services"]["backend"]
    frontend = compose["services"]["frontend"]

    assert backend["build"] == {
        "context": ".",
        "dockerfile": "docker/Dockerfile.backend",
    }
    assert frontend["build"] == {
        "context": ".",
        "dockerfile": "docker/Dockerfile.frontend",
    }
    for service in (backend, frontend):
        dockerfile = ROOT_DIR / service["build"]["dockerfile"]
        assert dockerfile.is_file()

    assert backend["ports"] == [
        "127.0.0.1:${MUYE_COMPOSE_API_PORT:-18000}:8000"
    ]
    assert frontend["ports"] == [
        "127.0.0.1:${MUYE_COMPOSE_FRONTEND_PORT:-5173}:80"
    ]
    assert all(volume.startswith("./") for volume in backend["volumes"])

    environment = backend["environment"]
    assert environment["YOLO_API_URL"] == "http://127.0.0.1:8010/detect"
    assert environment["YOLO_LOCAL_MODEL_PATH"] == "/app/models/best.pt"
    assert environment["MUYE_PIPELINE_READY_FILE"] == "/app/data/runtime/pipeline.ready"
    assert environment["QWEN_USE_MOCK"] == "true"
    assert environment["QWEATHER_USE_MOCK"] == "true"
    assert environment["PX4_EXECUTION_MODE"] == "animated_demo"
    assert environment["PX4_ALLOW_FORCE_ARM"] == "false"
    assert "MUYE_CONTAINER_SMOKE" not in environment
    assert "/health" in " ".join(backend["healthcheck"]["test"])


def test_real_model_smoke_compose_is_isolated_without_fake_yolo() -> None:
    compose = yaml.safe_load(
        (ROOT_DIR / "docker-compose.real-smoke.yml").read_text(encoding="utf-8")
    )
    backend = compose["services"]["backend"]
    frontend = compose["services"]["frontend"]

    assert backend["ports"] == [
        "127.0.0.1:${MUYE_REAL_SMOKE_API_PORT:-18081}:8000"
    ]
    assert frontend["ports"] == [
        "127.0.0.1:${MUYE_REAL_SMOKE_FRONTEND_PORT:-5175}:80"
    ]
    assert "real-smoke-data:/app/data" in backend["volumes"]
    assert "./models:/app/models:ro" in backend["volumes"]
    assert "real-smoke-data" in compose["volumes"]

    environment = backend["environment"]
    assert "MUYE_CONTAINER_SMOKE" not in environment
    assert environment["YOLO_LOCAL_MODEL_PATH"] == "/app/models/best.pt"
    assert environment["MUYE_PIPELINE_READY_FILE"] == "/app/data/runtime/pipeline.ready"
    assert environment["QWEN_USE_MOCK"] == "true"
    assert environment["QWEATHER_USE_MOCK"] == "true"
    assert environment["MUYE_TAKEOFF_MODE"] == "auto"
    assert "/health" in " ".join(backend["healthcheck"]["test"])


def test_smoke_compose_is_isolated_and_explicitly_simulated() -> None:
    compose = yaml.safe_load(
        (ROOT_DIR / "docker-compose.smoke.yml").read_text(encoding="utf-8")
    )
    backend = compose["services"]["backend"]
    frontend = compose["services"]["frontend"]

    assert backend["ports"] == [
        "127.0.0.1:${MUYE_SMOKE_API_PORT:-18080}:8000",
        "127.0.0.1:${MUYE_SMOKE_YOLO_PORT:-18010}:8010",
    ]
    assert frontend["ports"] == [
        "127.0.0.1:${MUYE_SMOKE_FRONTEND_PORT:-5174}:80"
    ]
    assert "smoke-data:/app/data" in backend["volumes"]
    assert not any("/app/models" in volume for volume in backend["volumes"])
    assert "smoke-data" in compose["volumes"]

    environment = backend["environment"]
    assert environment["MUYE_CONTAINER_SMOKE"] == "true"
    assert environment["MUYE_PIPELINE_READY_FILE"] == "/app/data/runtime/pipeline.ready"
    assert environment["YOLO_API_URL"] == "http://127.0.0.1:8010/detect"
    assert environment["QWEN_USE_MOCK"] == "true"
    assert environment["QWEATHER_USE_MOCK"] == "true"
    assert environment["PX4_EXECUTION_MODE"] == "animated_demo"
    assert environment["MUYE_TAKEOFF_MODE"] == "auto"
    assert "/health" in " ".join(backend["healthcheck"]["test"])


def test_container_exposes_only_public_api_and_fails_fast() -> None:
    dockerfile = (ROOT_DIR / "docker/Dockerfile.backend").read_text(encoding="utf-8")
    entrypoint = (ROOT_DIR / "docker/entrypoint.sh").read_text(encoding="utf-8")
    dockerignore = (ROOT_DIR / ".dockerignore").read_text(encoding="utf-8")

    assert "EXPOSE 8000\n" in dockerfile
    assert "EXPOSE 8000 8010" not in dockerfile
    assert "9010" not in dockerfile
    assert 'kill -0 "$MAIN_PID"' in entrypoint
    assert 'MAIN_PID=""' in entrypoint
    assert 'API_PID=""' in entrypoint
    assert 'YOLO_PID=""' in entrypoint
    assert "MUYE_CONTAINER_SMOKE" in entrypoint
    assert "app.smoke_yolo_api:app" in entrypoint
    assert "--with-yolo-api" in entrypoint
    assert "models/best.pt" in (ROOT_DIR / "docker-compose.yml").read_text(encoding="utf-8")
    ignored_entries = {
        line.strip()
        for line in dockerignore.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    assert "docker" not in ignored_entries


def test_backend_image_apt_packages_compatible_with_debian_trixie() -> None:
    dockerfile = (ROOT_DIR / "docker/Dockerfile.backend").read_text(encoding="utf-8")

    # python:3.11-slim 已基于 Debian trixie，libgl1-mesa-glx 在该发行版被移除，
    # OpenCV 所需的 libGL.so.1 由 libgl1 提供。
    install_block = dockerfile.split("RUN apt-get update", 1)[1].split(
        "&& rm -rf", 1
    )[0]
    assert "libgl1 \\\n" in install_block
    assert "libgl1-mesa-glx" not in install_block


def test_docker_smoke_script_scopes_cleanup_to_its_project() -> None:
    content = (ROOT_DIR / "scripts/docker_smoke.sh").read_text(encoding="utf-8")

    assert 'PROJECT_NAME="${MUYE_SMOKE_PROJECT_NAME:-muye-smoke}"' in content
    assert '--file "$COMPOSE_FILE"' in content
    assert "up --build --wait --wait-timeout" in content
    assert "down --volumes --remove-orphans" in content
    assert "scripts/container_smoke.py" in content


def test_real_model_smoke_script_requires_weights_and_scopes_cleanup() -> None:
    content = (ROOT_DIR / "scripts/docker_real_smoke.sh").read_text(encoding="utf-8")

    assert 'PROJECT_NAME="${MUYE_REAL_SMOKE_PROJECT_NAME:-muye-real-smoke}"' in content
    assert 'MODEL_PATH="$ROOT_DIR/models/best.pt"' in content
    assert 'if [ ! -s "$MODEL_PATH" ]' in content
    assert '--file "$COMPOSE_FILE"' in content
    assert "up --build --wait --wait-timeout" in content
    assert "down --volumes --remove-orphans" in content
    assert "--mode real" in content
