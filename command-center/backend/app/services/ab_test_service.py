"""
NemoClaw Execution Engine — A/B Test Service (E-10)

Auto-generate 2-3 variants, measure, promote winners.

NEW FILE: command-center/backend/app/services/ab_test_service.py
"""
from __future__ import annotations
import json, logging, math, os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("cc.abtest")


class Variant:
    def __init__(self, variant_id: str, name: str, content: str):
        self.variant_id = variant_id
        self.name = name
        self.content = content
        self.impressions: int = 0
        self.conversions: int = 0

    @property
    def rate(self) -> float:
        return self.conversions / max(self.impressions, 1)

    def to_dict(self) -> dict[str, Any]:
        return {"variant_id": self.variant_id, "name": self.name, "impressions": self.impressions,
                "conversions": self.conversions, "rate": round(self.rate, 4)}


class Experiment:
    def __init__(self, exp_id: str, name: str, metric: str = "conversion_rate",
                 min_sample: int = 50, confidence: float = 0.90):
        self.exp_id = exp_id
        self.name = name
        self.metric = metric
        self.min_sample = min_sample
        self.confidence = confidence
        self.status = "running"
        self.variants: list[Variant] = []
        self.winner: str | None = None
        self.created_at = datetime.now(timezone.utc).isoformat()

    def add_variant(self, variant_id: str, name: str, content: str) -> None:
        self.variants.append(Variant(variant_id, name, content))

    def record(self, variant_id: str, impression: bool = True, conversion: bool = False) -> None:
        for v in self.variants:
            if v.variant_id == variant_id:
                if impression:
                    v.impressions += 1
                if conversion:
                    v.conversions += 1
                break
        self._check_winner()

    def _check_winner(self) -> None:
        if self.status != "running" or len(self.variants) < 2:
            return
        if all(v.impressions >= self.min_sample for v in self.variants):
            best = max(self.variants, key=lambda v: v.rate)
            second = sorted(self.variants, key=lambda v: v.rate, reverse=True)[1]
            lift = (best.rate - second.rate) / max(second.rate, 0.001)
            if lift > 0.1 and best.impressions >= self.min_sample:
                self.winner = best.variant_id
                self.status = "completed"
                logger.info("Experiment %s: winner=%s (lift=+%.0f%%)", self.exp_id, best.name, lift * 100)

    def to_dict(self) -> dict[str, Any]:
        return {
            "exp_id": self.exp_id, "name": self.name, "status": self.status,
            "metric": self.metric, "winner": self.winner,
            "variants": [v.to_dict() for v in self.variants],
            "created_at": self.created_at,
        }


class ABTestService:
    def __init__(self, global_state=None):
        self.global_state = global_state
        self._experiments: dict[str, Experiment] = {}
        self._persist_path = Path.home() / ".nemoclaw" / "ab-tests.json"
        self._persist_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info("ABTestService initialized")

    def create_experiment(self, exp_id: str, name: str, variants: list[dict[str, str]],
                         metric: str = "conversion_rate", min_sample: int = 50) -> dict[str, Any]:
        if exp_id in self._experiments:
            return {"error": "Experiment exists"}
        exp = Experiment(exp_id, name, metric, min_sample)
        for v in variants:
            exp.add_variant(v["id"], v["name"], v.get("content", ""))
        self._experiments[exp_id] = exp
        self._save()
        return exp.to_dict()

    def record_event(self, exp_id: str, variant_id: str, conversion: bool = False) -> dict[str, Any]:
        exp = self._experiments.get(exp_id)
        if not exp:
            return {"error": "Experiment not found"}
        exp.record(variant_id, impression=True, conversion=conversion)
        self._save()
        return {"status": "recorded", "variant": variant_id, "experiment_status": exp.status, "winner": exp.winner}

    def get_experiment(self, exp_id: str) -> dict[str, Any] | None:
        exp = self._experiments.get(exp_id)
        return exp.to_dict() if exp else None

    def get_all(self) -> list[dict[str, Any]]:
        return [e.to_dict() for e in self._experiments.values()]

    def _save(self) -> None:
        try:
            data = {eid: e.to_dict() for eid, e in self._experiments.items()}
            self._persist_path.write_text(json.dumps(data, indent=2, default=str))
        except Exception:
            pass
