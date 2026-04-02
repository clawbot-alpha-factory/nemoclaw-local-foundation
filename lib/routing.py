#!/usr/bin/env python3
"""
NemoClaw Routing Resolver v1.2.0
Shared module for resolving LLM routing through config/routing/routing-config.yaml.
Enforces architecture lock L-003: never hardcode provider/model in skills.

v1.2.0 additions:
  - call_llm_structured(): Pydantic-validated structured output via Instructor
  - Langfuse observability: automatic tracing on all call_llm() calls
  - validate_output(): Guardrails AI content validation
"""

import logging
import os
import threading
from pathlib import Path
from typing import Optional, Type, TypeVar

T = TypeVar("T")

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
        "nvidia": "NVIDIA_INFERENCE_API_KEY",
    }
    env_var = key_map.get(provider, "")
    return env.get(env_var, os.environ.get(env_var, ""))


def call_llm(messages, task_class="moderate", max_tokens=4000):
    """Route an LLM call through the config-driven routing system.

    Automatically traces via Langfuse when configured (set LANGFUSE_PUBLIC_KEY
    and LANGFUSE_SECRET_KEY in config/.env). No-op if keys are absent.

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
        _init_langfuse()
        lc_messages = _to_lc_messages(messages)
        llm = _build_llm(provider, model, api_key, max_tokens)

        # Use @observe if Langfuse is configured, otherwise call directly
        observe = _get_langfuse_observe()
        if observe:
            @observe(name=f"call_llm/{task_class}/{model}")
            def _traced_invoke():
                return llm.invoke(lc_messages)
            result = _traced_invoke()
            # Flush asynchronously so we don't block
            try:
                from langfuse import Langfuse
                Langfuse().flush()
            except Exception:
                pass
        else:
            result = llm.invoke(lc_messages)

        content = result.content
        # NVIDIA reasoning models (Nemotron 9B) may return content via raw API
        # but LangChain strips it when reasoning_content is present.
        # Fall back to direct API call for these models.
        if not content and provider == "nvidia":
            content = _nvidia_direct_chat(model, api_key, messages, max_tokens)
        return content, None
    except Exception as e:
        return None, str(e)


def _nvidia_direct_chat(model, api_key, messages, max_tokens):
    """Direct NVIDIA NIM chat call bypassing LangChain (for reasoning models).

    Nemotron reasoning models return content=None when reasoning is enabled
    and the response goes to reasoning_content. This extracts from either field.
    """
    try:
        import httpx
        resp = httpx.post(
            "https://integrate.api.nvidia.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [{"role": m.get("role", "user"), "content": m["content"]}
                             for m in messages if isinstance(m, dict)],
                "max_tokens": max_tokens * 3,  # reasoning models need more budget
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        msg = resp.json()["choices"][0]["message"]
        # Prefer content, fall back to reasoning_content
        return msg.get("content") or msg.get("reasoning_content", "") or ""
    except Exception as e:
        logger.warning(f"NVIDIA direct chat fallback failed: {e}")
        return ""


def estimate_cost(task_class="moderate"):
    """Return estimated cost per call for a task class."""
    _, _, cost = resolve_alias(task_class)
    return cost


def call_llm_or_chain(messages, task_class="moderate", task_domain=None, max_tokens=4000):
    """Smart dispatcher: uses chain routing for tier 3/4 when task_domain is set.

    Drop-in replacement for call_llm() — skills can switch to this to get
    automatic chain routing when their step declares a task_domain.

    Args:
        messages: List of dicts with 'role' and 'content' keys.
        task_class: Routing task class (determines tier).
        task_domain: Task domain for model selection (e.g., 'coding', 'research').
                     If None, falls back to single call_llm().
        max_tokens: Maximum tokens per step.

    Returns:
        Tuple of (response_text, error_string_or_None).
        Chain metadata is logged but not returned (keeps interface compatible).
    """
    if not task_domain:
        return call_llm(messages, task_class, max_tokens)

    try:
        from lib.chain_router import call_chain, get_tier
        tier = get_tier(task_class)
        if tier < 3:
            return call_llm(messages, task_class, max_tokens)

        response, meta, err = call_chain(messages, task_class, task_domain, max_tokens)
        if meta and meta.get("chain_used"):
            logger.info(
                f"Chain completed: tier={meta['tier']}, domain={task_domain}, "
                f"cost=${meta.get('total_cost', 0):.4f}, "
                f"providers={meta.get('providers_used', [])}"
            )
        return response, err
    except Exception as e:
        logger.warning(f"Chain routing failed, falling back to single call: {e}")
        return call_llm(messages, task_class, max_tokens)


# ---------------------------------------------------------------------------
# Langfuse observability (opt-in, no-op if not configured)
# ---------------------------------------------------------------------------

_langfuse_initialized = False


def _init_langfuse():
    """Initialize Langfuse via environment variables. Call once at startup."""
    global _langfuse_initialized
    if _langfuse_initialized:
        return
    _langfuse_initialized = True
    env = load_env()
    pk = env.get("LANGFUSE_PUBLIC_KEY", "")
    sk = env.get("LANGFUSE_SECRET_KEY", "")
    host = env.get("LANGFUSE_HOST", "https://us.cloud.langfuse.com")
    if pk and sk:
        # Langfuse v4 reads from env vars automatically
        os.environ.setdefault("LANGFUSE_PUBLIC_KEY", pk)
        os.environ.setdefault("LANGFUSE_SECRET_KEY", sk)
        os.environ.setdefault("LANGFUSE_HOST", host)
        logger.info("Langfuse observability enabled (v4 OpenTelemetry)")


def _get_langfuse_observe():
    """Get the Langfuse observe decorator if available."""
    _init_langfuse()
    if not os.environ.get("LANGFUSE_PUBLIC_KEY"):
        return None
    try:
        from langfuse import observe
        return observe
    except ImportError:
        return None


def _build_llm(provider, model, api_key, max_tokens):
    """Build a LangChain LLM instance for the given provider."""
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=model, max_tokens=max_tokens, api_key=api_key)
    elif provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=model, max_output_tokens=max_tokens, google_api_key=api_key
        )
    elif provider == "nvidia":
        # NVIDIA NIM uses OpenAI-compatible API at integrate.api.nvidia.com
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model,
            max_tokens=max_tokens,
            api_key=api_key,
            base_url="https://integrate.api.nvidia.com/v1",
        )
    else:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=model, max_tokens=max_tokens, api_key=api_key)


def _to_lc_messages(messages):
    """Convert dict messages to LangChain message objects."""
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
    return lc_messages


# ---------------------------------------------------------------------------
# Instructor: structured LLM output with Pydantic validation
# ---------------------------------------------------------------------------

def call_llm_structured(
    messages,
    response_model: Type[T],
    task_class: str = "moderate",
    max_tokens: int = 4000,
    max_retries: int = 2,
) -> tuple[Optional[T], Optional[str]]:
    """Route an LLM call and return a validated Pydantic model.

    Uses Instructor to patch the LLM client and auto-retry on validation
    failure. Works with all 9 routing aliases (Anthropic/OpenAI/Google).

    Args:
        messages: List of dicts with 'role' and 'content'.
        response_model: Pydantic model class defining expected output shape.
        task_class: Routing task class.
        max_tokens: Maximum tokens for the response.
        max_retries: Retries on validation failure (default 2).

    Returns:
        Tuple of (validated_model_instance, error_string_or_None).
    """
    provider, model, cost = resolve_from_env_or_config(task_class)
    api_key = get_api_key(provider)

    if not api_key:
        return None, f"{provider.upper()} API key not found"

    try:
        import instructor

        if provider == "anthropic":
            import anthropic
            client = instructor.from_anthropic(
                anthropic.Anthropic(api_key=api_key),
                max_tokens=max_tokens,
            )
            result = client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                max_retries=max_retries,
                messages=[{"role": m.get("role", "user"), "content": m["content"]} for m in messages],
                response_model=response_model,
            )
        elif provider == "google":
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            client = instructor.from_gemini(
                client=genai.GenerativeModel(model_name=model),
            )
            result = client.chat.completions.create(
                messages=[{"role": m.get("role", "user"), "content": m["content"]} for m in messages],
                response_model=response_model,
                max_retries=max_retries,
            )
        else:
            from openai import OpenAI
            client = instructor.from_openai(
                OpenAI(api_key=api_key),
            )
            result = client.chat.completions.create(
                model=model,
                max_completion_tokens=max_tokens,
                max_retries=max_retries,
                messages=[{"role": m.get("role", "user"), "content": m["content"]} for m in messages],
                response_model=response_model,
            )

        return result, None
    except ImportError:
        return None, "instructor not installed — run: pip install instructor"
    except Exception as e:
        return None, str(e)


# ---------------------------------------------------------------------------
# Guardrails AI: content validation for output quality gate
# ---------------------------------------------------------------------------

def validate_output(
    text: str,
    min_length: int = 0,
    max_length: int = 50000,
    check_safety: bool = False,
    check_pii: bool = False,
) -> tuple[str, list[str]]:
    """Validate LLM output with built-in checks + optional NVIDIA safety/PII.

    Args:
        text: The output text to validate.
        min_length: Minimum character length (0 = no minimum).
        max_length: Maximum character length.
        check_safety: Run NVIDIA Content Safety 4B check.
        check_pii: Run PII detection (regex fallback or NIM).

    Returns:
        Tuple of (validated_text, list_of_warnings).
    """
    warnings = []

    # Length checks
    if min_length and len(text) < min_length:
        warnings.append(f"Output too short: {len(text)} chars (min {min_length})")
    if len(text) > max_length:
        warnings.append(f"Output too long: {len(text)} chars (max {max_length})")
        text = text[:max_length]

    # NVIDIA Content Safety (if requested and available)
    if check_safety:
        try:
            from lib.content_safety import check_safety as _check_safety
            result = _check_safety(text, reasoning=False)
            if not result["safe"]:
                warnings.append(f"Content safety: {result['reason'][:200]}")
        except Exception as e:
            warnings.append(f"Safety check error: {e}")

    # PII detection (if requested)
    if check_pii:
        try:
            from lib.content_safety import detect_pii
            entities, err = detect_pii(text)
            if err:
                warnings.append(f"PII check error: {err}")
            elif entities:
                types = list(set(e["type"] for e in entities))
                warnings.append(f"PII detected: {', '.join(types)} ({len(entities)} instances)")
        except Exception as e:
            warnings.append(f"PII check error: {e}")

    return text, warnings
