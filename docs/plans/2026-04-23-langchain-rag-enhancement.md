# LangChain RAG 增强实现计划

> **For Hermes:** 使用 subagent-driven-development 逐任务执行此计划。

**目标：** 为 muye 项目增加 LangChain RAG 检索层，利用历史数据和知识库增强 AI 决策质量

**架构：**
```
用户上传图片
    ↓
YOLO 检测害虫
    ↓
LangChain RAG 检索 ←── ChromaDB 向量库
    │                  ├── 农药知识库（pesticide_catalog）
    │                  ├── 历史决策案例（decisions）
    │                  └── 农业知识文档（docs/）
    ↓
千问生成用药建议（带上下文增强）
    ↓
无人机执行
```

**技术栈：**
- LangChain 0.3+（核心框架）
- ChromaDB（轻量本地向量数据库）
- 千问 Embedding（text-embedding-v3）
- 复用现有千问 API 配置

---

## Phase 1: 环境准备与依赖安装

### Task 1: 安装 LangChain 依赖

**目标：** 添加 LangChain 和 ChromaDB 到项目依赖

**文件：**
- Modify: `requirements.txt`

**实现：**

```diff
--- a/requirements.txt
+++ b/requirements.txt
@@ -13,3 +13,9 @@ ultralytics>=8.3.0
 pytest>=8.2.0
 pytest-asyncio>=0.23.7
+
+# LangChain RAG
+langchain>=0.3.0
+langchain-community>=0.3.0
+langchain-openai>=0.3.0  # 兼容千问 OpenAI 格式
+chromadb>=0.5.0
+langchain-chroma>=0.2.0
```

**验证：**

```bash
cd ~/muye && source .venv/bin/activate && pip install -r requirements.txt
python -c "import langchain; import chromadb; print('OK')"
```

**提交：**

```bash
git add requirements.txt && git commit -m "feat: add LangChain RAG dependencies"
```

---

### Task 2: 创建 RAG 模块目录结构

**目标：** 建立模块化目录结构

**文件：**
- Create: `modules/rag/__init__.py`
- Create: `modules/rag/embeddings.py`
- Create: `modules/rag/vectorstore.py`
- Create: `modules/rag/retriever.py`
- Create: `modules/rag/knowledge_loader.py`

**实现：**

```bash
mkdir -p ~/muye/modules/rag
touch ~/muye/modules/rag/__init__.py
```

**提交：**

```bash
git add modules/rag/ && git commit -m "feat: create RAG module directory structure"
```

---

## Phase 2: 向量存储与 Embedding

### Task 3: 实现千问 Embedding 适配器

**目标：** 创建兼容千问 API 的 LangChain Embedding 类

**文件：**
- Create: `modules/rag/embeddings.py`

**实现：**

```python
"""LangChain Embedding adapter for Qwen API."""

from __future__ import annotations

import os
from typing import List

from langchain_core.embeddings import Embeddings
from pydantic import BaseModel


class QwenEmbeddings(BaseModel, Embeddings):
    """Qwen embedding model compatible with LangChain.
    
    Uses Qwen's text-embedding API (OpenAI-compatible format).
    """
    
    api_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    api_key: str | None = None
    model: str = "text-embedding-v3"
    dimensions: int = 1024
    
    def __init__(self, **data):
        super().__init__(**data)
        self.api_key = self.api_key or os.getenv("QWEN_API_KEY")
        if not self.api_key:
            raise ValueError("QWEN_API_KEY not set")
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of documents."""
        import httpx
        
        url = f"{self.api_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        response = httpx.post(
            url,
            headers=headers,
            json={
                "model": self.model,
                "input": texts,
                "dimensions": self.dimensions,
                "encoding_format": "float",
            },
            timeout=60.0,
        )
        response.raise_for_status()
        
        data = response.json()
        return [item["embedding"] for item in data["data"]]
    
    def embed_query(self, text: str) -> List[float]:
        """Embed a single query."""
        result = self.embed_documents([text])
        return result[0]
    
    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        """Async embed documents."""
        import httpx
        
        url = f"{self.api_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                url,
                headers=headers,
                json={
                    "model": self.model,
                    "input": texts,
                    "dimensions": self.dimensions,
                    "encoding_format": "float",
                },
            )
            response.raise_for_status()
            data = response.json()
            return [item["embedding"] for item in data["data"]]
    
    async def aembed_query(self, text: str) -> List[float]:
        """Async embed a single query."""
        result = await self.aembed_documents([text])
        return result[0]
```

