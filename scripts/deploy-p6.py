#!/usr/bin/env python3
"""
NemoClaw P-6 Deployment: Metrics Time-Range Aggregation

Patches: metrics_service.py (4 new methods)
Patches: autonomous.py router (3 new endpoints)

Run from repo root:
    cd ~/nemoclaw-local-foundation
    python3 scripts/deploy-p6.py
"""

from pathlib import Path
import sys

BACKEND = Path.home() / "nemoclaw-local-foundation" / "command-center" / "backend"

# ═══════════════════════════════════════════════════════════════════
# NEW METHODS for MetricsService
# ═══════════════════════════════════════════════════════════════════

METRICS_METHODS = '''

    # ── Time-Range Aggregation (P-6) ────────────────────────────────

    MAX_RANGE_DAYS = 365

    def query_range(self, after: str, before: str) -> list[dict[str, Any]]:
        """Return snapshots within date range. Inclusive after, exclusive before, UTC.

        Snapshots sorted ascending by date.
        """
        results = []
        for snap in self._snapshots:
            date = snap.get("date", "")
            if not date:
                continue
            if date >= after and date < before:
                results.append(snap)
        results.sort(key=lambda s: s.get("date", ""))
        return results

    def aggregate(self, after: str, before: str) -> dict[str, Any]:
        """Compute avg/min/max/sum/count/first/last/trend/change_pct per numeric metric.

        Only aggregates fields that are int or float. Skips strings, dicts, lists.
        Division-by-zero guarded: change_pct = None when first is 0.
        Empty ranges return zeroed aggregation with count=0.
        """
        # Validate range
        self._validate_range(after, before)

        snapshots = self.query_range(after, before)
        count = len(snapshots)

        if count == 0:
            return {
                "after": after,
                "before": before,
                "count": 0,
                "metrics": {},
                "note": "No snapshots in range",
            }

        # Collect numeric fields
        numeric_keys: set[str] = set()
        for snap in snapshots:
            for k, v in snap.items():
                if isinstance(v, (int, float)) and k != "date":
                    numeric_keys.add(k)

        metrics: dict[str, Any] = {}
        for key in sorted(numeric_keys):
            values = []
            for snap in snapshots:
                v = snap.get(key)
                if isinstance(v, (int, float)):
                    values.append(float(v))

            if not values:
                continue

            first_val = values[0]
            last_val = values[-1]
            avg_val = sum(values) / len(values)

            # Trend: compare first vs last
            if last_val > first_val:
                trend = "up"
            elif last_val < first_val:
                trend = "down"
            else:
                trend = "flat"

            # Change pct: guard division by zero
            if first_val != 0:
                change_pct = round((last_val - first_val) / abs(first_val) * 100, 2)
            else:
                change_pct = None

            metrics[key] = {
                "avg": round(avg_val, 4),
                "min": round(min(values), 4),
                "max": round(max(values), 4),
                "sum": round(sum(values), 4),
                "count": len(values),
                "first": first_val,
                "last": last_val,
                "trend": trend,
                "change_pct": change_pct,
            }

        return {
            "after": after,
            "before": before,
            "count": count,
            "metrics": metrics,
        }

    def compare_periods(
        self,
        a_after: str, a_before: str,
        b_after: str, b_before: str,
    ) -> dict[str, Any]:
        """Compare two date ranges. Returns delta + pct_change per metric.

        Includes count mismatch warning if sample sizes differ >50%.
        """
        agg_a = self.aggregate(a_after, a_before)
        agg_b = self.aggregate(b_after, b_before)

        comparison: dict[str, Any] = {}
        all_keys = set(agg_a.get("metrics", {}).keys()) | set(agg_b.get("metrics", {}).keys())

        for key in sorted(all_keys):
            a_avg = agg_a.get("metrics", {}).get(key, {}).get("avg", 0)
            b_avg = agg_b.get("metrics", {}).get(key, {}).get("avg", 0)
            delta = round(b_avg - a_avg, 4)

            if a_avg != 0:
                change_pct = round(delta / abs(a_avg) * 100, 2)
            else:
                change_pct = None

            if b_avg > a_avg:
                direction = "up"
            elif b_avg < a_avg:
                direction = "down"
            else:
                direction = "flat"

            comparison[key] = {
                "a_avg": a_avg,
                "b_avg": b_avg,
                "delta": delta,
                "change_pct": change_pct,
                "direction": direction,
            }

        # Count mismatch warning
        a_count = agg_a.get("count", 0)
        b_count = agg_b.get("count", 0)
        warning = ""
        if a_count > 0 and b_count > 0:
            ratio = min(a_count, b_count) / max(a_count, b_count)
            if ratio < 0.5:
                warning = f"Unequal sample sizes: period_a={a_count}, period_b={b_count}"

        return {
            "period_a": {"after": a_after, "before": a_before, "count": a_count, "aggregation": agg_a.get("metrics", {})},
            "period_b": {"after": b_after, "before": b_before, "count": b_count, "aggregation": agg_b.get("metrics", {})},
            "comparison": comparison,
            "warning": warning,
        }

    def get_period_preset(self, preset: str) -> dict[str, Any]:
        """Get aggregation or comparison for a preset period.

        Presets use full days excluding today.
        "7d" = last 7 complete days (yesterday back 7), compared to previous 7.
        """
        valid_presets = {"24h": 1, "7d": 7, "30d": 30, "90d": 90}
        if preset not in valid_presets:
            raise ValueError(f"Invalid preset '{preset}'. Must be one of: {', '.join(valid_presets)}")

        days = valid_presets[preset]
        today = datetime.now(timezone.utc).date()

        # Period B (recent): yesterday back N days
        b_before = today.isoformat()  # exclusive: today not included
        b_after = (today - timedelta(days=days)).isoformat()

        # Period A (previous): the N days before period B
        a_before = b_after
        a_after = (today - timedelta(days=days * 2)).isoformat()

        return self.compare_periods(a_after, a_before, b_after, b_before)

    def _validate_range(self, after: str, before: str) -> None:
        """Validate date range. Max 365 days."""
        try:
            a = datetime.fromisoformat(after).date() if "T" not in after else datetime.fromisoformat(after.replace("Z", "+00:00")).date()
            b = datetime.fromisoformat(before).date() if "T" not in before else datetime.fromisoformat(before.replace("Z", "+00:00")).date()
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid date format: {e}")

        span = (b - a).days
        if span > self.MAX_RANGE_DAYS:
            raise ValueError(f"Range spans {span} days — max is {self.MAX_RANGE_DAYS}")
        if span < 0:
            raise ValueError("'after' must be before 'before'")
'''


