#!/usr/bin/env python3
"""
NemoClaw Routing Resolver v1.1.0
Shared module for resolving LLM routing through config/routing/routing-config.yaml.
Enforces architecture lock L-003: never hardcode provider/model in skills.
"""

import logging
import os
import sys
import threading
from pathlib import Path

logger = logging.getLogger("nemoclaw.routing")

REPO = Path(__file__).resolve().parents[1]
ROUTING_CONFIG = REPO / "config" / "routing" / "routing-config.yaml"
ENV_FILE = REPO / "config" / ".env"

_routing_cache = None
_env_cache = None
_cache_lock = threading.Lock()


def _load_yaml(path):
    """Load a YAML file with error handling."""
    import yaml
    try:
        with open(path) as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        logger.error(f"Routing config not found: {path}")
        raise FileNotFoundError(
            f"NemoClaw routing config missing: {path}\n"
            f"Expected at: {ROUTING_CONFIG}\n"
            f"Run 'python3 scripts/validate.py' to diagnose."
        )
    except yaml.YAMLError as e:
        logger.error(f"Malformed YAML in {path}: {e}")
        raise ValueError(
            f"NemoClaw routing config is malformed: {path}\n"
            f"YAML error: {e}"
        )


def load_routing_config():
    """Load and cache the routing config from YAML (thread-safe)."""
    global _routing_cache
    if _routing_cache is not None:
        return _routing_cache
    with _cache_lock:
        if _routing_cache is not None:
            return _routing_cache
        cfg = _load_yaml(ROUTING_CONFIG)
        if not isinstance(cfg, dict) or "providers" not in cfg:
            raise ValueError(
                f"Routing config missing 'providers' key: {ROUTING_CONFIG}"
            )
        _routing_cache = cfg
        return cfg


def load_env():
    """Load API keys from config/.env (thread-safe)."""
    global _env_cache
    if _env_cache is not None:
        return _env_cache
    with _cache_lock:
        if _env_cache is not None:
            return _env_cache
        keys = {}
        if ENV_FILE.exists():
            with open(ENV_FILE) as f:
                for ln in f:
                    ln = ln.strip()
                    if "=" in ln and not ln.startswith("#"):
                        a, b = ln.split("=", 1)
                        keys[a.strip()] = b.strip()
        _env_cache = keys
        return keys


def resolve_alias(task_class="moderate"):
    """Resolve a task class to (provider, model, estimated_cost) using routing config."""
    cfg = load_routing_config()
    providers = cfg.get("providers", {})
    rules = cfg.get("routing_rules", {})
    default_alias = cfg.get("defaults", {}).get("default_alias", "cheap_openai")

    alias = rules.get(task_class, default_alias)
    if alias not in providers:
        alias = default_alias

    entry = providers.get(alias)
    if entry is None:
        # Last resort: use the first available provider
        if providers:
            alias = next(iter(providers))
            entry = providers[alias]
            logger.warning(f"Default alias '{default_alias}' not in providers, falling back to '{alias}'")
        else:
            raise ValueError("No providers defined in routing-config.yaml")

    return entry["provider"], entry["model"], entry.get("estimated_cost_per_call", 0.01)


def resolve_from_env_or_config(task_class="moderate"):
    """Resolve routing: check CC_LLM_PROVIDER/CC_LLM_MODEL env vars first, then config."""
    p = os.environ.get("CC_LLM_PROVIDER", "")
    m = os.environ.get("CC_LLM_MODEL", "")
    if p and m:
        cfg = load_routing_config()
        providers = cfg.get("providers", {})
        cost = 0.01
        for entry in providers.values():
            if entry.get("provider") == p and entry.get("model") == m:
                cost = entry.get("estimated_cost_per_call", 0.01)
                break
        return p, m, cost
    return resolve_alias(task_class)


def get_api_key(provider):
    """Get the API key for a provider."""
    env = load_env()
    key_map = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "google": "GOOGLE_API_KEY",
    }
    env_var = key_map.get(provider, "")
    return env.get(env_var, os.environ.get(env_var, ""))


def call_llm(messages, task_class="moderate", max_tokens=4000):
    """Route an LLM call through the config-driven routing system.

    Args:
        messages: List of dicts with 'role' and 'content' keys,
                  or LangChain message objects.
        task_class: Routing task class (e.g. 'moderate', 'complex_reasoning',
                    'structured_short', 'general_short', 'premium').
        max_tokens: Maximum tokens for the response.

    Returns:
        Tuple of (response_text, error_string_or_None).
    """
    provider, model, cost = resolve_from_env_or_config(task_class)
    api_key = get_api_key(provider)

    if not api_key:
        return None, f"{provider.upper()} API key not found"

    try:
        from langchain_core.messages import HumanMessage, SystemMessage

        lc_messages = []
        for m in messages:
            if isinstance(m, dict):
                if m.get("role") == "system":
                    lc_messages.append(SystemMessage(content=m["content"]))
                else:
                    lc_messages.append(HumanMessage(content=m["content"]))
            else:
                lc_messages.append(m)

        if provider == "anthropic":
            from langchain_anthropic import ChatAnthropic
            llm = ChatAnthropic(model=model, max_tokens=max_tokens, api_key=api_key)
        elif provider == "google":
            from langchain_google_genai import ChatGoogleGenerativeAI
            llm = ChatGoogleGenerativeAI(
                model=model, max_output_tokens=max_tokens, google_api_key=api_key
            )
        else:
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(model=model, max_tokens=max_tokens, api_key=api_key)

        result = llm.invoke(lc_messages)
        return result.content, None
    except Exception as e:
        return None, str(e)


def estimate_cost(task_class="moderate"):
    """Return estimated cost per call for a task class."""
    _, _, cost = resolve_alias(task_class)
    return cost