**验证：**

```bash
cd ~/muye && source .venv/bin/activate
python -c "
from modules.rag.embeddings import QwenEmbeddings
embed = QwenEmbeddings()
print('QwenEmbeddings initialized OK')
"
```

**提交：**

```bash
git add modules/rag/embeddings.py && git commit -m "feat: add Qwen embedding adapter for LangChain"
```

---

### Task 4: 实现 ChromaDB 向量存储封装

**目标：** 创建向量存储管理器，持久化到 data/ 目录

**文件：**
- Create: `modules/rag/vectorstore.py`

**实现：**

```python
"""ChromaDB vector store manager for Muye RAG."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain_chroma import Chroma
from langchain_core.documents import Document

from modules.common import DATA_DIR
from modules.rag.embeddings import QwenEmbeddings


# Collection names
COLLECTION_PESTICIDES = "pesticides"
COLLECTION_DECISIONS = "decisions"
COLLECTION_KNOWLEDGE = "agri_knowledge"


class VectorStoreManager:
    """Manages ChromaDB vector stores for different knowledge domains."""
    
    def __init__(
        self,
        persist_directory: Path | None = None,
        embedding: QwenEmbeddings | None = None,
    ):
        self.persist_directory = persist_directory or DATA_DIR / "chroma_db"
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        self.embedding = embedding or QwenEmbeddings()
        
        self._stores: dict[str, Chroma] = {}
    
    def get_store(self, collection_name: str) -> Chroma:
        """Get or create a vector store for a collection."""
        if collection_name not in self._stores:
            self._stores[collection_name] = Chroma(
                collection_name=collection_name,
                embedding_function=self.embedding,
                persist_directory=str(self.persist_directory),
            )
        return self._stores[collection_name]
    
    def add_documents(
        self,
        collection_name: str,
        documents: list[Document],
    ) -> list[str]:
        """Add documents to a collection."""
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
        """Search with relevance scores."""
        store = self.get_store(collection_name)
        return store.similarity_search_with_score(query, k=k)
    
    def delete_collection(self, collection_name: str) -> None:
        """Delete a collection."""
        if collection_name in self._stores:
            self._stores[collection_name].delete_collection()
            del self._stores[collection_name]
    
    def get_retriever(
        self,
        collection_name: str,
        search_type: str = "similarity",
        search_kwargs: dict[str, Any] | None = None,
    ):
        """Get a LangChain retriever for a collection."""
        store = self.get_store(collection_name)
        return store.as_retriever(
            search_type=search_type,
            search_kwargs=search_kwargs or {"k": 5},
        )
```

**验证：**

```bash
cd ~/muye && source .venv/bin/activate
python -c "
from modules.rag.vectorstore import VectorStoreManager
mgr = VectorStoreManager()
print(f'VectorStore initialized at: {mgr.persist_directory}')
"
```

**提交：**

```bash
git add modules/rag/vectorstore.py && git commit -m "feat: add ChromaDB vector store manager"
```

---

## Phase 3: 知识库加载

### Task 5: 实现农药知识库加载器

**目标：** 从 SQLite + JSON 种子数据加载农药知识到向量库

**文件：**
- Create: `modules/rag/knowledge_loader.py`

**实现：**

