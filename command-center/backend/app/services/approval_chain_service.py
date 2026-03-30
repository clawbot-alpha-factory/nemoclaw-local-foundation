"""
NemoClaw Execution Engine — ApprovalChainService (E-4c)

Multi-level approvals (#41): configurable chains per action type + spend.

NEW FILE: command-center/backend/app/services/approval_chain_service.py
"""
from __future__ import annotations
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("cc.approval_chain")

APPROVAL_CHAINS = {
    "low_spend": {
        "threshold": 10.0,
        "chain": [],
        "description": "Auto-approved within guardrails",
    },
    "medium_spend": {
        "threshold": 50.0,
        "chain": ["operations_lead"],
        "description": "$10-$50: Operations approves",
    },
    "high_spend": {
        "threshold": 100.0,
        "chain": ["operations_lead", "executive_operator"],
        "description": "$50-$100: Operations → CEO",
    },
    "critical_spend": {
        "threshold": float("inf"),
        "chain": ["operations_lead", "operations_lead", "executive_operator"],
        "description": ">$100: Operations → COO → CEO",
    },
    "first_bridge": {
        "threshold": 0,
        "chain": ["executive_operator"],
        "description": "First-time bridge: CEO approval",
    },
    "first_email": {
        "threshold": 0,
        "chain": ["operations_lead"],
        "description": "First-time email: COO approval",
    },
}

class ApprovalRequest:
    def __init__(self, action: str, amount: float, requested_by: str, chain_type: str):
        self.request_id = str(uuid.uuid4())[:8]
        self.action = action
        self.amount = amount
        self.requested_by = requested_by
        self.chain_type = chain_type
        self.chain = list(APPROVAL_CHAINS.get(chain_type, {}).get("chain", []))
        self.current_step = 0
        self.status = "pending"
        self.approvals: list[dict[str, Any]] = []
        self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "action": self.action,
            "amount": self.amount,
            "requested_by": self.requested_by,
            "chain_type": self.chain_type,
            "chain": self.chain,
            "current_step": self.current_step,
            "status": self.status,
            "approvals": self.approvals,
            "created_at": self.created_at,
        }

class ApprovalChainService:
    def __init__(self, audit_service=None):
        self.audit_service = audit_service
        self.requests: dict[str, ApprovalRequest] = {}
        logger.info("ApprovalChainService initialized (%d chain types)", len(APPROVAL_CHAINS))

    def get_chain_for_spend(self, amount: float) -> str:
        if amount < 10:
            return "low_spend"
        elif amount < 50:
            return "medium_spend"
        elif amount < 100:
            return "high_spend"
        else:
            return "critical_spend"

    def submit(self, action: str, amount: float, requested_by: str, chain_type: str = "") -> dict[str, Any]:
        if not chain_type:
            chain_type = self.get_chain_for_spend(amount)

        chain_def = APPROVAL_CHAINS.get(chain_type, {})
        chain = chain_def.get("chain", [])

        if not chain:
            if self.audit_service:
                self.audit_service.log("auto_approved", requested_by, {"action": action, "amount": amount})
            return {"status": "auto_approved", "action": action, "amount": amount}

        req = ApprovalRequest(action, amount, requested_by, chain_type)
        self.requests[req.request_id] = req
        logger.info("Approval requested: %s ($%.2f) chain=%s", action, amount, chain_type)
        return {"status": "pending", "request": req.to_dict()}

    def approve(self, request_id: str, approver: str) -> dict[str, Any]:
        req = self.requests.get(request_id)
        if not req:
            return {"success": False, "reason": "Request not found"}
        if req.status != "pending":
            return {"success": False, "reason": f"Request already {req.status}"}

        # Validate approver matches expected role
        if req.current_step < len(req.chain):
            expected = req.chain[req.current_step]
            if approver != expected and approver != "executive_operator":
                return {"success": False, "reason": f"Expected approver: {expected}, got: {approver}"}
        req.approvals.append({"approver": approver, "action": "approved", "timestamp": datetime.now(timezone.utc).isoformat()})
        req.current_step += 1

        if req.current_step >= len(req.chain):
            req.status = "approved"
            if self.audit_service:
                self.audit_service.log("approval_complete", approver, {"request_id": request_id, "amount": req.amount})
        return {"success": True, "request": req.to_dict()}

    def reject(self, request_id: str, rejector: str, reason: str = "") -> dict[str, Any]:
        req = self.requests.get(request_id)
        if not req:
            return {"success": False, "reason": "Request not found"}
        req.status = "rejected"
        req.approvals.append({"approver": rejector, "action": "rejected", "reason": reason, "timestamp": datetime.now(timezone.utc).isoformat()})
        if self.audit_service:
            self.audit_service.log("approval_rejected", rejector, {"request_id": request_id, "reason": reason})
        return {"success": True, "request": req.to_dict()}

    def get_pending(self) -> list[dict[str, Any]]:
        return [r.to_dict() for r in self.requests.values() if r.status == "pending"]

    def get_chains(self) -> dict[str, Any]:
        return dict(APPROVAL_CHAINS)
