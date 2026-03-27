#!/usr/bin/env python3
"""
NemoClaw Agent Memory System v1.0 (MA-2)

3-layer memory architecture for multi-agent coordination:

Layer 1 — Private Memory (per agent)
  - Lessons learned, calibration, performance history
  - Only the owning agent can read/write
  - Persistent across all workflows

Layer 2 — Shared Workspace (per workflow)
  - Artifacts, decisions, insights, workflow state
  - All agents read, write restricted by domain patterns (MA-1)
  - Lives for workflow duration + retention

Layer 3 — Long-Term Memory (cross-workflow)
  - Validated patterns, proven strategies, decision outcomes
  - Executive Operator writes (auto-promoted from shared)
  - All agents read

Storage: JSON now, migrate to SQLite at 1000+ entries.
Conflict: Block+escalate for critical keys, last-write-wins for auxiliary.
Promotion: Auto-promote high-confidence insights.

Usage:
  from agent_memory import MemorySystem
  mem = MemorySystem(workspace_id="my_workflow")
  mem.shared.write("market_trends", data, agent="strategy_lead", importance="critical")
  mem.private("strategy_lead").write("lesson_1", "Always check TAM first")
  mem.long_term.read("pricing_pattern_saas")
"""

import fnmatch
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path.home() / ".nemoclaw"
AGENTS_DIR = BASE_DIR / "agents"
WORKSPACES_DIR = BASE_DIR / "workspaces"
LONG_TERM_DIR = BASE_DIR / "memory"

MAX_PRIVATE_ENTRIES = 500
AUTO_PROMOTE_CONFIDENCE = 0.75
MAX_PROMPT_INJECTION_ENTRIES = 10
MAX_PROMPT_INJECTION_CHARS = 4000


# ═══════════════════════════════════════════════════════════════════════════════
# MEMORY ENTRY
# ═══════════════════════════════════════════════════════════════════════════════