```python
"""Knowledge loaders for RAG vector store."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from langchain_core.documents import Document

from modules.common import DATA_DIR
from modules.sqlite_store import SqliteStore


def load_pesticide_from_sqlite(
    store: SqliteStore,
    limit: int = 1000,
) -> list[Document]:
    """Load pesticide catalog from SQLite as LangChain Documents."""
    
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
    
    documents = []
    for row in rows:
        # Build searchable content
        content_parts = [
            f"农药名称：{row.get('product_name', '')}",
            f"有效成分：{row.get('active_ingredient', '')}",
            f"剂型：{row.get('formulation', '')}",
        ]
        
        target_crops = row.get('target_crops') or ''
        target_pests = row.get('target_pests') or ''
        
        if target_crops:
            content_parts.append(f"适用作物：{target_crops}")
        if target_pests:
            content_parts.append(f"防治对象：{target_pests}")
        if row.get('toxicity'):
            content_parts.append(f"毒性：{row.get('toxicity')}")
        if row.get('dilution_guidance'):
            content_parts.append(f"稀释指导：{row.get('dilution_guidance')}")
        
        content = "\n".join(content_parts)
        
        metadata = {
            'source': 'pesticide_catalog',
            'pesticide_id': row.get('pesticide_id'),
            'product_name': row.get('product_name'),
            'target_pests': target_pests,
            'target_crops': target_crops,
            'toxicity': row.get('toxicity'),
        }
        
        documents.append(Document(page_content=content, metadata=metadata))
    
    return documents


def load_pesticide_from_json(json_path: Path) -> list[Document]:
    """Load pesticide catalog from JSON seed file."""
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    documents = []
    
    # Handle different JSON structures
    items = data if isinstance(data, list) else data.get('data', data.get('pesticides', []))
    
    for item in items:
        if not isinstance(item, dict):
            continue
        
        content_parts = []
        
        product_name = item.get('product_name') or item.get('name') or item.get('农药名称', '')
        if not product_name:
            continue
        
        content_parts.append(f"农药名称：{product_name}")
        
        if item.get('active_ingredient') or item.get('有效成分'):
            content_parts.append(f"有效成分：{item.get('active_ingredient') or item.get('有效成分')}")
        if item.get('formulation') or item.get('剂型'):
            content_parts.append(f"剂型：{item.get('formulation') or item.get('剂型')}")
        if item.get('target_crops') or item.get('适用作物'):
            content_parts.append(f"适用作物：{item.get('target_crops') or item.get('适用作物')}")
        if item.get('target_pests') or item.get('防治对象'):
            content_parts.append(f"防治对象：{item.get('target_pests') or item.get('防治对象')}")
        if item.get('dilution_guidance') or item.get('稀释指导'):
            content_parts.append(f"稀释指导：{item.get('dilution_guidance') or item.get('稀释指导')}")
        if item.get('toxicity') or item.get('毒性'):
            content_parts.append(f"毒性：{item.get('toxicity') or item.get('毒性')}")
        
        content = "\n".join(content_parts)
        
        metadata = {
            'source': 'pesticide_seed',
            'pesticide_id': item.get('pesticide_id') or item.get('id'),
            'product_name': product_name,
            'target_pests': item.get('target_pests') or item.get('防治对象', ''),
            'target_crops': item.get('target_crops') or item.get('适用作物', ''),
        }
        
        documents.append(Document(page_content=content, metadata=metadata))
    
    return documents


def load_historical_decisions(
    store: SqliteStore,
    limit: int = 100,
) -> list[Document]:
    """Load historical decisions as reference documents."""
    
    rows = store.fetch_all(
        """
        SELECT 
            d.request_id,
            d.decision_text,
            d.timestamp,
            t.field_id,
            GROUP_CONCAT(det.label, ', ') as detected_pests
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
    
    documents = []
    for row in rows:
        try:
            decision = json.loads(row.get('decision_text', '{}'))
        except json.JSONDecodeError:
            continue
        
        if not decision:
            continue
        
        detected_pests = row.get('detected_pests', '')
        
        content_parts = [
            f"历史案例：{row.get('request_id', 'unknown')}",
            f"检测到的害虫：{detected_pests}",
            f"推荐农药：{decision.get('用药', {}).get('农药名称', '')}",
            f"用药浓度：{decision.get('用药', {}).get('浓度', '')}",
            f"配比：{decision.get('用药', {}).get('配比', '')}",
        ]
        
        if decision.get('农事建议'):
            suggestions = decision['农事建议']
            if isinstance(suggestions, list):
                content_parts.append(f"农事建议：{'; '.join(suggestions)}")
        
        content = "\n".join(content_parts)
        
        metadata = {
            'source': 'historical_decision',
            'request_id': row.get('request_id'),
            'timestamp': row.get('timestamp'),
            'detected_pests': detected_pests,
            'pesticide_name': decision.get('用药', {}).get('农药名称', ''),
        }
        
        documents.append(Document(page_content=content, metadata=metadata))
    
    return documents


def load_knowledge_from_docs(docs_dir: Path) -> list[Document]:
    """Load markdown/text documents from docs directory."""
    
    documents = []
    
    for md_file in docs_dir.rglob('*.md'):
        content = md_file.read_text(encoding='utf-8')
        
        # Skip very short or auto-generated files
        if len(content) < 100:
            continue
        
        # Create chunks for long documents
        # Simple chunking by paragraphs
        paragraphs = content.split('\n\n')
        
        for i, para in enumerate(paragraphs):
            if len(para.strip()) < 50:
                continue
            
            doc = Document(
                page_content=para.strip(),
                metadata={
                    'source': 'doc',
                    'file': str(md_file.relative_to(docs_dir)),
                    'chunk': i,
                },
            )
            documents.append(doc)
    
    return documents
```

