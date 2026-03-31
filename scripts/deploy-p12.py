#!/usr/bin/env python3
"""
NemoClaw P-12 Deployment: Idempotency for Bridge Calls

Patches: bridge_manager.py (idempotency cache in execute())

Run from repo root:
    cd ~/nemoclaw-local-foundation
    python3 scripts/deploy-p12.py
"""

from pathlib import Path
import sys

BACKEND = Path.home() / "nemoclaw-local-foundation" / "command-center" / "backend"


def deploy():
    errors = []

    print("1/1 Patching bridge_manager.py...")
    bm_path = BACKEND / "app" / "services" / "bridge_manager.py"
    bm = bm_path.read_text()

    # Patch 1: Add hashlib import
    bm = bm.replace(
        "import asyncio\nimport json\nimport logging\nimport os",
        "import asyncio\nimport hashlib\nimport json\nimport logging\nimport os",
    )

    # Patch 2: Add idempotency constant
    bm = bm.replace(
        "    MAX_RETRIES = 3\n    BACKOFF_BASE = 2",
        "    MAX_RETRIES = 3\n    BACKOFF_BASE = 2\n    IDEMPOTENCY_CACHE_SIZE = 1000",
    )

    # Patch 3: Add idempotency cache in __init__
    bm = bm.replace(
        "        self._persist_path.parent.mkdir(parents=True, exist_ok=True)\n\n        self._init_configs()",
        "        self._persist_path.parent.mkdir(parents=True, exist_ok=True)\n"
        "        self._idempotency_cache: dict[str, dict[str, Any]] = {}  # P-12\n"
        "        self._idempotency_order: list[str] = []  # P-12: LRU eviction order\n\n"
        "        self._init_configs()",
    )

    # Patch 4: Add idempotency_key param + check in execute()
    bm = bm.replace(
        '''    async def execute(
        self,
        bridge: str,
        action: str,
        params: dict[str, Any] | None = None,
        skip_approval: bool = False,
    ) -> dict[str, Any]:
        """Execute a bridge action with rate limiting, retry, and cost tracking."""
        params = params or {}
        call = BridgeCall(bridge=bridge, action=action, params=params)''',
        '''    @staticmethod
    def compute_idempotency_key(bridge: str, action: str, params: dict[str, Any]) -> str:
        """Generate a deterministic idempotency key from bridge + action + params."""
        raw = json.dumps({"b": bridge, "a": action, "p": params}, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    async def execute(
        self,
        bridge: str,
        action: str,
        params: dict[str, Any] | None = None,
        skip_approval: bool = False,
        idempotency_key: str = "",
    ) -> dict[str, Any]:
        """Execute a bridge action with rate limiting, retry, cost tracking, and idempotency.

        If idempotency_key is provided and was already executed successfully,
        returns cached result without re-executing.
        """
        params = params or {}

        # P-12: Idempotency check
        if idempotency_key and idempotency_key in self._idempotency_cache:
            cached = self._idempotency_cache[idempotency_key]
            logger.info("Idempotency hit: key=%s bridge=%s action=%s", idempotency_key[:8], bridge, action)
            return {**cached, "idempotent": True, "cached": True}

        call = BridgeCall(bridge=bridge, action=action, params=params)''',
    )

    # Patch 5: Cache successful results after execution
    bm = bm.replace(
        '''                self._record_call(call)
                return {"success": True, "result": result, "cost": call.cost, "attempts": call.attempts}''',
        '''                self._record_call(call)
                exec_result = {"success": True, "result": result, "cost": call.cost, "attempts": call.attempts}

                # P-12: Cache successful result for idempotency
                if idempotency_key:
                    self._idempotency_cache[idempotency_key] = exec_result
                    self._idempotency_order.append(idempotency_key)
                    while len(self._idempotency_order) > self.IDEMPOTENCY_CACHE_SIZE:
                        evict_key = self._idempotency_order.pop(0)
                        self._idempotency_cache.pop(evict_key, None)

                return exec_result''',
    )

    bm_path.write_text(bm)
    try:
        compile(bm_path.read_text(), str(bm_path), "exec")
        print("  ✅ Compiles")
    except SyntaxError as e:
        errors.append(f"bridge_manager.py: {e}")
        print(f"  ❌ {e}")

    print()
    if errors:
        print(f"⛔ {len(errors)} ERRORS:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("✅ P-12 deployed successfully")
        print()
        print("Backend auto-reloads. Validate:")
        print()
        print('  TOKEN=$(cat ~/.nemoclaw/cc-token)')
        print()
        print('  # Bridges still work')
        print('  curl -s -H "Authorization: Bearer $TOKEN" \\')
        print('    http://127.0.0.1:8100/api/bridges/status | python3 -c "import json,sys; d=json.load(sys.stdin); print(\'Bridges:\', list(d.get(\'bridges\',{}).keys()))"')
        print()
        print('  # Full validation')
        print('  cd ~/nemoclaw-local-foundation && bash scripts/validate-p1-p10.sh')
        print()
        print('  git add -A && git status')
        print('  git commit -m "feat(engine): P-12 idempotency for bridge calls — dedup cache, auto-key, LRU eviction"')
        print('  git push origin main')


if __name__ == "__main__":
    deploy()
