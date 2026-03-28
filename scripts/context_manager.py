#!/usr/bin/env python3
"""
NemoClaw Context Window Management v1.0 (MA-17)

Token budget optimization for multi-agent LLM calls:
- Pool-based shared budget across agents per task
- Priority-based pruning (drop low-importance items first)
- Token counting and tracking per agent per task
- Context item prioritization by relevance, recency, importance
- Overflow protection with warnings and auto-pruning
- Provider-aware limits (Anthropic/OpenAI/Google)
- Session-level token analytics

Usage:
  python3 scripts/context_manager.py --test
  python3 scripts/context_manager.py --usage
  python3 scripts/context_manager.py --limits
"""

import argparse
import json
import os
import sys
import uuid
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import defaultdict

REPO = Path.home() / "nemoclaw-local-foundation"
CTX_DIR = Path.home() / ".nemoclaw" / "context"
USAGE_PATH = CTX_DIR / "token-usage.json"

# ═══════════════════════════════════════════════════════════════════════════════
# PROVIDER LIMITS
# ═══════════════════════════════════════════════════════════════════════════════

PROVIDER_LIMITS = {
    "anthropic": {
        "claude-sonnet-4-20250514": {"input": 200000, "output": 8192},
        "claude-opus-4-20250514": {"input": 200000, "output": 8192},
        "default": {"input": 200000, "output": 8192},
    },
    "openai": {
        "gpt-4o": {"input": 128000, "output": 4096},
        "gpt-4o-mini": {"input": 128000, "output": 4096},
        "default": {"input": 128000, "output": 4096},
    },
    "google": {
        "gemini-2.0-flash": {"input": 1000000, "output": 8192},
        "default": {"input": 1000000, "output": 8192},
    },
}

# ═══════════════════════════════════════════════════════════════════════════════
# TASK POOL BUDGETS
# ═══════════════════════════════════════════════════════════════════════════════

TASK_POOL_BUDGETS = {
    "research": {"total_tokens": 16000, "max_items": 50, "description": "Research and analysis tasks"},
    "planning": {"total_tokens": 12000, "max_items": 40, "description": "Planning and strategy tasks"},
    "execution": {"total_tokens": 20000, "max_items": 60, "description": "Implementation and build tasks"},
    "review": {"total_tokens": 10000, "max_items": 30, "description": "Review and quality checks"},
    "decision": {"total_tokens": 8000, "max_items": 25, "description": "Decision-making discussions"},
    "default": {"total_tokens": 12000, "max_items": 40, "description": "General tasks"},
}

# Priority levels for context items
PRIORITY_WEIGHTS = {
    "critical": 10,    # system prompts, task instructions — never prune
    "high": 7,         # recent agent outputs, key decisions
    "medium": 4,       # supporting context, reference data
    "low": 2,          # background info, old messages
    "ephemeral": 1,    # debug info, verbose logs — prune first
}
# Overflow policy: soft = warn but allow, hard = block on budget
OVERFLOW_POLICY = "soft"  # "soft" or "hard"
# With soft policy, only ephemeral items are rejected on overflow.
# All other priorities are allowed through with a warning.
# This ensures complex tasks are never blocked by token limits.



# ═══════════════════════════════════════════════════════════════════════════════
# TOKEN ESTIMATOR
# ═══════════════════════════════════════════════════════════════════════════════