# ═══════════════════════════════════════════════════════════════════
# NEW ENDPOINTS for autonomous.py
# ═══════════════════════════════════════════════════════════════════

ROUTER_ENDPOINTS = '''

# ── Metrics Time-Range Aggregation (P-6) ──

@router.get("/metrics/range")
async def metrics_range(
    request: Request,
    after: str = "",
    before: str = "",
) -> dict[str, Any]:
    """Query metric snapshots within a date range."""
    if not after or not before:
        raise HTTPException(400, "Both 'after' and 'before' query params required (ISO date)")
    svc = _svc(request, "metrics_service")
    try:
        snapshots = svc.query_range(after, before)
        return {"after": after, "before": before, "count": len(snapshots), "snapshots": snapshots}
    except ValueError as e:
        raise HTTPException(400, str(e))

@router.get("/metrics/aggregate")
async def metrics_aggregate(
    request: Request,
    preset: str = "",
    after: str = "",
    before: str = "",
) -> dict[str, Any]:
    """Aggregate metrics over a time range or preset period."""
    svc = _svc(request, "metrics_service")
    try:
        if preset:
            # Preset returns comparison (includes aggregation for both periods)
            return svc.get_period_preset(preset)
        elif after and before:
            return svc.aggregate(after, before)
        else:
            raise HTTPException(400, "Provide 'preset' (24h/7d/30d/90d) or 'after' + 'before' params")
    except ValueError as e:
        raise HTTPException(400, str(e))

@router.get("/metrics/compare")
async def metrics_compare(
    request: Request,
    preset: str = "",
    a_after: str = "",
    a_before: str = "",
    b_after: str = "",
    b_before: str = "",
) -> dict[str, Any]:
    """Compare metrics between two time periods."""
    svc = _svc(request, "metrics_service")
    try:
        if preset:
            return svc.get_period_preset(preset)
        elif a_after and a_before and b_after and b_before:
            return svc.compare_periods(a_after, a_before, b_after, b_before)
        else:
            raise HTTPException(400, "Provide 'preset' or all four params: a_after, a_before, b_after, b_before")
    except ValueError as e:
        raise HTTPException(400, str(e))

'''


