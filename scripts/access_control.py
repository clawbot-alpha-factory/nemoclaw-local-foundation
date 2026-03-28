#!/usr/bin/env python3
"""
NemoClaw Security & Access Control v1.0 (MA-19)

Permission and access control layer for multi-agent system:
- Hybrid model: role-based baseline + capability extensions
- 6 access domains: skills, memory, config, decisions, external, data
- Block + auto-escalate on unauthorized access
- Full audit trail of all access attempts
- Temporary permission grants with expiry
- MA-4 decision log integration for escalations

Usage:
  python3 scripts/access_control.py --test
  python3 scripts/access_control.py --permissions AGENT_ID
  python3 scripts/access_control.py --audit
  python3 scripts/access_control.py --violations
  python3 scripts/access_control.py --grants
"""

import argparse
import json
import os
import sys
import uuid
import yaml
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import defaultdict

REPO = Path.home() / "nemoclaw-local-foundation"
SEC_DIR = Path.home() / ".nemoclaw" / "security"
AUDIT_PATH = SEC_DIR / "access-audit.jsonl"
VIOLATIONS_PATH = SEC_DIR / "access-violations.jsonl"
GRANTS_PATH = SEC_DIR / "temp-grants.json"
STATS_PATH = SEC_DIR / "security-stats.json"

# ═══════════════════════════════════════════════════════════════════════════════
# ACCESS DOMAINS & RESOURCES
# ═══════════════════════════════════════════════════════════════════════════════

ACCESS_DOMAINS = {
    "skills": {
        "description": "Execute skills",
        "actions": ["execute", "list", "inspect"],
    },
    "memory": {
        "description": "Read/write agent memory workspaces",
        "actions": ["read", "write", "delete", "promote"],
    },
    "config": {
        "description": "Modify system configuration",
        "actions": ["read", "modify", "reset"],
    },
    "decisions": {
        "description": "Propose, approve, override decisions",
        "actions": ["propose", "vote", "approve", "override", "veto"],
    },
    "external": {
        "description": "Call external APIs and services",
        "actions": ["api_call", "webhook", "scrape"],
    },
    "data": {
        "description": "Access sensitive business data",
        "actions": ["read_public", "read_private", "read_financial", "export"],
    },
    "web": {
        "description": "Browser automation via PinchTab",
        "actions": ["navigate", "text", "click", "fill", "screenshot", "eval"],
    },
}

# ═══════════════════════════════════════════════════════════════════════════════
# ROLE-BASED PERMISSIONS (baseline)
# ═══════════════════════════════════════════════════════════════════════════════

ROLE_PERMISSIONS = {
    "executive_operator": {
        "skills": ["execute", "list", "inspect"],
        "memory": ["read", "write", "delete", "promote"],
        "config": ["read", "modify", "reset"],
        "decisions": ["propose", "vote", "approve", "override", "veto"],
        "external": ["api_call", "webhook"],
        "data": ["read_public", "read_private", "read_financial", "export"],
        "web": ["navigate", "text", "click", "fill", "screenshot", "eval"],
    },
    "strategy_lead": {
        "skills": ["execute", "list", "inspect"],
        "memory": ["read", "write", "promote"],
        "config": ["read"],
        "decisions": ["propose", "vote"],
        "external": ["api_call"],
        "data": ["read_public", "read_private"],
        "web": ["navigate", "text", "click", "fill", "screenshot"],
    },
    "product_architect": {
        "skills": ["execute", "list", "inspect"],
        "memory": ["read", "write", "promote"],
        "config": ["read"],
        "decisions": ["propose", "vote"],
        "external": ["api_call"],
        "data": ["read_public", "read_private"],
        "web": ["navigate", "text"],
    },
    "engineering_lead": {
        "skills": ["execute", "list", "inspect"],
        "memory": ["read", "write"],
        "config": ["read"],
        "decisions": ["propose", "vote"],
        "external": ["api_call"],
        "data": ["read_public"],
        "web": ["navigate", "text"],
    },
    "growth_revenue_lead": {
        "skills": ["execute", "list", "inspect"],
        "memory": ["read", "write", "promote"],
        "config": ["read"],
        "decisions": ["propose", "vote"],
        "external": ["api_call", "webhook"],
        "data": ["read_public", "read_private", "read_financial"],
        "web": ["navigate", "text", "click", "fill", "screenshot"],
    },
    "operations_lead": {
        "skills": ["execute", "list", "inspect"],
        "memory": ["read", "write"],
        "config": ["read", "modify"],
        "decisions": ["propose", "vote"],
        "external": ["api_call"],
        "data": ["read_public"],
        "web": ["navigate", "text"],
    },
    "narrative_content_lead": {
        "skills": ["execute", "list", "inspect"],
        "memory": ["read", "write"],
        "config": ["read"],
        "decisions": ["propose", "vote"],
        "external": [],
        "data": ["read_public"],
        "web": ["navigate", "text", "click", "fill", "screenshot"],
    },
}

