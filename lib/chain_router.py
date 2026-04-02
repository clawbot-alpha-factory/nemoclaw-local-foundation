#!/usr/bin/env python3
"""
NemoClaw Chain Router v1.0.0
Multi-step cross-provider chain routing for tier 3/4 tasks.

Tier 1/2: delegates to call_llm() (single call).
Tier 3: 3-step chain — generate → review → improve (cross-provider).
Tier 4: 4-step chain — generate → critique → synthesize → validate (3 providers).

Model selection is dynamic via config/routing/model-rankings.yaml.
When new models release, update that file — all chains adapt automatically.
"""

import json
import logging
import subprocess
import sys
import threading
import time
from pathlib import Path

logger = logging.getLogger("nemoclaw.chain_router")

REPO = Path(__file__).resolve().parents[1]

# All config loading delegated to config_loader (mtime-cached, shared with routing.py)
from lib.config_loader import (
    load_routing_config,
    load_rankings,
    load_skill_domains,
    load_budget_config,
    get_api_key,
    lookup_skill_domain,
    BUDGET_CONFIG,
)


def get_tier(task_class):
    """Look up tier number for a task_class from routing-config.yaml tier_mapping."""
    cfg = load_routing_config()
    tier_map = cfg.get("tier_mapping", {})
    return tier_map.get(task_class, 2)


def _get_provider_for_ref(ref):
    """Resolve the provider for a model ref (alias name or executor name)."""
    rankings = load_rankings()

    # Check executors first
    executors = rankings.get("executors", {})
    if ref in executors:
        return executors[ref].get("provider", "unknown")

    # Check routing-config providers
    cfg = load_routing_config()
    providers = cfg.get("providers", {})
    if ref in providers:
        return providers[ref].get("provider", "unknown")

    return "unknown"


def _is_executor(ref):
    """Check if a ref is an agentic executor (not a plain API model)."""
    rankings = load_rankings()
    return ref in rankings.get("executors", {})


def _get_cost_for_ref(ref):
    """Get estimated cost for a ref."""
    rankings = load_rankings()
    executors = rankings.get("executors", {})
    if ref in executors:
        return executors[ref].get("cost_per_task", 0.50)

    cfg = load_routing_config()
    providers = cfg.get("providers", {})
    if ref in providers:
        return providers[ref].get("estimated_cost_per_call", 0.01)

    return 0.01


# ── Model Selection ──────────────────────────────────────────────────────────

def select_models_for_chain(task_domain, tier):
    """Select models for each chain step based on task domain and tier.

    Enforces cross-provider diversity: adjacent steps use different providers.
    Tier 4 uses 3 distinct providers across the chain.

    Returns:
        List of dicts: [{ref, role, provider, prompt_prefix, is_executor, cost}, ...]
    """
    rankings = load_rankings()
    domains = rankings.get("task_domains", {})
    templates = rankings.get("chain_templates", {})

    domain_entry = domains.get(task_domain)
    if not domain_entry:
        logger.warning(f"Unknown task_domain '{task_domain}', falling back to 'research'")
        domain_entry = domains.get("research", {})

    template_key = f"tier_{tier}"
    template = templates.get(template_key)
    if not template:
        logger.error(f"No chain template for {template_key}")
        return []

    chain_steps = []
    used_providers = []

    for step_def in template["steps"]:
        role = step_def["role"]
        source = step_def["source"]
        prompt_prefix = step_def.get("prompt_prefix", "")

        # Resolve the ref from source
        if source == "rank_1":
            ref = domain_entry.get("rank_1", {}).get("ref")
        elif source == "rank_2":
            ref = domain_entry.get("rank_2", {}).get("ref")
        elif source == "rank_3":
            ref = domain_entry.get("rank_3", {}).get("ref")
        elif source == "review":
            ref = domain_entry.get("review", {}).get("ref")
        elif source == "premium_claude":
            ref = "premium_claude"
        else:
            ref = source

        if not ref:
            logger.warning(f"No ref resolved for role={role}, source={source}")
            continue

        provider = _get_provider_for_ref(ref)

        # Enforce cross-provider diversity for reviewer/critic/validator
        if role in ("reviewer", "critic", "validator") and used_providers:
            if provider == used_providers[-1]:
                # Try to find alternate from a different rank
                for alt_key in ["rank_2", "rank_3", "review", "rank_1"]:
                    alt_entry = domain_entry.get(alt_key, {})
                    alt_ref = alt_entry.get("ref") if isinstance(alt_entry, dict) else None
                    if alt_ref and _get_provider_for_ref(alt_ref) != used_providers[-1]:
                        ref = alt_ref
                        provider = _get_provider_for_ref(ref)
                        break

        chain_steps.append({
            "ref": ref,
            "role": role,
            "provider": provider,
            "prompt_prefix": prompt_prefix,
            "is_executor": _is_executor(ref),
            "cost": _get_cost_for_ref(ref),
        })
        used_providers.append(provider)

    return chain_steps


