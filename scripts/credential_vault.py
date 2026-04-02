#!/usr/bin/env python3
"""
NemoClaw Credential Vault (credential_vault.py)
Fernet-encrypted credential storage at ~/.nemoclaw/vault/credentials.enc

Never stores plaintext. Never commits to git. Per-agent access control.

Usage:
    from credential_vault import CredentialVault
    vault = CredentialVault()
    vault.store("heygen.com", "username_password", {"username": "x", "password": "y"})
    ok, creds = vault.retrieve("heygen.com", agent_id="narrative_content_lead")

CLI:
    python3 scripts/credential_vault.py --store SERVICE TYPE
    python3 scripts/credential_vault.py --retrieve SERVICE
    python3 scripts/credential_vault.py --list
    python3 scripts/credential_vault.py --test
"""

import base64
import getpass
import hashlib
import json
import logging
import os
import stat
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

REPO = Path(__file__).resolve().parent.parent
VAULT_DIR = Path.home() / ".nemoclaw" / "vault"
VAULT_FILE = VAULT_DIR / "credentials.enc"
SALT_FILE = VAULT_DIR / ".salt"
LOG_DIR = Path.home() / ".nemoclaw" / "browser"
AUDIT_LOG = LOG_DIR / "vault-audit.jsonl"

logger = logging.getLogger("nemoclaw.vault")


def _load_vault_config() -> dict:
    """Load vault config from vault-config.yaml."""
    config_path = REPO / "config" / "vault-config.yaml"
    if config_path.exists():
        try:
            import yaml
            with open(config_path) as f:
                return yaml.safe_load(f).get("vault", {})
        except Exception:
            pass
    return {}