# Sensitive resources that require explicit permission
SENSITIVE_RESOURCES = {
    "config:budget-config.yaml": {"min_level": 1, "actions": ["modify", "reset"]},
    "config:routing-config.yaml": {"min_level": 1, "actions": ["modify"]},
    "config:.env": {"min_level": 1, "actions": ["read", "modify"]},
    "data:customer_records": {"min_level": 1, "actions": ["read_private", "export"]},
    "data:financial_reports": {"min_level": 2, "actions": ["read_financial"]},
    "external:payment_api": {"min_level": 1, "actions": ["api_call"]},
    "decisions:irreversible": {"min_level": 1, "actions": ["approve", "override"]},
}


# ═══════════════════════════════════════════════════════════════════════════════
# TEMPORARY GRANTS
# ═══════════════════════════════════════════════════════════════════════════════

class GrantManager:
    """Manages temporary permission grants."""

    def __init__(self):
        self.grants = {}  # grant_id → grant
        self._load()

    def _load(self):
        SEC_DIR.mkdir(parents=True, exist_ok=True)
        if GRANTS_PATH.exists():
            try:
                with open(GRANTS_PATH) as f:
                    self.grants = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.grants = {}

    def _save(self):
        SEC_DIR.mkdir(parents=True, exist_ok=True)
        with open(GRANTS_PATH, "w") as f:
            json.dump(self.grants, f, indent=2)

    def grant(self, agent_id, domain, action, granted_by, duration_hours=24, reason=""):
        """Grant temporary permission.

        Returns: (grant_id, expiry)
        """
        grant_id = f"grant_{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc)
        expiry = (now + timedelta(hours=duration_hours)).isoformat()

        self.grants[grant_id] = {
            "id": grant_id,
            "agent_id": agent_id,
            "domain": domain,
            "action": action,
            "granted_by": granted_by,
            "granted_at": now.isoformat(),
            "expires_at": expiry,
            "reason": reason,
            "revoked": False,
        }
        self._save()
        return grant_id, expiry

    def revoke(self, grant_id):
        """Revoke a grant."""
        if grant_id in self.grants:
            self.grants[grant_id]["revoked"] = True
            self._save()
            return True
        return False

    def has_grant(self, agent_id, domain, action):
        """Check if agent has an active temporary grant.

        Returns: (has_grant, grant_id)
        """
        now = datetime.now(timezone.utc)
        for gid, grant in self.grants.items():
            if (grant["agent_id"] == agent_id and
                grant["domain"] == domain and
                grant["action"] == action and
                not grant["revoked"]):
                try:
                    expiry = datetime.fromisoformat(
                        grant["expires_at"].replace("Z", "+00:00"))
                    if now < expiry:
                        return True, gid
                except (ValueError, AttributeError):
                    continue
        return False, None

    def cleanup_expired(self):
        """Remove expired grants."""
        now = datetime.now(timezone.utc)
        expired = []
        for gid, grant in list(self.grants.items()):
            try:
                expiry = datetime.fromisoformat(
                    grant["expires_at"].replace("Z", "+00:00"))
                if now >= expiry:
                    expired.append(gid)
            except (ValueError, AttributeError):
                continue
        for gid in expired:
            del self.grants[gid]
        if expired:
            self._save()
        return expired

    def get_active(self, agent_id=None):
        """Get active grants, optionally filtered by agent."""
        now = datetime.now(timezone.utc)
        active = []
        for gid, grant in self.grants.items():
            if grant["revoked"]:
                continue
            try:
                expiry = datetime.fromisoformat(
                    grant["expires_at"].replace("Z", "+00:00"))
                if now < expiry:
                    if agent_id is None or grant["agent_id"] == agent_id:
                        active.append(grant)
            except (ValueError, AttributeError):
                continue
        return active


