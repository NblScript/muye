from __future__ import annotations

from pathlib import Path

import yaml


ROOT_DIR = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT_DIR / ".github" / "workflows" / "ci.yml"


def load_workflow() -> tuple[str, dict]:
    content = WORKFLOW_PATH.read_text(encoding="utf-8")
    return content, yaml.safe_load(content)


def test_ci_workflow_has_read_only_permissions_and_all_triggers() -> None:
    content, workflow = load_workflow()

    assert workflow["permissions"] == {"contents": "read"}
    assert "  push:\n" in content
    assert "  pull_request:\n" in content
    assert "  merge_group:\n" in content
    assert "  workflow_dispatch:\n" in content
    assert "cancel-in-progress: true" in content
    assert content.count("persist-credentials: false") == 3


def test_ci_backend_runs_full_fixed_data_and_documentation_checks() -> None:
    _, workflow = load_workflow()
    backend = workflow["jobs"]["backend"]
    serialized_steps = "\n".join(str(step) for step in backend["steps"])

    assert backend["timeout-minutes"] == 20
    assert "python-version': '3.11" in serialized_steps
    assert "python -m pytest tests" in serialized_steps
    assert "not px4_simulator" in serialized_steps
    assert "scripts/eval_fixed_set.py" in serialized_steps
    assert "scripts/verify_docs.py" in serialized_steps
    assert "fixed-heatmap-evaluation" in serialized_steps


def test_ci_frontend_uses_lockfile_and_runs_quality_pipeline() -> None:
    _, workflow = load_workflow()
    frontend = workflow["jobs"]["frontend"]
    serialized_steps = "\n".join(str(step) for step in frontend["steps"])

    assert "node-version': '22" in serialized_steps
    assert "frontend/package-lock.json" in serialized_steps
    assert "npm ci" in serialized_steps
    assert "npm audit --omit=dev --audit-level=high" in serialized_steps
    assert "npm run lint" in serialized_steps
    assert "npm run test" in serialized_steps
    assert "npm run build" in serialized_steps
    assert "playwright install --with-deps chromium" in serialized_steps
    assert "npm run test:e2e" in serialized_steps
    assert "frontend-browser-layout-report" in serialized_steps
    assert "frontend-dist" in serialized_steps
    assert frontend["timeout-minutes"] == 25


def test_ci_builds_and_runs_isolated_container_smoke() -> None:
    content, workflow = load_workflow()
    containers = workflow["jobs"]["containers"]
    commands = [step.get("run") for step in containers["steps"] if step.get("run")]

    assert containers["timeout-minutes"] == 30
    assert commands == [
        "docker compose config --quiet",
        "docker compose --file docker-compose.smoke.yml config --quiet",
        "docker compose --file docker-compose.real-smoke.yml config --quiet",
        "docker compose build",
        "./scripts/docker_smoke.sh",
    ]
    assert containers["name"] == "Container build and end-to-end smoke"
    assert content.count("actions/checkout@v7") == 3
    assert "actions/setup-python@v7" in content
    assert "actions/setup-node@v7" in content
    assert content.count("actions/upload-artifact@v7") == 3