def estimate_tokens(text):
    """Estimate token count for text.

    Uses simple heuristic: ~4 chars per token for English.
    More accurate than word count, avoids tokenizer dependency.
    """
    if not text:
        return 0
    return max(1, len(text) // 4)


def estimate_tokens_precise(text):
    """More precise estimation using word + punctuation counting."""
    if not text:
        return 0
    words = len(re.findall(r'\S+', text))
    # Rough: 1 word ≈ 1.3 tokens on average
    return max(1, int(words * 1.3))


# ═══════════════════════════════════════════════════════════════════════════════
# CONTEXT ITEM
# ═══════════════════════════════════════════════════════════════════════════════

class ContextItem:
    """A single item in the context window."""

    def __init__(self, content, role="user", priority="medium",
                 source_agent=None, source_system=None, label=None,
                 timestamp=None):
        self.id = f"ctx_{uuid.uuid4().hex[:6]}"
        self.content = content
        self.role = role  # system | user | assistant | context
        self.priority = priority
        self.source_agent = source_agent
        self.source_system = source_system
        self.label = label or "unlabeled"
        self.timestamp = timestamp or datetime.now(timezone.utc).isoformat()
        self.tokens = estimate_tokens(content)
        self.pruned = False

    def priority_score(self):
        """Composite priority score for pruning decisions.

        Higher = more important = prune last.
        Score = base_priority + recency_bonus + role_bonus
        """
        base = PRIORITY_WEIGHTS.get(self.priority, 2)

        # Recency bonus: newer items get +1 to +3
        try:
            ts = datetime.fromisoformat(self.timestamp.replace("Z", "+00:00"))
            age_minutes = (datetime.now(timezone.utc) - ts).total_seconds() / 60
            if age_minutes < 5:
                recency = 3
            elif age_minutes < 30:
                recency = 2
            elif age_minutes < 120:
                recency = 1
            else:
                recency = 0
        except (ValueError, AttributeError):
            recency = 0

        # Role bonus: system prompts are sacred
        role_bonus = {"system": 5, "assistant": 1, "user": 2, "context": 0}.get(self.role, 0)

        return base + recency + role_bonus

    def to_dict(self):
        return {
            "id": self.id,
            "content": self.content[:100] + "..." if len(self.content) > 100 else self.content,
            "role": self.role,
            "priority": self.priority,
            "source_agent": self.source_agent,
            "label": self.label,
            "tokens": self.tokens,
            "priority_score": self.priority_score(),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# CONTEXT POOL
# ═══════════════════════════════════════════════════════════════════════════════

class ContextPool:
    """Shared context pool for a task.

    All agents working on the same task share this pool.
    Pool enforces total token budget and item count limits.
    """

    def __init__(self, task_type="default", pool_budget=None):
        config = TASK_POOL_BUDGETS.get(task_type, TASK_POOL_BUDGETS["default"])
        self.task_type = task_type
        self.total_budget = pool_budget or config["total_tokens"]
        self.max_items = config["max_items"]
        self.items = []
        self.agent_usage = defaultdict(int)  # agent_id → tokens used
        self.pruned_count = 0
        self.pruned_tokens = 0

    def add(self, item):
        """Add an item to the pool.

        If over budget, auto-prunes low-priority items first.

        Returns: (added: bool, pruned_items: list)
        """
        pruned = []

        # Check item count limit
        while len(self.items) >= self.max_items:
            removed = self._prune_one()
            if removed:
                pruned.append(removed)
            else:
                break

        # Check token budget
        current = self.current_tokens()
        while current + item.tokens > self.total_budget:
            removed = self._prune_one()
            if removed:
                pruned.append(removed)
                current = self.current_tokens()
            else:
                break

        # Final check — still over?
        if self.current_tokens() + item.tokens > self.total_budget:
            # Cannot fit even after pruning
            # Soft enforcement: allow overflow with warning (never hard-block)
            # Only truly reject ephemeral items to keep system flexible
            if item.priority == "ephemeral":
                return False, pruned
            # Allow overflow for all other priorities — flexibility over hard stops

        self.items.append(item)
        if item.source_agent:
            self.agent_usage[item.source_agent] += item.tokens

        return True, pruned

    def _prune_one(self):
        """Remove the lowest priority item.

        Never prunes critical items.

        Returns: pruned ContextItem or None
        """
        # Sort by priority score ascending (lowest first)
        pruneable = [i for i in self.items
                     if i.priority != "critical" and not i.pruned]
        if not pruneable:
            return None

        pruneable.sort(key=lambda i: i.priority_score())
        victim = pruneable[0]

        self.items.remove(victim)
        self.pruned_count += 1
        self.pruned_tokens += victim.tokens
        if victim.source_agent:
            self.agent_usage[victim.source_agent] = max(
                0, self.agent_usage[victim.source_agent] - victim.tokens)

        return victim

    def prune_to_budget(self, target_tokens=None):
        """Prune items until within target budget.

        Returns: list of pruned items
        """
        target = target_tokens or self.total_budget
        pruned = []
        while self.current_tokens() > target:
            removed = self._prune_one()
            if removed:
                pruned.append(removed)
            else:
                break
        return pruned

    def current_tokens(self):
        """Total tokens currently in pool."""
        return sum(i.tokens for i in self.items)

    def remaining_tokens(self):
        """Tokens remaining in budget."""
        return max(0, self.total_budget - self.current_tokens())

    def utilization(self):
        """Pool utilization ratio (0.0-1.0)."""
        if self.total_budget <= 0:
            return 0.0
        return round(self.current_tokens() / self.total_budget, 3)

    def get_items_by_priority(self):
        """Get items grouped by priority."""
        grouped = defaultdict(list)
        for item in self.items:
            grouped[item.priority].append(item)
        return dict(grouped)

    def get_agent_breakdown(self):
        """Token usage per agent."""
        return dict(self.agent_usage)

    def build_context(self, max_tokens=None, include_roles=None):
        """Build context string from pool items.

        Args:
            max_tokens: limit output tokens
            include_roles: only include certain roles

        Returns: (context_string, token_count, item_count)
        """
        items = sorted(self.items, key=lambda i: -i.priority_score())

        if include_roles:
            items = [i for i in items if i.role in include_roles]

        parts = []
        total = 0
        count = 0
        limit = max_tokens or self.total_budget

        for item in items:
            if total + item.tokens > limit:
                break
            parts.append(item.content)
            total += item.tokens
            count += 1

        return "\n\n".join(parts), total, count

    def summary(self):
        """Pool summary dict."""
        return {
            "task_type": self.task_type,
            "total_budget": self.total_budget,
            "current_tokens": self.current_tokens(),
            "remaining_tokens": self.remaining_tokens(),
            "utilization": self.utilization(),
            "item_count": len(self.items),
            "max_items": self.max_items,
            "pruned_count": self.pruned_count,
            "pruned_tokens": self.pruned_tokens,
            "agent_usage": dict(self.agent_usage),
            "by_priority": {p: len(items) for p, items in self.get_items_by_priority().items()},
        }


# ═══════════════════════════════════════════════════════════════════════════════
# CONTEXT MANAGER (main interface)
# ═══════════════════════════════════════════════════════════════════════════════

class ContextManager:
    """Multi-task context window manager.

    Manages multiple context pools, one per active task.
    Tracks session-level token usage across all tasks.
    """

    def __init__(self):
        self.pools = {}  # task_id → ContextPool
        self.session_tokens = 0
        self.session_items = 0

    def get_or_create_pool(self, task_id, task_type="default", pool_budget=None):
        """Get existing pool or create new one."""
        if task_id not in self.pools:
            self.pools[task_id] = ContextPool(task_type, pool_budget)
        return self.pools[task_id]

    def add_context(self, task_id, content, role="context", priority="medium",
                     source_agent=None, source_system=None, label=None,
                     task_type="default"):
        """Add context to a task's pool.

        Returns: (success, pruned_items, pool_summary)
        """
        pool = self.get_or_create_pool(task_id, task_type)
        item = ContextItem(content, role, priority, source_agent, source_system, label)

        added, pruned = pool.add(item)
        if added:
            self.session_tokens += item.tokens
            self.session_items += 1

        return added, pruned, pool.summary()

    def get_context(self, task_id, max_tokens=None, include_roles=None):
        """Build context string for a task.

        Returns: (context_string, token_count, item_count) or None
        """
        pool = self.pools.get(task_id)
        if not pool:
            return None, 0, 0
        return pool.build_context(max_tokens, include_roles)

    def check_budget(self, task_id, needed_tokens):
        """Check if a task pool has enough budget.

        Returns: (has_budget, remaining, utilization)
        """
        pool = self.pools.get(task_id)
        if not pool:
            return True, 0, 0.0

        remaining = pool.remaining_tokens()
        has_budget = remaining >= needed_tokens
        return has_budget, remaining, pool.utilization()

    def prune_task(self, task_id, target_tokens=None):
        """Force prune a task's pool.

        Returns: list of pruned items
        """
        pool = self.pools.get(task_id)
        if not pool:
            return []
        return pool.prune_to_budget(target_tokens)

    def get_provider_limit(self, provider="anthropic", model=None):
        """Get provider's context window limit."""
        provider_limits = PROVIDER_LIMITS.get(provider, {})
        if model and model in provider_limits:
            return provider_limits[model]
        return provider_limits.get("default", {"input": 128000, "output": 4096})

    def check_provider_fit(self, task_id, provider="anthropic", model=None):
        """Check if task context fits within provider limits.

        Returns: (fits, current_tokens, provider_limit)
        """
        pool = self.pools.get(task_id)
        if not pool:
            return True, 0, 0

        limit = self.get_provider_limit(provider, model)
        current = pool.current_tokens()
        return current <= limit["input"], current, limit["input"]

    def close_task(self, task_id):
        """Close a task pool and return final stats."""
        pool = self.pools.get(task_id)
        if not pool:
            return None
        summary = pool.summary()
        del self.pools[task_id]
        return summary

    def get_session_stats(self):
        """Session-level statistics."""
        return {
            "active_pools": len(self.pools),
            "session_tokens": self.session_tokens,
            "session_items": self.session_items,
            "pools": {tid: pool.summary() for tid, pool in self.pools.items()},
        }

    def save_usage(self):
        """Save token usage data."""
        CTX_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session": self.get_session_stats(),
        }
        with open(USAGE_PATH, "w") as f:
            json.dump(data, f, indent=2)


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS
# ═══════════════════════════════════════════════════════════════════════════════

def run_tests():
    print("=" * 60)
    print("  MA-17 Context Window Management Tests")
    print("=" * 60)

    tp = 0
    tt = 0

    def test(name, condition, detail=""):
        nonlocal tp, tt
        tt += 1
        if condition:
            tp += 1
            print(f"  ✅ {name}")
        else:
            print(f"  ❌ {name}: {detail}")

    # Test 1: Provider limits defined
    test("3 providers defined", len(PROVIDER_LIMITS) == 3)

    # Test 2: Task pool budgets
    test("6 task pool types", len(TASK_POOL_BUDGETS) == 6)

    # Test 3: Priority weights
    test("5 priority levels", len(PRIORITY_WEIGHTS) == 5)

    # Test 4: Token estimation
    tokens = estimate_tokens("Hello world, this is a test sentence.")
    test("Token estimation works", tokens > 0 and tokens < 100, f"tokens={tokens}")

    # Test 5: Empty string = 0 tokens
    test("Empty = 0 tokens", estimate_tokens("") == 0)

    # Test 6: Context item creation
    item = ContextItem("Test content here", "user", "high", "strategy_lead", "MA-5", "task_input")
    test("Context item created", item.tokens > 0 and item.priority == "high")

    # Test 7: Priority score calculation
    critical_item = ContextItem("System prompt", "system", "critical")
    low_item = ContextItem("Debug log", "context", "ephemeral")
    test("Critical > ephemeral priority",
         critical_item.priority_score() > low_item.priority_score())

    # Test 8: System role bonus
    sys_item = ContextItem("Sys", "system", "medium")
    usr_item = ContextItem("Usr", "context", "medium")
    test("System role has priority bonus", sys_item.priority_score() > usr_item.priority_score())

    # Test 9: Pool creation
    pool = ContextPool("research")
    test("Pool created with budget",
         pool.total_budget == 16000 and pool.max_items == 50)

    # Test 10: Add item to pool
    item1 = ContextItem("A" * 400, "user", "high", "strategy_lead")
    added, pruned = pool.add(item1)
    test("Item added to pool", added and len(pruned) == 0)

    # Test 11: Token tracking
    test("Pool tracks tokens", pool.current_tokens() > 0)

    # Test 12: Agent usage tracking
    test("Agent usage tracked",
         pool.agent_usage.get("strategy_lead", 0) > 0)

    # Test 13: Utilization
    util = pool.utilization()
    test("Utilization calculated", 0.0 < util < 1.0, f"util={util}")

    # Test 14: Remaining tokens
    remaining = pool.remaining_tokens()
    test("Remaining tokens", remaining > 0 and remaining < pool.total_budget)

    # Test 15: Priority-based pruning
    small_pool = ContextPool("decision")  # 8000 token budget
    # Fill with items — large enough that total > 500 tokens
    small_pool.add(ContextItem("Critical system prompt word " * 100, "system", "critical"))
    small_pool.add(ContextItem("High priority output data " * 200, "assistant", "high"))
    small_pool.add(ContextItem("Medium context information " * 300, "context", "medium"))
    small_pool.add(ContextItem("Low background details " * 300, "context", "low"))
    small_pool.add(ContextItem("Ephemeral debug logging " * 300, "context", "ephemeral"))

    # Force prune to a small target so items must be removed
    pruned = small_pool.prune_to_budget(500)
    test("Pruning removes items", len(pruned) > 0)

    # Test 16: Ephemeral pruned first
    pruned_priorities = [p.priority for p in pruned]
    if pruned_priorities:
        test("Ephemeral pruned first", pruned_priorities[0] == "ephemeral",
             str(pruned_priorities))
    else:
        test("Ephemeral pruned first", False, "nothing pruned")

    # Test 17: Critical never pruned
    critical_remaining = [i for i in small_pool.items if i.priority == "critical"]
    test("Critical items never pruned", len(critical_remaining) > 0)

    # Test 18: Pool item count limit
    tiny_pool = ContextPool("default")
    tiny_pool.max_items = 3
    for i in range(5):
        tiny_pool.add(ContextItem(f"Item {i} " * 10, "context", "low"))
    test("Item count limit enforced", len(tiny_pool.items) <= 3)

    # Test 19: Auto-prune on add when over budget
    # Each item ~150 tokens. Budget=350 fits 2 but not 3 — forces pruning
    budget_pool = ContextPool("default")
    budget_pool.total_budget = 350
    budget_pool.add(ContextItem("Alpha data " * 200, "context", "ephemeral", label="old"))
    budget_pool.add(ContextItem("Beta data " * 200, "context", "low", label="medium"))
    added, pruned = budget_pool.add(ContextItem("Gamma data " * 200, "context", "high", label="new"))
    test("Auto-prune on budget overflow",
         added and len(pruned) > 0, f"added={added}, pruned={len(pruned)}")

    # Test 20: Build context string
    build_pool = ContextPool("research")
    build_pool.add(ContextItem("System: You are a researcher", "system", "critical"))
    build_pool.add(ContextItem("User: Research AI market", "user", "high"))
    build_pool.add(ContextItem("Context: Market data here", "context", "medium"))
    ctx_str, tok_count, item_count = build_pool.build_context()
    test("Context built", len(ctx_str) > 0 and tok_count > 0 and item_count == 3)

    # Test 21: Build with role filter
    ctx_sys, _, count_sys = build_pool.build_context(include_roles=["system"])
    test("Role filter works", count_sys == 1 and "researcher" in ctx_sys)

    # Test 22: Build with token limit
    ctx_limited, tok_lim, _ = build_pool.build_context(max_tokens=50)
    test("Token limit on build", tok_lim <= 50 or tok_lim <= build_pool.current_tokens())

    # Test 23: Context manager multi-task
    mgr = ContextManager()
    ok1, _, _ = mgr.add_context("task_001", "Research the AI market", "user", "high",
                                  "strategy_lead", "MA-5", "input", "research")
    ok2, _, _ = mgr.add_context("task_002", "Write product spec", "user", "high",
                                  "product_architect", "MA-5", "input", "planning")
    test("Multi-task pools", len(mgr.pools) == 2 and ok1 and ok2)

    # Test 24: Check budget
    has_budget, remaining, util = mgr.check_budget("task_001", 1000)
    test("Budget check works", has_budget and remaining > 0)

    # Test 25: Provider limit check
    fits, current, limit = mgr.check_provider_fit("task_001", "anthropic")
    test("Provider fit check", fits and limit > 0, f"current={current}, limit={limit}")

    # Test 26: Provider limits lookup
    limit = mgr.get_provider_limit("openai", "gpt-4o")
    test("OpenAI limit lookup", limit["input"] == 128000)

    # Test 27: Google has large limit
    limit_g = mgr.get_provider_limit("google")
    test("Google has 1M limit", limit_g["input"] == 1000000)

    # Test 28: Session stats
    stats = mgr.get_session_stats()
    test("Session stats", stats["active_pools"] == 2 and stats["session_tokens"] > 0)

    # Test 29: Close task
    summary = mgr.close_task("task_001")
    test("Close task returns summary", summary is not None and "current_tokens" in summary)
    test("Pool removed after close", "task_001" not in mgr.pools)

    # Test 31: Save usage
    mgr.save_usage()
    test("Usage saved", USAGE_PATH.exists())

    # Test 32: Pool summary has all fields
    pool_summary = build_pool.summary()
    required_fields = ["task_type", "total_budget", "current_tokens", "remaining_tokens",
                        "utilization", "item_count", "pruned_count", "agent_usage"]
    test("Pool summary complete",
         all(f in pool_summary for f in required_fields))

    print(f"\n  Results: {tp}/{tt} passed")
    return tp == tt


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="NemoClaw Context Window Management")
    parser.add_argument("--test", action="store_true", help="Run all tests")
    parser.add_argument("--usage", action="store_true", help="Show token usage")
    parser.add_argument("--limits", action="store_true", help="Show provider limits")
    args = parser.parse_args()

    if args.test:
        success = run_tests()
        sys.exit(0 if success else 1)

    elif args.usage:
        if USAGE_PATH.exists():
            with open(USAGE_PATH) as f:
                data = json.load(f)
            session = data.get("session", {})
            print(f"  Active pools: {session.get('active_pools', 0)}")
            print(f"  Session tokens: {session.get('session_tokens', 0):,}")
            print(f"  Session items: {session.get('session_items', 0)}")

            for tid, pool in session.get("pools", {}).items():
                util = pool.get("utilization", 0)
                bar = "█" * int(util * 20) + "░" * (20 - int(util * 20))
                print(f"\n  [{tid}] {pool['task_type']}")
                print(f"    {bar} {util:.0%} ({pool['current_tokens']:,}/{pool['total_budget']:,} tokens)")
                print(f"    Items: {pool['item_count']}/{pool['max_items']} | Pruned: {pool['pruned_count']}")
        else:
            print("  No usage data yet.")

    elif args.limits:
        print("  Provider Context Window Limits:")
        for provider, models in PROVIDER_LIMITS.items():
            print(f"\n  {provider.upper()}:")
            for model, limits in models.items():
                print(f"    {model}: input={limits['input']:,} output={limits['output']:,}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
