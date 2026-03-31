"""
NemoClaw Execution Engine — SkillMarketplaceService (P-8)

Discover, preview, install, update, and uninstall skills from GitHub repos.
Validates schema + security scan before install. Tracks provenance with checksums.

Atomic install via temp dir. Soft-delete on uninstall. Discovery cache (10min TTL).
Version comparison with semver for update detection.

NEW FILE: command-center/backend/app/services/skill_marketplace_service.py
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml

logger = logging.getLogger("cc.marketplace")

# ── Constants ───────────────────────────────────────────────────────
DISCOVERY_CACHE_TTL = 600  # 10 minutes
DANGEROUS_PATTERNS = [
    r"\bos\.system\b",
    r"\bsubprocess\b",
    r"\beval\s*\(",
    r"\bexec\s*\(",
    r"\b__import__\s*\(",
    r"\bos\.popen\b",
    r"\bos\.exec",
    r"\bos\.spawn",
]
REQUIRED_YAML_FIELDS = {"name", "version", "description"}
SCHEMA_VERSION_REQUIRED = 2


class MarketplaceEntry:
    """Tracks a marketplace skill."""

    def __init__(
        self,
        skill_id: str,
        source_repo: str = "",
        source_path: str = "",
        version: str = "",
        status: str = "available",
        installed_at: str = "",
        validation_result: dict[str, Any] | None = None,
        checksum: str = "",
    ):
        self.skill_id = skill_id
        self.source_repo = source_repo
        self.source_path = source_path
        self.version = version
        self.status = status
        self.installed_at = installed_at
        self.validation_result = validation_result or {}
        self.checksum = checksum

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "source_repo": self.source_repo,
            "source_path": self.source_path,
            "version": self.version,
            "status": self.status,
            "installed_at": self.installed_at,
            "validation_result": self.validation_result,
            "checksum": self.checksum,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> MarketplaceEntry:
        return cls(**{k: d.get(k, "") for k in [
            "skill_id", "source_repo", "source_path", "version",
            "status", "installed_at", "checksum",
        ]}, validation_result=d.get("validation_result", {}))


class SkillMarketplaceService:
    """
    Discover, install, update, and uninstall skills from GitHub repos.

    - Discover: scan repos for skill directories (skill.yaml + run.py)
    - Validate: schema check + security scan before install
    - Install: atomic via temp dir, checksum tracked
    - Update: semver comparison, backup + reinstall
    - Uninstall: soft-delete (rename to .disabled-{id})
    """

    def __init__(self, repo_root: Path, skill_service=None):
        self._repo_root = Path(repo_root)
        self._skills_dir = self._repo_root / "skills"
        self._skill_service = skill_service
        self._persist_dir = Path.home() / ".nemoclaw"
        self._persist_dir.mkdir(parents=True, exist_ok=True)
        self._registry_path = self._persist_dir / "marketplace-registry.json"

        self._sources: list[dict[str, str]] = []
        self._entries: dict[str, MarketplaceEntry] = {}
        self._discover_cache: list[dict[str, Any]] = []
        self._discover_cache_time: float = 0

        self._load()
        logger.info(
            "SkillMarketplaceService initialized (%d sources, %d entries)",
            len(self._sources), len(self._entries),
        )

    # ── Persistence ─────────────────────────────────────────────────

    def _load(self) -> None:
        if not self._registry_path.exists():
            return
        try:
            data = json.loads(self._registry_path.read_text())
            self._sources = data.get("sources", [])
            for k, v in data.get("entries", {}).items():
                self._entries[k] = MarketplaceEntry.from_dict(v)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load marketplace registry: %s", e)

    def _save(self) -> None:
        try:
            self._registry_path.write_text(json.dumps({
                "sources": self._sources,
                "entries": {k: v.to_dict() for k, v in self._entries.items()},
                "saved_at": datetime.now(timezone.utc).isoformat(),
            }, indent=2, default=str))
        except OSError as e:
            logger.error("Failed to save marketplace registry: %s", e)

    # ── Sources ─────────────────────────────────────────────────────

    def get_sources(self) -> list[dict[str, str]]:
        return list(self._sources)

    def add_source(self, url: str, name: str = "") -> dict[str, Any]:
        """Add a GitHub repo as a skill source."""
        url = url.rstrip("/")
        if not name:
            name = url.split("/")[-1]

        # Check duplicate
        for s in self._sources:
            if s["url"] == url:
                return {"status": "exists", "source": s}

        source = {"url": url, "name": name, "added_at": datetime.now(timezone.utc).isoformat()}
        self._sources.append(source)
        self._save()
        logger.info("Added marketplace source: %s (%s)", name, url)
        return {"status": "added", "source": source}

    def remove_source(self, url: str) -> bool:
        before = len(self._sources)
        self._sources = [s for s in self._sources if s["url"] != url]
        if len(self._sources) < before:
            self._save()
            return True
        return False

    # ── Discovery ───────────────────────────────────────────────────

    def discover(self, force: bool = False) -> list[dict[str, Any]]:
        """Scan all source repos for available skills. Cached for 10 minutes."""
        now = time.time()
        if not force and self._discover_cache and (now - self._discover_cache_time) < DISCOVERY_CACHE_TTL:
            return self._discover_cache

        results: list[dict[str, Any]] = []
        for source in self._sources:
            try:
                skills = self._scan_repo(source["url"])
                for skill in skills:
                    skill["source_name"] = source["name"]
                    skill["source_url"] = source["url"]
                    # Check install status
                    sid = skill.get("skill_id", "")
                    if sid in self._entries:
                        entry = self._entries[sid]
                        skill["status"] = entry.status
                        skill["installed_version"] = entry.version
                    else:
                        skill["status"] = "available"
                results.extend(skills)
            except Exception as e:
                logger.warning("Failed to scan source %s: %s", source["url"], e)
                results.append({
                    "source_name": source["name"],
                    "source_url": source["url"],
                    "error": str(e),
                })

        self._discover_cache = results
        self._discover_cache_time = now
        return results

    def _scan_repo(self, repo_url: str) -> list[dict[str, Any]]:
        """Clone repo to temp dir and scan for skills (dirs with skill.yaml + run.py)."""
        tmp_dir = Path(f"/tmp/marketplace-scan-{uuid4().hex[:8]}")
        try:
            # Shallow clone
            result = subprocess.run(
                ["git", "clone", "--depth", "1", repo_url, str(tmp_dir)],
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode != 0:
                raise RuntimeError(f"Git clone failed: {result.stderr[:200]}")

            # Scan for skill directories
            skills: list[dict[str, Any]] = []
            for skill_dir in sorted(tmp_dir.iterdir()):
                if not skill_dir.is_dir():
                    continue
                yaml_path = skill_dir / "skill.yaml"
                run_path = skill_dir / "run.py"
                if yaml_path.exists() and run_path.exists():
                    try:
                        meta = yaml.safe_load(yaml_path.read_text())
                        skills.append({
                            "skill_id": meta.get("name", skill_dir.name),
                            "display_name": meta.get("display_name", meta.get("name", "")),
                            "version": meta.get("version", "0.0.0"),
                            "description": meta.get("description", ""),
                            "author": meta.get("author", ""),
                            "tier": meta.get("tier", ""),
                            "source_path": skill_dir.name,
                        })
                    except Exception as e:
                        logger.warning("Failed to parse %s: %s", yaml_path, e)

            # Also check skills/ subdirectory (common repo layout)
            skills_subdir = tmp_dir / "skills"
            if skills_subdir.is_dir():
                for skill_dir in sorted(skills_subdir.iterdir()):
                    if not skill_dir.is_dir():
                        continue
                    yaml_path = skill_dir / "skill.yaml"
                    run_path = skill_dir / "run.py"
                    if yaml_path.exists() and run_path.exists():
                        try:
                            meta = yaml.safe_load(yaml_path.read_text())
                            skills.append({
                                "skill_id": meta.get("name", skill_dir.name),
                                "display_name": meta.get("display_name", meta.get("name", "")),
                                "version": meta.get("version", "0.0.0"),
                                "description": meta.get("description", ""),
                                "author": meta.get("author", ""),
                                "tier": meta.get("tier", ""),
                                "source_path": f"skills/{skill_dir.name}",
                            })
                        except Exception as e:
                            logger.warning("Failed to parse %s: %s", yaml_path, e)

            return skills
        finally:
            if tmp_dir.exists():
                shutil.rmtree(tmp_dir, ignore_errors=True)

    # ── Preview ─────────────────────────────────────────────────────

    def preview(self, skill_id: str) -> dict[str, Any]:
        """Show skill metadata from discovery cache without installing."""
        for skill in self._discover_cache:
            if skill.get("skill_id") == skill_id:
                return skill
        return {"error": f"Skill '{skill_id}' not found in discovery cache. Run discover first."}

    # ── Validation ──────────────────────────────────────────────────

    def _validate_skill(self, skill_dir: Path) -> dict[str, Any]:
        """Validate schema + security. Returns validation result."""
        issues: list[str] = []
        warnings: list[str] = []

        yaml_path = skill_dir / "skill.yaml"
        run_path = skill_dir / "run.py"

        # Check files exist
        if not yaml_path.exists():
            issues.append("Missing skill.yaml")
        if not run_path.exists():
            issues.append("Missing run.py")
        if issues:
            return {"valid": False, "issues": issues, "warnings": warnings}

        # Parse YAML
        try:
            meta = yaml.safe_load(yaml_path.read_text())
        except Exception as e:
            issues.append(f"Invalid YAML: {e}")
            return {"valid": False, "issues": issues, "warnings": warnings}

        # Required fields
        for field in REQUIRED_YAML_FIELDS:
            if field not in meta:
                issues.append(f"Missing required field: {field}")

        # Schema version
        sv = meta.get("schema_version")
        if sv and sv != SCHEMA_VERSION_REQUIRED:
            warnings.append(f"schema_version is {sv}, expected {SCHEMA_VERSION_REQUIRED}")

        # Compile check
        try:
            code = run_path.read_text()
            compile(code, str(run_path), "exec")
        except SyntaxError as e:
            issues.append(f"run.py has syntax error: {e}")

        # Security scan
        if run_path.exists():
            code = run_path.read_text()
            for pattern in DANGEROUS_PATTERNS:
                matches = re.findall(pattern, code)
                if matches:
                    warnings.append(f"Potentially dangerous pattern: {pattern} ({len(matches)} occurrences)")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "name": meta.get("name", ""),
            "version": meta.get("version", ""),
        }

    def _compute_checksum(self, skill_dir: Path) -> str:
        """SHA256 hash of all files in skill directory recursively."""
        h = hashlib.sha256()
        for fpath in sorted(skill_dir.rglob("*")):
            if fpath.is_file() and not fpath.name.startswith("."):
                h.update(fpath.read_bytes())
        return h.hexdigest()[:16]

    # ── Install ─────────────────────────────────────────────────────

    def install(self, skill_id: str) -> dict[str, Any]:
        """Install a skill from discovery cache. Atomic via temp dir."""
        # Find in cache
        skill_info = None
        for s in self._discover_cache:
            if s.get("skill_id") == skill_id:
                skill_info = s
                break

        if not skill_info:
            return {"status": "error", "detail": f"Skill '{skill_id}' not in discovery cache. Run discover first."}

        # Collision check: folder + registry
        target_dir = self._skills_dir / skill_id
        if target_dir.exists():
            return {"status": "error", "detail": f"Skill directory '{skill_id}' already exists"}
        if skill_id in self._entries and self._entries[skill_id].status == "installed":
            return {"status": "error", "detail": f"Skill '{skill_id}' already installed"}

        # Clone repo to temp
        repo_url = skill_info["source_url"]
        source_path = skill_info.get("source_path", skill_id)
        tmp_dir = Path(f"/tmp/marketplace-install-{uuid4().hex[:8]}")

        try:
            result = subprocess.run(
                ["git", "clone", "--depth", "1", repo_url, str(tmp_dir)],
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode != 0:
                return {"status": "error", "detail": f"Git clone failed: {result.stderr[:200]}"}

            # Find skill in cloned repo
            skill_src = tmp_dir / source_path
            if not skill_src.is_dir():
                return {"status": "error", "detail": f"Source path '{source_path}' not found in repo"}

            # Validate
            validation = self._validate_skill(skill_src)
            if not validation["valid"]:
                entry = MarketplaceEntry(
                    skill_id=skill_id, source_repo=repo_url,
                    source_path=source_path, status="failed",
                    validation_result=validation,
                )
                self._entries[skill_id] = entry
                self._save()
                return {"status": "failed", "validation": validation}

            # Atomic move to skills/
            shutil.copytree(skill_src, target_dir)
            # Create outputs dir
            (target_dir / "outputs").mkdir(exist_ok=True)

            # Compute checksum
            checksum = self._compute_checksum(target_dir)

            # Register
            entry = MarketplaceEntry(
                skill_id=skill_id,
                source_repo=repo_url,
                source_path=source_path,
                version=skill_info.get("version", "0.0.0"),
                status="installed",
                installed_at=datetime.now(timezone.utc).isoformat(),
                validation_result=validation,
                checksum=checksum,
            )
            self._entries[skill_id] = entry
            self._save()

            # Reload skill service if available
            if self._skill_service and hasattr(self._skill_service, "reload"):
                self._skill_service.reload()

            logger.info("Installed marketplace skill: %s (v%s) from %s", skill_id, entry.version, repo_url)
            return {"status": "installed", "entry": entry.to_dict()}

        except Exception as e:
            # Cleanup on failure
            if target_dir.exists():
                shutil.rmtree(target_dir, ignore_errors=True)
            logger.error("Install failed for %s: %s", skill_id, e)
            return {"status": "error", "detail": str(e)}
        finally:
            if tmp_dir.exists():
                shutil.rmtree(tmp_dir, ignore_errors=True)

    # ── Update ──────────────────────────────────────────────────────

    def check_updates(self) -> list[dict[str, Any]]:
        """Check all installed skills for available updates via semver comparison."""
        updates: list[dict[str, Any]] = []
        discovered = {s["skill_id"]: s for s in self._discover_cache if "skill_id" in s}

        for sid, entry in self._entries.items():
            if entry.status != "installed":
                continue
            remote = discovered.get(sid)
            if not remote:
                continue
            remote_ver = remote.get("version", "0.0.0")
            if self._version_gt(remote_ver, entry.version):
                updates.append({
                    "skill_id": sid,
                    "installed_version": entry.version,
                    "available_version": remote_ver,
                    "source_repo": entry.source_repo,
                })

        return updates

    def update(self, skill_id: str) -> dict[str, Any]:
        """Update an installed skill: backup → uninstall → reinstall."""
        entry = self._entries.get(skill_id)
        if not entry or entry.status != "installed":
            return {"status": "error", "detail": f"Skill '{skill_id}' not installed"}

        # Backup
        target_dir = self._skills_dir / skill_id
        backup_dir = self._skills_dir / f".backup-{skill_id}"
        if target_dir.exists():
            if backup_dir.exists():
                shutil.rmtree(backup_dir)
            shutil.copytree(target_dir, backup_dir)

        # Remove current
        if target_dir.exists():
            shutil.rmtree(target_dir)
        old_version = entry.version

        # Reinstall
        result = self.install(skill_id)

        if result.get("status") == "installed":
            # Cleanup backup
            if backup_dir.exists():
                shutil.rmtree(backup_dir, ignore_errors=True)
            logger.info("Updated %s: %s → %s", skill_id, old_version, result.get("entry", {}).get("version", "?"))
        else:
            # Restore backup
            if backup_dir.exists() and not target_dir.exists():
                shutil.move(str(backup_dir), str(target_dir))
                logger.warning("Update failed for %s — restored backup", skill_id)
            result["rollback"] = True

        return result

    @staticmethod
    def _version_gt(a: str, b: str) -> bool:
        """Simple semver comparison: is a > b?"""
        def parse(v: str) -> tuple[int, ...]:
            parts = []
            for p in v.replace("v", "").split(".")[:3]:
                try:
                    parts.append(int(p))
                except ValueError:
                    parts.append(0)
            while len(parts) < 3:
                parts.append(0)
            return tuple(parts)
        return parse(a) > parse(b)

    # ── Uninstall ───────────────────────────────────────────────────

    def uninstall(self, skill_id: str) -> dict[str, Any]:
        """Soft-delete: rename directory to .disabled-{id}, mark as disabled."""
        entry = self._entries.get(skill_id)
        if not entry:
            return {"status": "error", "detail": f"Skill '{skill_id}' not in marketplace registry"}

        target_dir = self._skills_dir / skill_id
        disabled_dir = self._skills_dir / f".disabled-{skill_id}"

        if target_dir.exists():
            if disabled_dir.exists():
                shutil.rmtree(disabled_dir)
            shutil.move(str(target_dir), str(disabled_dir))

        entry.status = "disabled"
        self._save()

        if self._skill_service and hasattr(self._skill_service, "reload"):
            self._skill_service.reload()

        logger.info("Uninstalled (soft-delete) marketplace skill: %s", skill_id)
        return {"status": "disabled", "skill_id": skill_id}

    # ── Query ───────────────────────────────────────────────────────

    def get_installed(self) -> list[dict[str, Any]]:
        return [e.to_dict() for e in self._entries.values() if e.status == "installed"]

    def get_entry(self, skill_id: str) -> dict[str, Any] | None:
        entry = self._entries.get(skill_id)
        return entry.to_dict() if entry else None

    def get_stats(self) -> dict[str, Any]:
        by_status: dict[str, int] = {}
        for e in self._entries.values():
            by_status[e.status] = by_status.get(e.status, 0) + 1
        return {
            "total_sources": len(self._sources),
            "total_entries": len(self._entries),
            "by_status": by_status,
            "cache_age_seconds": round(time.time() - self._discover_cache_time) if self._discover_cache_time else None,
            "cached_skills": len(self._discover_cache),
        }
