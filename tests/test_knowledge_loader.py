"""Smoke tests for modules/decision/rag/knowledge_loader.py"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from modules.decision.rag.knowledge_loader import (
    build_historical_decision_document,
    load_historical_decisions,
    load_knowledge_from_docs,
    load_pesticide_from_json,
    load_pesticide_from_sqlite,
)
from modules.infra.sqlite_store import SqliteStore


def test_load_pesticide_from_json_parses_basic_record(tmp_path: Path) -> None:
    """Test loading pesticide data from JSON file."""
    json_data = {
        "pesticides": [
            {
                "product_name": "吡虫啉",
                "active_ingredient": "imidacloprid",
                "target_crops": "小麦",
                "target_pests": "蚜虫",
            }
        ]
    }
    json_file = tmp_path / "pesticides.json"
    json_file.write_text(json.dumps(json_data, ensure_ascii=False), encoding="utf-8")

    documents = load_pesticide_from_json(json_file)

    assert len(documents) == 1
    assert "吡虫啉" in documents[0].page_content
    assert documents[0].metadata["source"] == "pesticide_seed"


def test_load_pesticide_from_json_handles_chinese_keys(tmp_path: Path) -> None:
    """Test loading pesticide data with Chinese field names."""
    json_data = [
        {
            "农药名称": "阿维菌素",
            "有效成分": "abamectin",
            "防治对象": "红蜘蛛",
        }
    ]
    json_file = tmp_path / "pesticides_cn.json"
    json_file.write_text(json.dumps(json_data, ensure_ascii=False), encoding="utf-8")

    documents = load_pesticide_from_json(json_file)

    assert len(documents) == 1
    assert "阿维菌素" in documents[0].page_content


def test_load_pesticide_from_sqlite_returns_documents(tmp_path: Path) -> None:
    """Test loading pesticide data from SQLite store."""
    store = SqliteStore(tmp_path / "muye.db")
    try:
        store.upsert_pesticide_catalog_record(
            {
                "pesticide_id": "p-001",
                "product_name": "吡虫啉",
                "active_ingredient": "imidacloprid",
                "target_crops": ["小麦"],
                "target_pests": ["蚜虫"],
            }
        )

        documents = load_pesticide_from_sqlite(store, limit=10)

        assert len(documents) == 1
        assert "吡虫啉" in documents[0].page_content
        assert documents[0].metadata["source"] == "pesticide_catalog"
    finally:
        store.close()


def test_load_knowledge_from_docs_extracts_paragraphs(tmp_path: Path) -> None:
    """Test loading knowledge from markdown documents."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()

    # File must be >= 100 chars; each paragraph must be >= 50 chars after strip
    paragraph_1 = "这是第一段内容，介绍害虫防治的基本知识，需要足够长才能被提取，至少五十个字符才能通过筛选条件的限制要求才能进入。"
    paragraph_2 = "这是第二段，关于农药使用注意事项，同样需要足够的长度才能被提取出来，满足最小长度要求才行，必须超过五十个字符才能被收录。"
    md_content = f"# 害虫防治指南\n\n{paragraph_1}\n\n{paragraph_2}\n\n补充说明：以上内容仅供参考，具体用药请遵医嘱，安全第一。"

    (docs_dir / "guide.md").write_text(md_content, encoding="utf-8")

    documents = load_knowledge_from_docs(docs_dir)

    assert len(documents) >= 1
    for doc in documents:
        assert doc.metadata["source"] == "doc"


def test_load_historical_decisions_returns_documents(tmp_path: Path) -> None:
    """Test loading historical decisions from SQLite store."""
    store = SqliteStore(tmp_path / "muye.db")
    try:
        # Use _ensure_task + raw SQL to set up test data matching the loader's query
        with store._lock:
            store._connection.execute(
                "INSERT OR IGNORE INTO fields (field_id, field_name) VALUES (?, ?)",
                ("field-001", "测试田"),
            )
            # Create a task row
            store._connection.execute(
                "INSERT OR IGNORE INTO tasks (request_id, status) VALUES (?, ?)",
                ("req-001", "completed"),
            )
            # Set field_id on the task
            store._connection.execute(
                "UPDATE tasks SET field_id = ? WHERE request_id = ?",
                ("field-001", "req-001"),
            )
            # Insert a detection
            store._connection.execute(
                "INSERT INTO detections (request_id, label, confidence, bbox) VALUES (?, ?, ?, ?)",
                ("req-001", "蚜虫", 0.95, "{}"),
            )
            # Insert a decision
            store._connection.execute(
                "INSERT INTO decisions (request_id, timestamp, decision_text) VALUES (?, ?, ?)",
                (
                    "req-001",
                    "2026-04-24T00:00:00Z",
                    json.dumps(
                        {"用药": {"农药名称": "吡虫啉", "浓度": "1:1000"}},
                        ensure_ascii=False,
                    ),
                ),
            )
            store._connection.commit()

        documents = load_historical_decisions(store, limit=10)

        assert len(documents) == 1
        assert documents[0].metadata["source"] == "historical_decision"
    finally:
        store.close()


def test_build_historical_decision_document_builds_incremental_index_payload() -> None:
    document = build_historical_decision_document(
        request_id="req-123",
        decision={
            "用药": {
                "农药名称": "吡虫啉",
                "浓度": "1:1000",
                "配比": "1:1200",
            },
            "农事建议": ["避开大风时段"],
        },
        pest_types=["aphid", "蚜虫"],
        field_id="field-001",
        crop_name="冬小麦",
        timestamp="2026-05-11T00:00:00Z",
    )

    assert document is not None
    assert document.metadata["source"] == "historical_decision"
    assert document.metadata["request_id"] == "req-123"
    assert document.metadata["crop_name"] == "冬小麦"
    assert "检测到的害虫：aphid, 蚜虫" in document.page_content
    assert "推荐农药：吡虫啉" in document.page_content
