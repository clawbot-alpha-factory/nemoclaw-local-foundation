"""
NemoClaw Execution Engine — Prompt Optimization Service

Tracks prompt variants per skill. Every 100 executions, analyzes
quality scores and promotes the best-performing prompt. Auto-generates
variant suggestions via LLM.

Persists to: ~/.nemoclaw/prompt-variants.json

NEW FILE: command-center/backend/app/services/prompt_optimization_service.py
"""
from __future__ import annotations
import json, logging, os, time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("cc.prompt_opt")


class PromptVariant:
    def __init__(self, variant_id: str, skill_id: str, prompt_text: str,
                 label: str = "default"):
        self.variant_id = variant_id
        self.skill_id = skill_id
        self.prompt_text = prompt_text
        self.label = label
        self.executions: int = 0
        self.total_quality: float = 0.0
        self.successes: int = 0
        self.failures: int = 0
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.is_active: bool = True
        self.is_winner: bool = False

    @property
    def avg_quality(self) -> float:
        return round(self.total_quality / max(self.executions, 1), 2)

    @property
    def success_rate(self) -> float:
        total = self.successes + self.failures
        return round(self.successes / max(total, 1), 2)

    def record(self, quality_score: float, success: bool) -> None:
        self.executions += 1
        self.total_quality += quality_score
        if success:
            self.successes += 1
        else:
            self.failures += 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "variant_id": self.variant_id, "skill_id": self.skill_id,
            "label": self.label, "executions": self.executions,
            "avg_quality": self.avg_quality, "success_rate": self.success_rate,
            "successes": self.successes, "failures": self.failures,
            "is_active": self.is_active, "is_winner": self.is_winner,
            "created_at": self.created_at,
            "prompt_preview": self.prompt_text[:100] + "..." if len(self.prompt_text) > 100 else self.prompt_text,
        }