# ── Step Execution ───────────────────────────────────────────────────────────

def _call_model(ref, messages, max_tokens=4000):
    """Execute a single LLM API call via routing.py."""
    from lib.routing import call_llm
    return call_llm(messages, task_class=ref, max_tokens=max_tokens)


def _call_model_direct(ref, messages, max_tokens=4000):
    """Call a model by its provider alias directly (bypassing routing_rules).

    Reuses routing.py's _build_llm and _to_lc_messages to avoid duplication.
    Used when the chain router has already resolved the specific alias.
    """
    from lib.routing import _build_llm, _to_lc_messages
    cfg = load_routing_config()
    providers = cfg.get("providers", {})

    entry = providers.get(ref)
    if not entry:
        # ref is a routing rule name, not a provider alias — use call_llm
        return _call_model(ref, messages, max_tokens)

    provider = entry["provider"]
    model = entry["model"]
    api_key = get_api_key(provider)

    if not api_key:
        return None, f"{provider.upper()} API key not found"

    try:
        lc_messages = _to_lc_messages(messages)
        llm = _build_llm(provider, model, api_key, max_tokens)
        result = llm.invoke(lc_messages)
        return result.content, None
    except Exception as e:
        return None, str(e)


def _run_executor(ref, messages, context=None):
    """Dispatch to an agentic executor (Claude Code or Codex).

    Returns (response_text, error_or_None).
    """
    rankings = load_rankings()
    executor = rankings.get("executors", {}).get(ref)
    if not executor:
        return None, f"Unknown executor: {ref}"

    invoke_cmd = executor.get("invoke", "")
    if not invoke_cmd:
        return None, f"No invoke command for executor: {ref}"

    # Build prompt from messages
    prompt_parts = []
    for m in messages:
        if isinstance(m, dict):
            prompt_parts.append(m.get("content", ""))
        else:
            prompt_parts.append(str(m))
    prompt = "\n\n".join(prompt_parts)

    try:
        if ref == "claude_code":
            result = subprocess.run(
                ["claude", "--print", "--dangerously-skip-permissions", "-p", prompt],
                capture_output=True, text=True, timeout=300,
                cwd=str(REPO),
            )
            if result.returncode != 0:
                return None, f"Claude Code error: {result.stderr[:500]}"
            return result.stdout, None

        elif ref == "codex":
            result = subprocess.run(
                ["codex", "--quiet", "--approval-mode", "full-auto", "-p", prompt],
                capture_output=True, text=True, timeout=300,
                cwd=str(REPO),
            )
            if result.returncode != 0:
                return None, f"Codex error: {result.stderr[:500]}"
            return result.stdout, None

        else:
            return None, f"Unsupported executor: {ref}"

    except FileNotFoundError:
        logger.warning(f"Executor '{ref}' not found on PATH, falling back to API model")
        # Fall back to the executor's underlying model via API
        model_alias = _executor_fallback_alias(ref)
        return _call_model_direct(model_alias, messages)
    except subprocess.TimeoutExpired:
        return None, f"Executor '{ref}' timed out after 300s"


