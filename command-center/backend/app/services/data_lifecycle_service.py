"""
NemoClaw Execution Engine — Data Lifecycle Service (E-12)

30-day archive, log rotation, stale data cleanup.
Keeps the system lean and fast.

NEW FILE: command-center/backend/app/services/data_lifecycle_service.py
"""
from __future__ import annotations
import json, logging, os, shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger("cc.data_lifecycle")


class DataLifecycleService:
    """
    Manages data retention, archiving, and cleanup.

    - Archives data older than 30 days
    - Rotates log files when > 10MB
    - Cleans stale checkpoints, orphan outputs
    """

    ARCHIVE_DAYS = 30
    MAX_LOG_SIZE_MB = 10
    NEMOCLAW_DIR = Path.home() / ".nemoclaw"
    ARCHIVE_DIR = Path.home() / ".nemoclaw" / "archive"

    def __init__(self):
        self.ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        self._last_run: str | None = None
        logger.info("DataLifecycleService initialized")

    def run_maintenance(self) -> dict[str, Any]:
        """Run full maintenance cycle."""
        results: dict[str, Any] = {"timestamp": datetime.now(timezone.utc).isoformat()}

        # 1. Archive old JSON state files
        archived = self._archive_old_data()
        results["archived_files"] = archived

        # 2. Rotate large log files
        rotated = self._rotate_logs()
        results["rotated_logs"] = rotated

        # 3. Clean stale skill outputs
        cleaned = self._clean_stale_outputs()
        results["cleaned_outputs"] = cleaned

        # 4. Trim large state files
        trimmed = self._trim_state_files()
        results["trimmed_files"] = trimmed

        self._last_run = results["timestamp"]
        logger.info("Maintenance complete: %d archived, %d rotated, %d cleaned, %d trimmed",
                    archived, rotated, cleaned, trimmed)
        return results

    def _archive_old_data(self) -> int:
        """Move files older than 30 days to archive."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.ARCHIVE_DAYS)
        archived = 0
        archive_targets = ["event-log.json", "bridge-calls.json", "chain-executions.json"]

        for target in archive_targets:
            src = self.NEMOCLAW_DIR / target
            if src.exists():
                try:
                    stat = src.stat()
                    mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
                    if mtime < cutoff:
                        dest = self.ARCHIVE_DIR / f"{target}.{mtime.strftime('%Y%m%d')}"
                        shutil.copy2(str(src), str(dest))
                        # Safe write: verify archive → rename → new file
                        if dest.exists() and dest.stat().st_size > 0:
                            src.write_text("[]")
                        else:
                            logger.warning("Archive copy failed verification for %s", target)
                        archived += 1
                except Exception as e:
                    logger.warning("Archive failed for %s: %s", target, e)
        return archived

    def _rotate_logs(self) -> int:
        """Rotate log files larger than threshold."""
        rotated = 0
        log_files = list(self.NEMOCLAW_DIR.glob("*.json"))
        for f in log_files:
            try:
                if f.stat().st_size > self.MAX_LOG_SIZE_MB * 1024 * 1024:
                    # Trim to last 1000 entries
                    data = json.loads(f.read_text())
                    if isinstance(data, list) and len(data) > 1000:
                        f.write_text(json.dumps(data[-1000:], indent=2, default=str))
                        rotated += 1
                    elif isinstance(data, dict):
                        # For dict-type files, just keep as-is (they're bounded)
                        pass
            except Exception:
                pass
        return rotated

    def _clean_stale_outputs(self) -> int:
        """Remove skill outputs older than 30 days."""
        cleaned = 0
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.ARCHIVE_DAYS)
        skills_dir = Path.home() / "nemoclaw-local-foundation" / "skills"
        if not skills_dir.exists():
            return 0

        for output_dir in skills_dir.glob("*/outputs"):
            for f in output_dir.glob("*.md"):
                try:
                    mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
                    if mtime < cutoff:
                        f.unlink()
                        # Also remove envelope
                        envelope = f.with_suffix("").with_suffix("_envelope.json")
                        if envelope.exists():
                            envelope.unlink()
                        cleaned += 1
                except Exception:
                    pass
        return cleaned

    def _trim_state_files(self) -> int:
        """Trim state files that grow unbounded."""
        trimmed = 0
        trim_targets = {
            "global-state.json": 5000,  # max entries per collection
            "failure-log.json": 200,
            "metrics-history.json": 365,
        }
        for filename, max_entries in trim_targets.items():
            fp = self.NEMOCLAW_DIR / filename
            if not fp.exists():
                continue
            try:
                data = json.loads(fp.read_text())
                changed = False
                if isinstance(data, list) and len(data) > max_entries:
                    data = data[-max_entries:]
                    changed = True
                elif isinstance(data, dict):
                    for key in data:
                        if isinstance(data[key], list) and len(data[key]) > max_entries:
                            data[key] = data[key][-max_entries:]
                            changed = True
                if changed:
                    fp.write_text(json.dumps(data, indent=2, default=str))
                    trimmed += 1
            except Exception:
                pass
        return trimmed

    def get_disk_usage(self) -> dict[str, Any]:
        """Get disk usage for NemoClaw data."""
        total = 0
        file_sizes: dict[str, float] = {}
        for f in self.NEMOCLAW_DIR.glob("*.json"):
            size = f.stat().st_size
            total += size
            file_sizes[f.name] = round(size / 1024, 1)
        return {
            "total_kb": round(total / 1024, 1),
            "total_mb": round(total / (1024 * 1024), 2),
            "files": dict(sorted(file_sizes.items(), key=lambda x: x[1], reverse=True)[:20]),
            "archive_size_kb": round(sum(f.stat().st_size for f in self.ARCHIVE_DIR.glob("*")) / 1024, 1)
            if self.ARCHIVE_DIR.exists() else 0,
        }

    def get_stats(self) -> dict[str, Any]:
        return {"last_run": self._last_run, "disk_usage": self.get_disk_usage()}