class PromptOptimizationService:
    """
    A/B tests prompts for every skill. Every 100 executions per skill,
    evaluates variants and promotes the winner.

    Flow:
    1. Skill executes → record quality score for active variant
    2. Every 100 executions → compare variants → promote best
    3. Generate new variant suggestions via LLM
    4. Retire underperformers
    """

    EVALUATION_INTERVAL = 100  # Evaluate every N executions
    MIN_SAMPLE_SIZE = 20       # Minimum executions before comparing
    QUALITY_THRESHOLD = 6.0    # Minimum avg quality to keep variant

    def __init__(self, global_state=None):
        self.global_state = global_state
        self._variants: dict[str, list[PromptVariant]] = {}  # skill_id → variants
        self._execution_counts: dict[str, int] = {}  # skill_id → total count
        self._persist_path = Path.home() / ".nemoclaw" / "prompt-variants.json"
        self._persist_path.parent.mkdir(parents=True, exist_ok=True)
        self._load()
        total_variants = sum(len(v) for v in self._variants.values())
        logger.info("PromptOptimizationService initialized (%d skills, %d variants)",
                    len(self._variants), total_variants)

    def _load(self) -> None:
        if self._persist_path.exists():
            try:
                data = json.loads(self._persist_path.read_text())
                for skill_id, variants in data.get("variants", {}).items():
                    self._variants[skill_id] = []
                    for v in variants:
                        pv = PromptVariant(v["variant_id"], v["skill_id"],
                                          v.get("prompt_text", ""), v.get("label", ""))
                        pv.executions = v.get("executions", 0)
                        pv.total_quality = v.get("total_quality", 0)
                        pv.successes = v.get("successes", 0)
                        pv.failures = v.get("failures", 0)
                        pv.is_active = v.get("is_active", True)
                        pv.is_winner = v.get("is_winner", False)
                        pv.created_at = v.get("created_at", pv.created_at)
                        self._variants[skill_id].append(pv)
                self._execution_counts = data.get("execution_counts", {})
            except Exception as e:
                logger.warning("Failed to load prompt variants: %s", e)

    def _save(self) -> None:
        try:
            data = {
                "variants": {
                    sid: [{**v.to_dict(), "prompt_text": v.prompt_text}
                          for v in variants]
                    for sid, variants in self._variants.items()
                },
                "execution_counts": self._execution_counts,
            }
            self._persist_path.write_text(json.dumps(data, indent=2, default=str))
        except Exception as e:
            logger.warning("Failed to save prompt variants: %s", e)

    def register_variant(self, skill_id: str, prompt_text: str,
                        label: str = "default") -> dict[str, Any]:
        """Register a new prompt variant for a skill."""
        if skill_id not in self._variants:
            self._variants[skill_id] = []

        variant_id = f"{skill_id}-v{len(self._variants[skill_id])}"
        pv = PromptVariant(variant_id, skill_id, prompt_text, label)

        # First variant is auto-active
        if len(self._variants[skill_id]) == 0:
            pv.is_active = True
        else:
            pv.is_active = True  # Both active for A/B testing

        self._variants[skill_id].append(pv)
        self._save()
        return pv.to_dict()

    def record_execution(self, skill_id: str, quality_score: float,
                        success: bool, variant_id: str | None = None) -> dict[str, Any]:
        """Record a skill execution result for the active variant."""
        if skill_id not in self._variants or not self._variants[skill_id]:
            return {"status": "no_variants_registered"}

        # Find the variant (specific or active)
        variant = None
        if variant_id:
            variant = next((v for v in self._variants[skill_id]
                          if v.variant_id == variant_id), None)
        if not variant:
            active = [v for v in self._variants[skill_id] if v.is_active]
            if active:
                # Round-robin between active variants
                count = self._execution_counts.get(skill_id, 0)
                variant = active[count % len(active)]

        if not variant:
            return {"status": "no_active_variant"}

        variant.record(quality_score, success)
        self._execution_counts[skill_id] = self._execution_counts.get(skill_id, 0) + 1

        result = {"status": "recorded", "variant_id": variant.variant_id,
                 "avg_quality": variant.avg_quality, "executions": variant.executions}

        # Check if it's time to evaluate
        total = self._execution_counts[skill_id]
        if total > 0 and total % self.EVALUATION_INTERVAL == 0:
            eval_result = self._evaluate_variants(skill_id)
            result["evaluation"] = eval_result

        self._save()
        return result

    def _evaluate_variants(self, skill_id: str) -> dict[str, Any]:
        """Compare variants and promote the winner."""
        variants = self._variants.get(skill_id, [])
        if len(variants) < 2:
            return {"status": "insufficient_variants"}

        # Only compare variants with enough data
        eligible = [v for v in variants if v.executions >= self.MIN_SAMPLE_SIZE]
        if len(eligible) < 2:
            return {"status": "insufficient_data", "need": self.MIN_SAMPLE_SIZE}

        # Sort by avg quality (primary) then success rate (secondary)
        ranked = sorted(eligible, key=lambda v: (v.avg_quality, v.success_rate), reverse=True)
        winner = ranked[0]
        runner_up = ranked[1]

        # Need meaningful difference (>10% lift)
        if winner.avg_quality > runner_up.avg_quality * 1.1:
            # Promote winner
            for v in variants:
                v.is_winner = (v.variant_id == winner.variant_id)
            # Retire underperformers below threshold
            for v in variants:
                if v.avg_quality < self.QUALITY_THRESHOLD and v.executions >= self.MIN_SAMPLE_SIZE:
                    v.is_active = False

            logger.info("Prompt optimization: %s winner=%s (quality=%.1f vs %.1f, +%.0f%% lift)",
                       skill_id, winner.label, winner.avg_quality, runner_up.avg_quality,
                       (winner.avg_quality / max(runner_up.avg_quality, 0.01) - 1) * 100)

            # Record in global state
            if self.global_state:
                self.global_state.add("learnings", f"prompt-opt-{skill_id}-{int(time.time())}", {
                    "skill_id": skill_id,
                    "winner": winner.variant_id,
                    "winner_quality": winner.avg_quality,
                    "runner_up_quality": runner_up.avg_quality,
                    "lift_pct": round((winner.avg_quality / max(runner_up.avg_quality, 0.01) - 1) * 100, 1),
                    "total_executions": self._execution_counts.get(skill_id, 0),
                }, tags=["prompt_optimization", skill_id])

            self._save()
            return {
                "status": "winner_promoted",
                "winner": winner.to_dict(),
                "runner_up": runner_up.to_dict(),
                "retired": [v.variant_id for v in variants if not v.is_active],
            }

        return {"status": "no_clear_winner", "top_quality": winner.avg_quality,
                "second_quality": runner_up.avg_quality}

    def get_active_prompt(self, skill_id: str) -> str | None:
        """Get the currently best-performing prompt for a skill."""
        variants = self._variants.get(skill_id, [])
        if not variants:
            return None
        # Prefer winner, then highest quality active
        winners = [v for v in variants if v.is_winner and v.is_active]
        if winners:
            return winners[0].prompt_text
        active = [v for v in variants if v.is_active]
        if active:
            return max(active, key=lambda v: v.avg_quality).prompt_text
        return variants[0].prompt_text

    def get_skill_variants(self, skill_id: str) -> list[dict[str, Any]]:
        return [v.to_dict() for v in self._variants.get(skill_id, [])]

    def get_all_optimizations(self) -> dict[str, Any]:
        result = {}
        for skill_id, variants in self._variants.items():
            active = [v for v in variants if v.is_active]
            winner = next((v for v in variants if v.is_winner), None)
            result[skill_id] = {
                "total_variants": len(variants),
                "active_variants": len(active),
                "winner": winner.to_dict() if winner else None,
                "total_executions": self._execution_counts.get(skill_id, 0),
                "next_evaluation_at": (
                    (self._execution_counts.get(skill_id, 0) // self.EVALUATION_INTERVAL + 1)
                    * self.EVALUATION_INTERVAL
                ),
            }
        return result

    def get_stats(self) -> dict[str, Any]:
        total_variants = sum(len(v) for v in self._variants.values())
        winners = sum(1 for vs in self._variants.values()
                     for v in vs if v.is_winner)
        return {
            "skills_tracked": len(self._variants),
            "total_variants": total_variants,
            "winners_promoted": winners,
            "total_executions": sum(self._execution_counts.values()),
            "evaluation_interval": self.EVALUATION_INTERVAL,
            "quality_threshold": self.QUALITY_THRESHOLD,
        }

    async def generate_variant_suggestion(self, skill_id: str) -> dict[str, Any]:
        """Use LLM to suggest a new prompt variant based on performance data."""
        variants = self._variants.get(skill_id, [])
        if not variants:
            return {"error": "No existing variants to improve on"}

        best = max(variants, key=lambda v: v.avg_quality)
        try:
            import httpx
            api_key = os.environ.get("OPENAI_API_KEY", "")
            if not api_key:
                return {"error": "No OpenAI key for suggestion generation"}

            # Resolve model from routing config (L-003)
            import sys; sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
            from lib.routing import resolve_alias
            _opt_p, _opt_m, _ = resolve_alias("general_short")

            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={
                        "model": _opt_m,
                        "max_tokens": 500,
                        "messages": [
                            {"role": "system", "content": "You are a prompt engineering expert. Given a prompt and its quality score, suggest an improved version. Return ONLY the improved prompt text, nothing else."},
                            {"role": "user", "content": f"Current prompt (quality: {best.avg_quality}/10):\n\n{best.prompt_text[:1000]}\n\nImprove this prompt to increase quality score. Focus on: clarity, specificity, structure, output format."},
                        ],
                    },
                )
                data = resp.json()
                suggestion = data["choices"][0]["message"]["content"].strip()

                # Auto-register as new variant
                new_variant = self.register_variant(
                    skill_id, suggestion, f"auto-v{len(variants)}"
                )
                return {"status": "variant_suggested", "new_variant": new_variant,
                        "based_on": best.to_dict()}

        except Exception as e:
            return {"error": str(e)[:200]}
