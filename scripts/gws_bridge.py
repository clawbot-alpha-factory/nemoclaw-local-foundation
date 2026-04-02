#!/usr/bin/env python3
"""
NemoClaw ↔ Google Workspace CLI Bridge (gws_bridge.py)
Wraps the `gws` CLI binary for Gmail, Drive, Sheets, Calendar, Docs.

Service account auth — no browser needed for any Google service.
Returns NemoClaw-standard tuples: (success: bool, data_or_error).

Usage:
    from gws_bridge import GWSBridge
    gws = GWSBridge(agent_id="growth_revenue_lead")
    ok, result = gws.gmail_search("is:unread")

    python3 scripts/gws_bridge.py --test
"""

import json
import logging
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

REPO = Path(__file__).resolve().parent.parent
LOG_DIR = Path.home() / ".nemoclaw" / "integrations"
ACTION_LOG = LOG_DIR / "gws-actions.jsonl"

logger = logging.getLogger("nemoclaw.gws")


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

def _load_gws_config() -> dict:
    """Load google_workspace section from browser-autonomy.yaml."""
    config_path = REPO / "config" / "browser-autonomy.yaml"
    if config_path.exists():
        try:
            import yaml
            with open(config_path) as f:
                data = yaml.safe_load(f)
            return data.get("autonomy", {}).get("gws", {})
        except Exception:
            pass
    return {}


# ---------------------------------------------------------------------------
# GWSBridge
# ---------------------------------------------------------------------------

