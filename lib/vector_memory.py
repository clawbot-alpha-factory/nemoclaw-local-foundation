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
import re
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

    def add_memory(self, collection: str, content: str, metadata: Optional[dict] = None, agent_id: Optional[str] = None) -> None:
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

    def add_skill_output(self, skill_id: str, agent_id: str, output_text: str, metadata: Optional[dict] = None) -> None:
        """Index a skill execution result."""
        meta = metadata or {}
        meta.update({"skill_id": skill_id, "agent_id": agent_id})
        self.add_memory("skill_outputs", output_text[:5000], meta)

    def add_entity(self, name: str, description: str, entity_type: str, source_agent: str) -> None:
        """Track a person, company, or concept."""
        self.add_memory("entity_memory", f"{name}: {description}", {
            "entity_name": name, "entity_type": entity_type, "source_agent": source_agent,
        })

    def accumulate_from_mission(self, mission_dir: Path) -> int:
        """Scan mission deliverables and index knowledge into project_context.

        Reads *.md, *.json, *.yaml from mission_dir, uses call_llm (L-003) to
        extract categorized knowledge items (code_pattern, architecture_decision,
        strategy_insight, lesson_learned), deduplicates against existing entries
        (cosine similarity > 0.95 = skip), and indexes with mission_id provenance.

        Args:
            mission_dir: Path to the mission's local directory.

        Returns:
            Count of new items added to project_context.
        """
        if not mission_dir.is_dir():
            logger.warning("accumulate_from_mission: not a directory: %s", mission_dir)
            return 0

        mission_id = mission_dir.name  # e.g. "mission-abc123"
        files = []
        for ext in ("*.md", "*.json", "*.yaml"):
            files.extend(mission_dir.glob(ext))
        if not files:
            logger.info("accumulate_from_mission: no deliverables in %s", mission_dir)
            return 0

        added = 0
        for fpath in files:
            try:
                content = fpath.read_text(encoding="utf-8", errors="replace")[:5000]
            except OSError as e:
                logger.warning("Failed to read %s: %s", fpath, e)
                continue

            if len(content.strip()) < 50:
                continue

            # Extract knowledge items via LLM (L-003)
            items = self._extract_knowledge(content, fpath.name)
            for item in items:
                category = item.get("category", "general")
                text = item.get("content", "").strip()
                if not text or len(text) < 20:
                    continue

                # Deduplicate: cosine similarity > 0.95 means skip
                existing = self.search("project_context", text, n_results=1)
                if existing and existing[0].get("score", 0) > 0.95:
                    logger.debug("Dedup skip (%.3f): %s", existing[0]["score"], text[:60])
                    continue

                self.add_memory("project_context", text, {
                    "mission_id": mission_id,
                    "category": category,
                    "source_file": fpath.name,
                    "importance": self._category_importance(category),
                })
                added += 1

        logger.info(
            "accumulate_from_mission: added %d items from %s (%d files scanned)",
            added, mission_id, len(files),
        )
        return added

    def _extract_knowledge(self, content: str, filename: str) -> list[dict]:
        """Use call_llm to extract structured knowledge items from content."""
        try:
            from lib.routing import call_llm
            prompt = (
                "Extract knowledge items from this project deliverable. "
                "Return a JSON array where each item has:\n"
                '  {"category": "<code_pattern|architecture_decision|strategy_insight|lesson_learned>", '
                '"content": "<one concise sentence>"}\n\n'
                "Extract only genuinely reusable knowledge. Max 5 items.\n\n"
                f"File: {filename}\n---\n{content[:3000]}"
            )
            result, err = call_llm(
                [{"role": "user", "content": prompt}],
                task_class="structured_short",
                max_tokens=500,
            )
            if not result or err:
                return []

            # Parse JSON array from LLM response
            text = result.strip()
            # Handle markdown code fences
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()

            items = json.loads(text)
            if isinstance(items, list):
                return [i for i in items if isinstance(i, dict) and "content" in i]
        except (json.JSONDecodeError, Exception) as e:
            logger.debug("Knowledge extraction failed for %s: %s", filename, e)
        return []

    @staticmethod
    def _category_importance(category: str) -> int:
        """Map knowledge category to importance score."""
        return {
            "architecture_decision": 9,
            "lesson_learned": 8,
            "strategy_insight": 7,
            "code_pattern": 6,
        }.get(category, 5)

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

    def prune_old(self, days: int = 90) -> None:
        """Remove entries older than N days."""
        cutoff = time.time() - (days * 86400)
        if self._fallback:
            for name in COLLECTIONS:
                self._fallback_store[name] = [
                    e for e in self._fallback_store[name]
                    if e.get("metadata", {}).get("timestamp", time.time()) > cutoff
                ]
        else:
            total_pruned = 0
            for name in COLLECTIONS:
                try:
                    col = self._client.get_or_create_collection(name)
                    results = col.get(where={"timestamp": {"$lt": cutoff}})
                    if results and results["ids"]:
                        col.delete(ids=results["ids"])
                        total_pruned += len(results["ids"])
                except Exception as e:
                    logger.warning("Failed to prune collection %s: %s", name, e)
            if total_pruned:
                logger.info("Pruned %d entries older than %d days from ChromaDB", total_pruned, days)

    # ── Cognitive memory operations ──────────────────────────────────

    def encode(self, text: str, metadata: Optional[dict] = None, importance: Optional[int] = None, collection: str = "agent_memory"):
        """Store a memory with importance scoring.

        If importance is not provided, uses a lightweight LLM call to score 1-10.
        """
        meta = metadata or {}

        if importance is None:
            try:
                from lib.routing import call_llm
                prompt = (
                    "Rate the importance of this memory for a business automation agent on a scale of 1-10. "
                    "1=trivial, 5=moderate, 10=critical. Reply with ONLY the number.\n\n"
                    f"Memory: {text[:500]}"
                )
                result, err = call_llm(
                    [{"role": "user", "content": prompt}],
                    task_class="structured_short",
                    max_tokens=10,
                )
                if result and not err:
                    match = re.search(r"\b(\d{1,2})\b", result.strip())
                    importance = min(max(int(match.group(1)), 1), 10) if match else 5
                else:
                    importance = 5
            except Exception as e:
                logger.warning(f"Importance scoring failed: {e} — defaulting to 5")
                importance = 5

        meta["importance"] = importance
        self.add_memory(collection, text, meta)
        logger.debug(f"Encoded memory (importance={importance}): {text[:80]}")

    def consolidate(self, collection: str = "agent_memory", max_age_days: int = 90, similarity_threshold: float = 0.85) -> dict:
        """Consolidate similar memories and prune low-importance old entries.

        1. Find clusters of similar memories (>= similarity_threshold).
        2. Merge each cluster into a summary via LLM, delete originals.
        3. Prune items with importance < 3 older than max_age_days.

        Returns: {"merged": int, "pruned": int}
        """
        if collection not in COLLECTIONS:
            return {"merged": 0, "pruned": 0}

        merged_count = 0
        pruned_count = 0
        cutoff = time.time() - (max_age_days * 86400)

        if self._fallback:
            entries = self._fallback_store.get(collection, [])

            # ── Prune low-importance old items ──
            keep = []
            for e in entries:
                meta = e.get("metadata", {})
                imp = meta.get("importance", 5)
                ts = meta.get("timestamp", time.time())
                if imp < 3 and ts < cutoff:
                    pruned_count += 1
                else:
                    keep.append(e)
            self._fallback_store[collection] = keep

            # ── Cluster similar memories (simple word-overlap for fallback) ──
            entries = self._fallback_store[collection]
            used = set()
            clusters = []
            for i, a in enumerate(entries):
                if i in used:
                    continue
                cluster = [i]
                a_words = set(a["content"].lower().split())
                for j, b in enumerate(entries):
                    if j <= i or j in used:
                        continue
                    b_words = set(b["content"].lower().split())
                    union = len(a_words | b_words)
                    if union > 0 and len(a_words & b_words) / union >= similarity_threshold:
                        cluster.append(j)
                        used.add(j)
                if len(cluster) > 1:
                    used.update(cluster)
                    clusters.append(cluster)

            for cluster_idxs in clusters:
                texts = [entries[i]["content"] for i in cluster_idxs]
                try:
                    from lib.routing import call_llm
                    prompt = (
                        "Merge these related memories into ONE concise summary (1-2 sentences):\n\n"
                        + "\n".join(f"- {t[:300]}" for t in texts)
                    )
                    result, err = call_llm(
                        [{"role": "user", "content": prompt}],
                        task_class="structured_short",
                        max_tokens=150,
                    )
                    summary = result.strip() if result and not err else " | ".join(t[:100] for t in texts)
                except Exception:
                    summary = " | ".join(t[:100] for t in texts)

                # Keep highest importance from cluster
                max_imp = max(entries[i].get("metadata", {}).get("importance", 5) for i in cluster_idxs)
                # Remove originals (reverse order to preserve indices)
                for i in sorted(cluster_idxs, reverse=True):
                    self._fallback_store[collection].pop(i)
                # Add merged entry
                self.add_memory(collection, summary, {"importance": max_imp, "consolidated": True})
                merged_count += len(cluster_idxs)

        else:
            # ── ChromaDB path ──
            try:
                col = self._collections[collection]
                all_data = col.get(include=["documents", "metadatas"])
                ids = all_data.get("ids", [])
                docs = all_data.get("documents", [])
                metas = all_data.get("metadatas", [])

                # ── Prune low-importance old items ──
                prune_ids = []
                for i, doc_id in enumerate(ids):
                    meta = metas[i] if i < len(metas) else {}
                    imp = meta.get("importance", 5)
                    ts = meta.get("timestamp", time.time())
                    if imp < 3 and ts < cutoff:
                        prune_ids.append(doc_id)

                if prune_ids:
                    col.delete(ids=prune_ids)
                    pruned_count = len(prune_ids)

                # ── Cluster via ChromaDB similarity search ──
                remaining = col.get(include=["documents", "metadatas"])
                r_ids = remaining.get("ids", [])
                r_docs = remaining.get("documents", [])
                r_metas = remaining.get("metadatas", [])

                used = set()
                clusters = []
                for i, doc in enumerate(r_docs):
                    if r_ids[i] in used:
                        continue
                    results = col.query(query_texts=[doc], n_results=min(10, len(r_docs)))
                    cluster_ids = []
                    cluster_docs = []
                    cluster_imps = []
                    for j, rid in enumerate(results.get("ids", [[]])[0]):
                        if rid in used:
                            continue
                        dist = results.get("distances", [[]])[0][j]
                        similarity = 1 - dist
                        if similarity >= similarity_threshold:
                            cluster_ids.append(rid)
                            cluster_docs.append(results.get("documents", [[]])[0][j])
                            idx = r_ids.index(rid) if rid in r_ids else -1
                            imp = r_metas[idx].get("importance", 5) if idx >= 0 and idx < len(r_metas) else 5
                            cluster_imps.append(imp)
                            used.add(rid)

                    if len(cluster_ids) > 1:
                        clusters.append((cluster_ids, cluster_docs, cluster_imps))

                for cluster_ids, cluster_docs, cluster_imps in clusters:
                    try:
                        from lib.routing import call_llm
                        prompt = (
                            "Merge these related memories into ONE concise summary (1-2 sentences):\n\n"
                            + "\n".join(f"- {t[:300]}" for t in cluster_docs)
                        )
                        result, err = call_llm(
                            [{"role": "user", "content": prompt}],
                            task_class="structured_short",
                            max_tokens=150,
                        )
                        summary = result.strip() if result and not err else " | ".join(t[:100] for t in cluster_docs)
                    except Exception:
                        summary = " | ".join(t[:100] for t in cluster_docs)

                    col.delete(ids=cluster_ids)
                    max_imp = max(cluster_imps)
                    self.add_memory(collection, summary, {"importance": max_imp, "consolidated": True})
                    merged_count += len(cluster_ids)

            except Exception as e:
                logger.warning(f"Consolidation failed for {collection}: {e}")

        logger.info(f"Consolidation complete: merged={merged_count}, pruned={pruned_count}")
        return {"merged": merged_count, "pruned": pruned_count}

    def forget(self, collection: str, filter_criteria: dict) -> int:
        """Delete memories matching filter criteria.

        Supported filter keys:
        - agent_id: str — match exact agent
        - older_than_days: int — match entries older than N days
        - skill_id: str — match exact skill
        - importance_below: int — match entries with importance < N

        Returns: count of deleted entries.
        """
        if collection not in COLLECTIONS:
            return 0

        deleted = 0
        agent_id = filter_criteria.get("agent_id")
        older_than_days = filter_criteria.get("older_than_days")
        skill_id = filter_criteria.get("skill_id")
        importance_below = filter_criteria.get("importance_below")
        cutoff = time.time() - (older_than_days * 86400) if older_than_days else None

        if self._fallback:
            entries = self._fallback_store.get(collection, [])
            keep = []
            for e in entries:
                meta = e.get("metadata", {})
                match = True
                if agent_id and meta.get("agent_id") != agent_id:
                    match = False
                if skill_id and meta.get("skill_id") != skill_id:
                    match = False
                if cutoff and meta.get("timestamp", time.time()) >= cutoff:
                    match = False
                if importance_below and meta.get("importance", 5) >= importance_below:
                    match = False
                if match:
                    deleted += 1
                else:
                    keep.append(e)
            self._fallback_store[collection] = keep
        else:
            try:
                col = self._collections[collection]
                all_data = col.get(include=["metadatas"])
                ids = all_data.get("ids", [])
                metas = all_data.get("metadatas", [])

                delete_ids = []
                for i, doc_id in enumerate(ids):
                    meta = metas[i] if i < len(metas) else {}
                    match = True
                    if agent_id and meta.get("agent_id") != agent_id:
                        match = False
                    if skill_id and meta.get("skill_id") != skill_id:
                        match = False
                    if cutoff and meta.get("timestamp", time.time()) >= cutoff:
                        match = False
                    if importance_below and meta.get("importance", 5) >= importance_below:
                        match = False
                    if match:
                        delete_ids.append(doc_id)

                if delete_ids:
                    col.delete(ids=delete_ids)
                    deleted = len(delete_ids)
            except Exception as e:
                logger.warning(f"Forget failed for {collection}: {e}")

        logger.info(f"Forgot {deleted} memories from {collection} (criteria={filter_criteria})")
        return deleted