class CredentialVault:
    """Fernet-encrypted credential storage with per-agent access control."""

    def __init__(self, vault_key: str = None):
        self.config = _load_vault_config()

        # Ensure vault directory exists with restricted permissions
        VAULT_DIR.mkdir(parents=True, exist_ok=True)
        LOG_DIR.mkdir(parents=True, exist_ok=True)

        # Derive encryption key
        raw_key = vault_key or os.environ.get("NEMOCLAW_VAULT_KEY", "")
        if not raw_key:
            # Auto-generate and persist a random key on first run (dev only)
            keyfile = VAULT_DIR / ".keyfile"
            if keyfile.exists():
                raw_key = keyfile.read_text().strip()
            else:
                import secrets
                raw_key = secrets.token_hex(32)
                keyfile.write_text(raw_key)
                os.chmod(str(keyfile), stat.S_IRUSR | stat.S_IWUSR)
                logger.info("Generated vault key at %s (set NEMOCLAW_VAULT_KEY for production)", keyfile)

        self._fernet = self._derive_key(raw_key)
        self._data = self._load()
        self.max_failed_attempts = self.config.get("max_failed_attempts", 5)
        self._failed_attempts = {}

    def _derive_key(self, raw_key: str):
        """Derive Fernet key from raw key + machine salt using PBKDF2."""
        from cryptography.fernet import Fernet
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        from cryptography.hazmat.primitives import hashes

        # Get or create salt
        if SALT_FILE.exists():
            salt = SALT_FILE.read_bytes()
        else:
            salt = os.urandom(16)
            SALT_FILE.write_bytes(salt)
            os.chmod(str(SALT_FILE), stat.S_IRUSR | stat.S_IWUSR)

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(raw_key.encode()))
        return Fernet(key)

    def _load(self) -> dict:
        """Load and decrypt vault data."""
        if not VAULT_FILE.exists():
            return {"credentials": {}, "metadata": {"created": datetime.now(timezone.utc).isoformat()}}
        try:
            encrypted = VAULT_FILE.read_bytes()
            decrypted = self._fernet.decrypt(encrypted)
            return json.loads(decrypted.decode())
        except Exception as e:
            logger.error(f"Failed to decrypt vault: {e}")
            return {"credentials": {}, "metadata": {"error": str(e)}}

    def _save(self):
        """Encrypt and save vault data."""
        self._data["metadata"]["modified"] = datetime.now(timezone.utc).isoformat()
        plaintext = json.dumps(self._data, indent=2).encode()
        encrypted = self._fernet.encrypt(plaintext)
        VAULT_FILE.write_bytes(encrypted)
        # Restrict file permissions
        os.chmod(str(VAULT_FILE), stat.S_IRUSR | stat.S_IWUSR)

    def _audit(self, action: str, service: str, agent_id: str = None,
               success: bool = True, reason: str = None):
        """Append to audit log."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "service": service,
            "agent_id": agent_id,
            "success": success,
        }
        if reason:
            entry["reason"] = reason
        try:
            with open(AUDIT_LOG, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass

    # -------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------

    def store(self, service: str, credential_type: str, data: dict,
              allowed_agents: list = None) -> bool:
        """Store a credential.

        Args:
            service: Service identifier (e.g. "heygen.com")
            credential_type: One of: username_password, oauth_token, api_key, totp_secret
            data: Credential fields (e.g. {"username": "x", "password": "y"})
            allowed_agents: List of agent IDs that can access this credential.
                           None = all agents can access.
        Returns:
            True if stored successfully.
        """
        self._data["credentials"][service] = {
            "type": credential_type,
            "data": data,
            "allowed_agents": allowed_agents,
            "stored_at": datetime.now(timezone.utc).isoformat(),
        }
        self._save()
        self._audit("store", service, success=True)
        return True

    def retrieve(self, service: str, agent_id: str = None) -> tuple:
        """Retrieve a credential.

        Args:
            service: Service identifier
            agent_id: Requesting agent ID (for access control)

        Returns:
            (success, credential_data_or_error)
        """
        # Check lockout
        if agent_id and self._failed_attempts.get(agent_id, 0) >= self.max_failed_attempts:
            self._audit("retrieve", service, agent_id, False, "locked_out")
            return (False, f"Agent '{agent_id}' locked out after {self.max_failed_attempts} failed attempts")

        cred = self._data.get("credentials", {}).get(service)
        if not cred:
            self._audit("retrieve", service, agent_id, False, "not_found")
            return (False, f"No credentials stored for '{service}'")

        # Check agent access
        allowed = cred.get("allowed_agents")
        if allowed and agent_id and agent_id not in allowed:
            self._failed_attempts[agent_id] = self._failed_attempts.get(agent_id, 0) + 1
            self._audit("retrieve", service, agent_id, False, "unauthorized")
            return (False, f"Agent '{agent_id}' not authorized for '{service}'")

        self._audit("retrieve", service, agent_id, True)
        return (True, {
            "type": cred["type"],
            **cred["data"],
        })

    def list_services(self) -> list:
        """List all stored service names."""
        return list(self._data.get("credentials", {}).keys())

    def delete(self, service: str) -> bool:
        """Delete a stored credential."""
        if service in self._data.get("credentials", {}):
            del self._data["credentials"][service]
            self._save()
            self._audit("delete", service, success=True)
            return True
        return False

    def rotate_key(self, new_key: str) -> bool:
        """Re-encrypt all credentials with a new vault key.

        Args:
            new_key: New raw key string

        Returns:
            True if rotation succeeded.
        """
        try:
            # Keep current data
            current_data = self._data

            # Delete old salt to force new derivation
            if SALT_FILE.exists():
                SALT_FILE.unlink()

            # Re-derive with new key
            self._fernet = self._derive_key(new_key)
            self._data = current_data
            self._save()
            self._audit("rotate_key", "*", success=True)
            return True
        except Exception as e:
            logger.error(f"Key rotation failed: {e}")
            return False

    def generate_totp(self, service: str, agent_id: str = None) -> tuple:
        """Generate a TOTP code for a service with stored TOTP secret.

        Returns:
            (success, {"code": "123456", "valid_for": 30})
        """
        ok, cred = self.retrieve(service, agent_id)
        if not ok:
            return (False, cred)

        if cred.get("type") != "totp_secret":
            return (False, f"Credential for '{service}' is not a TOTP secret")

        secret = cred.get("secret")
        if not secret:
            return (False, f"No TOTP secret found for '{service}'")

        try:
            import pyotp
            totp = pyotp.TOTP(secret)
            code = totp.now()
            remaining = totp.interval - (int(time.time()) % totp.interval)
            return (True, {"code": code, "valid_for": remaining})
        except Exception as e:
            return (False, str(e))


# ---------------------------------------------------------------------------
# Credential Generator — autonomous credential provisioning
# ---------------------------------------------------------------------------

class CredentialGenerator:
    """Generate credentials for autonomous account creation.

    Uses Gmail alias pattern (base+service@gmail.com) for unique emails
    per service. Generates secure passwords and agent-branded usernames.
    Auto-stores generated credentials in the vault.

    Usage:
        from credential_vault import CredentialGenerator
        gen = CredentialGenerator()
        creds = gen.provision("heygen.com", agent_id="narrative_content_lead")
        # creds = {"email": "clawdtob+heygen-narrative@gmail.com",
        #          "password": "xK9!mP2...", "username": "nemoclaw-narrative"}
    """

    BASE_EMAIL = "clawdtob@gmail.com"

    def __init__(self, vault: CredentialVault = None):
        self.vault = vault or CredentialVault()
        self._config = _load_vault_config()
        # Allow override of base email
        self.base_email = self._config.get("generator", {}).get(
            "base_email", self.BASE_EMAIL
        )

    def generate_email_alias(self, service: str, agent_id: str = "") -> str:
        """Generate a unique Gmail alias for a service.

        Pattern: base+service-agent@gmail.com
        Example: clawdtob+heygen-narrative@gmail.com
        """
        local, domain = self.base_email.split("@", 1)
        # Clean service name for email
        svc = service.replace(".", "-").replace(" ", "-").lower()[:20]
        agent_tag = agent_id.replace("_", "").replace("lead", "")[:10] if agent_id else ""
        suffix = f"{svc}-{agent_tag}" if agent_tag else svc
        return f"{local}+{suffix}@{domain}"

    def generate_password(self, length: int = 24) -> str:
        """Generate a cryptographically secure password.

        Guaranteed to have: uppercase, lowercase, digit, special char.
        """
        import secrets
        import string
        alphabet = string.ascii_letters + string.digits + "!@#$%&*_+-="
        # Ensure at least one of each class
        password = [
            secrets.choice(string.ascii_uppercase),
            secrets.choice(string.ascii_lowercase),
            secrets.choice(string.digits),
            secrets.choice("!@#$%&*_+-="),
        ]
        password += [secrets.choice(alphabet) for _ in range(length - 4)]
        # Shuffle so required chars aren't always at the start
        import random
        random.shuffle(password)
        return "".join(password)

    def generate_username(self, agent_id: str, service: str = "") -> str:
        """Generate an agent-branded username.

        Pattern: nemoclaw-{agent_short}-{random4}
        Example: nemoclaw-narrative-a3f2
        """
        agent_short = agent_id.replace("_lead", "").replace("_", "-")[:15]
        suffix = os.urandom(2).hex()
        return f"nemoclaw-{agent_short}-{suffix}"

    def provision(
        self,
        service: str,
        agent_id: str,
        include_username: bool = False,
    ) -> dict:
        """Generate and store credentials for a new service account.

        Creates email alias + password (+ optional username), stores in vault,
        returns the generated credentials.

        Args:
            service: Domain name of the service (e.g., "heygen.com").
            agent_id: Agent requesting the account.
            include_username: Generate a username (some sites need it).

        Returns:
            Dict with email, password, and optionally username.
        """
        # Check if credentials already exist
        ok, existing = self.vault.retrieve(service, agent_id)
        if ok and existing:
            logger.info(f"Credentials already exist for {service}/{agent_id}")
            return existing

        email = self.generate_email_alias(service, agent_id)
        password = self.generate_password()
        creds = {"username": email, "password": password}

        if include_username:
            username = self.generate_username(agent_id, service)
            creds["display_username"] = username

        # Store in vault
        self.vault.store(service, "username_password", creds, allowed_agents=[agent_id])
        logger.info(f"Provisioned credentials for {service}/{agent_id}: {email}")

        return creds

    def provision_oauth(self, service: str, agent_id: str) -> dict:
        """Provision Google OAuth credentials (uses existing Google account).

        For sites that support "Sign in with Google", no new credentials needed.
        Just stores the OAuth reference pointing to the base Google account.
        """
        creds = {
            "method": "google_oauth",
            "email": self.base_email,
            "service": service,
        }
        self.vault.store(service, "oauth_token", creds, allowed_agents=[agent_id])
        logger.info(f"Provisioned OAuth for {service}/{agent_id} via {self.base_email}")
        return creds


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def _run_tests():
    """Run vault tests."""
    import tempfile
    from unittest.mock import patch

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
    print("  Credential Vault Tests")
    print("=" * 60)

    # Use temp directory for tests — patch the module globals directly
    global VAULT_FILE, SALT_FILE, VAULT_DIR

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        test_vault = tmp / "vault" / "credentials.enc"
        test_salt = tmp / "vault" / ".salt"

        orig_vault = VAULT_FILE
        orig_salt = SALT_FILE
        orig_dir = VAULT_DIR
        VAULT_FILE = test_vault
        SALT_FILE = test_salt
        VAULT_DIR = tmp / "vault"
        (tmp / "vault").mkdir(parents=True, exist_ok=True)

        try:
            # Test 1: Create vault
            def test_create():
                vault = CredentialVault(vault_key="test-key-123")
                assert vault is not None
                assert len(vault.list_services()) == 0
            test("Create vault", test_create)

            # Test 2: Store credential
            def test_store():
                vault = CredentialVault(vault_key="test-key-123")
                ok = vault.store("test.com", "username_password",
                                 {"username": "user", "password": "pass123"})
                assert ok is True
            test("Store credential", test_store)

            # Test 3: Retrieve credential
            def test_retrieve():
                vault = CredentialVault(vault_key="test-key-123")
                vault.store("test.com", "username_password",
                            {"username": "user", "password": "pass123"})
                ok, cred = vault.retrieve("test.com")
                assert ok is True
                assert cred["username"] == "user"
                assert cred["password"] == "pass123"
                assert cred["type"] == "username_password"
            test("Retrieve credential", test_retrieve)

            # Test 4: Encryption at rest
            def test_encrypted():
                # Clean slate
                if test_vault.exists():
                    test_vault.unlink()
                if test_salt.exists():
                    test_salt.unlink()
                vault = CredentialVault(vault_key="test-key-enc")
                vault.store("secret.com", "api_key", {"key": "sk-12345"})
                assert test_vault.exists(), f"Vault file not created"
                raw = test_vault.read_bytes()
                assert b"sk-12345" not in raw
                assert b"secret.com" not in raw
            test("Encryption at rest", test_encrypted)

            # Test 5: Agent access control
            def test_access_control():
                vault = CredentialVault(vault_key="test-key-123")
                vault.store("restricted.com", "api_key", {"key": "abc"},
                            allowed_agents=["agent_a"])
                ok, _ = vault.retrieve("restricted.com", agent_id="agent_a")
                assert ok is True
                ok, err = vault.retrieve("restricted.com", agent_id="agent_b")
                assert ok is False
                assert "not authorized" in err.lower()
            test("Agent access control", test_access_control)

            # Test 6: Not found
            def test_not_found():
                vault = CredentialVault(vault_key="test-key-123")
                ok, err = vault.retrieve("nonexistent.com")
                assert ok is False
            test("Not found error", test_not_found)

            # Test 7: List services
            def test_list():
                vault = CredentialVault(vault_key="test-key-123")
                vault.store("a.com", "api_key", {"key": "1"})
                vault.store("b.com", "api_key", {"key": "2"})
                services = vault.list_services()
                assert "a.com" in services
                assert "b.com" in services
            test("List services", test_list)

            # Test 8: Delete
            def test_delete():
                vault = CredentialVault(vault_key="test-key-123")
                vault.store("deleteme.com", "api_key", {"key": "x"})
                assert vault.delete("deleteme.com") is True
                ok, _ = vault.retrieve("deleteme.com")
                assert ok is False
            test("Delete credential", test_delete)

            # Test 9: Key rotation
            def test_rotation():
                vault = CredentialVault(vault_key="old-key")
                vault.store("rotate.com", "api_key", {"key": "rotated"})
                assert vault.rotate_key("new-key") is True
                # Reload with new key
                vault2 = CredentialVault(vault_key="new-key")
                ok, cred = vault2.retrieve("rotate.com")
                assert ok is True
                assert cred["key"] == "rotated"
            test("Key rotation", test_rotation)

            # Test 10: TOTP generation
            def test_totp():
                vault = CredentialVault(vault_key="test-key-123")
                # Standard test secret
                vault.store("2fa.com", "totp_secret",
                            {"secret": "JBSWY3DPEHPK3PXP", "issuer": "Test"})
                ok, result = vault.generate_totp("2fa.com")
                assert ok is True
                assert len(result["code"]) == 6
                assert result["valid_for"] > 0
            test("TOTP generation", test_totp)

            # Test 11: TOTP wrong type
            def test_totp_wrong_type():
                vault = CredentialVault(vault_key="test-key-123")
                vault.store("nottotp.com", "api_key", {"key": "abc"})
                ok, err = vault.generate_totp("nottotp.com")
                assert ok is False
                assert "not a totp" in err.lower()
            test("TOTP wrong type error", test_totp_wrong_type)

            # Test 12: Failed attempts lockout
            def test_lockout():
                vault = CredentialVault(vault_key="test-key-123")
                vault.max_failed_attempts = 3
                vault.store("locked.com", "api_key", {"key": "x"},
                            allowed_agents=["good_agent"])
                for _ in range(3):
                    vault.retrieve("locked.com", agent_id="bad_agent")
                ok, err = vault.retrieve("locked.com", agent_id="bad_agent")
                assert ok is False
                assert "locked out" in err.lower()
            test("Failed attempts lockout", test_lockout)

            # Test 13: Vault file permissions
            def test_permissions():
                if test_vault.exists():
                    test_vault.unlink()
                if test_salt.exists():
                    test_salt.unlink()
                vault = CredentialVault(vault_key="test-key-perm")
                vault.store("perm.com", "api_key", {"key": "x"})
                assert test_vault.exists(), f"Vault file not created"
                mode = oct(os.stat(str(test_vault)).st_mode)[-3:]
                assert mode == "600", f"Expected 600, got {mode}"
            test("Vault file permissions (600)", test_permissions)

            # Test 14: Persistence across instances
            def test_persistence():
                v1 = CredentialVault(vault_key="persist-key")
                v1.store("persist.com", "api_key", {"key": "persist_val"})
                v2 = CredentialVault(vault_key="persist-key")
                ok, cred = v2.retrieve("persist.com")
                assert ok is True
                assert cred["key"] == "persist_val"
            test("Persistence across instances", test_persistence)

        finally:
            VAULT_FILE = orig_vault
            SALT_FILE = orig_salt
            VAULT_DIR = orig_dir

    print()
    print(f"  {'=' * 50}")
    print(f"  Vault Tests: {'PASS' if failed == 0 else 'FAIL'}")
    print(f"  Passed: {passed}/{total}")
    if failed > 0:
        print(f"  Failed: {failed}/{total}")
    print(f"  {'=' * 50}")

    return failed == 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if "--test" in sys.argv:
        success = _run_tests()
        sys.exit(0 if success else 1)
    elif "--list" in sys.argv:
        vault = CredentialVault()
        services = vault.list_services()
        if services:
            print("Stored credentials:")
            for s in services:
                print(f"  - {s}")
        else:
            print("No credentials stored.")
    elif "--store" in sys.argv:
        idx = sys.argv.index("--store")
        if idx + 2 >= len(sys.argv):
            print("Usage: --store SERVICE TYPE")
            sys.exit(1)
        service = sys.argv[idx + 1]
        cred_type = sys.argv[idx + 2]
        vault = CredentialVault()
        data = {}
        if cred_type == "username_password":
            data["username"] = input("Username: ")
            data["password"] = getpass.getpass("Password: ")
        elif cred_type == "api_key":
            data["key"] = getpass.getpass("API Key: ")
        elif cred_type == "totp_secret":
            data["secret"] = getpass.getpass("TOTP Secret: ")
            data["issuer"] = input("Issuer: ")
        else:
            print(f"Unknown type: {cred_type}")
            sys.exit(1)
        vault.store(service, cred_type, data)
        print(f"✅ Stored {cred_type} for {service}")
    elif "--retrieve" in sys.argv:
        idx = sys.argv.index("--retrieve")
        if idx + 1 >= len(sys.argv):
            print("Usage: --retrieve SERVICE")
            sys.exit(1)
        service = sys.argv[idx + 1]
        vault = CredentialVault()
        ok, cred = vault.retrieve(service)
        if ok:
            print(f"✅ {service}: type={cred.get('type')}, fields={[k for k in cred if k != 'type']}")
        else:
            print(f"❌ {cred}")
    else:
        print("Usage: credential_vault.py [--test | --list | --store SERVICE TYPE | --retrieve SERVICE]")
