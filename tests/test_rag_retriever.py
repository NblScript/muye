from __future__ import annotations

from langchain_core.documents import Document

from modules.decision.rag.retriever import DecisionRAGRetriever, RetrievedContext
from modules.decision.rag.vectorstore import COLLECTION_DECISIONS, COLLECTION_KNOWLEDGE, COLLECTION_PESTICIDES


def test_retrieved_context_to_prompt_text_formats_sections() -> None:
    context = RetrievedContext(
        pesticides=[
            Document(
                page_content="农药名称：吡虫啉",
                metadata={"target_pests": "aphid"},
            )
        ],
        historical_cases=[
            Document(
                page_content="历史案例：req-1\n推荐农药：吡虫啉",
                metadata={"request_id": "req-1"},
            )
        ],
        knowledge_chunks=[
            Document(
                page_content="蚜虫高发时需注意风速与漂移风险。",
                metadata={"file": "guide.md"},
            )
        ],
        pesticide_scores=[0.12],
        decision_scores=[0.34],
        knowledge_scores=[0.56],
    )

    text = context.to_prompt_text()

    assert "=== RAG 检索增强上下文 ===" in text
    assert "【相关农药推荐】" in text
    assert "【历史相似案例】" in text
    assert "【农业知识参考】" in text
    assert "1. 农药名称：吡虫啉" in text
    assert "参考值：0.12" in text
    assert "参考值：0.34" in text
    assert "参考值：0.56" in text


class FakeVectorStore:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, int]] = []
        self.responses: dict[str, list[tuple[Document, float]]] = {
            COLLECTION_PESTICIDES: [],
            COLLECTION_DECISIONS: [],
            COLLECTION_KNOWLEDGE: [],
        }

    def similarity_search_with_score(
        self,
        collection_name: str,
        query: str,
        k: int = 5,
    ) -> list[tuple[Document, float]]:
        self.calls.append((collection_name, query, k))
        return list(self.responses[collection_name])


def test_decision_rag_retriever_calls_vector_store_similarity_search_with_score() -> None:
    vector_store = FakeVectorStore()
    vector_store.responses[COLLECTION_PESTICIDES] = [
        (
            Document(
                page_content="农药名称：吡虫啉\n防治对象：aphid",
                metadata={"target_pests": "aphid"},
            ),
            0.11,
        )
    ]
    vector_store.responses[COLLECTION_DECISIONS] = [
        (
            Document(
                page_content="历史案例：req-1",
                metadata={"request_id": "req-1"},
            ),
            0.22,
        )
    ]
    vector_store.responses[COLLECTION_KNOWLEDGE] = [
        (
            Document(
                page_content="防治蚜虫时优先检查风速与作物叶面湿度。",
                metadata={"file": "guide.md"},
            ),
            0.33,
        )
    ]
    retriever = DecisionRAGRetriever(vector_store=vector_store, pesticide_k=1, decision_k=1)

    result = retriever.retrieve(pest_types=["aphid"], crop_name="小麦")

    assert len(result.pesticides) == 1
    assert len(result.historical_cases) == 1
    assert len(result.knowledge_chunks) == 1
    assert vector_store.calls == [
        (COLLECTION_PESTICIDES, "小麦 aphid aphids 蚜虫 防治农药", 2),
        (COLLECTION_KNOWLEDGE, "小麦 aphid aphids 蚜虫 病虫害防治 用药 安全 注意事项", 3),
        (COLLECTION_DECISIONS, "aphid", 1),
    ]


def test_decision_rag_retriever_filters_pesticides_by_pest_type() -> None:
    vector_store = FakeVectorStore()
    matching_doc = Document(
        page_content="农药名称：吡虫啉\n防治对象：aphid",
        metadata={"target_pests": "aphid"},
    )
    non_matching_doc = Document(
        page_content="农药名称：代森锰锌\n防治对象：rust",
        metadata={"target_pests": "rust"},
    )
    vector_store.responses[COLLECTION_PESTICIDES] = [
        (non_matching_doc, 0.05),
        (matching_doc, 0.15),
    ]
    retriever = DecisionRAGRetriever(vector_store=vector_store, pesticide_k=1, decision_k=0)

    result = retriever.retrieve(pest_types=["aphid"])

    assert result.pesticides == [matching_doc]
    assert result.pesticide_scores == [0.15]
    assert result.knowledge_chunks == []


def test_decision_rag_retriever_uses_crop_name_from_field_context_when_missing_argument() -> None:
    vector_store = FakeVectorStore()
    vector_store.responses[COLLECTION_PESTICIDES] = [
        (
            Document(
                page_content="农药名称：吡虫啉\n防治对象：aphid",
                metadata={"target_pests": "aphid"},
            ),
            0.11,
        )
    ]
    retriever = DecisionRAGRetriever(vector_store=vector_store, pesticide_k=1, decision_k=0)

    retriever.retrieve(
        pest_types=["蚜虫", "armyworm"],
        field_context={"crop_cycle": {"crop_name": "玉米"}},
    )

    assert vector_store.calls[0] == (
        COLLECTION_PESTICIDES,
        "玉米 aphid aphids 蚜虫 armyworm army worm 粘虫 防治农药",
        2,
    )
    assert vector_store.calls[1] == (
        COLLECTION_KNOWLEDGE,
        "玉米 aphid aphids 蚜虫 armyworm army worm 粘虫 病虫害防治 用药 安全 注意事项",
        3,
    )
    assert vector_store.calls[2] == (
        COLLECTION_DECISIONS,
        "aphid、armyworm",
        0,
    )