def _executor_fallback_alias(ref):
    """Map an executor to its fallback API alias when the CLI is unavailable."""
    fallbacks = {
        "claude_code": "premium_claude",
        "codex": "reasoning_openai",
    }
    return fallbacks.get(ref, "reasoning_claude")


def _log_chain_spend(step_info, task_class, task_domain):
    """Log chain step spend to provider-usage.jsonl (same format as budget-enforcer)."""
    from datetime import datetime, timezone
    log_path = Path.home() / ".nemoclaw" / "logs" / "provider-usage.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "task_class": task_class,
        "alias_selected": step_info["ref"],
        "model_used": "",
        "provider": step_info["provider"],
        "estimated_cost_usd": step_info["cost"],
        "chain_role": step_info["role"],
        "chain_domain": task_domain,
        "fallback_used": False,
    }

    # Resolve model name
    cfg = load_routing_config()
    providers = cfg.get("providers", {})
    alias_entry = providers.get(step_info["ref"], {})
    entry["model_used"] = alias_entry.get("model", step_info["ref"])

    try:
        with open(log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        logger.warning(f"Failed to log chain spend: {e}")


def _check_provider_budget(provider):
    """Check if provider budget is exhausted. Returns (ok, message)."""
    spend_path = Path.home() / ".nemoclaw" / "logs" / "provider-spend.json"

    if not spend_path.exists():
        return True, "no budget data"

    try:
        with open(spend_path) as f:
            spend = json.load(f)
        budget_cfg = load_budget_config()

        provider_spend = spend.get(provider, {})
        cumulative = provider_spend.get("cumulative_spend_usd", 0)
        budget_entry = budget_cfg.get("budgets", {}).get(provider, {})
        limit = budget_entry.get("total_usd", 100.0)

        # Free-tier providers (total_usd=0) are rate-limited, not budget-limited
        if limit == 0:
            return True, f"{provider} free tier (rate-limited only)"

        if cumulative >= limit:
            return False, f"{provider} budget exhausted: ${cumulative:.2f}/${limit:.2f}"
        return True, f"${cumulative:.2f}/${limit:.2f}"
    except Exception:
        return True, "budget check failed (allowing)"


def _execute_step(step_info, messages, max_tokens=4000):
    """Execute a single chain step — model API call or agentic executor.

    Checks provider budget before execution and logs spend after.
    Returns (response_text, error_or_None).
    """
    ref = step_info["ref"]
    provider = step_info["provider"]

    # Budget gate
    ok, msg = _check_provider_budget(provider)
    if not ok:
        logger.warning(f"  [chain] budget blocked for {ref}: {msg}")
        return None, f"Budget exhausted for {provider}: {msg}"

    if step_info["is_executor"]:
        return _run_executor(ref, messages)
    else:
        return _call_model_direct(ref, messages, max_tokens)


# ── Chain Execution ──────────────────────────────────────────────────────────

def _estimate_confidence(output: str) -> float:
    """Estimate output confidence based on structure and length heuristics."""
    score = 0.5
    if len(output) > 200:
        score += 0.1
    if len(output) > 500:
        score += 0.05
    if "##" in output:
        score += 0.1
    if "- " in output or "1." in output:
        score += 0.05
    if len(output) > 1000:
        score += 0.05
    if any(w in output.lower() for w in ["conclusion", "summary", "recommendation"]):
        score += 0.05
    return min(score, 1.0)


def call_chain(messages, task_class="premium", task_domain=None, max_tokens=4000):
    """Execute a chain-routed LLM call for tier 3/4 tasks.

    For tier 1/2 or when task_domain is None, falls back to single call_llm().

    Args:
        messages: List of dicts with 'role' and 'content' keys.
        task_class: Routing task class (determines tier).
        task_domain: Task domain for model selection (e.g., 'coding', 'research').
        max_tokens: Maximum tokens per step.

    Returns:
        Tuple of (final_response, chain_metadata, error_string_or_None).
        chain_metadata contains: tier, task_domain, steps (list of step results),
        total_cost, models_used.
    """
    tier = get_tier(task_class)

    # Tier 1/2 or no domain: single call
    if tier < 3 or not task_domain:
        from lib.routing import call_llm
        response, err = call_llm(messages, task_class, max_tokens)
        meta = {
            "tier": tier,
            "task_domain": task_domain,
            "chain_used": False,
            "steps": [],
            "total_cost": 0,
            "models_used": [],
        }
        return response, meta, err

    # Tier 3/4: build and execute chain
    chain_steps = select_models_for_chain(task_domain, tier)
    if not chain_steps:
        # Fallback to single call
        from lib.routing import call_llm
        response, err = call_llm(messages, task_class, max_tokens)
        meta = {"tier": tier, "chain_used": False, "fallback_reason": "no chain steps resolved"}
        return response, meta, err

    # Check budget cap
    rankings = load_rankings()
    templates = rankings.get("chain_templates", {})
    budget_cap = templates.get(f"tier_{tier}", {}).get("budget_cap_per_chain", 1.0)
    estimated_total = sum(s["cost"] for s in chain_steps)
    if estimated_total > budget_cap:
        logger.warning(
            f"Chain cost ${estimated_total:.3f} exceeds cap ${budget_cap:.2f}, "
            f"trimming to essential steps"
        )
        # Keep generator + reviewer only (first 2 steps)
        chain_steps = chain_steps[:2]

    # Execute chain
    step_results = []
    current_output = None
    total_cost = 0
    t0 = time.time()

    # Extract the original user content from messages
    original_content = ""
    for m in messages:
        if isinstance(m, dict):
            original_content += m.get("content", "") + "\n"
        else:
            original_content += str(m) + "\n"

    for i, step_info in enumerate(chain_steps):
        # Confidence gating: skip steps marked by previous gating
        if step_info.get("_skipped"):
            logger.info(f"  [chain] step {i+1} ({step_info['role']}) SKIPPED (confidence gate)")
            continue

        role = step_info["role"]
        prompt_prefix = step_info["prompt_prefix"]
        ref = step_info["ref"]
        provider = step_info["provider"]

        step_t0 = time.time()

        # Build step-specific messages
        if role == "generator":
            step_messages = [
                {"role": "system", "content": prompt_prefix},
                {"role": "user", "content": original_content},
            ]
        elif role in ("reviewer", "critic"):
            step_messages = [
                {"role": "system", "content": prompt_prefix},
                {"role": "user", "content": (
                    f"## Original Task\n{original_content}\n\n"
                    f"## Output to Review\n{current_output}"
                )},
            ]
        elif role == "improver":
            # Improver gets: original task + previous output + review feedback
            step_messages = [
                {"role": "system", "content": prompt_prefix},
                {"role": "user", "content": (
                    f"## Original Task\n{original_content}\n\n"
                    f"## Previous Output\n{step_results[0]['output']}\n\n"
                    f"## Review Feedback\n{step_results[-1]['output']}"
                )},
            ]
        elif role == "synthesizer":
            # Synthesizer gets everything: task + initial output + all critiques
            critique_text = "\n\n".join(
                f"### {sr['role'].title()} ({sr['ref']})\n{sr['output']}"
                for sr in step_results[1:]  # skip generator
            )
            step_messages = [
                {"role": "system", "content": prompt_prefix},
                {"role": "user", "content": (
                    f"## Original Task\n{original_content}\n\n"
                    f"## Initial Output\n{step_results[0]['output']}\n\n"
                    f"## Critiques and Reviews\n{critique_text}"
                )},
            ]
        elif role == "validator":
            step_messages = [
                {"role": "system", "content": prompt_prefix},
                {"role": "user", "content": (
                    f"## Original Task\n{original_content}\n\n"
                    f"## Final Output to Validate\n{current_output}"
                )},
            ]
        else:
            step_messages = [
                {"role": "system", "content": prompt_prefix},
                {"role": "user", "content": current_output or original_content},
            ]

        # Execute
        logger.info(f"  [chain] step {i+1}/{len(chain_steps)}: {role} via {ref} ({provider})")
        print(f"    [chain] step {i+1}/{len(chain_steps)}: {role} → {ref} ({provider})")

        response, err = _execute_step(step_info, step_messages, max_tokens)

        step_elapsed = time.time() - step_t0
        step_cost = step_info["cost"]
        total_cost += step_cost

        step_result = {
            "step": i + 1,
            "role": role,
            "ref": ref,
            "provider": provider,
            "is_executor": step_info["is_executor"],
            "output": response,
            "error": err,
            "cost": step_cost,
            "elapsed_s": round(step_elapsed, 2),
        }
        step_results.append(step_result)

        # Log spend for this chain step
        if not err:
            _log_chain_spend(step_info, task_class, task_domain)

        if err:
            logger.error(f"  [chain] step {i+1} failed: {err}")
            if role == "generator":
                return None, {"tier": tier, "chain_used": True, "steps": step_results}, err
            logger.warning(f"  [chain] continuing with last good output after {role} failure")
            continue

        current_output = response

        # ── Confidence gating: skip unnecessary steps ─────────────────
        if response and role in ("generator", "reviewer"):
            confidence = _estimate_confidence(response)
            step_result["confidence"] = confidence
            remaining_roles = [s["role"] for s in chain_steps[i+1:]]
            if confidence >= 0.85 and role == "generator" and "reviewer" in remaining_roles:
                logger.info(f"  [chain] confidence {confidence:.2f} — skipping reviewer")
                skip_next = True
                for j in range(i+1, len(chain_steps)):
                    if chain_steps[j]["role"] == "reviewer":
                        chain_steps[j]["_skipped"] = True
                        break
            elif confidence >= 0.90 and role == "reviewer" and "critic" in remaining_roles:
                logger.info(f"  [chain] confidence {confidence:.2f} — skipping critic")
                for j in range(i+1, len(chain_steps)):
                    if chain_steps[j]["role"] == "critic":
                        chain_steps[j]["_skipped"] = True
                        break

    elapsed = time.time() - t0

    meta = {
        "tier": tier,
        "task_domain": task_domain,
        "chain_used": True,
        "steps": step_results,
        "total_cost": round(total_cost, 4),
        "models_used": [s["ref"] for s in chain_steps],
        "providers_used": list(dict.fromkeys(s["provider"] for s in chain_steps)),
        "elapsed_s": round(elapsed, 2),
    }

    # Final output selection logic:
    # - If chain was trimmed (no improver/synthesizer), use generator output
    # - For reviewer-only chains, the review is feedback, not the deliverable
    successful_roles = [s["role"] for s in step_results if not s.get("error")]
    if "improver" not in successful_roles and "synthesizer" not in successful_roles:
        # Chain was trimmed or no improver ran — generator output is the deliverable
        generator_output = next(
            (s["output"] for s in step_results if s["role"] == "generator" and s["output"]),
            current_output,
        )
        current_output = generator_output
        meta["trimmed"] = True

    # For tier 4 with validator: if validator says APPROVED, use synthesizer output
    if tier == 4 and len(step_results) >= 4:
        validator_output = step_results[-1].get("output", "")
        if validator_output and "APPROVED" in validator_output.upper():
            # Use synthesizer output (step 3) as final
            synthesizer_output = step_results[-2].get("output")
            if synthesizer_output:
                current_output = synthesizer_output
                meta["validator_approved"] = True
        else:
            meta["validator_approved"] = False
            meta["validator_concerns"] = validator_output

    return current_output, meta, None
