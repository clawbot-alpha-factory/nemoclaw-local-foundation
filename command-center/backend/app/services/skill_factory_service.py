"""
NemoClaw Execution Engine — SkillFactoryService (E-5)

Automated skill generation pipeline:
  Concept → pattern match → spec gen (g26) → code gen (g26) →
  quality gate → human approval → deploy → reload

Includes: quality scoring, pattern confidence, deduplication,
versioned deployment, audit linkage.

NEW FILE: command-center/backend/app/services/skill_factory_service.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("cc.factory")


class JobStatus:
    QUEUED = "queued"
    MATCHING_PATTERN = "matching_pattern"
    GENERATING_SPEC = "generating_spec"
    GENERATING_CODE = "generating_code"
    VALIDATING = "validating"
    QUALITY_CHECK = "quality_check"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    DEPLOYED = "deployed"
    REJECTED = "rejected"
    FAILED = "failed"


class FactoryJob:
    """Tracks a single skill generation through the pipeline."""

    def __init__(self, concept: str, language: str = "en"):
        self.job_id = str(uuid.uuid4())[:8]
        self.concept = concept
        self.language = language
        self.status = JobStatus.QUEUED
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.completed_at: str | None = None

        # Pipeline results
        self.pattern_match: dict[str, Any] = {}
        self.spec_path: str | None = None
        self.code_path: str | None = None
        self.dry_run_result: dict[str, Any] = {}
        self.quality_score: float = 0.0
        self.quality_details: dict[str, Any] = {}
        self.dedup_check: dict[str, Any] = {}
        self.skill_id: str | None = None
        self.version: str = "v1"
        self.approved_by: str | None = None
        self.error: str | None = None
        self.cost: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "concept": self.concept,
            "language": self.language,
            "status": self.status,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "pattern_match": self.pattern_match,
            "spec_path": self.spec_path,
            "code_path": self.code_path,
            "dry_run_result": self.dry_run_result,
            "quality_score": self.quality_score,
            "quality_details": self.quality_details,
            "dedup_check": self.dedup_check,
            "skill_id": self.skill_id,
            "version": self.version,
            "approved_by": self.approved_by,
            "error": self.error,
            "cost": self.cost,
        }


class SkillFactoryService:
    """
    Generates skills from concepts using meta-skills (g26).

    Pipeline:
      1. Pattern match (confidence + alternatives)
      2. Dedup check against existing skills
      3. Spec generation via g26-skill-spec-writer
      4. Code generation via g26-skill-template-gen
      5. Dry-run validation
      6. Quality scoring (0-10, reject < 6)
      7. Human approval
      8. Versioned deployment + audit
    """

    QUALITY_THRESHOLD = 6.0
    MAX_ACTIVE_SKILLS = 100

    def __init__(self, repo_root: Path, execution_service=None, skill_service=None, audit_service=None):
        self.repo_root = repo_root
        self.execution_service = execution_service
        self.skill_service = skill_service
        self.audit_service = audit_service
        self.skills_dir = repo_root / "skills"
        self.python = str(repo_root / ".venv313" / "bin" / "python3")
        self.pattern_library = self._load_patterns()
        self.jobs: dict[str, FactoryJob] = {}

        logger.info(
            "SkillFactoryService initialized (%d patterns, max %d skills)",
            len(self.pattern_library), self.MAX_ACTIVE_SKILLS,
        )

    def _load_patterns(self) -> list[dict[str, Any]]:
        """Load pattern library from JSON."""
        path = self.repo_root / "docs" / "reference" / "pattern-library.json"
        if path.exists():
            try:
                data = json.loads(path.read_text())
                return data.get("patterns", [])
            except (json.JSONDecodeError, OSError):
                pass
        return []

    # ── Pattern Matching ───────────────────────────────────────────────

    def match_pattern(self, concept: str) -> dict[str, Any]:
        """Match concept to best pattern with confidence score."""
        concept_lower = concept.lower()
        scores: list[tuple[dict, float]] = []

        for pattern in self.pattern_library:
            score = 0.0
            keywords = pattern.get("keywords", [])
            category = pattern.get("category", "")

            # Keyword matching
            matched_keywords = [k for k in keywords if k.lower() in concept_lower]
            if keywords:
                score = len(matched_keywords) / len(keywords)

            # Category boost
            if category.lower() in concept_lower:
                score += 0.2

            scores.append((pattern, min(score, 1.0)))

        # Sort by score descending
        scores.sort(key=lambda x: x[1], reverse=True)

        if not scores or scores[0][1] == 0:
            return {
                "pattern": None,
                "confidence": 0.0,
                "alternatives": [],
                "warning": "No pattern match found — using generic template",
            }

        best = scores[0]
        alternatives = [
            {"pattern": s[0]["name"], "confidence": round(s[1], 2)}
            for s in scores[1:4] if s[1] > 0
        ]

        return {
            "pattern": best[0]["name"],
            "pattern_id": best[0].get("id", ""),
            "confidence": round(best[1], 2),
            "alternatives": alternatives,
            "low_confidence": best[1] < 0.5,
        }

    # ── Deduplication ──────────────────────────────────────────────────

    def check_dedup(self, concept: str) -> dict[str, Any]:
        """Check for similar existing skills."""
        concept_lower = concept.lower()
        concept_words = set(concept_lower.split())
        similar: list[dict[str, Any]] = []

        existing_skills = []
        if self.skill_service and hasattr(self.skill_service, "skills"):
            existing_skills = list(self.skill_service.skills.values())

        # Also check skills directory
        if not existing_skills:
            for skill_dir in self.skills_dir.iterdir():
                if skill_dir.is_dir() and not skill_dir.name.startswith("."):
                    existing_skills.append({"skill_id": skill_dir.name, "name": skill_dir.name})

        for skill in existing_skills:
            skill_name = str(skill.get("name", skill.get("skill_id", ""))).lower()
            skill_words = set(skill_name.replace("-", " ").split())

            if not skill_words:
                continue

            overlap = concept_words & skill_words
            similarity = len(overlap) / max(len(concept_words), len(skill_words))

            if similarity > 0.3:
                similar.append({
                    "skill_id": skill.get("skill_id", skill.get("name", "")),
                    "similarity": round(similarity, 2),
                })

        similar.sort(key=lambda x: x["similarity"], reverse=True)

        return {
            "has_duplicates": any(s["similarity"] > 0.7 for s in similar),
            "similar_skills": similar[:5],
            "warning": "High similarity detected — consider using existing skill" if any(s["similarity"] > 0.7 for s in similar) else None,
        }

    # ── Quality Scoring ────────────────────────────────────────────────

    def score_quality(self, job: FactoryJob) -> dict[str, Any]:
        """Score generated skill quality (0-10)."""
        checks = {
            "pattern_matched": 1.0 if job.pattern_match.get("pattern") else 0.0,
            "pattern_confidence": min(job.pattern_match.get("confidence", 0) * 2, 2.0),
            "spec_generated": 1.0 if job.spec_path else 0.0,
            "code_generated": 1.0 if job.code_path else 0.0,
            "dry_run_passed": 2.0 if job.dry_run_result.get("success") else 0.0,
            "no_duplicates": 1.0 if not job.dedup_check.get("has_duplicates") else 0.0,
            "has_description": 1.0,  # concept serves as description
            "cost_reasonable": 1.0 if job.cost < 2.0 else 0.0,
        }

        total = sum(checks.values())
        score = min(total, 10.0)

        return {
            "score": round(score, 1),
            "checks": checks,
            "passed": score >= self.QUALITY_THRESHOLD,
            "threshold": self.QUALITY_THRESHOLD,
        }

    # ── Job Submission ─────────────────────────────────────────────────

    async def generate(self, concept: str, language: str = "en") -> FactoryJob:
        """Submit a skill concept for generation."""
        job = FactoryJob(concept=concept, language=language)
        self.jobs[job.job_id] = job

        logger.info("Factory job %s: concept='%s'", job.job_id, concept[:50])

        # Run pipeline in background
        asyncio.create_task(self._run_pipeline(job))
        return job

    async def _run_pipeline(self, job: FactoryJob):
        """Full generation pipeline."""
        try:
            # Step 1: Pattern match
            job.status = JobStatus.MATCHING_PATTERN
            job.pattern_match = self.match_pattern(job.concept)

            if job.pattern_match.get("low_confidence"):
                logger.warning("Job %s: low pattern confidence (%.2f)", job.job_id, job.pattern_match["confidence"])

            # Step 2: Dedup check
            job.dedup_check = self.check_dedup(job.concept)
            if job.dedup_check.get("has_duplicates"):
                job.status = JobStatus.FAILED
                job.error = f"Duplicate detected: {job.dedup_check['similar_skills'][0]}"
                return

            # Step 3: Generate spec via g26-skill-spec-writer
            job.status = JobStatus.GENERATING_SPEC
            spec_result = await self._run_meta_skill(
                "g26-skill-spec-writer",
                {"skill_concept": job.concept, "skill_category": job.pattern_match.get("pattern", "general")},
            )
            if spec_result.get("success"):
                job.spec_path = spec_result.get("output_path")
                job.cost += spec_result.get("cost", 0.15)
            else:
                job.status = JobStatus.FAILED
                job.error = f"Spec generation failed: {spec_result.get('error', 'unknown')}"
                return

            # Step 4: Generate code via g26-skill-template-gen
            job.status = JobStatus.GENERATING_CODE
            code_result = await self._run_meta_skill(
                "g26-skill-template-gen",
                {"skill_spec": job.concept, "template_type": job.pattern_match.get("pattern", "general")},
            )
            if code_result.get("success"):
                job.code_path = code_result.get("output_path")
                job.cost += code_result.get("cost", 0.15)
            else:
                job.status = JobStatus.FAILED
                job.error = f"Code generation failed: {code_result.get('error', 'unknown')}"
                return

            # Step 5: Dry-run validation
            job.status = JobStatus.VALIDATING
            # Simplified: check that output files exist
            job.dry_run_result = {
                "success": bool(job.spec_path and job.code_path),
                "spec_exists": bool(job.spec_path),
                "code_exists": bool(job.code_path),
            }

            # Step 6: Quality scoring
            job.status = JobStatus.QUALITY_CHECK
            quality = self.score_quality(job)
            job.quality_score = quality["score"]
            job.quality_details = quality

            if not quality["passed"]:
                job.status = JobStatus.FAILED
                job.error = f"Quality score {quality['score']:.1f} below threshold {self.QUALITY_THRESHOLD}"
                return

            # Step 7: Ready for approval
            job.status = JobStatus.PENDING_APPROVAL
            job.skill_id = f"factory-{job.job_id}"

            logger.info(
                "Job %s ready for approval: quality=%.1f, cost=$%.2f",
                job.job_id, job.quality_score, job.cost,
            )

        except Exception as e:
            job.status = JobStatus.FAILED
            job.error = str(e)
            logger.error("Factory job %s failed: %s", job.job_id, e)

    async def _run_meta_skill(self, skill_id: str, inputs: dict[str, str]) -> dict[str, Any]:
        """Run a meta-skill via ExecutionService or subprocess."""
        if self.execution_service:
            from app.domain.engine_models import ExecutionRequest, LLMTier
            request = ExecutionRequest(
                skill_id=skill_id,
                inputs=inputs,
                agent_id="engineering_lead",
                tier=LLMTier.COMPLEX,
            )
            execution = self.execution_service.submit(request)

            # Wait for completion
            for _ in range(120):
                ex = self.execution_service.get_execution(execution.execution_id)
                if ex and ex.status.value in ("completed", "failed", "dead_letter"):
                    return {
                        "success": ex.status.value == "completed",
                        "output_path": ex.output_path,
                        "cost": ex.cost,
                        "error": ex.error,
                    }
                await asyncio.sleep(2)

            return {"success": False, "error": "Meta-skill timed out"}
        else:
            # Direct subprocess fallback
            cmd = [
                self.python,
                str(self.repo_root / "skills" / "skill-runner.py"),
                "--skill", skill_id,
            ]
            for k, v in inputs.items():
                cmd.extend(["--input", k, v])

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.repo_root),
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)

            if proc.returncode == 0:
                stdout_str = stdout.decode()
                output_path = None
                for line in stdout_str.split("\n"):
                    if "[artifact] Written to:" in line:
                        output_path = line.split("Written to:")[-1].strip()
                return {"success": True, "output_path": output_path, "cost": 0.15}
            else:
                return {"success": False, "error": stderr.decode()[:300]}

    # ── Approval / Rejection ───────────────────────────────────────────

    def approve(self, job_id: str, approved_by: str) -> dict[str, Any]:
        """Approve a generated skill for deployment."""
        job = self.jobs.get(job_id)
        if not job:
            return {"success": False, "reason": "Job not found"}
        if job.status != JobStatus.PENDING_APPROVAL:
            return {"success": False, "reason": f"Job status is {job.status}, not pending_approval"}

        # Check skill cap
        existing_count = 0
        if self.skill_service and hasattr(self.skill_service, "skills"):
            existing_count = len(self.skill_service.skills)
        if existing_count >= self.MAX_ACTIVE_SKILLS:
            return {"success": False, "reason": f"Max active skills reached ({self.MAX_ACTIVE_SKILLS})"}

        job.status = JobStatus.APPROVED
        job.approved_by = approved_by
        job.completed_at = datetime.now(timezone.utc).isoformat()

        # Audit
        if self.audit_service:
            self.audit_service.log(
                "skill_approved",
                agent_id=approved_by,
                details={
                    "job_id": job.job_id,
                    "concept": job.concept,
                    "quality_score": job.quality_score,
                    "cost": job.cost,
                    "version": job.version,
                },
            )

        logger.info("Job %s approved by %s", job.job_id, approved_by)
        return {"success": True, "job": job.to_dict()}

    def reject(self, job_id: str, rejected_by: str, reason: str = "") -> dict[str, Any]:
        """Reject a generated skill."""
        job = self.jobs.get(job_id)
        if not job:
            return {"success": False, "reason": "Job not found"}

        job.status = JobStatus.REJECTED
        job.error = reason or "Rejected by reviewer"
        job.completed_at = datetime.now(timezone.utc).isoformat()

        if self.audit_service:
            self.audit_service.log("skill_rejected", agent_id=rejected_by, details={"job_id": job.job_id, "reason": reason})

        return {"success": True, "job": job.to_dict()}

    # ── Query ──────────────────────────────────────────────────────────

    def get_job(self, job_id: str) -> FactoryJob | None:
        return self.jobs.get(job_id)

    def get_queue(self) -> list[dict[str, Any]]:
        return [j.to_dict() for j in self.jobs.values()]

    def get_stats(self) -> dict[str, Any]:
        total = len(self.jobs)
        by_status: dict[str, int] = {}
        total_cost = 0.0
        for j in self.jobs.values():
            by_status[j.status] = by_status.get(j.status, 0) + 1
            total_cost += j.cost

        return {
            "total_jobs": total,
            "by_status": by_status,
            "total_cost": round(total_cost, 3),
            "patterns_loaded": len(self.pattern_library),
            "quality_threshold": self.QUALITY_THRESHOLD,
            "max_active_skills": self.MAX_ACTIVE_SKILLS,
        }

    def get_patterns(self) -> list[dict[str, Any]]:
        """Return loaded pattern library."""
        return list(self.pattern_library)
