"""Tests for multi-model switching (detection + decision)."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import pytest

from modules.detection.local_yolo_api import (
    LocalYoloApiService,
    LocalYoloSettings,
    UltralyticsPredictor,
    _resolve_model_from_config,
)


# ── 检测模型配置解析 ──


def test_resolve_model_from_multi_model_config():
    config: dict[str, Any] = {
        "models": {
            "yolov8n": {"path": "models/best.pt", "device": "auto"},
            "yolov8s": {"path": "models/yolov8s.pt", "device": "cpu"},
        },
        "active_model": "yolov8s",
        "local_api": {"model_path": "models/old.pt"},
    }
    model_path, device, model_name, available = _resolve_model_from_config(config)
    assert model_name == "yolov8s"
    assert device == "cpu"
    assert "yolov8n" in available
    assert "yolov8s" in available


def test_resolve_model_fallback_to_local_api():
    config: dict[str, Any] = {
        "local_api": {"model_path": "models/best.pt", "device": "auto"},
    }
    model_path, device, model_name, available = _resolve_model_from_config(config)
    assert model_name == ""
    assert device == "auto"
    assert available == {}


def test_resolve_model_active_not_in_models():
    config: dict[str, Any] = {
        "models": {"yolov8n": {"path": "models/best.pt", "device": "auto"}},
        "active_model": "nonexistent",
        "local_api": {"model_path": "models/fallback.pt", "device": "cpu"},
    }
    model_path, device, model_name, available = _resolve_model_from_config(config)
    # active_model 不存在时回退到 local_api
    assert model_name == ""


def test_resolve_model_env_override(monkeypatch):
    monkeypatch.setenv("YOLO_LOCAL_MODEL_PATH", "/custom/model.pt")
    monkeypatch.setenv("YOLO_LOCAL_DEVICE", "cuda:0")
    config: dict[str, Any] = {
        "models": {"yolov8n": {"path": "models/best.pt", "device": "auto"}},
        "active_model": "yolov8n",
        "local_api": {},
    }
    model_path, device, model_name, available = _resolve_model_from_config(config)
    assert str(model_path) == "/custom/model.pt"
    assert device == "cuda:0"


# ── 模型切换 ──


def test_reload_model_raises_for_unknown():
    settings = LocalYoloSettings(
        host="127.0.0.1",
        port=8010,
        model_path=Path("/tmp/dummy.pt"),
        device="auto",
        api_key="",
        allowed_ips=[],
        rate_limit_per_minute=120,
        max_batch_size=4,
        model_name="yolov8n",
        available_models={"yolov8n": {"path": "/tmp/dummy.pt", "device": "auto"}},
    )

    # 用一个不需要真实模型文件的 predictor mock
    class FakePredictor:
        model_path = Path("/tmp/dummy.pt")

        def predict(self, image_paths, confidence_threshold):
            return []

    service = LocalYoloApiService(settings=settings, predictor=FakePredictor())  # type: ignore

    with pytest.raises(Exception, match="不存在"):
        service.reload_model("nonexistent")


def test_reload_model_raises_for_missing_file():
    settings = LocalYoloSettings(
        host="127.0.0.1",
        port=8010,
        model_path=Path("/tmp/dummy.pt"),
        device="auto",
        api_key="",
        allowed_ips=[],
        rate_limit_per_minute=120,
        max_batch_size=4,
        model_name="yolov8n",
        available_models={
            "yolov8n": {"path": "/tmp/dummy.pt", "device": "auto"},
            "missing": {"path": "/tmp/nonexistent_model.pt", "device": "auto"},
        },
    )

    class FakePredictor:
        model_path = Path("/tmp/dummy.pt")

        def predict(self, image_paths, confidence_threshold):
            return []

    service = LocalYoloApiService(settings=settings, predictor=FakePredictor())  # type: ignore

    with pytest.raises(Exception, match="模型文件不存在"):
        service.reload_model("missing")


# ── 决策模型 provider 映射 ──


def test_load_provider_mapping_from_file(tmp_path):
    config_content = """
expert_providers:
  entomologist: deepseek
  agronomist: xiaomi
  pesticide_specialist: qwen
"""
    config_file = tmp_path / "model_config.yaml"
    config_file.write_text(config_content)

    from modules.decision.agents.expert_roles import load_provider_mapping

    mapping = load_provider_mapping(config_file)
    assert mapping == {
        "entomologist": "deepseek",
        "agronomist": "xiaomi",
        "pesticide_specialist": "qwen",
    }


def test_load_provider_mapping_missing_file(tmp_path):
    from modules.decision.agents.expert_roles import load_provider_mapping

    mapping = load_provider_mapping(tmp_path / "nonexistent.yaml")
    assert mapping == {}


def test_apply_provider_mapping():
    from modules.decision.agents.expert_roles import EXPERT_ROLES, apply_provider_mapping

    # 保存原始值
    original = {k: v["llm_provider"] for k, v in EXPERT_ROLES.items()}

    try:
        apply_provider_mapping({
            "entomologist": "xiaomi",
            "agronomist": "qwen",
        })
        assert EXPERT_ROLES["entomologist"]["llm_provider"] == "xiaomi"
        assert EXPERT_ROLES["agronomist"]["llm_provider"] == "qwen"
        # 未映射的角色不变
        assert EXPERT_ROLES["pesticide_specialist"]["llm_provider"] == original["pesticide_specialist"]
    finally:
        # 恢复原始值
        for k, v in original.items():
            EXPERT_ROLES[k]["llm_provider"] = v


def test_apply_provider_mapping_unknown_role():
    from modules.decision.agents.expert_roles import EXPERT_ROLES, apply_provider_mapping

    original_entomologist = EXPERT_ROLES["entomologist"]["llm_provider"]

    try:
        apply_provider_mapping({
            "nonexistent_role": "qwen",
            "entomologist": "deepseek",
        })
        assert EXPERT_ROLES["entomologist"]["llm_provider"] == "deepseek"
    finally:
        EXPERT_ROLES["entomologist"]["llm_provider"] = original_entomologist


def test_load_provider_mapping_empty_expert_providers(tmp_path):
    config_content = """
expert_providers: {}
"""
    config_file = tmp_path / "model_config.yaml"
    config_file.write_text(config_content)

    from modules.decision.agents.expert_roles import load_provider_mapping

    mapping = load_provider_mapping(config_file)
    assert mapping == {}


def test_load_provider_mapping_invalid_format(tmp_path):
    config_content = """
expert_providers: "not a dict"
"""
    config_file = tmp_path / "model_config.yaml"
    config_file.write_text(config_content)

    from modules.decision.agents.expert_roles import load_provider_mapping

    mapping = load_provider_mapping(config_file)
    assert mapping == {}
