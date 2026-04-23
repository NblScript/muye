"""ChromaDB vector store manager for Muye RAG."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

from modules.common import DATA_DIR
from modules.rag.embeddings import QwenEmbeddings


COLLECTION_PESTICIDES = "pesticides"
COLLECTION_DECISIONS = "decisions"
COLLECTION_KNOWLEDGE = "agri_knowledge"


class VectorStoreManager:
    """Manage persistent Chroma vector stores for different collections."""

    def __init__(
        self,
        persist_directory: Path | None = None,
        embedding: QwenEmbeddings | None = None,
    ) -> None:
        self.persist_directory = persist_directory or DATA_DIR / "chroma_db"
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        self.embedding = embedding or QwenEmbeddings()
        self._stores: dict[str, Chroma] = {}

    def get_store(self, collection_name: str) -> Chroma:
        """Get or lazily create a vector store for a collection."""
        if collection_name not in self._stores:
            self._stores[collection_name] = Chroma(
                collection_name=collection_name,
                embedding_function=self.embedding,
                persist_directory=str(self.persist_directory),
            )
        return self._stores[collection_name]

    def add_documents(self, collection_name: str, documents: list[Document]) -> list[str]:
        """Add documents to the target collection."""
        if not documents:
            return []
        store = self.get_store(collection_name)
        return store.add_documents(documents)

    def similarity_search(
        self,
        collection_name: str,
        query: str,
        k: int = 5,
        filter: dict[str, Any] | None = None,
    ) -> list[Document]:
        """Search for similar documents."""
        store = self.get_store(collection_name)
        return store.similarity_search(query, k=k, filter=filter)

    def similarity_search_with_score(
        self,
        collection_name: str,
        query: str,
        k: int = 5,
    ) -> list[tuple[Document, float]]:
        """Search for similar documents with scores."""
        store = self.get_store(collection_name)
        return store.similarity_search_with_score(query, k=k)

    def delete_collection(self, collection_name: str) -> None:
        """Delete a collection from the persistent store."""
        store = self._stores.pop(collection_name, None)
        if store is None:
            store = Chroma(
                collection_name=collection_name,
                embedding_function=self.embedding,
                persist_directory=str(self.persist_directory),
            )
        store.delete_collection()

    def as_retriever(
        self,
        collection_name: str,
        search_type: str = "similarity",
        search_kwargs: dict[str, Any] | None = None,
    ) -> BaseRetriever:
        """Return a LangChain retriever bound to the target collection."""
        store = self.get_store(collection_name)
        return store.as_retriever(
            search_type=search_type,
            search_kwargs=search_kwargs or {"k": 5},
        )

    def get_retriever(
        self,
        collection_name: str,
        search_type: str = "similarity",
        search_kwargs: dict[str, Any] | None = None,
    ) -> BaseRetriever:
        """Backward-compatible alias for retriever access."""
        return self.as_retriever(
            collection_name=collection_name,
            search_type=search_type,
            search_kwargs=search_kwargs,
        )
