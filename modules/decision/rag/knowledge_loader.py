"""Knowledge loaders for RAG vector stores."""

from __future__ import annotations

import json
from pathlib import Path

from langchain_core.documents import Document

from modules.infra.sqlite_store import SqliteStore


def load_pesticide_from_sqlite(store: SqliteStore, limit: int = 1000) -> list[Document]:
    """Load pesticide catalog records from SQLite."""
    rows = store.fetch_all(
        """
        SELECT
            pesticide_id,
            product_name,
            active_ingredient,
            formulation,
            toxicity,
            manufacturer,
            target_crops,
            target_pests,
            dilution_guidance
        FROM pesticide_catalog
        ORDER BY product_name
        LIMIT ?
        """,
        (limit,),
    )

    documents: list[Document] = []
    for row in rows:
        target_crops = row.get("target_crops") or ""
        target_pests = row.get("target_pests") or ""

        content_parts = [
            f"农药名称：{row.get('product_name', '')}",
            f"有效成分：{row.get('active_ingredient', '')}",
            f"剂型：{row.get('formulation', '')}",
        ]
        if target_crops:
            content_parts.append(f"适用作物：{target_crops}")
        if target_pests:
            content_parts.append(f"防治对象：{target_pests}")
        if row.get("toxicity"):
            content_parts.append(f"毒性：{row.get('toxicity')}")
        if row.get("manufacturer"):
            content_parts.append(f"生产企业：{row.get('manufacturer')}")
        if row.get("dilution_guidance"):
            content_parts.append(f"稀释指导：{row.get('dilution_guidance')}")

        documents.append(
            Document(
                page_content="\n".join(content_parts),
                metadata={
                    "source": "pesticide_catalog",
                    "pesticide_id": row.get("pesticide_id"),
                    "product_name": row.get("product_name"),
                    "target_crops": target_crops,
                    "target_pests": target_pests,
                    "toxicity": row.get("toxicity"),
                },
            )
        )

    return documents


def load_pesticide_from_json(json_path: Path) -> list[Document]:
    """Load pesticide seed data from JSON."""
    with json_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    items = data if isinstance(data, list) else data.get("data", data.get("pesticides", []))
    documents: list[Document] = []

    for item in items:
        if not isinstance(item, dict):
            continue

        product_name = item.get("product_name") or item.get("name") or item.get("农药名称", "")
        if not product_name:
            continue

        content_parts = [f"农药名称：{product_name}"]
        if item.get("active_ingredient") or item.get("有效成分"):
            content_parts.append(
                f"有效成分：{item.get('active_ingredient') or item.get('有效成分')}"
            )
        if item.get("formulation") or item.get("剂型"):
            content_parts.append(f"剂型：{item.get('formulation') or item.get('剂型')}")
        if item.get("target_crops") or item.get("适用作物"):
            content_parts.append(
                f"适用作物：{item.get('target_crops') or item.get('适用作物')}"
            )
        if item.get("target_pests") or item.get("防治对象"):
            content_parts.append(
                f"防治对象：{item.get('target_pests') or item.get('防治对象')}"
            )
        if item.get("dilution_guidance") or item.get("稀释指导"):
            content_parts.append(
                f"稀释指导：{item.get('dilution_guidance') or item.get('稀释指导')}"
            )
        if item.get("toxicity") or item.get("毒性"):
            content_parts.append(f"毒性：{item.get('toxicity') or item.get('毒性')}")
        if item.get("manufacturer") or item.get("生产企业"):
            content_parts.append(
                f"生产企业：{item.get('manufacturer') or item.get('生产企业')}"
            )

        documents.append(
            Document(
                page_content="\n".join(content_parts),
                metadata={
                    "source": "pesticide_seed",
                    "pesticide_id": item.get("pesticide_id") or item.get("id"),
                    "product_name": product_name,
                    "target_pests": item.get("target_pests") or item.get("防治对象", ""),
                    "target_crops": item.get("target_crops") or item.get("适用作物", ""),
                },
            )
        )

    return documents


