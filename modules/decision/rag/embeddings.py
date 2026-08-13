"""LangChain embedding adapter for Qwen API."""

from __future__ import annotations

import os

import httpx
from langchain_core.embeddings import Embeddings
from pydantic import BaseModel


class QwenEmbeddings(BaseModel, Embeddings):
    """Qwen embedding model compatible with LangChain."""

    api_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    api_key: str | None = None
    model: str = "text-embedding-v3"
    dimensions: int = 1024
    timeout: float = 60.0

    def __init__(self, **data: object) -> None:
        super().__init__(**data)
        self.api_key = self.api_key or os.getenv("QWEN_API_KEY")
        if not self.api_key:
            raise ValueError("QWEN_API_KEY not set")

    def _request_payload(self, texts: list[str]) -> dict[str, object]:
        return {
            "model": self.model,
            "input": texts,
            "dimensions": self.dimensions,
            "encoding_format": "float",
        }

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def embed_documents(self, texts: list[str], batch_size: int = 10) -> list[list[float]]:
        """Embed a list of documents, batching to respect API limits."""
        if not texts:
            return []

        all_embeddings: list[list[float]] = []
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            response = httpx.post(
                f"{self.api_url}/embeddings",
                headers=self._headers(),
                json=self._request_payload(batch),
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            all_embeddings.extend(item["embedding"] for item in data["data"])
        return all_embeddings

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query."""
        result = self.embed_documents([text])
        return result[0] if result else []

    async def aembed_documents(self, texts: list[str], batch_size: int = 10) -> list[list[float]]:
        """Async embed a list of documents, batching to respect API limits."""
        if not texts:
            return []

        all_embeddings: list[list[float]] = []
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for start in range(0, len(texts), batch_size):
                batch = texts[start : start + batch_size]
                response = await client.post(
                    f"{self.api_url}/embeddings",
                    headers=self._headers(),
                    json=self._request_payload(batch),
                )
                response.raise_for_status()
                data = response.json()
                all_embeddings.extend(item["embedding"] for item in data["data"])
        return all_embeddings

    async def aembed_query(self, text: str) -> list[float]:
        """Async embed a single query."""
        result = await self.aembed_documents([text])
        return result[0] if result else []
