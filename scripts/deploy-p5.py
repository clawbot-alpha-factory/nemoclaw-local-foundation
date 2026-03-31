#!/usr/bin/env python3
"""
NemoClaw P-5 Deployment: Approval Model + Rubric Scores

Patches: approval_chain_service.py (rubric scoring, factor derivation, hard overrides)
Patches: enterprise.py (3 new endpoints)

Run from repo root:
    cd ~/nemoclaw-local-foundation
    python3 scripts/deploy-p5.py
"""

from pathlib import Path
import sys

BACKEND = Path.home() / "nemoclaw-local-foundation" / "command-center" / "backend"


def deploy():
    errors = []

    # ═══════════════════════════════════════════════════════════════
    # 1. PATCH approval_chain_service.py
    # ═══════════════════════════════════════════════════════════════
    print("1/2 Patching approval_chain_service.py...")

    svc_path = BACKEND / "app" / "services" / "approval_chain_service.py"
    svc = svc_path.read_text()

    # Patch 1a: Add imports (json, Path)
    svc = svc.replace(
        "from __future__ import annotations\nimport logging\nimport uuid\nfrom datetime import datetime, timezone\nfrom typing import Any",
        "from __future__ import annotations\nimport json\nimport logging\nimport uuid\nfrom datetime import datetime, timezone\nfrom pathlib import Path\nfrom typing import Any",
    )

    # Patch 1b: Add rubric constants after APPROVAL_CHAINS
    rubric_constants = '''

# ── Rubric Scoring (P-5) ────────────────────────────────────────────
POLICY_VERSION = "v1"

RUBRIC_WEIGHTS = {
    "spend": 0.25,
    "reversibility": 0.25,
    "external_impact": 0.25,
    "novelty": 0.15,
    "data_sensitivity": 0.10,
}

DECISION_THRESHOLDS = {
    "auto_approved": (0, 25),
    "single_approval": (26, 55),
    "chain_approval": (56, 80),
    "escalated": (81, 100),
}

# Deterministic factor derivation rules
EXTERNAL_IMPACT_MAP = {
    "read_only": 0, "apollo_search": 0, "analytics": 0,
    "internal_write": 3, "task_update": 3, "memory_write": 3,
    "external_api_write": 6, "hubspot_write": 6, "crm_update": 6,
    "send_email": 10, "cold_email_blast": 10, "outreach_sequence": 10,
    "send_message": 9, "whatsapp_send": 9,
}

REVERSIBILITY_MAP = {
    "read_only": 0, "apollo_search": 0, "analytics": 0,
    "internal_write": 2, "task_update": 2, "memory_write": 2,
    "crm_update": 5, "hubspot_write": 5,
    "send_email": 9, "cold_email_blast": 10, "outreach_sequence": 10,
    "send_message": 9, "whatsapp_send": 9,
    "payment": 8, "ad_spend": 8,
}

SCORE_HISTORY_MAX = 1000
DEDUP_WINDOW = 500

'''

    svc = svc.replace(
        "\nclass ApprovalRequest:",
        rubric_constants + "\nclass ApprovalRequest:",
    )

    # Patch 1c: Add rubric methods to ApprovalChainService (before get_pending)
    rubric_methods = '''
    # ── Rubric Scoring (P-5) ─────────────────────────────────────────

    def _init_rubric(self):
        """Lazy init for rubric state."""
        if not hasattr(self, "_score_history"):
            self._score_history: list[dict[str, Any]] = []
            self._score_dedup: dict[str, dict[str, Any]] = {}
            self._action_counts: dict[str, int] = {}
            self._persist_path = Path.home() / ".nemoclaw" / "approval-scores.json"
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            self._load_score_history()

    def _load_score_history(self):
        if self._persist_path.exists():
            try:
                data = json.loads(self._persist_path.read_text())
                self._score_history = data.get("history", [])[-SCORE_HISTORY_MAX:]
                self._action_counts = data.get("action_counts", {})
            except (json.JSONDecodeError, OSError):
                pass

    def _save_score_history(self):
        try:
            self._persist_path.write_text(json.dumps({
                "history": self._score_history[-SCORE_HISTORY_MAX:],
                "action_counts": self._action_counts,
                "saved_at": datetime.now(timezone.utc).isoformat(),
            }, indent=2, default=str))
        except OSError as e:
            logger.error("Failed to save score history: %s", e)

    def derive_factors(self, action: str, amount: float, user_factors: dict[str, float] | None = None) -> dict[str, Any]:
        """Derive risk factors from action metadata. System-computed values override user-provided.

        Returns dict with each factor value (0-10) and source (derived/provided).
        """
        self._init_rubric()
        factors: dict[str, Any] = {}
        provided = user_factors or {}

        # Spend: derived from amount
        if amount <= 1:
            spend_val = 1
        elif amount <= 5:
            spend_val = 3
        elif amount <= 20:
            spend_val = 5
        elif amount <= 50:
            spend_val = 7
        else:
            spend_val = min(int(amount / 10), 10)
        factors["spend"] = {"value": spend_val, "source": "derived"}

        # External impact: from action type lookup
        action_lower = action.lower().replace("-", "_").replace(" ", "_")
        if action_lower in EXTERNAL_IMPACT_MAP:
            factors["external_impact"] = {"value": EXTERNAL_IMPACT_MAP[action_lower], "source": "derived"}
        elif "external_impact" in provided:
            factors["external_impact"] = {"value": min(max(int(provided["external_impact"]), 0), 10), "source": "provided"}
        else:
            factors["external_impact"] = {"value": 5, "source": "default"}

        # Reversibility: from action type lookup
        if action_lower in REVERSIBILITY_MAP:
            factors["reversibility"] = {"value": REVERSIBILITY_MAP[action_lower], "source": "derived"}
        elif "reversibility" in provided:
            factors["reversibility"] = {"value": min(max(int(provided["reversibility"]), 0), 10), "source": "provided"}
        else:
            factors["reversibility"] = {"value": 5, "source": "default"}

        # Novelty: from action history count
        count = self._action_counts.get(action_lower, 0)
        if count > 10:
            novelty_val = 1
        elif count >= 1:
            novelty_val = 5
        else:
            novelty_val = 10
        factors["novelty"] = {"value": novelty_val, "source": "derived", "action_count": count}

        # Data sensitivity: can't auto-derive, accept user input or default
        if "data_sensitivity" in provided:
            factors["data_sensitivity"] = {"value": min(max(int(provided["data_sensitivity"]), 0), 10), "source": "provided"}
        else:
            factors["data_sensitivity"] = {"value": 0, "source": "default"}

        return factors

    def score_request(self, action: str, amount: float, factors: dict[str, Any]) -> dict[str, Any]:
        """Compute risk score from factors. Each factor has 'value' key (0-10).

        Formula: risk_score = (sum of value × weight) × 10 → 0-100
        """
        weighted_sum = 0.0
        breakdown: dict[str, Any] = {}

        for dim, weight in RUBRIC_WEIGHTS.items():
            factor = factors.get(dim, {})
            value = factor.get("value", 5) if isinstance(factor, dict) else factor
            value = min(max(float(value), 0), 10)
            contribution = value * weight
            weighted_sum += contribution
            breakdown[dim] = {
                "value": value,
                "weight": weight,
                "contribution": round(contribution, 3),
                "source": factor.get("source", "unknown") if isinstance(factor, dict) else "raw",
            }

        risk_score = round(weighted_sum * 10, 1)  # Scale 0-10 → 0-100

        # Determine decision from thresholds
        decision = "chain_approval"  # default
        for level, (low, high) in DECISION_THRESHOLDS.items():
            if low <= risk_score <= high:
                decision = level
                break

        # Hard override rules (P-5 review item #8)
        ext_val = breakdown.get("external_impact", {}).get("value", 0)
        rev_val = breakdown.get("reversibility", {}).get("value", 0)
        sens_val = breakdown.get("data_sensitivity", {}).get("value", 0)

        override_reason = ""
        if ext_val >= 8 and rev_val >= 8:
            if decision != "escalated":
                override_reason = f"Hard override: external_impact={ext_val} + reversibility={rev_val} → forced escalation"
                decision = "escalated"
        if sens_val >= 8 and decision == "auto_approved":
            override_reason = f"Hard override: data_sensitivity={sens_val} → minimum single_approval"
            decision = "single_approval"

        return {
            "risk_score": risk_score,
            "decision": decision,
            "breakdown": breakdown,
            "override_reason": override_reason,
            "policy_version": POLICY_VERSION,
        }

    def simulate_score(self, action: str, amount: float, user_factors: dict[str, float] | None = None) -> dict[str, Any]:
        """Dry-run: derive factors + score without side effects."""
        factors = self.derive_factors(action, amount, user_factors)
        result = self.score_request(action, amount, factors)
        result["factors_used"] = factors
        result["simulation"] = True
        return result

    def submit_with_rubric(
        self,
        action: str,
        amount: float,
        requested_by: str,
        user_factors: dict[str, float] | None = None,
        request_id: str = "",
    ) -> dict[str, Any]:
        """Score then route approval based on rubric.

        Two-step routing:
        1. Rubric determines approval LEVEL (auto/single/chain/escalated)
        2. For chain_approval, spend determines which CHAIN definition to use
        """
        self._init_rubric()

        # Idempotency check
        if request_id and request_id in self._score_dedup:
            logger.info("Duplicate request_id %s — returning cached", request_id)
            return self._score_dedup[request_id]

        # Derive + score
        factors = self.derive_factors(action, amount, user_factors)
        score_result = self.score_request(action, amount, factors)
        decision = score_result["decision"]

        # Track action for novelty
        action_lower = action.lower().replace("-", "_").replace(" ", "_")
        self._action_counts[action_lower] = self._action_counts.get(action_lower, 0) + 1

        # Route based on decision
        if decision == "auto_approved":
            result = {
                "status": "auto_approved",
                "action": action,
                "amount": amount,
                "requested_by": requested_by,
                "scoring": score_result,
                "factors": factors,
            }
            if self.audit_service:
                self.audit_service.log("rubric_auto_approved", requested_by, {
                    "action": action, "amount": amount, "risk_score": score_result["risk_score"],
                })
        elif decision == "single_approval":
            req = ApprovalRequest(action, amount, requested_by, "medium_spend")
            req.chain = ["operations_lead"]
            self.requests[req.request_id] = req
            result = {
                "status": "pending",
                "approval_level": "single_approval",
                "request": req.to_dict(),
                "scoring": score_result,
                "factors": factors,
            }
        elif decision == "escalated":
            req = ApprovalRequest(action, amount, requested_by, "critical_spend")
            req.chain = ["executive_operator"]
            self.requests[req.request_id] = req
            result = {
                "status": "pending",
                "approval_level": "escalated",
                "request": req.to_dict(),
                "scoring": score_result,
                "factors": factors,
            }
        else:  # chain_approval
            chain_type = self.get_chain_for_spend(amount)
            submit_result = self.submit(action, amount, requested_by, chain_type)
            result = {
                **submit_result,
                "approval_level": "chain_approval",
                "scoring": score_result,
                "factors": factors,
            }

        # Record in score history
        history_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "amount": amount,
            "requested_by": requested_by,
            "risk_score": score_result["risk_score"],
            "decision": decision,
            "factors": {k: v.get("value") if isinstance(v, dict) else v for k, v in factors.items()},
            "override_reason": score_result.get("override_reason", ""),
            "policy_version": POLICY_VERSION,
            "request_id": request_id or "none",
        }
        self._score_history.append(history_entry)
        if len(self._score_history) > SCORE_HISTORY_MAX:
            self._score_history = self._score_history[-SCORE_HISTORY_MAX:]
        self._save_score_history()

        # Idempotency cache
        if request_id:
            self._score_dedup[request_id] = result
            # Cap dedup cache
            if len(self._score_dedup) > DEDUP_WINDOW:
                oldest = list(self._score_dedup.keys())[:-DEDUP_WINDOW]
                for k in oldest:
                    del self._score_dedup[k]

        # Activity log integration
        if hasattr(self, "_activity_log") and self._activity_log:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.ensure_future(self._activity_log.append(
                        category="system",
                        action="approval_scored",
                        actor_type="agent" if requested_by else "system",
                        actor_id=requested_by or "system",
                        entity_type="",
                        entity_id="",
                        summary=f"Rubric scored {action}: {score_result['risk_score']}/100 → {decision}",
                        details={"risk_score": score_result["risk_score"], "decision": decision, "amount": amount},
                    ))
            except Exception:
                pass

        logger.info(
            "Rubric: %s score=%.1f → %s (by %s, $%.2f)",
            action, score_result["risk_score"], decision, requested_by, amount,
        )
        return result

    def get_score_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get recent scoring decisions."""
        self._init_rubric()
        return self._score_history[-limit:]

'''

    # Insert before get_pending
    svc = svc.replace(
        "    def get_pending(self) -> list[dict[str, Any]]:",
        rubric_methods + "    def get_pending(self) -> list[dict[str, Any]]:",
    )

    # Patch 1d: Add activity_log param to __init__
    svc = svc.replace(
        "    def __init__(self, audit_service=None):\n        self.audit_service = audit_service",
        "    def __init__(self, audit_service=None, activity_log_service=None):\n        self.audit_service = audit_service\n        self._activity_log = activity_log_service",
    )

    svc_path.write_text(svc)
    try:
        compile(svc_path.read_text(), str(svc_path), "exec")
        print("  ✅ approval_chain_service.py compiles")
    except SyntaxError as e:
        errors.append(f"approval_chain_service.py: {e}")
        print(f"  ❌ approval_chain_service.py: {e}")

    # ═══════════════════════════════════════════════════════════════
    # 2. PATCH enterprise.py router
    # ═══════════════════════════════════════════════════════════════
    print("2/2 Patching enterprise.py router...")

    ent_path = BACKEND / "app" / "api" / "routers" / "enterprise.py"
    ent = ent_path.read_text()

    # Add new request models after ApprovalSubmit
    ent = ent.replace(
        "class ApprovalSubmit(BaseModel):\n    action: str\n    amount: float\n    requested_by: str\n    chain_type: str = \"\"",
        '''class ApprovalSubmit(BaseModel):
    action: str
    amount: float
    requested_by: str
    chain_type: str = ""

class RubricScoreRequest(BaseModel):
    action: str
    amount: float = 0.0
    factors: dict[str, float] = {}

class RubricSubmitRequest(BaseModel):
    action: str
    amount: float = 0.0
    requested_by: str
    factors: dict[str, float] = {}
    request_id: str = ""''',
    )

    # Add 3 new endpoints before the chains endpoint
    new_endpoints = '''
# ── Rubric Scoring (P-5) ──
@router.post("/api/engine/approvals/score")
async def score_approval(body: RubricScoreRequest, request: Request) -> dict[str, Any]:
    """Dry-run rubric score simulation — no side effects."""
    svc = _svc(request, "approval_chain_service", "ApprovalChainService")
    return svc.simulate_score(body.action, body.amount, body.factors or None)

@router.post("/api/engine/approvals/submit-scored")
async def submit_scored_approval(body: RubricSubmitRequest, request: Request) -> dict[str, Any]:
    """Submit approval with rubric scoring. Scores first, then routes based on risk level."""
    svc = _svc(request, "approval_chain_service", "ApprovalChainService")
    return svc.submit_with_rubric(
        action=body.action, amount=body.amount,
        requested_by=body.requested_by,
        user_factors=body.factors or None,
        request_id=body.request_id,
    )

@router.get("/api/engine/approvals/score-history")
async def score_history(request: Request, limit: int = 50) -> dict[str, Any]:
    """Get recent rubric scoring decisions."""
    svc = _svc(request, "approval_chain_service", "ApprovalChainService")
    history = svc.get_score_history(limit=limit)
    return {"total": len(history), "entries": history}

'''

    ent = ent.replace(
        '@router.get("/api/engine/approvals/chains")',
        new_endpoints + '@router.get("/api/engine/approvals/chains")',
    )

    ent_path.write_text(ent)
    try:
        compile(ent_path.read_text(), str(ent_path), "exec")
        print("  ✅ enterprise.py compiles")
    except SyntaxError as e:
        errors.append(f"enterprise.py: {e}")
        print(f"  ❌ enterprise.py: {e}")

    # ═══════════════════════════════════════════════════════════════
    # 3. PATCH main.py — pass activity_log to approval chain
    # ═══════════════════════════════════════════════════════════════
    print("3/3 Patching main.py...")

    main_path = BACKEND / "app" / "main.py"
    main = main_path.read_text()

    main = main.replace(
        '    app.state.approval_chain_service = ApprovalChainService(audit_service=app.state.audit_service)',
        '    app.state.approval_chain_service = ApprovalChainService(\n        audit_service=app.state.audit_service,\n        activity_log_service=getattr(app.state, "activity_log_service", None),\n    )',
    )

    main_path.write_text(main)
    try:
        compile(main_path.read_text(), str(main_path), "exec")
        print("  ✅ main.py compiles")
    except SyntaxError as e:
        errors.append(f"main.py: {e}")
        print(f"  ❌ main.py: {e}")

    # ═══════════════════════════════════════════════════════════════
    # SUMMARY
    # ═══════════════════════════════════════════════════════════════
    print()
    if errors:
        print(f"⛔ {len(errors)} ERRORS:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("✅ P-5 deployed successfully")
        print()
        print("Restart backend, then validate:")
        print()
        print('  TOKEN=$(cat ~/.nemoclaw/cc-token)')
        print()
        print('  # 1. Simulate low-risk (should auto-approve)')
        print('  curl -s -X POST -H "Authorization: Bearer $TOKEN" \\')
        print('    -H "Content-Type: application/json" \\')
        print("    -d '{\"action\":\"apollo_search\",\"amount\":0.01,\"factors\":{\"data_sensitivity\":0}}' \\")
        print('    http://127.0.0.1:8100/api/engine/approvals/score | python3 -m json.tool')
        print()
        print('  # 2. Simulate high-risk (should escalate)')
        print('  curl -s -X POST -H "Authorization: Bearer $TOKEN" \\')
        print('    -H "Content-Type: application/json" \\')
        print("    -d '{\"action\":\"cold_email_blast\",\"amount\":25.0,\"factors\":{\"data_sensitivity\":6}}' \\")
        print('    http://127.0.0.1:8100/api/engine/approvals/score | python3 -m json.tool')
        print()
        print('  # 3. Submit with rubric (low-risk → auto-approved)')
        print('  curl -s -X POST -H "Authorization: Bearer $TOKEN" \\')
        print('    -H "Content-Type: application/json" \\')
        print("    -d '{\"action\":\"apollo_search\",\"amount\":0.01,\"requested_by\":\"sales_outreach_lead\",\"factors\":{\"data_sensitivity\":0}}' \\")
        print('    http://127.0.0.1:8100/api/engine/approvals/submit-scored | python3 -m json.tool')
        print()
        print('  # 4. Submit with rubric (high-risk → escalated)')
        print('  curl -s -X POST -H "Authorization: Bearer $TOKEN" \\')
        print('    -H "Content-Type: application/json" \\')
        print("    -d '{\"action\":\"cold_email_blast\",\"amount\":25.0,\"requested_by\":\"marketing_campaigns_lead\",\"factors\":{\"data_sensitivity\":6}}' \\")
        print('    http://127.0.0.1:8100/api/engine/approvals/submit-scored | python3 -m json.tool')
        print()
        print('  # 5. Idempotency test (same request_id → cached)')
        print('  curl -s -X POST -H "Authorization: Bearer $TOKEN" \\')
        print('    -H "Content-Type: application/json" \\')
        print("    -d '{\"action\":\"apollo_search\",\"amount\":0.01,\"requested_by\":\"sales_outreach_lead\",\"request_id\":\"dedup-test-1\"}' \\")
        print('    http://127.0.0.1:8100/api/engine/approvals/submit-scored | python3 -m json.tool')
        print('  # Run again — should return same result')
        print('  curl -s -X POST -H "Authorization: Bearer $TOKEN" \\')
        print('    -H "Content-Type: application/json" \\')
        print("    -d '{\"action\":\"apollo_search\",\"amount\":0.01,\"requested_by\":\"sales_outreach_lead\",\"request_id\":\"dedup-test-1\"}' \\")
        print('    http://127.0.0.1:8100/api/engine/approvals/submit-scored | python3 -m json.tool')
        print()
        print('  # 6. Score history')
        print('  curl -s -H "Authorization: Bearer $TOKEN" \\')
        print('    http://127.0.0.1:8100/api/engine/approvals/score-history | python3 -m json.tool')
        print()
        print('  # 7. Existing submit still works (backward compat)')
        print('  curl -s -X POST -H "Authorization: Bearer $TOKEN" \\')
        print('    -H "Content-Type: application/json" \\')
        print("    -d '{\"action\":\"test_action\",\"amount\":5.0,\"requested_by\":\"ops\"}' \\")
        print('    http://127.0.0.1:8100/api/engine/approvals/submit | python3 -m json.tool')
        print()
        print('  # 8. Regression')
        print('  cd ~/nemoclaw-local-foundation && bash scripts/full_regression.sh')
        print()
        print('  # 9. Commit')
        print('  git add -A && git status')
        print('  git commit -m "feat(engine): P-5 approval rubric scoring — risk-based routing, factor derivation, hard overrides, policy versioning"')
        print('  git push origin main')


if __name__ == "__main__":
    deploy()
