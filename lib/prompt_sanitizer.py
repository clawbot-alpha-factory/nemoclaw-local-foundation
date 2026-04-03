"""
Prompt Sanitizer — Detect and redact secrets before they reach LLM context.

Catches API keys (Anthropic, OpenAI, AWS, GitHub, GitLab), bearer tokens,
passwords in common formats, and generic long hex/base64 strings that look
like credentials.
"""

import logging
import re
from typing import NamedTuple

logger = logging.getLogger("nemoclaw.prompt_sanitizer")


class _Pattern(NamedTuple):
    label: str
    regex: re.Pattern


SECRET_PATTERNS: list[_Pattern] = [
    _Pattern("ANTHROPIC_KEY", re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}")),
    _Pattern("OPENAI_KEY", re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}")),
    _Pattern("AWS_KEY", re.compile(r"AKIA[0-9A-Z]{16}")),
    _Pattern("GITHUB_TOKEN", re.compile(r"gh[ps]_[A-Za-z0-9_]{36,}")),
    _Pattern("GITHUB_OAUTH", re.compile(r"gho_[A-Za-z0-9_]{36,}")),
    _Pattern("GITLAB_TOKEN", re.compile(r"glpat-[A-Za-z0-9_-]{20,}")),
    _Pattern("BEARER_TOKEN", re.compile(r"Bearer\s+[A-Za-z0-9_.\-]{20,}", re.IGNORECASE)),
    _Pattern("GOOGLE_KEY", re.compile(r"AIza[A-Za-z0-9_-]{35}")),
    _Pattern("SLACK_TOKEN", re.compile(r"xox[bpas]-[A-Za-z0-9-]{10,}")),
    _Pattern("PASSWORD", re.compile(
        r"(?:password|passwd|pwd|secret|token)\s*[:=]\s*['\"]?([^\s'\"]{8,})",
        re.IGNORECASE,
    )),
    _Pattern("GENERIC_SECRET", re.compile(r"[A-Za-z0-9+/]{40,}={0,2}")),
]


def sanitize(text: str) -> str:
    """Replace detected secrets with [REDACTED-{type}] placeholders."""
    if not text:
        return text

    redacted = text
    found = False

    for pat in SECRET_PATTERNS:
        if pat.regex.search(redacted):
            found = True
            redacted = pat.regex.sub(f"[REDACTED-{pat.label}]", redacted)

    if found:
        logger.warning("Secrets detected and redacted from prompt text")

    return redacted


def has_secrets(text: str) -> bool:
    """Check if text contains any secret patterns (detection only)."""
    if not text:
        return False
    return any(pat.regex.search(text) for pat in SECRET_PATTERNS)
