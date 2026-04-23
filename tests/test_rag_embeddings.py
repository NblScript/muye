from __future__ import annotations

import pytest

from modules.rag.embeddings import QwenEmbeddings


class StubResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self._payload


def test_qwen_embeddings_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QWEN_API_KEY", raising=False)

    with pytest.raises(ValueError, match="QWEN_API_KEY not set"):
        QwenEmbeddings(api_key=None)


def test_qwen_embeddings_initializes_with_api_key() -> None:
    embeddings = QwenEmbeddings(api_key="test-key")

    assert embeddings.api_key == "test-key"
    assert embeddings.model == "text-embedding-v3"


def test_qwen_embeddings_embed_documents_returns_empty_list_for_empty_input() -> None:
    embeddings = QwenEmbeddings(api_key="test-key")

    assert embeddings.embed_documents([]) == []


def test_qwen_embeddings_embed_documents_sends_expected_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_post(
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, object],
        timeout: float,
    ) -> StubResponse:
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return StubResponse(
            {
                "data": [
                    {"embedding": [0.1, 0.2]},
                    {"embedding": [0.3, 0.4]},
                ]
            }
        )

    monkeypatch.setattr("modules.rag.embeddings.httpx.post", fake_post)

    embeddings = QwenEmbeddings(
        api_url="https://dashscope.test/v1",
        api_key="test-key",
        model="text-embedding-v3",
        dimensions=512,
        timeout=12.5,
    )

    result = embeddings.embed_documents(["虫害一", "虫害二"])

    assert result == [[0.1, 0.2], [0.3, 0.4]]
    assert captured == {
        "url": "https://dashscope.test/v1/embeddings",
        "headers": {
            "Authorization": "Bearer test-key",
            "Content-Type": "application/json",
        },
        "json": {
            "model": "text-embedding-v3",
            "input": ["虫害一", "虫害二"],
            "dimensions": 512,
            "encoding_format": "float",
        },
        "timeout": 12.5,
    }
