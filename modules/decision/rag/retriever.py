"""RAG retriever for agricultural decision support."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langchain_core.documents import Document

from modules.decision.rag.vectorstore import (
    COLLECTION_DECISIONS,
    COLLECTION_KNOWLEDGE,
    COLLECTION_PESTICIDES,
    VectorStoreManager,
)


PEST_SYNONYMS: dict[str, tuple[str, ...]] = {
    "aphid": ("aphid", "aphids", "蚜虫"),
    "rice-planthopper": ("rice-planthopper", "planthopper", "brown planthopper", "稻飞虱", "飞虱"),
    "armyworm": ("armyworm", "army worm", "粘虫"),
    "corn-borer": ("corn-borer", "corn borer", "玉米螟"),
    "rice-leaf-roller": ("rice-leaf-roller", "rice leaf roller", "稻纵卷叶螟", "卷叶螟"),
    "red-spider": ("red-spider", "red spider", "spider mite", "红蜘蛛"),
    "whitefly": ("whitefly", "white fly", "白粉虱"),
    "grub": ("grub", "蛴螬"),
}


@dataclass
class RetrievedContext:
    """Structured retrieval result for decision prompting."""

    pesticides: list[Document]
    historical_cases: list[Document]
    knowledge_chunks: list[Document]
    pesticide_scores: list[float]
    decision_scores: list[float]
    knowledge_scores: list[float]

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
                lines.append(f"   参考值：{score:.2f}")

        if self.historical_cases:
            lines.extend(["", "【历史相似案例】"])
            for index, (doc, score) in enumerate(
                zip(self.historical_cases, self.decision_scores), start=1
            ):
                lines.append("")
                lines.append(f"{index}. {doc.page_content}")
                lines.append(f"   参考值：{score:.2f}")

        if self.knowledge_chunks:
            lines.extend(["", "【农业知识参考】"])
            for index, (doc, score) in enumerate(
                zip(self.knowledge_chunks, self.knowledge_scores), start=1
            ):
                lines.append("")
                lines.append(f"{index}. {doc.page_content}")
                lines.append(f"   参考值：{score:.2f}")

        lines.extend(["", "=== 请参考以上信息生成用药建议 ===", ""])
        return "\n".join(lines)


class DecisionRAGRetriever:
    """Retrieve pest-relevant pesticides and historical decision cases."""

    def __init__(
        self,
        vector_store: VectorStoreManager,
        pesticide_k: int = 5,
        decision_k: int = 3,
        knowledge_k: int = 3,
    ) -> None:
        self.vector_store = vector_store
        self.pesticide_k = pesticide_k
        self.decision_k = decision_k
        self.knowledge_k = knowledge_k

    def retrieve(
        self,
        pest_types: list[str],
        crop_name: str | None = None,
        field_context: dict[str, Any] | None = None,
    ) -> RetrievedContext:
        """Retrieve relevant pesticides and historical decisions."""
        normalized_pests = self._normalize_pest_types(pest_types)
        pest_query = "、".join(normalized_pests) if normalized_pests else "害虫防治"
        crop_hint = crop_name or self._extract_crop_name(field_context)
        pest_terms = self._expand_pest_terms(normalized_pests)

        if crop_hint:
            query = f"{crop_hint} {' '.join(pest_terms)} 防治农药".strip()
        else:
            query = f"{' '.join(pest_terms)} 防治农药".strip() or "害虫防治农药"

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

        knowledge_query_parts = [crop_hint] if crop_hint else []
        knowledge_query_parts.extend(pest_terms)
        knowledge_query_parts.append("病虫害防治 用药 安全 注意事项")
        knowledge_query = " ".join(part for part in knowledge_query_parts if part).strip()
        knowledge_docs_scores = self.vector_store.similarity_search_with_score(
            COLLECTION_KNOWLEDGE,
            knowledge_query or pest_query,
            k=self.knowledge_k,
        )

        decision_docs_scores = self.vector_store.similarity_search_with_score(
            COLLECTION_DECISIONS,
            pest_query,
            k=self.decision_k,
        )

        return RetrievedContext(
            pesticides=filtered_pesticides[: self.pesticide_k],
            historical_cases=[doc for doc, _ in decision_docs_scores],
            knowledge_chunks=[doc for doc, _ in knowledge_docs_scores],
            pesticide_scores=filtered_scores[: self.pesticide_k],
            decision_scores=[score for _, score in decision_docs_scores],
            knowledge_scores=[score for _, score in knowledge_docs_scores],
        )

    def _normalize_pest_types(self, pest_types: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for pest in pest_types:
            canonical = self._canonicalize_pest_type(pest)
            if canonical and canonical not in seen:
                seen.add(canonical)
                normalized.append(canonical)
        return normalized

    def _canonicalize_pest_type(self, pest_type: str | None) -> str:
        if not pest_type:
            return ""
        token = pest_type.strip().lower()
        if not token:
            return ""

        for canonical, aliases in PEST_SYNONYMS.items():
            if token == canonical:
                return canonical
            if token in {alias.lower() for alias in aliases}:
                return canonical
        return token

    def _expand_pest_terms(self, pest_types: list[str]) -> list[str]:
        expanded: list[str] = []
        seen: set[str] = set()
        for pest in pest_types:
            aliases = PEST_SYNONYMS.get(pest, (pest,))
            for alias in aliases:
                normalized_alias = alias.strip()
                if normalized_alias and normalized_alias not in seen:
                    seen.add(normalized_alias)
                    expanded.append(normalized_alias)
        return expanded

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
            aliases = PEST_SYNONYMS.get(pest, (pest,))
            for alias in aliases:
                pest_lower = alias.lower()
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