def load_historical_decisions(store: SqliteStore, limit: int = 100) -> list[Document]:
    """Load historical decision records from SQLite."""
    rows = store.fetch_all(
        """
        SELECT
            d.request_id,
            d.decision_text,
            d.timestamp,
            t.field_id,
            GROUP_CONCAT(det.label, ', ') AS detected_pests
        FROM decisions d
        JOIN tasks t ON d.request_id = t.request_id
        LEFT JOIN detections det ON t.request_id = det.request_id
        WHERE d.decision_text IS NOT NULL
        GROUP BY d.request_id
        ORDER BY d.timestamp DESC
        LIMIT ?
        """,
        (limit,),
    )

    documents: list[Document] = []
    for row in rows:
        try:
            decision = json.loads(row.get("decision_text", "{}"))
        except json.JSONDecodeError:
            continue

        if not decision:
            continue

        detected_pests = row.get("detected_pests", "")
        pesticide = decision.get("用药", {})
        content_parts = [
            f"历史案例：{row.get('request_id', 'unknown')}",
            f"地块：{row.get('field_id', '')}",
            f"检测到的害虫：{detected_pests}",
            f"推荐农药：{pesticide.get('农药名称', '')}",
            f"用药浓度：{pesticide.get('浓度', '')}",
            f"配比：{pesticide.get('配比', '')}",
        ]

        suggestions = decision.get("农事建议")
        if isinstance(suggestions, list) and suggestions:
            content_parts.append(f"农事建议：{'; '.join(str(item) for item in suggestions)}")
        elif isinstance(suggestions, str) and suggestions:
            content_parts.append(f"农事建议：{suggestions}")

        documents.append(
            Document(
                page_content="\n".join(content_parts),
                metadata={
                    "source": "historical_decision",
                    "request_id": row.get("request_id"),
                    "field_id": row.get("field_id"),
                    "timestamp": row.get("timestamp"),
                    "detected_pests": detected_pests,
                    "pesticide_name": pesticide.get("农药名称", ""),
                },
            )
        )

    return documents


def build_historical_decision_document(
    *,
    request_id: str,
    decision: dict[str, object],
    pest_types: list[str] | None = None,
    field_id: str | None = None,
    crop_name: str | None = None,
    timestamp: str | None = None,
) -> Document | None:
    """Build a single historical decision document for incremental RAG indexing."""
    if not decision:
        return None

    pesticide = decision.get("用药", {})
    if not isinstance(pesticide, dict):
        pesticide = {}

    normalized_pests = [str(item).strip() for item in (pest_types or []) if str(item).strip()]
    content_parts = [
        f"历史案例：{request_id}",
        f"地块：{field_id or ''}",
        f"检测到的害虫：{', '.join(normalized_pests)}",
        f"推荐农药：{pesticide.get('农药名称', '')}",
        f"用药浓度：{pesticide.get('浓度', '')}",
        f"配比：{pesticide.get('配比', '')}",
    ]
    if crop_name:
        content_parts.append(f"作物：{crop_name}")

    suggestions = decision.get("农事建议")
    if isinstance(suggestions, list) and suggestions:
        content_parts.append(f"农事建议：{'; '.join(str(item) for item in suggestions)}")
    elif isinstance(suggestions, str) and suggestions:
        content_parts.append(f"农事建议：{suggestions}")

    return Document(
        page_content="\n".join(content_parts),
        metadata={
            "source": "historical_decision",
            "request_id": request_id,
            "field_id": field_id or "",
            "timestamp": timestamp or "",
            "detected_pests": ", ".join(normalized_pests),
            "pesticide_name": str(pesticide.get("农药名称", "")),
            "crop_name": crop_name or "",
        },
    )


def load_knowledge_from_docs(docs_dir: Path) -> list[Document]:
    """Load markdown documents from the docs directory."""
    documents: list[Document] = []

    for md_file in docs_dir.rglob("*.md"):
        content = md_file.read_text(encoding="utf-8")
        if len(content) < 100:
            continue

        paragraphs = content.split("\n\n")
        for index, paragraph in enumerate(paragraphs):
            text = paragraph.strip()
            if len(text) < 50:
                continue

            documents.append(
                Document(
                    page_content=text,
                    metadata={
                        "source": "doc",
                        "file": str(md_file.relative_to(docs_dir)),
                        "chunk": index,
                    },
                )
            )

    return documents
