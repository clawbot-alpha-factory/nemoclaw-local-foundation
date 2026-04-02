#!/usr/bin/env python3
"""
NemoClaw Authentication Flow Handler (auth_flows.py)
Manages web login flows using browser-use + credential vault.

Supports: username/password, Google OAuth, TOTP 2FA.
Uses site-profiles.yaml for per-site selectors and auth methods.

Usage:
    from auth_flows import AuthFlowHandler
    handler = AuthFlowHandler(browser_adapter, vault)
    ok, result = await handler.login("heygen.com", agent_id="narrative_content_lead")

    python3 scripts/auth_flows.py --test
"""

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

REPO = Path(__file__).resolve().parent.parent
LOG_DIR = Path.home() / ".nemoclaw" / "browser"
AUTH_LOG = LOG_DIR / "auth-actions.jsonl"

logger = logging.getLogger("nemoclaw.auth")


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def _load_site_profiles() -> dict:
    """Load site-profiles.yaml."""
    config_path = REPO / "config" / "site-profiles.yaml"
    if config_path.exists():
        try:
            import yaml
            with open(config_path) as f:
                return yaml.safe_load(f).get("sites", {})
        except Exception:
            pass
    return {}


# ---------------------------------------------------------------------------
# AuthFlowHandler
# ---------------------------------------------------------------------------