**验证：**

```bash
cd ~/muye && source .venv/bin/activate
python -c "
from modules.rag.knowledge_loader import load_pesticide_from_json
from pathlib import Path

# Try loading from seed
seed_path = Path('data/seeds/henan/pesticide_catalog.json')
if seed_path.exists():
    docs = load_pesticide_from_json(seed_path)
    print(f'Loaded {len(docs)} documents from pesticide_catalog.json')
else:
    print(f'Seed file not found at {seed_path}')
"
```

**提交：**

```bash
git add modules/rag/knowledge_loader.py && git commit -m "feat: add knowledge loaders for pesticide catalog and historical decisions"
```

---

### Task 6: 导入农药种子数据

**目标：** 将 `data/seeds/henan/pesticide_catalog.json` 导入 SQLite

**前提：** 检查种子数据格式，确定导入方式

**验证：**

```bash
# 检查种子数据结构
head -100 ~/muye/data/seeds/henan/pesticide_catalog.json
```

**说明：** 如果种子数据已存在，需要编写导入脚本；如果格式不匹配，需要转换。

---

## Phase 4: RAG 检索器集成

### Task 7: 实现决策增强检索器

**目标：** 创建高层检索器，根据害虫类型检索相关农药和历史案例

**文件：**
- Create: `modules/rag/retriever.py`

**实现：**

