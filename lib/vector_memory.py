"""
Vector Memory — Persistent semantic memory for all agents using ChromaDB.

Collections:
- agent_memory: per-agent episodic memories
- skill_outputs: indexed skill execution results
- entity_memory: people, companies, concepts
- project_context: per-project shared knowledge

Falls back to simple dict storage if ChromaDB is not installed.
"""

import json
import logging
import time
import uuid
from pathlib import Path
from typing import Optional

logger = logging.getLogger("nemoclaw.vector_memory")

PERSIST_DIR = Path.home() / ".nemoclaw" / "vector-store"
COLLECTIONS = ["agent_memory", "skill_outputs", "entity_memory", "project_context"]


class VectorMemory:
    """Persistent semantic memory backed by ChromaDB."""

    def __init__(self, persist_dir: Optional[Path] = None):
        self.persist_dir = persist_dir or PERSIST_DIR
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self._client = None
        self._collections = {}
        self._fallback = False
        self._init_client()

    def _init_client(self):
        try:
            import chromadb
            self._client = chromadb.PersistentClient(path=str(self.persist_dir))
            for name in COLLECTIONS:
                self._collections[name] = self._client.get_or_create_collection(
                    name=name,
                    metadata={"hnsw:space": "cosine"},
                )
            logger.info(f"VectorMemory initialized with ChromaDB at {self.persist_dir}")
        except ImportError:
            logger.warning("ChromaDB not installed — using fallback dict storage")
            self._fallback = True
            self._fallback_store = {name: [] for name in COLLECTIONS}
        except Exception as e:
            logger.warning(f"ChromaDB init failed: {e} — using fallback")
            self._fallback = True
            self._fallback_store = {name: [] for name in COLLECTIONS}

    def add_memory(self, collection: str, content: str, metadata: Optional[dict] = None, agent_id: Optional[str] = None):
        """Add a memory entry to a collection."""
        if collection not in COLLECTIONS:
            logger.warning(f"Unknown collection: {collection}")
            return

        meta = metadata or {}
        if agent_id:
            meta["agent_id"] = agent_id
        meta["timestamp"] = time.time()
        doc_id = str(uuid.uuid4())[:12]

        if self._fallback:
            self._fallback_store[collection].append({
                "id": doc_id, "content": content, "metadata": meta,
            })
            return

        try:
            self._collections[collection].add(
                documents=[content], metadatas=[meta], ids=[doc_id],
            )
        except Exception as e:
            logger.warning(f"Failed to add to {collection}: {e}")

    def add_skill_output(self, skill_id: str, agent_id: str, output_text: str, metadata: Optional[dict] = None):
        """Index a skill execution result."""
        meta = metadata or {}
        meta.update({"skill_id": skill_id, "agent_id": agent_id})
        self.add_memory("skill_outputs", output_text[:5000], meta)

    def add_entity(self, name: str, description: str, entity_type: str, source_agent: str):
        """Track a person, company, or concept."""
        self.add_memory("entity_memory", f"{name}: {description}", {
            "entity_name": name, "entity_type": entity_type, "source_agent": source_agent,
        })

    def search(self, collection: str, query: str, n_results: int = 5, agent_id: Optional[str] = None) -> list:
        """Search a collection by semantic similarity."""
        if collection not in COLLECTIONS:
            return []

        if self._fallback:
            entries = self._fallback_store.get(collection, [])
            if agent_id:
                entries = [e for e in entries if e.get("metadata", {}).get("agent_id") == agent_id]
            # Simple keyword matching fallback
            scored = []
            query_words = set(query.lower().split())
            for e in entries:
                content_words = set(e["content"].lower().split())
                overlap = len(query_words & content_words)
                if overlap > 0:
                    scored.append((overlap, e))
            scored.sort(key=lambda x: -x[0])
            return [{"content": e["content"], "metadata": e["metadata"], "score": s / max(len(query_words), 1)}
                    for s, e in scored[:n_results]]

        try:
            where = {"agent_id": agent_id} if agent_id else None
            results = self._collections[collection].query(
                query_texts=[query], n_results=n_results, where=where,
            )
            output = []
            for i, doc in enumerate(results.get("documents", [[]])[0]):
                meta = results.get("metadatas", [[]])[0][i] if results.get("metadatas") else {}
                dist = results.get("distances", [[]])[0][i] if results.get("distances") else 0
                output.append({"content": doc, "metadata": meta, "score": round(1 - dist, 4)})
            return output
        except Exception as e:
            logger.warning(f"Search failed in {collection}: {e}")
            return []

    def get_relevant_context(self, query: str, collections: Optional[list] = None, n_results: int = 10) -> list:
        """Search across multiple collections and merge results."""
        cols = collections or COLLECTIONS
        all_results = []
        for col in cols:
            results = self.search(col, query, n_results=n_results // len(cols) + 1)
            for r in results:
                r["collection"] = col
            all_results.extend(results)
        all_results.sort(key=lambda x: -x.get("score", 0))
        return all_results[:n_results]

    def get_entity(self, name: str) -> list:
        """Find all mentions of an entity."""
        return self.search("entity_memory", name, n_results=20)

    def get_stats(self) -> dict:
        """Get counts per collection."""
        stats = {}
        if self._fallback:
            for name, entries in self._fallback_store.items():
                stats[name] = len(entries)
        else:
            for name, col in self._collections.items():
                stats[name] = col.count()
        stats["backend"] = "fallback" if self._fallback else "chromadb"
        return stats

    def prune_old(self, days: int = 90):
        """Remove entries older than N days."""
        cutoff = time.time() - (days * 86400)
        if self._fallback:
            for name in COLLECTIONS:
                self._fallback_store[name] = [
                    e for e in self._fallback_store[name]
                    if e.get("metadata", {}).get("timestamp", time.time()) > cutoff
                ]
        else:
            logger.info(f"Pruning entries older than {days} days (ChromaDB manual delete)")
            # ChromaDB doesn't support time-based deletion natively
            # Would need to query + delete by ID
