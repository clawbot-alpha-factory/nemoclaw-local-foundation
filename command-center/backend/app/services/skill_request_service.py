"""
SkillRequestService — Agent-initiated skill request workflow.
When an agent detects a missing capability, it submits a SkillRequest.
The request goes through a corporate approval process:
  1. Agent submits request with context
  2. operations_lead reviews for feasibility
  3. If approved → skill_factory_service generates spec + code
  4. Quality gate (MA-11 peer review)
  5. If passes → auto-deployed to skill library
  6. If rejected → agent notified with reason
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("cc.skill_request")

REQUESTS_DIR = Path.home() / ".nemoclaw" / "skill-requests"
REQUESTS_DIR.mkdir(parents=True, exist_ok=True)

class SkillRequest:
    def __init__(self, requesting_agent, capability_needed, context, priority="medium"):
        self.request_id = str(uuid.uuid4())[:8]
        self.requesting_agent = requesting_agent
        self.capability_needed = capability_needed
        self.context = context
        self.priority = priority
        self.status = "pending"  # pending, under_review, approved, building, deployed, rejected
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.reviewed_by = None
        self.review_notes = None
        self.skill_id = None
        self.rejection_reason = None

class SkillRequestService:
    def __init__(self):
        self.requests = {}
        self._load()
        logger.info(f"SkillRequestService initialized ({len(self.requests)} requests)")

    def _load(self):
        path = REQUESTS_DIR / "requests.json"
        if path.exists():
            data = json.loads(path.read_text())
            for r in data:
                req = SkillRequest(r["requesting_agent"], r["capability_needed"], r["context"], r.get("priority", "medium"))
                req.request_id = r["request_id"]
                req.status = r["status"]
                req.created_at = r["created_at"]
                req.reviewed_by = r.get("reviewed_by")
                req.review_notes = r.get("review_notes")
                req.skill_id = r.get("skill_id")
                req.rejection_reason = r.get("rejection_reason")
                self.requests[req.request_id] = req

    def _save(self):
        path = REQUESTS_DIR / "requests.json"
        data = [vars(r) for r in self.requests.values()]
        path.write_text(json.dumps(data, indent=2))

    def submit_request(self, requesting_agent, capability_needed, context, priority="medium"):
        req = SkillRequest(requesting_agent, capability_needed, context, priority)
        self.requests[req.request_id] = req
        self._save()
        logger.info(f"Skill request {req.request_id} from {requesting_agent}: {capability_needed}")
        return req.request_id

    def review_request(self, request_id, reviewer_agent, approved, notes="", rejection_reason=""):
        req = self.requests.get(request_id)
        if not req:
            return None, "Request not found"
        req.reviewed_by = reviewer_agent
        req.review_notes = notes
        if approved:
            req.status = "approved"
            logger.info(f"Request {request_id} approved by {reviewer_agent}")
        else:
            req.status = "rejected"
            req.rejection_reason = rejection_reason
            logger.info(f"Request {request_id} rejected by {reviewer_agent}: {rejection_reason}")
        self._save()
        return req, None

    def mark_building(self, request_id, skill_id):
        req = self.requests.get(request_id)
        if req:
            req.status = "building"
            req.skill_id = skill_id
            self._save()

    def mark_deployed(self, request_id):
        req = self.requests.get(request_id)
        if req:
            req.status = "deployed"
            self._save()
            logger.info(f"Request {request_id} deployed as skill {req.skill_id}")

    def get_pending(self):
        return [r for r in self.requests.values() if r.status == "pending"]

    def get_request(self, request_id):
        return self.requests.get(request_id)

    def get_all(self):
        return list(self.requests.values())

    def get_stats(self):
        statuses = {}
        for r in self.requests.values():
            statuses[r.status] = statuses.get(r.status, 0) + 1
        return {"total": len(self.requests), "by_status": statuses}
