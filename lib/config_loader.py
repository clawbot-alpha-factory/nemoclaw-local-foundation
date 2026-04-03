#!/usr/bin/env python3
"""
NemoClaw Config Loader v1.0.0
Shared config loading with mtime-based cache invalidation.

This module is the single source of truth for loading:
  - routing-config.yaml (aliases, routing rules, tier mapping)
  - model-rankings.yaml (task domains, chain templates, executors)
  - capability-registry.yaml (skill_domains mapping)
  - budget-config.yaml (provider budgets)
  - config/.env (API keys)

Both lib/routing.py and lib/chain_router.py import from here,
eliminating the circular dependency between them.
"""

import logging
import os
import threading
from pathlib import Path

logger = logging.getLogger("nemoclaw.config")

REPO = Path(__file__).resolve().parents[1]
ROUTING_CONFIG = REPO / "config" / "routing" / "routing-config.yaml"
RANKINGS_CONFIG = REPO / "config" / "routing" / "model-rankings.yaml"
CAPABILITY_REGISTRY = REPO / "config" / "agents" / "capability-registry.yaml"
BUDGET_CONFIG = REPO / "config" / "routing" / "budget-config.yaml"
BACKENDS_CONFIG = REPO / "config" / "execution" / "backends.yaml"
ENV_FILE = REPO / "config" / ".env"

_cache_lock = threading.Lock()

# Cache entries: (data, mtime) tuples — invalidated when file changes
_routing_cache = (None, 0.0)
_rankings_cache = (None, 0.0)
_skill_domains_cache = (None, 0.0)
_budget_cache = (None, 0.0)
_backends_cache = (None, 0.0)
_env_cache = (None, 0.0)


def _load_yaml(path):
    """Load a YAML file with error handling."""
    import yaml
    try:
        with open(path) as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Config not found: {path}")
    except yaml.YAMLError as e:
        raise ValueError(f"Malformed YAML in {path}: {e}")


def _get_mtime(path):
    """Get file modification time, or 0 if not found."""
    try:
        return path.stat().st_mtime
    except (FileNotFoundError, OSError):
        return 0.0


def _load_cached(path, cache_tuple):
    """Load from cache if file hasn't changed, otherwise reload.

    Args:
        path: Path to the YAML file.
        cache_tuple: (data, mtime) tuple from the module-level cache.

    Returns:
        (data, new_cache_tuple)
    """
    data, cached_mtime = cache_tuple
    current_mtime = _get_mtime(path)
    if data is not None and current_mtime == cached_mtime:
        return data, cache_tuple
    # Reload
    new_data = _load_yaml(path)
    return new_data, (new_data, current_mtime)


def load_routing_config():
    """Load routing-config.yaml with mtime-based cache invalidation (thread-safe)."""
    global _routing_cache
    data, _ = _routing_cache
    mtime = _get_mtime(ROUTING_CONFIG)
    if data is not None and mtime == _routing_cache[1]:
        return data
    with _cache_lock:
        data, _routing_cache = _load_cached(ROUTING_CONFIG, _routing_cache)
        if not isinstance(data, dict) or "providers" not in data:
            raise ValueError(f"Routing config missing 'providers' key: {ROUTING_CONFIG}")
        return data


def load_rankings():
    """Load model-rankings.yaml with mtime-based cache invalidation (thread-safe)."""
    global _rankings_cache
    data, _ = _rankings_cache
    mtime = _get_mtime(RANKINGS_CONFIG)
    if data is not None and mtime == _rankings_cache[1]:
        return data
    with _cache_lock:
        data, _rankings_cache = _load_cached(RANKINGS_CONFIG, _rankings_cache)
        return data


def load_skill_domains():
    """Load skill_domains from capability-registry.yaml (thread-safe, mtime-cached)."""
    global _skill_domains_cache
    data, _ = _skill_domains_cache
    mtime = _get_mtime(CAPABILITY_REGISTRY)
    if data is not None and mtime == _skill_domains_cache[1]:
        return data
    with _cache_lock:
        full_data, _skill_domains_cache = _load_cached(CAPABILITY_REGISTRY, _skill_domains_cache)
        domains = full_data.get("skill_domains", {}) if isinstance(full_data, dict) else {}
        # Store just the domains dict but keep the full mtime
        _skill_domains_cache = (domains, _skill_domains_cache[1])
        return domains


def load_budget_config():
    """Load budget-config.yaml with mtime-based cache invalidation (thread-safe)."""
    global _budget_cache
    data, _ = _budget_cache
    mtime = _get_mtime(BUDGET_CONFIG)
    if data is not None and mtime == _budget_cache[1]:
        return data
    with _cache_lock:
        data, _budget_cache = _load_cached(BUDGET_CONFIG, _budget_cache)
        return data


def load_backends_config():
    """Load config/execution/backends.yaml with mtime-based cache invalidation (thread-safe)."""
    global _backends_cache
    data, _ = _backends_cache
    mtime = _get_mtime(BACKENDS_CONFIG)
    if data is not None and mtime == _backends_cache[1]:
        return data
    with _cache_lock:
        data, _backends_cache = _load_cached(BACKENDS_CONFIG, _backends_cache)
        return data


def load_env():
    """Load API keys from config/.env with mtime-based cache invalidation (thread-safe)."""
    global _env_cache
    data, _ = _env_cache
    mtime = _get_mtime(ENV_FILE)
    if data is not None and mtime == _env_cache[1]:
        return data
    with _cache_lock:
        current_mtime = _get_mtime(ENV_FILE)
        if _env_cache[0] is not None and current_mtime == _env_cache[1]:
            return _env_cache[0]
        keys = {}
        if ENV_FILE.exists():
            with open(ENV_FILE) as f:
                for ln in f:
                    ln = ln.strip()
                    if "=" in ln and not ln.startswith("#"):
                        a, b = ln.split("=", 1)
                        keys[a.strip()] = b.strip()
        _env_cache = (keys, current_mtime)
        return keys


def lookup_skill_domain(skill_id):
    """Look up task_domain for a skill from the capability registry."""
    domains = load_skill_domains()
    return domains.get(skill_id)


def get_api_key(provider):
    """Get the API key for a provider.

    Priority: OS environment variable > config/.env file.
    This ensures Railway/Docker env vars take precedence over the file.
    """
    key_map = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "google": "GOOGLE_API_KEY",
        "nvidia": "NVIDIA_INFERENCE_API_KEY",
    }
    env_var = key_map.get(provider, "")
    # Check OS env first (Railway, Docker, etc.), then fall back to config/.env
    os_val = os.environ.get(env_var, "")
    if os_val:
        return os_val
    env = load_env()
    return env.get(env_var, "")


def invalidate_all():
    """Force all caches to reload on next access."""
    global _routing_cache, _rankings_cache, _skill_domains_cache, _budget_cache, _env_cache
    with _cache_lock:
        _routing_cache = (None, 0.0)
        _rankings_cache = (None, 0.0)
        _skill_domains_cache = (None, 0.0)
        _budget_cache = (None, 0.0)
        _backends_cache = (None, 0.0)
        _env_cache = (None, 0.0)