class GWSBridge:
    """NemoClaw bridge for Google Workspace CLI (gws).
    Covers Gmail, Drive, Sheets, Calendar, Docs, Chat, Admin — no browser needed."""

    def __init__(self, agent_id: str = None, credentials_file: str = None):
        self.agent_id = agent_id
        self.config = _load_gws_config()

        # Resolve gws binary
        self.gws_bin = shutil.which("gws")
        if not self.gws_bin:
            logger.warning("gws CLI not found in PATH. Install: npm install -g @googleworkspace/cli")

        # Auth: service account or OAuth credentials
        self.credentials_file = credentials_file or self.config.get("credentials_file")
        if self.credentials_file:
            self.credentials_file = os.path.expanduser(self.credentials_file)

        self.timeout = 30
        LOG_DIR.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------

    def _log_action(self, action: str, params: dict, success: bool,
                    result=None, error: str = None):
        """Append action to JSONL log."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": "gws",
            "agent_id": self.agent_id,
            "action": action,
            "params": {k: str(v)[:200] for k, v in params.items()},
            "success": success,
        }
        if error:
            entry["error"] = str(error)[:500]
        if result and isinstance(result, dict):
            entry["result_keys"] = list(result.keys())[:10]
        try:
            with open(ACTION_LOG, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass

    def _run(self, args: list, timeout: int = None) -> tuple:
        """Execute gws command and parse JSON output. Returns (success, data_or_error)."""
        if not self.gws_bin:
            return (False, "gws CLI not installed. Run: npm install -g @googleworkspace/cli")

        # Helper commands (prefixed with +) may not support --output json
        is_helper = any(a.startswith("+") for a in args)
        cmd = [self.gws_bin] + args
        if not is_helper:
            cmd += ["--output", "json"]

        env = os.environ.copy()
        if self.credentials_file and os.path.exists(self.credentials_file):
            env["GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE"] = self.credentials_file

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout or self.timeout,
                env=env,
            )

            if proc.returncode != 0:
                err = proc.stderr.strip() or proc.stdout.strip() or f"Exit code {proc.returncode}"
                return (False, err[:500])

            output = proc.stdout.strip()
            if not output:
                return (True, {})

            # Try JSON parse
            try:
                data = json.loads(output)
                return (True, data)
            except json.JSONDecodeError:
                # NDJSON (multiple lines)
                lines = output.split("\n")
                records = []
                for line in lines:
                    line = line.strip()
                    if line:
                        try:
                            records.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
                if records:
                    return (True, records)
                # Plain text output
                return (True, {"text": output})

        except subprocess.TimeoutExpired:
            return (False, f"Command timed out after {timeout or self.timeout}s")
        except FileNotFoundError:
            return (False, "gws binary not found")
        except Exception as e:
            return (False, str(e))

    def is_installed(self) -> bool:
        """Check if gws CLI is available."""
        return self.gws_bin is not None

    def health(self) -> tuple:
        """Check gws CLI health."""
        if not self.gws_bin:
            return (False, "gws CLI not installed")
        try:
            proc = subprocess.run(
                [self.gws_bin, "--version"],
                capture_output=True, text=True, timeout=5,
            )
            if proc.returncode == 0:
                return (True, {"version": proc.stdout.strip()})
            return (False, proc.stderr.strip())
        except Exception as e:
            return (False, str(e))

    # -------------------------------------------------------------------
    # Gmail
    # -------------------------------------------------------------------

    def gmail_send(self, to: str, subject: str, body: str,
                   cc: str = None, bcc: str = None) -> tuple:
        """Send an email via Gmail."""
        args = ["gmail", "+send", "--to", to, "--subject", subject, "--body", body]
        if cc:
            args.extend(["--cc", cc])
        if bcc:
            args.extend(["--bcc", bcc])
        ok, result = self._run(args)
        self._log_action("gmail_send", {"to": to, "subject": subject}, ok, result,
                         result if not ok else None)
        return (ok, result)

    def gmail_search(self, query: str, max_results: int = 20) -> tuple:
        """Search Gmail messages."""
        args = ["gmail", "users.messages", "list",
                "--params", json.dumps({"q": query, "maxResults": max_results})]
        ok, result = self._run(args)
        self._log_action("gmail_search", {"query": query}, ok, result,
                         result if not ok else None)
        return (ok, result)

    def gmail_read(self, message_id: str) -> tuple:
        """Read a specific Gmail message."""
        args = ["gmail", "users.messages", "get", "--id", message_id]
        ok, result = self._run(args)
        self._log_action("gmail_read", {"message_id": message_id}, ok, result,
                         result if not ok else None)
        return (ok, result)

    def gmail_reply(self, message_id: str, body: str) -> tuple:
        """Reply to a Gmail message."""
        args = ["gmail", "+reply", "--message-id", message_id, "--body", body]
        ok, result = self._run(args)
        self._log_action("gmail_reply", {"message_id": message_id}, ok, result,
                         result if not ok else None)
        return (ok, result)

    def gmail_labels(self) -> tuple:
        """List Gmail labels."""
        ok, result = self._run(["gmail", "users.labels", "list"])
        self._log_action("gmail_labels", {}, ok, result, result if not ok else None)
        return (ok, result)

    # -------------------------------------------------------------------
    # Drive
    # -------------------------------------------------------------------

    def drive_list(self, query: str = None, page_size: int = 20) -> tuple:
        """List Drive files."""
        params = {"pageSize": page_size}
        if query:
            params["q"] = query
        args = ["drive", "files", "list", "--params", json.dumps(params)]
        ok, result = self._run(args)
        self._log_action("drive_list", {"query": query or ""}, ok, result,
                         result if not ok else None)
        return (ok, result)

    def drive_upload(self, file_path: str, folder_id: str = None,
                     name: str = None) -> tuple:
        """Upload file to Drive."""
        if not os.path.exists(file_path):
            return (False, f"File not found: {file_path}")
        args = ["drive", "files", "create", "--upload-file", file_path]
        if name:
            args.extend(["--params", json.dumps({"name": name})])
        if folder_id:
            args.extend(["--params", json.dumps({"parents": [folder_id]})])
        ok, result = self._run(args, timeout=120)
        self._log_action("drive_upload", {"file": file_path}, ok, result,
                         result if not ok else None)
        return (ok, result)

    def drive_download(self, file_id: str, dest_path: str) -> tuple:
        """Download file from Drive."""
        args = ["drive", "files", "get", "--id", file_id,
                "--params", json.dumps({"alt": "media"})]
        ok, result = self._run(args, timeout=120)
        if ok and isinstance(result, dict) and "text" in result:
            try:
                Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
                with open(dest_path, "w") as f:
                    f.write(result["text"])
                return (True, {"path": dest_path})
            except Exception as e:
                return (False, str(e))
        self._log_action("drive_download", {"file_id": file_id}, ok, result,
                         result if not ok else None)
        return (ok, result)

    def drive_share(self, file_id: str, email: str, role: str = "reader") -> tuple:
        """Share a Drive file."""
        args = ["drive", "permissions", "create", "--file-id", file_id,
                "--params", json.dumps({
                    "type": "user", "role": role, "emailAddress": email
                })]
        ok, result = self._run(args)
        self._log_action("drive_share", {"file_id": file_id, "email": email}, ok, result,
                         result if not ok else None)
        return (ok, result)

    # -------------------------------------------------------------------
    # Sheets
    # -------------------------------------------------------------------

    def sheets_read(self, spreadsheet_id: str, range_: str) -> tuple:
        """Read values from a Google Sheet."""
        args = ["sheets", "+read", "--spreadsheet-id", spreadsheet_id, "--range", range_]
        ok, result = self._run(args)
        self._log_action("sheets_read", {"spreadsheet_id": spreadsheet_id, "range": range_},
                         ok, result, result if not ok else None)
        return (ok, result)

    def sheets_append(self, spreadsheet_id: str, range_: str, values: list) -> tuple:
        """Append rows to a Google Sheet."""
        args = ["sheets", "+append", "--spreadsheet-id", spreadsheet_id,
                "--range", range_, "--values", json.dumps(values)]
        ok, result = self._run(args)
        self._log_action("sheets_append", {"spreadsheet_id": spreadsheet_id},
                         ok, result, result if not ok else None)
        return (ok, result)

    def sheets_update(self, spreadsheet_id: str, range_: str, values: list) -> tuple:
        """Update values in a Google Sheet."""
        args = ["sheets", "spreadsheets.values", "update",
                "--spreadsheet-id", spreadsheet_id,
                "--range", range_,
                "--params", json.dumps({
                    "valueInputOption": "USER_ENTERED",
                    "values": values,
                })]
        ok, result = self._run(args)
        self._log_action("sheets_update", {"spreadsheet_id": spreadsheet_id},
                         ok, result, result if not ok else None)
        return (ok, result)

    # -------------------------------------------------------------------
    # Calendar
    # -------------------------------------------------------------------

    def calendar_agenda(self, days: int = 7) -> tuple:
        """Get upcoming calendar events."""
        args = ["calendar", "+agenda", "--days", str(days)]
        ok, result = self._run(args)
        self._log_action("calendar_agenda", {"days": days}, ok, result,
                         result if not ok else None)
        return (ok, result)

    def calendar_create_event(self, summary: str, start: str, end: str,
                              attendees: list = None,
                              description: str = None) -> tuple:
        """Create a calendar event."""
        args = ["calendar", "+insert", "--summary", summary,
                "--start", start, "--end", end]
        if description:
            args.extend(["--description", description])
        if attendees:
            for email in attendees:
                args.extend(["--attendee", email])
        ok, result = self._run(args)
        self._log_action("calendar_create_event", {"summary": summary}, ok, result,
                         result if not ok else None)
        return (ok, result)

    # -------------------------------------------------------------------
    # Docs
    # -------------------------------------------------------------------

    def docs_create(self, title: str) -> tuple:
        """Create a new Google Doc."""
        args = ["docs", "documents", "create",
                "--params", json.dumps({"title": title})]
        ok, result = self._run(args)
        self._log_action("docs_create", {"title": title}, ok, result,
                         result if not ok else None)
        return (ok, result)

    def docs_read(self, document_id: str) -> tuple:
        """Read a Google Doc."""
        args = ["docs", "documents", "get", "--document-id", document_id]
        ok, result = self._run(args)
        self._log_action("docs_read", {"document_id": document_id}, ok, result,
                         result if not ok else None)
        return (ok, result)

    # -------------------------------------------------------------------
    # Generic
    # -------------------------------------------------------------------

    def run_raw(self, service: str, *args) -> tuple:
        """Run an arbitrary gws command. For services not covered by helpers."""
        cmd_args = [service] + list(args)
        ok, result = self._run(cmd_args)
        self._log_action(f"raw:{service}", {"args": str(args)[:200]}, ok, result,
                         result if not ok else None)
        return (ok, result)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def _run_tests():
    """Run bridge tests with mocked subprocess."""
    from unittest.mock import patch, MagicMock

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
    print("  GWS Bridge Tests")
    print("=" * 60)

    def mock_proc(returncode=0, stdout="", stderr=""):
        proc = MagicMock()
        proc.returncode = returncode
        proc.stdout = stdout
        proc.stderr = stderr
        return proc

    # Test 1: Constructor
    def test_constructor():
        bridge = GWSBridge(agent_id="test")
        assert bridge.agent_id == "test"
    test("Constructor", test_constructor)

    # Test 2: Health check
    def test_health():
        bridge = GWSBridge()
        if bridge.gws_bin:
            ok, result = bridge.health()
            assert ok is True
            assert "version" in result
        else:
            ok, result = bridge.health()
            assert ok is False
    test("Health check", test_health)

    # Test 3: Gmail search (mocked)
    def test_gmail_search():
        bridge = GWSBridge(agent_id="test")
        bridge.gws_bin = "/usr/bin/true"
        with patch("subprocess.run", return_value=mock_proc(
            stdout='{"messages": [{"id": "msg1"}]}'
        )):
            ok, result = bridge.gmail_search("is:unread")
            assert ok is True
            assert "messages" in result
    test("Gmail search (mocked)", test_gmail_search)

    # Test 4: Gmail send (mocked)
    def test_gmail_send():
        bridge = GWSBridge(agent_id="test")
        bridge.gws_bin = "/usr/bin/true"
        with patch("subprocess.run", return_value=mock_proc(
            stdout='{"id": "msg_new"}'
        )):
            ok, result = bridge.gmail_send("user@test.com", "Test", "Hello")
            assert ok is True
    test("Gmail send (mocked)", test_gmail_send)

    # Test 5: Drive list (mocked)
    def test_drive_list():
        bridge = GWSBridge(agent_id="test")
        bridge.gws_bin = "/usr/bin/true"
        with patch("subprocess.run", return_value=mock_proc(
            stdout='{"files": [{"id": "f1", "name": "doc.pdf"}]}'
        )):
            ok, result = bridge.drive_list()
            assert ok is True
            assert "files" in result
    test("Drive list (mocked)", test_drive_list)

    # Test 6: Drive upload file not found
    def test_drive_upload_not_found():
        bridge = GWSBridge(agent_id="test")
        ok, result = bridge.drive_upload("/nonexistent/file.pdf")
        assert ok is False
        assert "not found" in result.lower()
    test("Drive upload file not found", test_drive_upload_not_found)

    # Test 7: Sheets read (mocked)
    def test_sheets_read():
        bridge = GWSBridge(agent_id="test")
        bridge.gws_bin = "/usr/bin/true"
        with patch("subprocess.run", return_value=mock_proc(
            stdout='{"values": [["A", "B"], ["1", "2"]]}'
        )):
            ok, result = bridge.sheets_read("spreadsheet_123", "Sheet1!A:B")
            assert ok is True
    test("Sheets read (mocked)", test_sheets_read)

    # Test 8: Calendar agenda (mocked)
    def test_calendar_agenda():
        bridge = GWSBridge(agent_id="test")
        bridge.gws_bin = "/usr/bin/true"
        with patch("subprocess.run", return_value=mock_proc(
            stdout='{"items": [{"summary": "Meeting"}]}'
        )):
            ok, result = bridge.calendar_agenda(7)
            assert ok is True
    test("Calendar agenda (mocked)", test_calendar_agenda)

    # Test 9: Command timeout
    def test_timeout():
        bridge = GWSBridge(agent_id="test")
        bridge.gws_bin = "/usr/bin/true"
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("gws", 30)):
            ok, result = bridge._run(["test"])
            assert ok is False
            assert "timed out" in result.lower()
    test("Command timeout", test_timeout)

    # Test 10: Command error
    def test_cmd_error():
        bridge = GWSBridge(agent_id="test")
        bridge.gws_bin = "/usr/bin/true"
        with patch("subprocess.run", return_value=mock_proc(
            returncode=1, stderr="Auth failed"
        )):
            ok, result = bridge._run(["gmail", "list"])
            assert ok is False
            assert "auth" in result.lower()
    test("Command error handling", test_cmd_error)

    # Test 11: Not installed
    def test_not_installed():
        bridge = GWSBridge(agent_id="test")
        bridge.gws_bin = None
        ok, result = bridge._run(["test"])
        assert ok is False
        assert "not installed" in result.lower()
    test("Not installed error", test_not_installed)

    # Test 12: NDJSON parsing
    def test_ndjson():
        bridge = GWSBridge(agent_id="test")
        bridge.gws_bin = "/usr/bin/true"
        ndjson = '{"id":"1"}\n{"id":"2"}\n{"id":"3"}'
        with patch("subprocess.run", return_value=mock_proc(stdout=ndjson)):
            ok, result = bridge._run(["test"])
            assert ok is True
            assert len(result) == 3
    test("NDJSON parsing", test_ndjson)

    # Test 13: Action log
    def test_action_log():
        bridge = GWSBridge(agent_id="test")
        bridge._log_action("test", {"key": "val"}, True)
        assert ACTION_LOG.exists()
    test("Action log file created", test_action_log)

    # Test 14: Raw command
    def test_raw():
        bridge = GWSBridge(agent_id="test")
        bridge.gws_bin = "/usr/bin/true"
        with patch("subprocess.run", return_value=mock_proc(stdout='{"ok":true}')):
            ok, result = bridge.run_raw("chat", "spaces", "list")
            assert ok is True
    test("Raw command passthrough", test_raw)

    # Test 15: is_installed
    def test_is_installed():
        bridge = GWSBridge()
        # gws was installed earlier
        assert isinstance(bridge.is_installed(), bool)
    test("is_installed returns bool", test_is_installed)

    print()
    print(f"  {'=' * 50}")
    print(f"  GWS Bridge Tests: {'PASS' if failed == 0 else 'FAIL'}")
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
        bridge = GWSBridge()
        ok, result = bridge.health()
        if ok:
            print(f"✅ gws CLI available: {result}")
        else:
            print(f"❌ gws CLI not available: {result}")
        sys.exit(0 if ok else 1)
