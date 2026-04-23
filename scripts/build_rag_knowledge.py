#!/usr/bin/env python
"""Build RAG knowledge base from SQLite and seed data."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.common import DATA_DIR, load_environment
from modules.rag.knowledge_loader import (
    load_historical_decisions,
    load_knowledge_from_docs,
    load_pesticide_from_json,
    load_pesticide_from_sqlite,
)
from modules.rag.vectorstore import (
    COLLECTION_DECISIONS,
    COLLECTION_KNOWLEDGE,
    COLLECTION_PESTICIDES,
    VectorStoreManager,
)
from modules.sqlite_store import SqliteStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build RAG knowledge base")
    parser.add_argument("--rebuild", action="store_true", help="Rebuild from scratch")
    parser.add_argument("--pesticides", action="store_true", help="Load pesticide catalog")
    parser.add_argument("--decisions", action="store_true", help="Load historical decisions")
    parser.add_argument("--all", action="store_true", help="Load all knowledge")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    load_environment()

    should_load_pesticides = args.all or args.pesticides or not (args.pesticides or args.decisions or args.all)
    should_load_decisions = args.all or args.decisions or not (args.pesticides or args.decisions or args.all)
    should_load_docs = args.all or not (args.pesticides or args.decisions or args.all)

    db_path = Path(os.getenv("MUYE_SQLITE_PATH", str(DATA_DIR / "muye.db")))
    store = SqliteStore(db_path)
    vector_store = VectorStoreManager()

    try:
        if args.rebuild:
            print("Rebuilding vector stores...")
            vector_store.delete_collection(COLLECTION_PESTICIDES)
            vector_store.delete_collection(COLLECTION_DECISIONS)
            vector_store.delete_collection(COLLECTION_KNOWLEDGE)

        if should_load_pesticides:
            print("Loading pesticide catalog...")
            pesticide_docs = load_pesticide_from_sqlite(store)
            print(f"SQLite pesticide rows loaded: {len(pesticide_docs)}")

            if not pesticide_docs:
                seed_path = DATA_DIR / "seeds" / "henan" / "pesticide_catalog.json"
                if seed_path.exists():
                    print(f"Falling back to JSON seed: {seed_path}")
                    pesticide_docs = load_pesticide_from_json(seed_path)

            if pesticide_docs:
                ids = vector_store.add_documents(COLLECTION_PESTICIDES, pesticide_docs)
                print(f"Pesticide documents indexed: {len(ids)}")
            else:
                print("No pesticide data found")

        if should_load_decisions:
            print("Loading historical decisions...")
            decision_docs = load_historical_decisions(store)
            if decision_docs:
                ids = vector_store.add_documents(COLLECTION_DECISIONS, decision_docs)
                print(f"Historical decision documents indexed: {len(ids)}")
            else:
                print("No historical decisions found")

        if should_load_docs:
            print("Loading markdown knowledge from docs/ ...")
            knowledge_docs = load_knowledge_from_docs(PROJECT_ROOT / "docs")
            if knowledge_docs:
                ids = vector_store.add_documents(COLLECTION_KNOWLEDGE, knowledge_docs)
                print(f"Docs knowledge chunks indexed: {len(ids)}")
            else:
                print("No docs knowledge found")

        print("Knowledge base built successfully!")
    finally:
        store.close()


if __name__ == "__main__":
    main()