def deploy():
    errors = []

    # ═══════════════════════════════════════════════════════════════
    # 1. PATCH metrics_service.py
    # ═══════════════════════════════════════════════════════════════
    print("1/2 Patching metrics_service.py...")

    svc_path = BACKEND / "app" / "services" / "metrics_service.py"
    svc = svc_path.read_text()

    # Insert new methods after get_trends
    old_trends = '''    def get_trends(self, days: int = 7) -> list[dict[str, Any]]:
        """Get metric trends over N days."""
        return self._snapshots[-days:]'''

    new_trends = old_trends + METRICS_METHODS

    if old_trends in svc:
        svc = svc.replace(old_trends, new_trends)
    elif "query_range" in svc:
        print("  ⚠️ Already patched")
    else:
        errors.append("get_trends patch target not found")
        print("  ❌ Patch target not found")

    svc_path.write_text(svc)
    try:
        compile(svc_path.read_text(), str(svc_path), "exec")
        print("  ✅ metrics_service.py compiles")
    except SyntaxError as e:
        errors.append(f"metrics_service.py: {e}")
        print(f"  ❌ {e}")

    # ═══════════════════════════════════════════════════════════════
    # 2. PATCH autonomous.py router
    # ═══════════════════════════════════════════════════════════════
    print("2/2 Patching autonomous.py router...")

    aut_path = BACKEND / "app" / "api" / "routers" / "autonomous.py"
    aut = aut_path.read_text()

    # Add Query import
    aut = aut.replace(
        "from fastapi import APIRouter, HTTPException, Request",
        "from fastapi import APIRouter, HTTPException, Query, Request",
    )

    # Insert new endpoints before prompt-optimization
    if "metrics/range" not in aut:
        aut = aut.replace(
            '@router.get("/prompt-optimization")',
            ROUTER_ENDPOINTS + '@router.get("/prompt-optimization")',
        )
    else:
        print("  ⚠️ Endpoints already present")

    aut_path.write_text(aut)
    try:
        compile(aut_path.read_text(), str(aut_path), "exec")
        print("  ✅ autonomous.py compiles")
    except SyntaxError as e:
        errors.append(f"autonomous.py: {e}")
        print(f"  ❌ {e}")

    # ═══════════════════════════════════════════════════════════════
    # SUMMARY
    # ═══════════════════════════════════════════════════════════════
    print()
    if errors:
        print(f"⛔ {len(errors)} ERRORS:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("✅ P-6 deployed successfully")
        print()
        print("Restart backend, then validate:")
        print()
        print('  TOKEN=$(cat ~/.nemoclaw/cc-token)')
        print()
        print('  # 1. Take a snapshot (so there is data)')
        print('  curl -s -X POST -H "Authorization: Bearer $TOKEN" \\')
        print('    http://127.0.0.1:8100/api/autonomous/self-audit | python3 -m json.tool')
        print()
        print('  # 2. Range query')
        print('  curl -s -H "Authorization: Bearer $TOKEN" \\')
        print('    "http://127.0.0.1:8100/api/autonomous/metrics/range?after=2026-01-01&before=2026-12-31" | python3 -m json.tool')
        print()
        print('  # 3. Aggregate with dates')
        print('  curl -s -H "Authorization: Bearer $TOKEN" \\')
        print('    "http://127.0.0.1:8100/api/autonomous/metrics/aggregate?after=2026-01-01&before=2026-12-31" | python3 -m json.tool')
        print()
        print('  # 4. Aggregate with preset')
        print('  curl -s -H "Authorization: Bearer $TOKEN" \\')
        print('    "http://127.0.0.1:8100/api/autonomous/metrics/aggregate?preset=30d" | python3 -m json.tool')
        print()
        print('  # 5. Compare with preset')
        print('  curl -s -H "Authorization: Bearer $TOKEN" \\')
        print('    "http://127.0.0.1:8100/api/autonomous/metrics/compare?preset=7d" | python3 -m json.tool')
        print()
        print('  # 6. Error: missing params')
        print('  curl -s -H "Authorization: Bearer $TOKEN" \\')
        print('    "http://127.0.0.1:8100/api/autonomous/metrics/aggregate" | python3 -m json.tool')
        print()
        print('  # 7. Error: invalid preset')
        print('  curl -s -H "Authorization: Bearer $TOKEN" \\')
        print('    "http://127.0.0.1:8100/api/autonomous/metrics/aggregate?preset=999d" | python3 -m json.tool')
        print()
        print('  # 8. Existing endpoints still work')
        print('  curl -s -H "Authorization: Bearer $TOKEN" \\')
        print('    http://127.0.0.1:8100/api/autonomous/dashboard | python3 -c "import json,sys; d=json.load(sys.stdin); print(\'Dashboard keys:\', list(d.keys()))"')
        print()
        print('  # 9. Regression')
        print('  cd ~/nemoclaw-local-foundation && bash scripts/full_regression.sh')
        print()
        print('  # 10. Commit')
        print('  git add -A && git status')
        print('  git commit -m "feat(engine): P-6 metrics time-range aggregation — range queries, period comparison, presets, trend detection"')
        print('  git push origin main')


if __name__ == "__main__":
    deploy()