```python
"""RAG retriever for agricultural decision support."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langchain_core.documents import Document

from modules.rag.vectorstore import (
    VectorStoreManager,
    COLLECTION_PESTICIDES,
    COLLECTION_DECISIONS,
)


@dataclass
class RetrievedContext:
    """RAG retrieval result."""
    
    pesticides: list[Document]
    historical_cases: list[Document]
    pesticide_scores: list[float]
    decision_scores: list[float]
    
    def to_prompt_text(self) -> str:
        """Format retrieved context as prompt text."""
        lines = ["\n=== RAG 检索增强上下文 ==="]
        
        if self.pesticides:
            lines.append("\n【相关农药推荐】")
            for i, (doc, score) in enumerate(zip(self.pesticides, self.pesticide_scores), 1):
                lines.append(f"\n{i}. {doc.page_content}")
                lines.append(f"   相关度：{score:.2f}")
        
        if self.historical_cases:
            lines.append("\n【历史相似案例】")
            for i, (doc, score) in enumerate(zip(self.historical_cases, self.decision_scores), 1):
                lines.append(f"\n{i}. {doc.page_content}")
                lines.append(f"   相似度：{score:.2f}")
        
        lines.append("\n=== 请参考以上信息生成用药建议 ===\n")
        
        return "\n".join(lines)


class DecisionRAGRetriever:
    """RAG retriever for agricultural decision support."""
    
    def __init__(
        self,
        vector_store: VectorStoreManager,
        pesticide_k: int = 5,
        decision_k: int = 3,
    ):
        self.vector_store = vector_store
        self.pesticide_k = pesticide_k
        self.decision_k = decision_k
    
    def retrieve(
        self,
        pest_types: list[str],
        crop_name: str | None = None,
        field_context: dict[str, Any] | None = None,
    ) -> RetrievedContext:
        """Retrieve relevant pesticides and historical cases."""
        
        # Build query from pest types
        pest_query = "、".join(pest_types) if pest_types else "害虫防治"
        
        if crop_name:
            query = f"{crop_name} {' '.join(pest_types)} 防治农药"
        else:
            query = f"{' '.join(pest_types)} 防治农药"
        
        # Search pesticides
        pesticide_docs_scores = self.vector_store.similarity_search_with_score(
            COLLECTION_PESTICIDES,
            query,
            k=self.pesticide_k * 2,  # Get more for filtering
        )
        
        # Filter by pest type if available
        filtered_pesticides = []
        filtered_scores = []
        for doc, score in pesticide_docs_scores:
            if self._matches_pest(doc, pest_types):
                filtered_pesticides.append(doc)
                filtered_scores.append(score)
                if len(filtered_pesticides) >= self.pesticide_k:
                    break
        
        # If not enough matches, use top results
        if len(filtered_pesticides) < self.pesticide_k:
            remaining = self.pesticide_k - len(filtered_pesticides)
            for doc, score in pesticide_docs_scores:
                if doc not in filtered_pesticides:
                    filtered_pesticides.append(doc)
                    filtered_scores.append(score)
                    if len(filtered_pesticides) >= self.pesticide_k:
                        break
        
        # Search historical decisions
        decision_docs_scores = self.vector_store.similarity_search_with_score(
            COLLECTION_DECISIONS,
            pest_query,
            k=self.decision_k,
        )
        
        decision_docs = [d for d, s in decision_docs_scores]
        decision_scores = [s for d, s in decision_docs_scores]
        
        return RetrievedContext(
            pesticides=filtered_pesticides[:self.pesticide_k],
            historical_cases=decision_docs,
            pesticide_scores=filtered_scores[:self.pesticide_k],
            decision_scores=decision_scores,
        )
    
    def _matches_pest(self, doc: Document, pest_types: list[str]) -> bool:
        """Check if document matches any pest type."""
        if not pest_types:
            return True
        
        target_pests = doc.metadata.get('target_pests', '').lower()
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
    """Build RAG-enhanced prompt for decision engine."""
    
    rag_text = retrieved_context.to_prompt_text()
    
    # Insert RAG context after basic info, before instructions
    enhanced_prompt = f"{base_prompt}\n{rag_text}"
    
    return enhanced_prompt
```

**验证：**

```bash
cd ~/muye && source .venv/bin/activate
python -c "
from modules.rag.retriever import DecisionRAGRetriever, RetrievedContext
print('Retriever module OK')
"
```

**提交：**

```bash
git add modules/rag/retriever.py && git commit -m "feat: add decision RAG retriever with pest-aware filtering"
```

---

## Phase 5: 集成到决策引擎

### Task 8: 更新 DecisionEngine 集成 RAG

**目标：** 修改 `ai_decision.py` 在生成决策前先检索相关知识

**文件：**
- Modify: `modules/ai_decision.py`

**实现要点：**

1. 在 `DecisionEngine.__init__` 添加可选的 `rag_retriever` 参数
2. 在 `generate_decision` 方法中调用 RAG 检索
3. 将检索结果注入到 prompt 中

```python
# In DecisionEngine.__init__
def __init__(
    self,
    # ... existing params ...
    rag_retriever: DecisionRAGRetriever | None = None,
) -> None:
    # ... existing code ...
    self.rag_retriever = rag_retriever


# In generate_decision method, after getting weather:
# Add RAG retrieval
rag_context_text = ""
if self.rag_retriever:
    pest_types = [d.get("pest_type", "") for d in pest_detections]
    crop_name = field_context.get("crop_cycle", {}).get("crop_name")
    
    try:
        retrieved = self.rag_retriever.retrieve(
            pest_types=pest_types,
            crop_name=crop_name,
            field_context=field_context,
        )
        rag_context_text = retrieved.to_prompt_text()
    except Exception as e:
        self.logger.warning(f"RAG retrieval failed: {e}")
```

---

### Task 9: 更新 main.py 初始化 RAG

**目标：** 在应用启动时初始化向量库和 RAG 组件

**文件：**
- Modify: `main.py`

**实现：** 在 `MuyeApplication.__init__` 中添加 RAG 初始化逻辑

---

## Phase 6: 知识库构建脚本

### Task 10: 创建知识库初始化脚本

**目标：** 提供命令行工具构建/更新向量库