def _make_entry(value, source_agent, importance="standard", confidence=0.5,
                tags=None, workflow_id=None):
    """Create a standardized memory entry."""
    return {
        "value": value,
        "source_agent": source_agent,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "importance": importance,       # critical | standard | auxiliary
        "confidence": confidence,       # 0.0 - 1.0
        "tags": tags or [],
        "workflow_id": workflow_id,
        "access_count": 0,
        "last_accessed": None,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# LAYER 1: PRIVATE MEMORY (per agent)
# ═══════════════════════════════════════════════════════════════════════════════

class PrivateMemory:
    """Per-agent private memory. Only the owning agent can read/write.
    
    Stores: lessons learned, calibration data, performance history.
    Persistent across all workflows.
    Auto-archives oldest entries when exceeding MAX_PRIVATE_ENTRIES.
    """

    def __init__(self, agent_id):
        self.agent_id = agent_id
        self.store = {}
        self.dir = AGENTS_DIR / agent_id
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / "private.json"
        self._load()

    def _load(self):
        if self.path.exists():
            with open(self.path) as f:
                self.store = json.load(f)

    def _save(self):
        with open(self.path, "w") as f:
            json.dump(self.store, f, indent=2)

    def write(self, key, value, importance="standard", confidence=0.5, tags=None):
        """Write to private memory. Auto-archives if over limit."""
        self.store[key] = _make_entry(
            value, self.agent_id, importance, confidence, tags
        )
        # Auto-archive oldest if over limit
        if len(self.store) > MAX_PRIVATE_ENTRIES:
            oldest_key = min(self.store, key=lambda k: self.store[k]["timestamp"])
            archive_path = self.dir / "archived.jsonl"
            with open(archive_path, "a") as f:
                f.write(json.dumps({oldest_key: self.store.pop(oldest_key)}) + "\n")
        self._save()

    def read(self, key, default=None):
        """Read from private memory."""
        entry = self.store.get(key)
        if entry is None:
            return default
        entry["access_count"] += 1
        entry["last_accessed"] = datetime.now(timezone.utc).isoformat()
        self._save()
        return entry["value"]

    def search(self, keyword):
        """Search private memory by keyword in keys and values."""
        results = {}
        for key, entry in self.store.items():
            val_str = str(entry["value"]).lower()
            if keyword.lower() in key.lower() or keyword.lower() in val_str:
                results[key] = entry
        return results

    def lessons(self):
        """Get all entries tagged as 'lesson'."""
        return {k: v for k, v in self.store.items() if "lesson" in v.get("tags", [])}

    def keys(self):
        return list(self.store.keys())

    def size(self):
        return len(self.store)


# ═══════════════════════════════════════════════════════════════════════════════
# LAYER 2: SHARED WORKSPACE (per workflow)
# ═══════════════════════════════════════════════════════════════════════════════

class SharedWorkspaceMemory:
    """Shared memory for a single workflow. All agents read, write restricted by domain.

    Write rules enforced via domain_patterns from MA-1 agent schema.
    Critical keys: block + escalate on conflict.
    Auxiliary keys: last-write-wins with audit log.
    """

    def __init__(self, workspace_id, domain_patterns=None):
        """
        Args:
            workspace_id: unique workflow identifier
            domain_patterns: dict of {agent_id: [glob_patterns]} for write access
        """
        self.workspace_id = workspace_id
        self.domain_patterns = domain_patterns or {}
        self.store = {}
        self.audit_log = []
        self.conflicts = []
        self.dir = WORKSPACES_DIR / workspace_id
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / "shared.json"
        self.audit_path = self.dir / "audit.jsonl"
        self._load()

    def _load(self):
        if self.path.exists():
            with open(self.path) as f:
                self.store = json.load(f)

    def _save(self):
        with open(self.path, "w") as f:
            json.dump(self.store, f, indent=2)

    def _audit(self, action, agent, key, detail=""):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "agent": agent,
            "key": key,
            "detail": detail,
        }
        self.audit_log.append(entry)
        with open(self.audit_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def _check_write_permission(self, agent_id, key):
        """Check if agent is allowed to write to this key.
        
        Returns: (allowed, reason)
        """
        patterns = self.domain_patterns.get(agent_id, [])

        # Executive operator has wildcard
        if "*" in patterns:
            return True, "Full access"

        for pattern in patterns:
            if fnmatch.fnmatch(key, pattern):
                return True, f"Matches {pattern}"

        return False, f"No matching pattern for '{key}' in {patterns}"

    def write(self, key, value, agent, importance="standard", confidence=0.5,
              tags=None, workflow_id=None):
        """Write to shared memory with domain enforcement and conflict handling.
        
        Returns: (success, message)
        """
        # Check write permission
        allowed, reason = self._check_write_permission(agent, key)
        if not allowed:
            self._audit("BLOCKED_WRITE", agent, key, reason)
            return False, f"MEMORY VIOLATION: {agent} cannot write '{key}': {reason}"

        # Conflict detection
        if key in self.store:
            existing = self.store[key]
            existing_agent = existing.get("source_agent")

            if existing_agent != agent:
                existing_importance = existing.get("importance", "standard")

                # Critical keys: block and escalate
                if existing_importance == "critical" or importance == "critical":
                    conflict = {
                        "key": key,
                        "existing_agent": existing_agent,
                        "new_agent": agent,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "resolution": "PENDING — escalate to executive_operator",
                    }
                    self.conflicts.append(conflict)
                    self._audit("CONFLICT_CRITICAL", agent, key,
                               f"Blocked: {existing_agent} wrote critical key, {agent} tried to overwrite")
                    return False, (
                        f"CONFLICT: Critical key '{key}' owned by {existing_agent}. "
                        f"Escalate to executive_operator."
                    )

                # Auxiliary keys: last-write-wins with audit
                self._audit("OVERWRITE", agent, key,
                           f"Previous: {existing_agent}, new: {agent} (last-write-wins)")

        # Write
        self.store[key] = _make_entry(
            value, agent, importance, confidence, tags, workflow_id
        )
        self._audit("WRITE", agent, key, f"importance={importance}, confidence={confidence}")
        self._save()
        return True, "OK"

    def read(self, key, default=None):
        """Read from shared memory. Any agent can read."""
        entry = self.store.get(key)
        if entry is None:
            return default
        entry["access_count"] = entry.get("access_count", 0) + 1
        entry["last_accessed"] = datetime.now(timezone.utc).isoformat()
        self._save()
        return entry["value"]

    def read_entry(self, key):
        """Read full entry (with metadata) from shared memory."""
        return self.store.get(key)

    def read_many(self, keys):
        """Read multiple keys."""
        return {k: self.read(k) for k in keys if k in self.store}

    def read_by_agent(self, agent_id):
        """Get all entries written by a specific agent."""
        return {k: v for k, v in self.store.items()
                if v.get("source_agent") == agent_id}

    def read_by_importance(self, importance):
        """Get all entries at a specific importance level."""
        return {k: v for k, v in self.store.items()
                if v.get("importance") == importance}

    def has(self, key):
        return key in self.store

    def keys(self):
        return list(self.store.keys())

    def size(self):
        return len(self.store)

    def get_conflicts(self):
        """Get unresolved conflicts."""
        return [c for c in self.conflicts if c.get("resolution", "").startswith("PENDING")]

    def resolve_conflict(self, key, winner_agent, rationale):
        """Resolve a conflict by choosing the winning agent's value."""
        for conflict in self.conflicts:
            if conflict["key"] == key and conflict["resolution"].startswith("PENDING"):
                conflict["resolution"] = f"RESOLVED: {winner_agent} wins — {rationale}"
                self._audit("CONFLICT_RESOLVED", "executive_operator", key, rationale)
                break

    def promotable_entries(self):
        """Get entries eligible for long-term promotion.
        
        Criteria: confidence >= AUTO_PROMOTE_CONFIDENCE and importance != auxiliary
        """
        return {
            k: v for k, v in self.store.items()
            if v.get("confidence", 0) >= AUTO_PROMOTE_CONFIDENCE
            and v.get("importance") != "auxiliary"
        }

    def dump(self):
        """Return human-readable memory summary."""
        result = {}
        for k, v in self.store.items():
            val_preview = str(v.get("value", ""))[:100].replace("\n", " ")
            result[k] = {
                "value_preview": val_preview,
                "source": v.get("source_agent"),
                "importance": v.get("importance"),
                "confidence": v.get("confidence"),
                "accessed": v.get("access_count", 0),
            }
        return result


# ═══════════════════════════════════════════════════════════════════════════════
# LAYER 3: LONG-TERM MEMORY (cross-workflow)
# ═══════════════════════════════════════════════════════════════════════════════

class LongTermMemory:
    """Persistent cross-workflow memory. Executive Operator curates.
    
    Auto-promotes high-confidence insights from shared workspaces.
    All agents can read. Only executive_operator writes.
    """

    def __init__(self):
        self.dir = LONG_TERM_DIR
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / "long-term.json"
        self.store = {}
        self._load()

    def _load(self):
        if self.path.exists():
            with open(self.path) as f:
                self.store = json.load(f)

    def _save(self):
        with open(self.path, "w") as f:
            json.dump(self.store, f, indent=2)

    def write(self, key, value, source_agent, source_workflow=None,
              confidence=0.8, tags=None):
        """Write to long-term memory. Should only be called by executive_operator."""
        self.store[key] = {
            **_make_entry(value, source_agent, "long_term", confidence, tags, source_workflow),
            "promoted_at": datetime.now(timezone.utc).isoformat(),
            "source_workflow": source_workflow,
            "validated": True,
        }
        self._save()

    def read(self, key, default=None):
        entry = self.store.get(key)
        if entry is None:
            return default
        entry["access_count"] = entry.get("access_count", 0) + 1
        entry["last_accessed"] = datetime.now(timezone.utc).isoformat()
        self._save()
        return entry["value"]

    def search(self, keyword):
        """Search long-term memory by keyword."""
        results = {}
        for key, entry in self.store.items():
            val_str = str(entry.get("value", "")).lower()
            if keyword.lower() in key.lower() or keyword.lower() in val_str:
                results[key] = entry
        return results

    def search_by_tags(self, tags):
        """Find entries matching any of the given tags."""
        results = {}
        for key, entry in self.store.items():
            entry_tags = set(entry.get("tags", []))
            if entry_tags & set(tags):
                results[key] = entry
        return results

    def auto_promote_from_workspace(self, shared_memory, workspace_id):
        """Auto-promote high-confidence entries from shared workspace.
        
        Returns: list of promoted keys
        """
        promotable = shared_memory.promotable_entries()
        promoted = []

        for key, entry in promotable.items():
            lt_key = f"{workspace_id}__{key}"
            # Don't duplicate
            if lt_key in self.store:
                continue
            self.write(
                lt_key,
                entry["value"],
                source_agent=entry["source_agent"],
                source_workflow=workspace_id,
                confidence=entry.get("confidence", 0.8),
                tags=entry.get("tags", []) + ["auto_promoted"],
            )
            promoted.append(lt_key)

        return promoted

    def keys(self):
        return list(self.store.keys())

    def size(self):
        return len(self.store)

    def dump(self):
        result = {}
        for k, v in self.store.items():
            val_preview = str(v.get("value", ""))[:100].replace("\n", " ")
            result[k] = {
                "value_preview": val_preview,
                "source": v.get("source_agent"),
                "confidence": v.get("confidence"),
                "source_workflow": v.get("source_workflow"),
                "accessed": v.get("access_count", 0),
            }
        return result


# ═══════════════════════════════════════════════════════════════════════════════
# MEMORY SYSTEM (unified access)
# ═══════════════════════════════════════════════════════════════════════════════

class MemorySystem:
    """Unified access to all 3 memory layers.
    
    Usage:
        mem = MemorySystem("my_workflow", domain_patterns={...})
        mem.shared.write("key", value, agent="strategy_lead")
        mem.private("strategy_lead").write("lesson", "always check TAM")
        mem.long_term.read("pricing_pattern")
        mem.inject_context("strategy_lead", max_entries=10)
    """

    def __init__(self, workspace_id, domain_patterns=None):
        self.workspace_id = workspace_id
        self.shared = SharedWorkspaceMemory(workspace_id, domain_patterns)
        self.long_term = LongTermMemory()
        self._private_cache = {}

    def private(self, agent_id):
        """Get private memory for a specific agent."""
        if agent_id not in self._private_cache:
            self._private_cache[agent_id] = PrivateMemory(agent_id)
        return self._private_cache[agent_id]

    def inject_context(self, agent_id, max_entries=MAX_PROMPT_INJECTION_ENTRIES,
                       max_chars=MAX_PROMPT_INJECTION_CHARS):
        """Build context string for injecting into an agent's LLM prompt.
        
        Priority: private lessons > shared critical > shared standard > long-term relevant
        
        Returns: context string for prompt injection
        """
        parts = []
        char_count = 0

        # 1. Private lessons (highest priority)
        private = self.private(agent_id)
        lessons = private.lessons()
        for key, entry in sorted(lessons.items(), 
                                  key=lambda x: x[1].get("timestamp", ""), reverse=True):
            if len(parts) >= max_entries:
                break
            text = f"[PRIVATE LESSON] {key}: {str(entry['value'])[:200]}"
            if char_count + len(text) > max_chars:
                break
            parts.append(text)
            char_count += len(text)

        # 2. Shared critical entries
        critical = self.shared.read_by_importance("critical")
        for key, entry in sorted(critical.items(),
                                  key=lambda x: x[1].get("timestamp", ""), reverse=True):
            if len(parts) >= max_entries:
                break
            text = f"[SHARED CRITICAL] {key} (from {entry['source_agent']}): {str(entry['value'])[:200]}"
            if char_count + len(text) > max_chars:
                break
            parts.append(text)
            char_count += len(text)

        # 3. Shared standard entries (from current workflow)
        standard = self.shared.read_by_importance("standard")
        for key, entry in sorted(standard.items(),
                                  key=lambda x: x[1].get("confidence", 0), reverse=True):
            if len(parts) >= max_entries:
                break
            text = f"[SHARED] {key} (from {entry['source_agent']}): {str(entry['value'])[:200]}"
            if char_count + len(text) > max_chars:
                break
            parts.append(text)
            char_count += len(text)

        # 4. Long-term relevant entries
        lt_entries = self.long_term.store
        for key, entry in sorted(lt_entries.items(),
                                  key=lambda x: x[1].get("access_count", 0), reverse=True):
            if len(parts) >= max_entries:
                break
            text = f"[LONG-TERM] {key}: {str(entry['value'])[:200]}"
            if char_count + len(text) > max_chars:
                break
            parts.append(text)
            char_count += len(text)

        if not parts:
            return ""

        header = f"=== AGENT MEMORY CONTEXT ({len(parts)} entries) ===\n"
        return header + "\n".join(parts) + "\n=== END MEMORY CONTEXT ==="

    def post_workflow_promote(self):
        """Run after workflow completes. Auto-promotes high-confidence shared entries.
        
        Returns: list of promoted keys
        """
        promoted = self.long_term.auto_promote_from_workspace(
            self.shared, self.workspace_id
        )
        return promoted

    def summary(self):
        """Print memory system summary."""
        print(f"Workspace: {self.workspace_id}")
        print(f"  Shared: {self.shared.size()} entries")
        print(f"  Long-term: {self.long_term.size()} entries")
        conflicts = self.shared.get_conflicts()
        if conflicts:
            print(f"  ⚠️  Unresolved conflicts: {len(conflicts)}")
        agents_with_private = list(self._private_cache.keys())
        for aid in agents_with_private:
            print(f"  Private ({aid}): {self.private(aid).size()} entries")

    def needs_migration(self):
        """Check if any memory layer exceeds 1000 entries (SQLite migration trigger)."""
        sizes = {
            "shared": self.shared.size(),
            "long_term": self.long_term.size(),
        }
        for aid in self._private_cache:
            sizes[f"private_{aid}"] = self.private(aid).size()
        
        triggers = {k: v for k, v in sizes.items() if v >= 1000}
        if triggers:
            return True, triggers
        return False, {}


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="NemoClaw Agent Memory System")
    parser.add_argument("--workspace", default="default", help="Workspace ID")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--test", action="store_true", help="Run enforcement tests")
    parser.add_argument("--dump-shared", action="store_true")
    parser.add_argument("--dump-long-term", action="store_true")
    parser.add_argument("--dump-private", metavar="AGENT_ID")
    parser.add_argument("--inject", metavar="AGENT_ID", help="Show prompt injection for agent")
    parser.add_argument("--promote", action="store_true", help="Run post-workflow promotion")
    args = parser.parse_args()

    # Load domain patterns from agent schema
    schema_path = Path.home() / "nemoclaw-local-foundation" / "config" / "agents" / "agent-schema.yaml"
    domain_patterns = {}
    if schema_path.exists():
        import yaml
        with open(schema_path) as f:
            schema = yaml.safe_load(f) or {}
        for agent_id, domain in schema.get("domain_boundaries", {}).items():
            domain_patterns[agent_id] = domain.get("memory_write_keys", [])

    mem = MemorySystem(args.workspace, domain_patterns)

    if args.summary:
        mem.summary()

    elif args.test:
        print("=" * 50)
        print("  MA-2 Memory System Enforcement Tests")
        print("=" * 50)
        print()

        # Test 1: Valid shared write
        ok, msg = mem.shared.write("market_trends", "AI agents growing 40%",
                                    agent="strategy_lead", importance="standard", confidence=0.8)
        print(f"  {'✅' if ok else '❌'} Strategy writes market_trends: {msg}")

        # Test 2: Invalid shared write (domain violation)
        ok, msg = mem.shared.write("market_trends", "overwrite attempt",
                                    agent="engineering_lead", importance="standard")
        print(f"  {'✅' if not ok else '❌'} Engineering blocked from market_trends: {msg[:80]}")

        # Test 3: Critical key conflict
        ok, msg = mem.shared.write("market_overview", "original analysis",
                                    agent="strategy_lead", importance="critical", confidence=0.9)
        print(f"  {'✅' if ok else '❌'} Strategy writes critical market_overview: {msg}")

        ok, msg = mem.shared.write("market_overview", "competing analysis",
                                    agent="operations_lead", importance="standard")
        print(f"  {'✅' if not ok else '❌'} Ops blocked from critical market_overview: {msg[:80]}")

        # Test 4: Auxiliary key last-write-wins
        ok, msg = mem.shared.write("workflow_status", "running",
                                    agent="operations_lead", importance="auxiliary")
        print(f"  {'✅' if ok else '❌'} Ops writes auxiliary workflow_status: {msg}")

        ok, msg = mem.shared.write("workflow_update", "complete",
                                    agent="operations_lead", importance="auxiliary")
        print(f"  {'✅' if ok else '❌'} Ops overwrites auxiliary key: {msg}")

        # Test 5: Private memory isolation
        mem.private("strategy_lead").write("lesson_1", "Always verify TAM",
                                           tags=["lesson"], confidence=0.9)
        val = mem.private("strategy_lead").read("lesson_1")
        print(f"  {'✅' if val else '❌'} Strategy reads own private: {val}")

        val2 = mem.private("engineering_lead").read("lesson_1")
        print(f"  {'✅' if val2 is None else '❌'} Engineering can't read strategy private: {val2}")

        # Test 6: Long-term promotion
        promoted = mem.post_workflow_promote()
        print(f"  {'✅' if len(promoted) > 0 else '⚠️'} Auto-promoted {len(promoted)} entries to long-term")

        # Test 7: Context injection
        context = mem.inject_context("strategy_lead")
        has_content = len(context) > 0
        print(f"  {'✅' if has_content else '⚠️'} Context injection: {len(context)} chars")

        # Test 8: Migration check
        needs, triggers = mem.needs_migration()
        print(f"  {'⚠️' if needs else '✅'} Migration needed: {needs} {triggers if needs else ''}")

        # Test 9: Conflict tracking
        conflicts = mem.shared.get_conflicts()
        print(f"  {'✅' if len(conflicts) > 0 else '❌'} Conflicts tracked: {len(conflicts)}")

        print()
        print(f"  Tests complete. Shared: {mem.shared.size()}, Long-term: {mem.long_term.size()}")

    elif args.dump_shared:
        for k, info in mem.shared.dump().items():
            print(f"  [{info['importance'][0]}] {k} ({info['source']}): {info['value_preview']}")

    elif args.dump_long_term:
        for k, info in mem.long_term.dump().items():
            print(f"  {k} ({info['source']}): {info['value_preview']}")

    elif args.dump_private:
        priv = mem.private(args.dump_private)
        for key in priv.keys():
            entry = priv.store[key]
            val = str(entry["value"])[:80]
            print(f"  {key}: {val}")

    elif args.inject:
        context = mem.inject_context(args.inject)
        print(context if context else "  (no memory context available)")

    elif args.promote:
        promoted = mem.post_workflow_promote()
        if promoted:
            print(f"  Promoted {len(promoted)} entries:")
            for k in promoted:
                print(f"    {k}")
        else:
            print("  No entries eligible for promotion")

    else:
        mem.summary()