class AuthFlowHandler:
    """Manages web authentication flows using browser-use + credential vault."""

    def __init__(self, browser_adapter=None, vault=None):
        """
        Args:
            browser_adapter: BrowserUseAdapter instance
            vault: CredentialVault instance
        """
        self.adapter = browser_adapter
        self.vault = vault
        self.sites = _load_site_profiles()
        self.sessions = {}  # agent_id -> {domain -> {logged_in, timestamp}}
        LOG_DIR.mkdir(parents=True, exist_ok=True)

    def _log(self, action: str, service: str, agent_id: str,
             success: bool, error: str = None):
        """Append to auth log."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "service": service,
            "agent_id": agent_id,
            "success": success,
        }
        if error:
            entry["error"] = str(error)[:500]
        try:
            with open(AUTH_LOG, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass

    def get_site_profile(self, service: str) -> dict:
        """Get site profile by domain or key."""
        if service in self.sites:
            return self.sites[service]
        # Try matching by domain substring
        for key, profile in self.sites.items():
            if key in service or service in key:
                return profile
        return {}

    def is_logged_in(self, agent_id: str, service: str) -> bool:
        """Check if agent has an active session for this service."""
        agent_sessions = self.sessions.get(agent_id, {})
        session = agent_sessions.get(service)
        if not session:
            return False
        # Session TTL: 24 hours
        elapsed = time.time() - session.get("timestamp", 0)
        if elapsed > 86400:
            return False
        return session.get("logged_in", False)

    def _mark_logged_in(self, agent_id: str, service: str):
        """Mark agent as logged in to service."""
        if agent_id not in self.sessions:
            self.sessions[agent_id] = {}
        self.sessions[agent_id][service] = {
            "logged_in": True,
            "timestamp": time.time(),
        }

    def _mark_logged_out(self, agent_id: str, service: str):
        """Mark agent as logged out."""
        if agent_id in self.sessions and service in self.sessions[agent_id]:
            del self.sessions[agent_id][service]

    async def login(self, service: str, agent_id: str,
                    method: str = "auto") -> tuple:
        """Execute login flow for a service.

        Args:
            service: Service identifier (e.g. "heygen.com")
            agent_id: Agent performing the login
            method: "auto", "password", "google_oauth", "totp"

        Returns:
            (success, {method_used, service, session_active})
        """
        # Check existing session
        if self.is_logged_in(agent_id, service):
            return (True, {"method_used": "existing_session", "service": service,
                           "session_active": True})

        profile = self.get_site_profile(service)
        if not profile:
            return (False, f"No site profile for '{service}'. Add it to config/site-profiles.yaml")

        # Login approval DISABLED — agents have full autonomy (2026-04-02)

        # Auto-detect method
        if method == "auto":
            auth_methods = profile.get("auth_methods", ["password"])
            method = auth_methods[0]

        # Get credentials
        if self.vault and method in ("password", "google_oauth"):
            ok, creds = self.vault.retrieve(service, agent_id)
            if not ok:
                self._log("login", service, agent_id, False, f"Vault: {creds}")
                return (False, f"Cannot retrieve credentials: {creds}")
        else:
            creds = {}

        # Execute flow
        try:
            if method == "password":
                ok, result = await self._login_password(service, agent_id, profile, creds)
            elif method == "google_oauth":
                ok, result = await self._login_google_oauth(service, agent_id, profile, creds)
            elif method == "totp":
                ok, result = await self._handle_2fa(service, agent_id)
            else:
                return (False, f"Unknown auth method: {method}")

            if ok:
                self._mark_logged_in(agent_id, service)
                self._log("login", service, agent_id, True)
            else:
                self._log("login", service, agent_id, False, str(result))

            return (ok, {
                "method_used": method,
                "service": service,
                "session_active": ok,
                **(result if isinstance(result, dict) else {"error": result}),
            })

        except Exception as e:
            self._log("login", service, agent_id, False, str(e))
            return (False, str(e))

    async def _login_password(self, service: str, agent_id: str,
                              profile: dict, creds: dict) -> tuple:
        """Username/password login flow."""
        if not self.adapter:
            return (False, "No browser adapter configured")

        login_url = profile.get("login_url")
        if not login_url:
            return (False, f"No login_url in profile for {service}")

        selectors = profile.get("selectors", {})
        username = creds.get("username", "")
        password = creds.get("password", "")

        if not username or not password:
            return (False, "Missing username or password in vault")

        # Use browser-use autonomous task for login
        goal = (
            f"Go to {login_url}. "
            f"Fill the email/username field with the value of x_username. "
            f"Fill the password field with the value of x_password. "
            f"Click the submit/login button. "
            f"Wait for the page to load after login."
        )

        ok, result = await self.adapter.run_task(
            goal=goal,
            start_url=login_url,
            sensitive_data={"x_username": username, "x_password": password},
            max_steps=15,
        )
        return (ok, result)

    async def _login_google_oauth(self, service: str, agent_id: str,
                                   profile: dict, creds: dict) -> tuple:
        """Google OAuth login flow."""
        if not self.adapter:
            return (False, "No browser adapter configured")

        login_url = profile.get("login_url")
        selectors = profile.get("selectors", {})
        google_button = selectors.get("google_button")

        email = creds.get("username", creds.get("email", ""))
        password = creds.get("password", "")

        if not email:
            return (False, "Missing email for Google OAuth")

        goal = f"Go to {login_url}. "
        if google_button:
            goal += f"Click the Google sign-in button. "
        goal += (
            f"In the Google login page, enter the email x_email. "
            f"Click Next. Enter the password x_password. Click Next. "
            f"If there's a consent screen, click Allow/Continue. "
            f"Wait for redirect back to {service}."
        )

        ok, result = await self.adapter.run_task(
            goal=goal,
            start_url=login_url,
            sensitive_data={"x_email": email, "x_password": password},
            max_steps=25,
        )
        return (ok, result)

    async def _handle_2fa(self, service: str, agent_id: str) -> tuple:
        """Handle TOTP 2FA."""
        if not self.vault:
            return (False, "No vault configured for TOTP")

        ok, totp_result = self.vault.generate_totp(service, agent_id)
        if not ok:
            return (False, f"TOTP generation failed: {totp_result}")

        code = totp_result["code"]

        if not self.adapter:
            return (True, {"code": code, "note": "No browser adapter — code generated only"})

        goal = (
            f"Find the 2FA/verification code input field. "
            f"Enter the code x_totp_code. "
            f"Click verify/submit."
        )

        ok, result = await self.adapter.run_task(
            goal=goal,
            sensitive_data={"x_totp_code": code},
            max_steps=10,
        )
        return (ok, result)

    async def check_session(self, agent_id: str, service: str) -> bool:
        """Verify if existing browser session is still valid."""
        profile = self.get_site_profile(service)
        post_login_check = profile.get("post_login_check")
        if not post_login_check or not self.adapter:
            return self.is_logged_in(agent_id, service)

        try:
            ok, _ = await self.adapter.wait_for_element(post_login_check, timeout=5000)
            if ok:
                self._mark_logged_in(agent_id, service)
            return ok
        except Exception:
            return False

    async def logout(self, agent_id: str, service: str) -> tuple:
        """Logout from a service."""
        self._mark_logged_out(agent_id, service)
        self._log("logout", service, agent_id, True)
        return (True, {"service": service, "agent_id": agent_id})


# ---------------------------------------------------------------------------
# Session Persistence
# ---------------------------------------------------------------------------

SESSION_FILE = LOG_DIR / "sessions.json"


def save_sessions(sessions: dict):
    """Persist sessions to disk for restart survival."""
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(SESSION_FILE, "w") as f:
            json.dump(sessions, f, indent=2)
    except Exception as e:
        logger.warning(f"Failed to save sessions: {e}")


def load_sessions() -> dict:
    """Load persisted sessions from disk. Prune expired (>24h)."""
    if not SESSION_FILE.exists():
        return {}
    try:
        with open(SESSION_FILE) as f:
            sessions = json.load(f)
        # Prune expired sessions
        now = time.time()
        pruned = {}
        for agent_id, agent_sessions in sessions.items():
            valid = {}
            for service, session in agent_sessions.items():
                if now - session.get("timestamp", 0) < 86400:
                    valid[service] = session
            if valid:
                pruned[agent_id] = valid
        return pruned
    except Exception:
        return {}


# Monkey-patch AuthFlowHandler to persist sessions
_original_mark_logged_in = AuthFlowHandler._mark_logged_in
_original_mark_logged_out = AuthFlowHandler._mark_logged_out


def _persistent_mark_logged_in(self, agent_id, service):
    _original_mark_logged_in(self, agent_id, service)
    save_sessions(self.sessions)


def _persistent_mark_logged_out(self, agent_id, service):
    _original_mark_logged_out(self, agent_id, service)
    save_sessions(self.sessions)


AuthFlowHandler._mark_logged_in = _persistent_mark_logged_in
AuthFlowHandler._mark_logged_out = _persistent_mark_logged_out


# ---------------------------------------------------------------------------
# Signup Handler — Autonomous Account Creation
# ---------------------------------------------------------------------------

class SignupHandler:
    """Autonomous account creation for any service with a site profile.

    Flow:
      1. Generate credentials (email alias + password)
      2. Navigate to signup page via browser-use
      3. Fill form autonomously (LLM-driven, handles dynamic forms)
      4. Submit + handle verification
      5. Store credentials in vault

    Usage:
        from auth_flows import SignupHandler
        handler = SignupHandler(browser_adapter, vault)
        ok, result = await handler.signup("heygen.com", "narrative_content_lead")
    """

    def __init__(self, browser_adapter=None, vault=None):
        self.adapter = browser_adapter
        self.vault = vault

        # Lazy imports to avoid circular deps
        try:
            from credential_vault import CredentialVault, CredentialGenerator
            self.vault = vault or CredentialVault()
            self.generator = CredentialGenerator(self.vault)
        except ImportError:
            self.vault = vault
            self.generator = None

        self.sites = _load_site_profiles()
        LOG_DIR.mkdir(parents=True, exist_ok=True)

    def _log(self, action, service, agent_id, success, error=None):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action, "service": service,
            "agent_id": agent_id, "success": success,
        }
        if error:
            entry["error"] = str(error)[:500]
        try:
            with open(AUTH_LOG, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass

    async def signup(self, service: str, agent_id: str,
                     method: str = "auto") -> tuple:
        """Create a new account on a service autonomously.

        Args:
            service: Service domain (e.g., "heygen.com").
            agent_id: Agent requesting account creation.
            method: "form" (fill signup form) or "google_oauth" (use Google).

        Returns:
            Tuple of (success: bool, result_dict_or_error).
        """
        profile = self.sites.get(service, {})
        if not profile:
            # Try substring match
            for key, p in self.sites.items():
                if key in service or service in key:
                    profile = p
                    break

        # Check if credentials already exist (already signed up)
        if self.vault:
            ok, existing = self.vault.retrieve(service, agent_id)
            if ok and existing:
                self._log("signup_skipped", service, agent_id, True, "Account already exists")
                return (True, {"status": "already_exists", "credentials": existing})

        # Determine signup method
        signup_method = method
        if signup_method == "auto":
            signup_method = profile.get("signup_method", "form")
            # Prefer OAuth if available
            if "google_oauth" in profile.get("auth_methods", []):
                signup_method = "google_oauth"

        if signup_method == "google_oauth":
            return await self._signup_oauth(service, agent_id, profile)
        else:
            return await self._signup_form(service, agent_id, profile)

    async def _signup_form(self, service, agent_id, profile) -> tuple:
        """Create account via signup form."""
        if not self.generator:
            return (False, "CredentialGenerator not available")
        if not self.adapter:
            return (False, "Browser adapter not available")

        # Generate credentials
        creds = self.generator.provision(service, agent_id, include_username=True)
        signup_url = profile.get("signup_url", profile.get("login_url", f"https://{service}/signup"))

        # Build goal for browser-use agent
        email = creds.get("username", "")
        password = creds.get("password", "")
        display_name = creds.get("display_username", "")

        goal = f"""Navigate to {signup_url} and create a new account.