**文件：**
- Create: `scripts/build_rag_knowledge.py`

**实现：**

```python
#!/usr/bin/env python
"""Build RAG knowledge base from SQLite and seed data."""

import argparse
from pathlib import Path

from modules.common import DATA_DIR
from modules.rag.vectorstore import (
    VectorStoreManager,
    COLLECTION_PESTICIDES,
    COLLECTION_DECISIONS,
)
from modules.rag.knowledge_loader import (
    load_pesticide_from_sqlite,
    load_pesticide_from_json,
    load_historical_decisions,
)
from modules.sqlite_store import SqliteStore


def main():
    parser = argparse.ArgumentParser(description="Build RAG knowledge base")
    parser.add_argument("--rebuild", action="store_true", help="Rebuild from scratch")
    parser.add_argument("--pesticides", action="store_true", help="Load pesticide catalog")
    parser.add_argument("--decisions", action="store_true", help="Load historical decisions")
    parser.add_argument("--all", action="store_true", help="Load all knowledge")
    args = parser.parse_args()
    
    store = SqliteStore(DATA_DIR / "muye.db")
    vector_store = VectorStoreManager()
    
    try:
        if args.rebuild:
            print("Rebuilding vector stores...")
            vector_store.delete_collection(COLLECTION_PESTICIDES)
            vector_store.delete_collection(COLLECTION_DECISIONS)
        
        if args.all or args.pesticides:
            print("Loading pesticide catalog...")
            
            # Try SQLite first
            docs = load_pesticide_from_sqlite(store)
            
            # Fallback to seed JSON
            if not docs:
                seed_path = DATA_DIR / "seeds" / "henan" / "pesticide_catalog.json"
                if seed_path.exists():
                    docs = load_pesticide_from_json(seed_path)
            
            if docs:
                ids = vector_store.add_documents(COLLECTION_PESTICIDES, docs)
                print(f"Loaded {len(ids)} pesticide documents")
            else:
                print("No pesticide data found")
        
        if args.all or args.decisions:
            print("Loading historical decisions...")
            docs = load_historical_decisions(store)
            
            if docs:
                ids = vector_store.add_documents(COLLECTION_DECISIONS, docs)
                print(f"Loaded {len(ids)} decision documents")
            else:
                print("No historical decisions found")
        
        print("Knowledge base built successfully!")
    
    finally:
        store.close()


if __name__ == "__main__":
    main()
```

**使用：**

```bash
cd ~/muye && source .venv/bin/activate
python scripts/build_rag_knowledge.py --all --rebuild
```

---

## Phase 7: 测试

### Task 11: 编写 RAG 模块单元测试

**目标：** 测试各组件功能

**文件：**
- Create: `tests/test_rag_embeddings.py`
- Create: `tests/test_rag_retriever.py`

---

## 实施顺序总结

```
Phase 1 (环境准备)
├── Task 1: 安装依赖
└── Task 2: 创建目录结构

Phase 2 (向量存储)
├── Task 3: QwenEmbedding 适配器
└── Task 4: ChromaDB 封装

Phase 3 (知识加载)
├── Task 5: 知识库加载器
└── Task 6: 导入种子数据

Phase 4 (检索器)
└── Task 7: 决策检索器

Phase 5 (集成)
├── Task 8: DecisionEngine 集成
└── Task 9: main.py 初始化

Phase 6 (脚本)
└── Task 10: 知识库构建脚本

Phase 7 (测试)
└── Task 11: 单元测试
```

---

## 风险与备选方案

| 风险 | 备选方案 |
|------|---------|
| 千问 Embedding API 不可用 | 使用 `sentence-transformers` 本地模型（如 paraphrase-multilingual） |
| ChromaDB 性能问题 | 切换到 FAISS（纯内存，更轻量） |
| 农药数据不足 | 使用公开农药数据库 API 补充 |

---

## 预期效果

实施后，决策流程变为：

```
原流程：
害虫检测 → 千问决策（无上下文）

新流程：
害虫检测 → RAG检索（农药库+历史案例）→ 千问决策（带增强上下文）
```

决策质量提升点：
1. 推荐农药更精准（基于知识库匹配）
2. 稀释配比更规范（基于标准指导）
3. 参考历史成功案例（相似害虫/作物组合）