# ═══════════════════════════════════════════════════════════════════════════════
# ACCESS CONTROLLER (main engine)
# ═══════════════════════════════════════════════════════════════════════════════

class AccessController:
    """Hybrid permission enforcement engine.

    Checks in order:
    1. Role-based baseline permissions
    2. Capability extensions (from agent-schema.yaml)
    3. Temporary grants
    4. Sensitive resource checks

    Unauthorized → block + auto-escalate to executive.
    """

    def __init__(self):
        self.grant_manager = GrantManager()
        self._authority = {}
        self._capabilities = {}
        self._load_agent_data()
        self.stats = SecurityStats()

    def _load_agent_data(self):
        try:
            with open(REPO / "config" / "agents" / "agent-schema.yaml") as f:
                schema = yaml.safe_load(f)
            for agent in schema.get("agents", []):
                self._authority[agent["agent_id"]] = agent.get("authority_level", 3)
        except Exception:
            self._authority = {}

        try:
            with open(REPO / "config" / "agents" / "capability-registry.yaml") as f:
                reg = yaml.safe_load(f).get("capabilities", {})
            self._capabilities = defaultdict(set)
            for cap_name, cap in reg.items():
                owner = cap.get("owned_by")
                if owner:
                    self._capabilities[owner].add(cap_name)
        except Exception:
            self._capabilities = defaultdict(set)

    def check_access(self, agent_id, domain, action, resource=None):
        """Check if an agent has permission for an action.

        Args:
            agent_id: who is requesting access
            domain: which access domain (skills, memory, config, etc.)
            action: what action (read, write, execute, etc.)
            resource: optional specific resource identifier

        Returns: AccessResult
        """
        result = AccessResult(agent_id, domain, action, resource)

        # 1. Check role-based permissions
        role_perms = ROLE_PERMISSIONS.get(agent_id, {})
        domain_perms = role_perms.get(domain, [])

        if action in domain_perms:
            result.granted = True
            result.grant_source = "role"
            self._audit(result)
            self.stats.record(result)
            return result

        # 2. Check capability extensions
        agent_caps = self._capabilities.get(agent_id, set())
        if self._capability_grants_access(agent_caps, domain, action):
            result.granted = True
            result.grant_source = "capability"
            self._audit(result)
            self.stats.record(result)
            return result

        # 3. Check temporary grants
        has_grant, grant_id = self.grant_manager.has_grant(agent_id, domain, action)
        if has_grant:
            result.granted = True
            result.grant_source = f"temp_grant:{grant_id}"
            self._audit(result)
            self.stats.record(result)
            return result

        # 4. Check sensitive resource restrictions
        if resource:
            resource_key = f"{domain}:{resource}"
            sensitive = SENSITIVE_RESOURCES.get(resource_key)
            if sensitive:
                agent_level = self._authority.get(agent_id, 3)
                if agent_level > sensitive["min_level"]:
                    result.granted = False
                    result.denial_reason = (
                        f"Sensitive resource '{resource}' requires authority level "
                        f"{sensitive['min_level']}, agent is level {agent_level}")

        # ── DENIED ──
        if not result.granted:
            if not result.denial_reason:
                result.denial_reason = (
                    f"{agent_id} lacks '{action}' permission in domain '{domain}'"
                    f"{f' for resource {resource}' if resource else ''}")
            result.escalated = True
            result.escalated_to = "executive_operator"

            self._audit(result)
            self._log_violation(result)
            self._escalate(result)
            self.stats.record(result)

        return result

    def _capability_grants_access(self, capabilities, domain, action):
        """Check if any capability extends access to this domain/action.

        Capabilities grant implicit access:
        - Having any skill capability → skills:execute,list,inspect
        - Having memory-related capability → memory:read,write
        """
        if not capabilities:
            return False

        # Any capability grants basic skill access
        if domain == "skills" and action in ("execute", "list", "inspect"):
            return len(capabilities) > 0

        return False

    def grant_temporary(self, agent_id, domain, action, granted_by,
                         duration_hours=24, reason=""):
        """Grant temporary permission.

        Only executive_operator or authority level 1 can grant.
        """
        granter_level = self._authority.get(granted_by, 3)
        if granter_level > 1 and granted_by != "executive_operator":
            return None, "Only authority level 1 can grant permissions"

        grant_id, expiry = self.grant_manager.grant(
            agent_id, domain, action, granted_by, duration_hours, reason)
        return grant_id, expiry

    def revoke_grant(self, grant_id):
        return self.grant_manager.revoke(grant_id)

    def get_permissions(self, agent_id):
        """Get all effective permissions for an agent.

        Returns: dict of domain → [actions]
        """
        perms = {}
        role_perms = ROLE_PERMISSIONS.get(agent_id, {})

        for domain in ACCESS_DOMAINS:
            actions = set(role_perms.get(domain, []))

            # Add capability extensions
            agent_caps = self._capabilities.get(agent_id, set())
            if agent_caps and domain == "skills":
                actions.update(["execute", "list", "inspect"])

            # Add temporary grants
            for grant in self.grant_manager.get_active(agent_id):
                if grant["domain"] == domain:
                    actions.add(grant["action"])

            perms[domain] = sorted(actions)

        return perms

    def _audit(self, result):
        """Audit log all access attempts."""
        SEC_DIR.mkdir(parents=True, exist_ok=True)
        entry = result.to_dict()
        with open(AUDIT_PATH, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def _log_violation(self, result):
        """Log access violations."""
        SEC_DIR.mkdir(parents=True, exist_ok=True)
        with open(VIOLATIONS_PATH, "a") as f:
            f.write(json.dumps(result.to_dict()) + "\n")

    def _escalate(self, result):
        """Auto-escalate unauthorized access to executive."""
        try:
            sys.path.insert(0, str(REPO / "scripts"))
            from decision_log import DecisionLog
            dl = DecisionLog()
            title = f"Access violation: {result.agent_id} → {result.domain}:{result.action}"
            desc = (
                f"Agent: {result.agent_id}\n"
                f"Domain: {result.domain}\n"
                f"Action: {result.action}\n"
                f"Resource: {result.resource or 'N/A'}\n"
                f"Reason: {result.denial_reason}\n"
                f"Auto-escalated to executive_operator\n"
            )
            dec_id, _ = dl.propose("executive_operator", title, desc,
                                    reversibility="reversible", confidence=0.9)
            dl.decide(dec_id, f"Access denied: {result.denial_reason[:80]}",
                     "Auto-escalated by AccessController", decided_by="executive_operator")
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════════════
# ACCESS RESULT
# ═══════════════════════════════════════════════════════════════════════════════

class AccessResult:
    """Result of an access check."""

    def __init__(self, agent_id, domain, action, resource=None):
        self.agent_id = agent_id
        self.domain = domain
        self.action = action
        self.resource = resource
        self.granted = False
        self.grant_source = None  # role | capability | temp_grant:ID
        self.denial_reason = None
        self.escalated = False
        self.escalated_to = None
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self):
        return {
            "timestamp": self.timestamp,
            "agent_id": self.agent_id,
            "domain": self.domain,
            "action": self.action,
            "resource": self.resource,
            "granted": self.granted,
            "grant_source": self.grant_source,
            "denial_reason": self.denial_reason,
            "escalated": self.escalated,
            "escalated_to": self.escalated_to,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# SECURITY STATISTICS
# ═══════════════════════════════════════════════════════════════════════════════

class SecurityStats:
    """Tracks access control statistics."""

    def __init__(self):
        self.data = {
            "total_checks": 0,
            "total_granted": 0,
            "total_denied": 0,
            "total_escalated": 0,
            "by_agent": {},
            "by_domain": {},
            "by_source": {},
        }
        self._load()

    def _load(self):
        SEC_DIR.mkdir(parents=True, exist_ok=True)
        if STATS_PATH.exists():
            try:
                with open(STATS_PATH) as f:
                    self.data = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

    def _save(self):
        SEC_DIR.mkdir(parents=True, exist_ok=True)
        with open(STATS_PATH, "w") as f:
            json.dump(self.data, f, indent=2)

    def record(self, result):
        self.data["total_checks"] += 1
        if result.granted:
            self.data["total_granted"] += 1
        else:
            self.data["total_denied"] += 1
        if result.escalated:
            self.data["total_escalated"] += 1

        # By agent
        agent = result.agent_id
        if agent not in self.data["by_agent"]:
            self.data["by_agent"][agent] = {"granted": 0, "denied": 0}
        if result.granted:
            self.data["by_agent"][agent]["granted"] += 1
        else:
            self.data["by_agent"][agent]["denied"] += 1

        # By domain
        domain = result.domain
        if domain not in self.data["by_domain"]:
            self.data["by_domain"][domain] = {"granted": 0, "denied": 0}
        if result.granted:
            self.data["by_domain"][domain]["granted"] += 1
        else:
            self.data["by_domain"][domain]["denied"] += 1

        # By source
        source = result.grant_source or "denied"
        if source not in self.data["by_source"]:
            self.data["by_source"][source] = 0
        self.data["by_source"][source] += 1

        self._save()


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS
# ═══════════════════════════════════════════════════════════════════════════════

def run_tests():
    print("=" * 60)
    print("  MA-19 Security & Access Control Tests")
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

    ac = AccessController()
    ac.grant_manager.grants = {}  # clean

    # Test 1: Access domains
    test("7 access domains", len(ACCESS_DOMAINS) == 7)

    # Test 2: All 7 agents have role permissions
    test("7 role permission sets", len(ROLE_PERMISSIONS) == 7)

    # Test 3: Executive has full access
    exec_perms = ROLE_PERMISSIONS["executive_operator"]
    has_all = all(len(exec_perms.get(d, [])) >= 2 for d in ACCESS_DOMAINS)
    test("Executive has broad permissions", has_all)

    # Test 4: Role-based access — granted
    r = ac.check_access("strategy_lead", "skills", "execute")
    test("Role: strategy_lead can execute skills", r.granted and r.grant_source == "role")

    # Test 5: Role-based access — denied
    r = ac.check_access("narrative_content_lead", "external", "api_call")
    test("Role: content lead blocked from external API",
         not r.granted, f"granted={r.granted}")

    # Test 6: Auto-escalation on denial
    test("Denial auto-escalates", r.escalated and r.escalated_to == "executive_operator")

    # Test 7: Denial reason provided
    test("Denial reason provided", r.denial_reason is not None and len(r.denial_reason) > 0)

    # Test 8: Config modify — only ops and executive
    r_eng = ac.check_access("engineering_lead", "config", "modify")
    r_ops = ac.check_access("operations_lead", "config", "modify")
    test("Engineering can't modify config", not r_eng.granted)
    test("Operations can modify config", r_ops.granted)

    # Test 10: Decision override — executive only
    r_strat = ac.check_access("strategy_lead", "decisions", "override")
    r_exec = ac.check_access("executive_operator", "decisions", "override")
    test("Strategy can't override decisions", not r_strat.granted)
    test("Executive can override decisions", r_exec.granted)

    # Test 12: Data access tiers
    r_pub = ac.check_access("engineering_lead", "data", "read_public")
    r_priv = ac.check_access("engineering_lead", "data", "read_private")
    test("Engineering: read_public OK", r_pub.granted)
    test("Engineering: read_private blocked", not r_priv.granted)

    # Test 14: Financial data — growth lead OK
    r_fin = ac.check_access("growth_revenue_lead", "data", "read_financial")
    test("Growth lead: financial data OK", r_fin.granted)

    # Test 15: Temporary grant
    gid, expiry = ac.grant_temporary(
        "narrative_content_lead", "external", "api_call",
        "executive_operator", duration_hours=2, reason="Needs API for research task")
    test("Temp grant created", gid is not None)

    # Test 16: Temp grant enables access
    r_after = ac.check_access("narrative_content_lead", "external", "api_call")
    test("Temp grant enables access",
         r_after.granted and "temp_grant" in (r_after.grant_source or ""))

    # Test 17: Revoke grant
    ac.revoke_grant(gid)
    r_revoked = ac.check_access("narrative_content_lead", "external", "api_call")
    test("Revoked grant blocks access", not r_revoked.granted)

    # Test 18: Only authority level 1 can grant
    result_id, msg = ac.grant_temporary(
        "engineering_lead", "config", "modify",
        "strategy_lead")  # level 2, not authorized
    test("Non-executive can't grant permissions", result_id is None)

    # Test 19: Sensitive resource check
    r_sens = ac.check_access("strategy_lead", "config", "modify",
                               resource=".env")
    test("Sensitive .env blocked for non-executive",
         not r_sens.granted, r_sens.denial_reason)

    # Test 20: Executive can access sensitive
    r_exec_sens = ac.check_access("executive_operator", "config", "modify",
                                    resource=".env")
    test("Executive can access .env", r_exec_sens.granted)

    # Test 21: Get effective permissions
    perms = ac.get_permissions("strategy_lead")
    test("Get permissions works",
         "skills" in perms and "execute" in perms.get("skills", []))

    # Test 22: Permissions include all domains
    test("Permissions cover all 7 domains", len(perms) == 7)

    # Test 23: Memory permissions
    r_mem = ac.check_access("engineering_lead", "memory", "delete")
    test("Engineering can't delete memory", not r_mem.granted)

    r_exec_mem = ac.check_access("executive_operator", "memory", "delete")
    test("Executive can delete memory", r_exec_mem.granted)

    # Test 25: Export data — executive only
    r_exp = ac.check_access("strategy_lead", "data", "export")
    test("Strategy can't export data", not r_exp.granted)

    r_exec_exp = ac.check_access("executive_operator", "data", "export")
    test("Executive can export data", r_exec_exp.granted)

    # Test 27: Stats tracking
    stats = ac.stats.data
    test("Stats: total checks > 0", stats["total_checks"] > 0)
    test("Stats: by_agent tracked", len(stats["by_agent"]) > 0)
    test("Stats: by_domain tracked", len(stats["by_domain"]) > 0)

    # Test 30: Audit log exists
    test("Audit log exists", AUDIT_PATH.exists())

    # Test 31: Violations log exists
    test("Violations log exists", VIOLATIONS_PATH.exists())

    # Test 32: AccessResult serializable
    r_dict = r.to_dict()
    test("AccessResult serializable",
         all(k in r_dict for k in ["agent_id", "domain", "action", "granted"]))

    # Test 33: Active grants listing
    ac.grant_temporary("engineering_lead", "data", "read_private",
                        "executive_operator", 24, "One-time research")
    active = ac.grant_manager.get_active("engineering_lead")
    test("Active grants listed", len(active) >= 1)

    # Test 34: Cleanup expired
    old_grant = {
        "id": "grant_expired",
        "agent_id": "test",
        "domain": "skills",
        "action": "execute",
        "granted_by": "executive_operator",
        "granted_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        "reason": "test",
        "revoked": False,
    }
    ac.grant_manager.grants["grant_expired"] = old_grant
    expired = ac.grant_manager.cleanup_expired()
    test("Expired grants cleaned up", "grant_expired" in expired)

    # ── Web Access Domain Tests ──
    # Test: Web domain exists
    test("Web access domain exists", "web" in ACCESS_DOMAINS)
    test("Web domain has 6 actions", len(ACCESS_DOMAINS["web"]["actions"]) == 6)

    # Test: Growth lead has web access
    r_web = ac.check_access("growth_revenue_lead", "web", "navigate")
    test("Growth lead: web navigate OK", r_web.granted)

    r_web_click = ac.check_access("growth_revenue_lead", "web", "click")
    test("Growth lead: web click OK", r_web_click.granted)

    # Test: Growth lead blocked from eval
    r_web_eval = ac.check_access("growth_revenue_lead", "web", "eval")
    test("Growth lead: web eval blocked", not r_web_eval.granted)

    # Test: Engineering lead limited to navigate + text
    r_eng_nav = ac.check_access("engineering_lead", "web", "navigate")
    r_eng_click = ac.check_access("engineering_lead", "web", "click")
    test("Engineering: web navigate OK", r_eng_nav.granted)
    test("Engineering: web click blocked", not r_eng_click.granted)

    # Test: Executive has full web access including eval
    r_exec_eval = ac.check_access("executive_operator", "web", "eval")
    test("Executive: web eval OK", r_exec_eval.granted)

    # Test: Content lead has web for publishing
    r_content_fill = ac.check_access("narrative_content_lead", "web", "fill")
    test("Content lead: web fill OK", r_content_fill.granted)

    # Test: Web permissions in get_permissions
    web_perms = ac.get_permissions("growth_revenue_lead")
    test("Web in get_permissions", "web" in web_perms and "navigate" in web_perms["web"])

    print(f"\n  Results: {tp}/{tt} passed")
    return tp == tt


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="NemoClaw Security & Access Control")
    parser.add_argument("--test", action="store_true", help="Run all tests")
    parser.add_argument("--permissions", metavar="AGENT", help="Show agent permissions")
    parser.add_argument("--audit", action="store_true", help="Show recent audit log")
    parser.add_argument("--violations", action="store_true", help="Show access violations")
    parser.add_argument("--grants", action="store_true", help="Show active grants")
    parser.add_argument("--stats", action="store_true", help="Show security stats")
    args = parser.parse_args()

    if args.test:
        success = run_tests()
        sys.exit(0 if success else 1)

    ac = AccessController()

    if args.permissions:
        perms = ac.get_permissions(args.permissions)
        print(f"  Permissions for {args.permissions}:")
        for domain, actions in perms.items():
            icon = "✅" if actions else "🚫"
            print(f"    {icon} {domain}: {', '.join(actions) if actions else 'none'}")

    elif args.audit:
        if AUDIT_PATH.exists():
            with open(AUDIT_PATH) as f:
                for line in f.readlines()[-20:]:
                    try:
                        e = json.loads(line.strip())
                        icon = "✅" if e["granted"] else "🛑"
                        print(f"  {icon} [{e['timestamp'][:19]}] {e['agent_id']}: "
                              f"{e['domain']}:{e['action']} "
                              f"({e.get('grant_source') or e.get('denial_reason', 'denied')[:40]})")
                    except json.JSONDecodeError:
                        continue
        else:
            print("  No audit log yet.")

    elif args.violations:
        if VIOLATIONS_PATH.exists():
            with open(VIOLATIONS_PATH) as f:
                for line in f.readlines()[-20:]:
                    try:
                        e = json.loads(line.strip())
                        print(f"  🛑 [{e['timestamp'][:19]}] {e['agent_id']}: "
                              f"{e['domain']}:{e['action']} — {e.get('denial_reason', '?')[:60]}")
                    except json.JSONDecodeError:
                        continue
        else:
            print("  No violations yet.")

    elif args.grants:
        active = ac.grant_manager.get_active()
        if not active:
            print("  No active grants.")
        else:
            for g in active:
                print(f"  🔑 [{g['id']}] {g['agent_id']}: {g['domain']}:{g['action']}")
                print(f"     Granted by: {g['granted_by']} | Expires: {g['expires_at'][:19]}")
                print(f"     Reason: {g.get('reason', 'N/A')}")

    elif args.stats:
        stats = ac.stats.data
        total = stats["total_checks"]
        granted = stats["total_granted"]
        denied = stats["total_denied"]
        rate = granted / total if total > 0 else 0
        print(f"  Total checks: {total}")
        print(f"  Granted: {granted} ({rate:.0%})")
        print(f"  Denied: {denied}")
        print(f"  Escalated: {stats['total_escalated']}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