Fill the signup form with:
- Email: {email}
- Password: {password}
- Name/Username: {display_name} (if there's a name field)
- Accept any terms/privacy checkboxes
- Click the signup/register/create account button
- Wait for account creation confirmation

If the form has a "Sign up with Google" option, DO NOT use it — fill the form directly.
If there's a CAPTCHA, try to solve it. If you can't, report it."""

        try:
            ok, result = await self.adapter.run_task(
                goal=goal,
                start_url=signup_url,
                max_steps=30,
                sensitive_data={"email": email, "password": password},
            )

            if ok:
                self._log("signup_form", service, agent_id, True)

                # Handle email verification if needed
                if profile.get("email_verification_required", True):
                    await self._verify_email(service, agent_id, email)

                return (True, {
                    "status": "created",
                    "method": "form",
                    "email": email,
                    "service": service,
                })
            else:
                self._log("signup_form", service, agent_id, False, result)
                return (False, f"Signup failed: {result}")

        except Exception as e:
            self._log("signup_form", service, agent_id, False, str(e))
            return (False, str(e))

    async def _signup_oauth(self, service, agent_id, profile) -> tuple:
        """Create account via Google OAuth (Sign in with Google)."""
        if not self.adapter:
            return (False, "Browser adapter not available")

        # For OAuth, we use the existing Google account
        if self.generator:
            self.generator.provision_oauth(service, agent_id)

        signup_url = profile.get("signup_url", profile.get("login_url", f"https://{service}/signup"))

        goal = f"""Navigate to {signup_url} and create a new account using Google OAuth.
Click the "Sign in with Google" or "Continue with Google" button.
If a Google account chooser appears, select the account.
If a consent screen appears, click "Allow" or "Continue".
Wait for account creation confirmation."""

        try:
            ok, result = await self.adapter.run_task(
                goal=goal,
                start_url=signup_url,
                max_steps=25,
            )

            if ok:
                self._log("signup_oauth", service, agent_id, True)
                return (True, {
                    "status": "created",
                    "method": "google_oauth",
                    "service": service,
                })
            else:
                self._log("signup_oauth", service, agent_id, False, result)
                return (False, f"OAuth signup failed: {result}")

        except Exception as e:
            self._log("signup_oauth", service, agent_id, False, str(e))
            return (False, str(e))

    async def _verify_email(self, service, agent_id, email) -> tuple:
        """Open Gmail, find verification email, click verify link.

        Uses GWS bridge for Gmail access if available, otherwise browser-use.
        """
        try:
            # Try GWS bridge first (faster, no browser needed)
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            try:
                from gws_bridge import GWSBridge
                gws = GWSBridge()
                ok, messages = gws.gmail_search(f"from:{service} to:{email} newer_than:10m", max_results=3)
                if ok and messages:
                    for msg in messages:
                        body = msg.get("body", "")
                        # Extract verification link
                        import re
                        links = re.findall(r'https?://[^\s<>"]+(?:verify|confirm|activate)[^\s<>"]*', body, re.I)
                        if links:
                            # Navigate to verification link
                            if self.adapter:
                                await self.adapter.run_task(
                                    goal=f"Navigate to this verification link and complete email verification: {links[0]}",
                                    start_url=links[0],
                                    max_steps=10,
                                )
                            self._log("email_verify", service, agent_id, True)
                            return (True, {"method": "gws", "link": links[0]})
            except ImportError:
                pass

            # Fallback: use browser-use to check Gmail directly
            if self.adapter:
                ok, result = await self.adapter.run_task(
                    goal=f"""Go to Gmail (https://mail.google.com).
Find the most recent email from {service} (it may be a verification/confirmation email).
Open it and click any verification/confirmation link inside.
Complete the verification process.""",
                    start_url="https://mail.google.com",
                    max_steps=20,
                )
                if ok:
                    self._log("email_verify", service, agent_id, True)
                    return (True, {"method": "browser", "result": result})

            self._log("email_verify", service, agent_id, False, "No verification method available")
            return (False, "Email verification not completed")

        except Exception as e:
            self._log("email_verify", service, agent_id, False, str(e))
            return (False, str(e))

    async def ensure_account(self, service: str, agent_id: str) -> tuple:
        """Ensure agent has an account on service. Create if needed.

        This is the main entry point for autonomous account lifecycle.
        Checks vault → if exists, return creds. If not, signup + return creds.
        """
        # Check vault first
        if self.vault:
            ok, creds = self.vault.retrieve(service, agent_id)
            if ok and creds:
                return (True, {"status": "existing", "credentials": creds})

        # No account — create one
        ok, result = await self.signup(service, agent_id)
        if ok:
            # Retrieve freshly stored credentials
            if self.vault:
                ok2, creds = self.vault.retrieve(service, agent_id)
                if ok2:
                    result["credentials"] = creds
        return (ok, result)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def _run_tests():
    """Run auth flow tests."""
    from unittest.mock import MagicMock, AsyncMock

    passed = 0
    failed = 0
    total = 0

    def test(name, fn):
        nonlocal passed, failed, total
        total += 1
        try:
            fn()
            passed += 1
            print(f"  ✅ {name}")
        except Exception as e:
            failed += 1
            print(f"  ❌ {name}: {e}")

    print("=" * 60)
    print("  Auth Flow Tests")
    print("=" * 60)

    # Test 1: Constructor
    def test_constructor():
        handler = AuthFlowHandler()
        assert handler.adapter is None
        assert handler.vault is None
        assert isinstance(handler.sites, dict)
    test("Constructor", test_constructor)

    # Test 2: Site profiles loaded
    def test_profiles():
        handler = AuthFlowHandler()
        assert "heygen.com" in handler.sites
        assert "instantly.ai" in handler.sites
        assert "linkedin.com" in handler.sites
    test("Site profiles loaded", test_profiles)

    # Test 3: Get site profile
    def test_get_profile():
        handler = AuthFlowHandler()
        profile = handler.get_site_profile("heygen.com")
        assert profile.get("login_url") is not None
        assert "google_oauth" in profile.get("auth_methods", [])
    test("Get site profile", test_get_profile)

    # Test 4: Session tracking
    def test_session():
        handler = AuthFlowHandler()
        assert handler.is_logged_in("agent_a", "test.com") is False
        handler._mark_logged_in("agent_a", "test.com")
        assert handler.is_logged_in("agent_a", "test.com") is True
        assert handler.is_logged_in("agent_b", "test.com") is False
    test("Session tracking", test_session)

    # Test 5: Session isolation
    def test_session_isolation():
        handler = AuthFlowHandler()
        handler._mark_logged_in("agent_a", "site1.com")
        handler._mark_logged_in("agent_b", "site2.com")
        assert handler.is_logged_in("agent_a", "site1.com") is True
        assert handler.is_logged_in("agent_a", "site2.com") is False
        assert handler.is_logged_in("agent_b", "site2.com") is True
    test("Session isolation", test_session_isolation)

    # Test 6: Logout
    def test_logout():
        handler = AuthFlowHandler()
        handler._mark_logged_in("agent_a", "test.com")
        loop = asyncio.new_event_loop()
        ok, _ = loop.run_until_complete(handler.logout("agent_a", "test.com"))
        loop.close()
        assert ok is True
        assert handler.is_logged_in("agent_a", "test.com") is False
    test("Logout clears session", test_logout)

    # Test 7: Login reuses session
    def test_reuse_session():
        handler = AuthFlowHandler()
        handler._mark_logged_in("agent_a", "heygen.com")
        loop = asyncio.new_event_loop()
        ok, result = loop.run_until_complete(handler.login("heygen.com", "agent_a"))
        loop.close()
        assert ok is True
        assert result["method_used"] == "existing_session"
    test("Login reuses existing session", test_reuse_session)

    # Test 8: No profile error
    def test_no_profile():
        handler = AuthFlowHandler()
        loop = asyncio.new_event_loop()
        ok, result = loop.run_until_complete(handler.login("unknown-site.xyz", "agent_a"))
        loop.close()
        assert ok is False
        assert "no site profile" in result.lower()
    test("No site profile error", test_no_profile)

    # Test 9: No vault creds
    def test_no_vault():
        mock_vault = MagicMock()
        mock_vault.retrieve.return_value = (False, "Not found")
        handler = AuthFlowHandler(vault=mock_vault)
        loop = asyncio.new_event_loop()
        ok, result = loop.run_until_complete(
            handler.login("heygen.com", "agent_a", method="password")
        )
        loop.close()
        assert ok is False
    test("No vault credentials error", test_no_vault)

    # Test 10: TOTP generation
    def test_totp():
        mock_vault = MagicMock()
        mock_vault.generate_totp.return_value = (True, {"code": "123456", "valid_for": 25})
        handler = AuthFlowHandler(vault=mock_vault)
        loop = asyncio.new_event_loop()
        ok, result = loop.run_until_complete(
            handler.login("heygen.com", "agent_a", method="totp")
        )
        loop.close()
        assert ok is True
        assert result.get("code") == "123456" or result.get("session_active") is True
    test("TOTP 2FA code generation", test_totp)

    # Test 11: Session TTL expiry
    def test_session_ttl():
        handler = AuthFlowHandler()
        handler.sessions["agent_a"] = {
            "expired.com": {"logged_in": True, "timestamp": time.time() - 90000}
        }
        assert handler.is_logged_in("agent_a", "expired.com") is False
    test("Session TTL expiry (24h)", test_session_ttl)

    # Test 12: Auth log created
    def test_auth_log():
        handler = AuthFlowHandler()
        handler._log("test", "test.com", "agent_a", True)
        assert AUTH_LOG.exists()
    test("Auth log file created", test_auth_log)

    print()
    print(f"  {'=' * 50}")
    print(f"  Auth Flow Tests: {'PASS' if failed == 0 else 'FAIL'}")
    print(f"  Passed: {passed}/{total}")
    if failed > 0:
        print(f"  Failed: {failed}/{total}")
    print(f"  {'=' * 50}")

    return failed == 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        success = _run_tests()
        sys.exit(0 if success else 1)
    else:
        print("Auth Flow Handler loaded. Use --test to run tests.")
        handler = AuthFlowHandler()
        print(f"Loaded {len(handler.sites)} site profiles:")
        for name in sorted(handler.sites.keys()):
            methods = handler.sites[name].get("auth_methods", [])
            print(f"  - {name}: {', '.join(methods)}")
