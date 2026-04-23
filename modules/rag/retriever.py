"""RAG retriever for agricultural decision support."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langchain_core.documents import Document

from modules.rag.vectorstore import (
    COLLECTION_DECISIONS,
    COLLECTION_PESTICIDES,
    VectorStoreManager,
)


@dataclass
class RetrievedContext:
    """Structured retrieval result for decision prompting."""

    pesticides: list[Document]
    historical_cases: list[Document]
    pesticide_scores: list[float]
    decision_scores: list[float]

    def to_prompt_text(self) -> str:
        """Format retrieved context as prompt text."""
        lines = ["", "=== RAG 检索增强上下文 ==="]

        if self.pesticides:
            lines.extend(["", "【相关农药推荐】"])
            for index, (doc, score) in enumerate(
                zip(self.pesticides, self.pesticide_scores), start=1
            ):
                lines.append("")
                lines.append(f"{index}. {doc.page_content}")
                lines.append(f"   相关度：{score:.2f}")

        if self.historical_cases:
            lines.extend(["", "【历史相似案例】"])
            for index, (doc, score) in enumerate(
                zip(self.historical_cases, self.decision_scores), start=1
            ):
                lines.append("")
                lines.append(f"{index}. {doc.page_content}")
                lines.append(f"   相似度：{score:.2f}")

        lines.extend(["", "=== 请参考以上信息生成用药建议 ===", ""])
        return "\n".join(lines)


class DecisionRAGRetriever:
    """Retrieve pest-relevant pesticides and historical decision cases."""

    def __init__(
        self,
        vector_store: VectorStoreManager,
        pesticide_k: int = 5,
        decision_k: int = 3,
    ) -> None:
        self.vector_store = vector_store
        self.pesticide_k = pesticide_k
        self.decision_k = decision_k

    def retrieve(
        self,
        pest_types: list[str],
        crop_name: str | None = None,
        field_context: dict[str, Any] | None = None,
    ) -> RetrievedContext:
        """Retrieve relevant pesticides and historical decisions."""
        normalized_pests = [pest.strip() for pest in pest_types if pest and pest.strip()]
        pest_query = "、".join(normalized_pests) if normalized_pests else "害虫防治"
        crop_hint = crop_name or self._extract_crop_name(field_context)

        if crop_hint:
            query = f"{crop_hint} {' '.join(normalized_pests)} 防治农药".strip()
        else:
            query = f"{' '.join(normalized_pests)} 防治农药".strip() or "害虫防治农药"

        pesticide_docs_scores = self.vector_store.similarity_search_with_score(
            COLLECTION_PESTICIDES,
            query,
            k=max(self.pesticide_k * 2, self.pesticide_k),
        )

        filtered_pesticides: list[Document] = []
        filtered_scores: list[float] = []
        for doc, score in pesticide_docs_scores:
            if self._matches_pest(doc, normalized_pests):
                filtered_pesticides.append(doc)
                filtered_scores.append(score)
                if len(filtered_pesticides) >= self.pesticide_k:
                    break

        if len(filtered_pesticides) < self.pesticide_k:
            for doc, score in pesticide_docs_scores:
                if doc in filtered_pesticides:
                    continue
                filtered_pesticides.append(doc)
                filtered_scores.append(score)
                if len(filtered_pesticides) >= self.pesticide_k:
                    break

        decision_docs_scores = self.vector_store.similarity_search_with_score(
            COLLECTION_DECISIONS,
            pest_query,
            k=self.decision_k,
        )

        return RetrievedContext(
            pesticides=filtered_pesticides[: self.pesticide_k],
            historical_cases=[doc for doc, _ in decision_docs_scores],
            pesticide_scores=filtered_scores[: self.pesticide_k],
            decision_scores=[score for _, score in decision_docs_scores],
        )

    def _extract_crop_name(self, field_context: dict[str, Any] | None) -> str | None:
        if not field_context:
            return None
        crop_cycle = field_context.get("crop_cycle")
        if isinstance(crop_cycle, dict):
            crop_name = crop_cycle.get("crop_name")
            if isinstance(crop_name, str) and crop_name.strip():
                return crop_name.strip()
        return None

    def _matches_pest(self, doc: Document, pest_types: list[str]) -> bool:
        """Check whether the document matches any pest type."""
        if not pest_types:
            return True

        target_pests = str(doc.metadata.get("target_pests", "")).lower()
        content = doc.page_content.lower()
        for pest in pest_types:
            pest_lower = pest.lower()
            if pest_lower in target_pests or pest_lower in content:
                return True
        return False


def build_rag_enhanced_prompt(
    pest_detections: list[dict[str, Any]],
    retrieved_context: RetrievedContext,
    base_prompt: str,
) -> str:
    """Build a prompt with appended RAG retrieval context."""
    del pest_detections
    return f"{base_prompt}\n{retrieved_context.to_prompt_text()}"
