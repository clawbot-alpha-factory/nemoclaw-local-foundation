#!/usr/bin/env python3
"""
NemoClaw Structured Logging v1.0.0
JSON-first logging with correlation IDs, agent context, and log levels.

Replaces all bare `logging.getLogger()` calls with structured output.
Every log line emits valid JSON to stderr (structured) and a human
summary to stdout when LOG_FORMAT=human.

Features:
- Correlation ID per request/task (propagated via contextvars)
- Agent + skill context binding
- Automatic error serialisation
- Compatible with CloudWatch, Datadog, Loki, Grafana

Usage:
    from lib.structured_logging import get_logger, bind_context, new_correlation_id

    log = get_logger("my.component")
    log.info("Skill started", skill_id="a01-arch-spec-writer", step=1)
    log.error("Step failed", error=str(e), skill_id="a01-arch-spec-writer")

    # Request-scoped correlation ID
    with new_correlation_id():
        run_skill(...)

    # Bind persistent context for a block
    with bind_context(agent_id="content_lead", task_id="t-42"):
        log.info("Agent task dispatched")
"""

from __future__ import annotations

import json
import logging
import os
import sys
import traceback
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Optional

# ── Context vars ─────────────────────────────────────────────────────────────

_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")
_bound_context: ContextVar[dict[str, Any]] = ContextVar("bound_context", default={})

LOG_FORMAT = os.environ.get("LOG_FORMAT", "json").lower()  # "json" | "human"
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
LOG_FILE = os.environ.get("LOG_FILE", "")  # optional file path


# ── JSON formatter ────────────────────────────────────────────────────────────

class StructuredFormatter(logging.Formatter):
    """Emits one JSON object per log record."""

    LEVEL_MAP = {
        logging.DEBUG: "DEBUG",
        logging.INFO: "INFO",
        logging.WARNING: "WARNING",
        logging.ERROR: "ERROR",
        logging.CRITICAL: "CRITICAL",
    }

    def format(self, record: logging.LogRecord) -> str:
        # Base fields
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": self.LEVEL_MAP.get(record.levelno, "INFO"),
            "logger": record.name,
            "msg": record.getMessage(),
        }

        # Correlation + context
        corr = _correlation_id.get("")
        if corr:
            payload["corr"] = corr

        bound = _bound_context.get({})
        if bound:
            payload.update(bound)

        # Structured kwargs passed via extra={...}
        extra = getattr(record, "structured", {})
        if extra:
            payload.update(extra)

        # Exception
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        elif record.exc_text:
            payload["exc"] = record.exc_text

        # Source location in DEBUG mode
        if record.levelno <= logging.DEBUG:
            payload["src"] = f"{record.filename}:{record.lineno}"

        return json.dumps(payload, default=str)


class HumanFormatter(logging.Formatter):
    """Human-readable format for local dev."""

    COLORS = {
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[35m",
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        level = record.levelname
        color = self.COLORS.get(level, "")
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        corr = _correlation_id.get("")
        corr_str = f"[{corr[:8]}] " if corr else ""
        extra = getattr(record, "structured", {})
        extra_str = " ".join(f"{k}={v}" for k, v in extra.items()) if extra else ""
        msg = record.getMessage()
        exc = ""
        if record.exc_info:
            exc = "\n" + self.formatException(record.exc_info)
        return f"{ts} {color}{level:8}{self.RESET} {corr_str}{record.name}: {msg}{(' ' + extra_str) if extra_str else ''}{exc}"


# ── Structured logger wrapper ─────────────────────────────────────────────────

class StructuredLogger:
    """Wraps a stdlib Logger and adds structured kwargs to every call."""

    def __init__(self, logger: logging.Logger):
        self._logger = logger

    def _log(self, level: int, msg: str, *args: Any, **kwargs: Any) -> None:
        if not self._logger.isEnabledFor(level):
            return
        # Support %-style format args for stdlib compatibility
        if args:
            try:
                msg = msg % args
            except (TypeError, ValueError):
                pass
        extra = {"structured": kwargs} if kwargs else {}
        self._logger.log(level, msg, extra=extra, stacklevel=3)

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._log(logging.DEBUG, msg, *args, **kwargs)

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._log(logging.INFO, msg, *args, **kwargs)

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._log(logging.WARNING, msg, *args, **kwargs)

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._log(logging.ERROR, msg, *args, **kwargs)

    def critical(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._log(logging.CRITICAL, msg, *args, **kwargs)

    def exception(self, msg: str, exc: Optional[BaseException] = None, **kwargs: Any) -> None:
        """Log an exception with traceback."""
        if exc:
            kwargs["exc_type"] = type(exc).__name__
            kwargs["exc_msg"] = str(exc)
            kwargs["traceback"] = traceback.format_exc()
        self._log(logging.ERROR, msg, **kwargs)

    # Pass-through for stdlib compat
    def isEnabledFor(self, level: int) -> bool:
        return self._logger.isEnabledFor(level)

    @property
    def name(self) -> str:
        return self._logger.name


# ── Setup ─────────────────────────────────────────────────────────────────────

_configured = False


def _setup_root_logging() -> None:
    global _configured
    if _configured:
        return
    _configured = True

    root = logging.getLogger()
    root.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    # Remove existing handlers
    root.handlers.clear()

    # Stderr handler
    stderr_handler = logging.StreamHandler(sys.stderr)
    if LOG_FORMAT == "human":
        stderr_handler.setFormatter(HumanFormatter())
    else:
        stderr_handler.setFormatter(StructuredFormatter())
    root.addHandler(stderr_handler)

    # Optional file handler
    if LOG_FILE:
        from pathlib import Path
        Path(LOG_FILE).parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(LOG_FILE)
        file_handler.setFormatter(StructuredFormatter())
        root.addHandler(file_handler)


def get_logger(name: str) -> StructuredLogger:
    """Get a structured logger for the given name."""
    _setup_root_logging()
    return StructuredLogger(logging.getLogger(name))


# ── Context managers ──────────────────────────────────────────────────────────

@contextmanager
def new_correlation_id(corr_id: Optional[str] = None):
    """Context manager that sets a new (or provided) correlation ID."""
    _id = corr_id or uuid.uuid4().hex
    token = _correlation_id.set(_id)
    try:
        yield _id
    finally:
        _correlation_id.reset(token)


@contextmanager
def bind_context(**kwargs: Any):
    """Context manager that adds fields to every log line in scope."""
    existing = _bound_context.get({})
    merged = {**existing, **kwargs}
    token = _bound_context.set(merged)
    try:
        yield
    finally:
        _bound_context.reset(token)


def get_correlation_id() -> str:
    """Get the current correlation ID (empty string if none set)."""
    return _correlation_id.get("")


def set_correlation_id(corr_id: str) -> None:
    """Set correlation ID imperatively (use new_correlation_id() when possible)."""
    _correlation_id.set(corr_id)


# ── FastAPI middleware helper ─────────────────────────────────────────────────

def make_logging_middleware():
    """
    Return a Starlette/FastAPI middleware class that:
    - Assigns a correlation ID to each request (X-Correlation-ID header or auto-generated)
    - Logs request + response with duration
    - Propagates correlation ID to response headers

    Usage in FastAPI app:
        from lib.structured_logging import make_logging_middleware
        app.add_middleware(make_logging_middleware())
    """
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request
    from starlette.responses import Response

    log = get_logger("nemoclaw.http")

    class LoggingMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            import time

            corr = request.headers.get("X-Correlation-ID") or uuid.uuid4().hex
            token = _correlation_id.set(corr)
            start = time.monotonic()
            try:
                response: Response = await call_next(request)
                duration_ms = round((time.monotonic() - start) * 1000, 1)
                log.info(
                    "HTTP request",
                    method=request.method,
                    path=str(request.url.path),
                    status=response.status_code,
                    duration_ms=duration_ms,
                    corr=corr,
                )
                response.headers["X-Correlation-ID"] = corr
                return response
            except Exception as exc:
                duration_ms = round((time.monotonic() - start) * 1000, 1)
                log.error(
                    "HTTP request failed",
                    method=request.method,
                    path=str(request.url.path),
                    duration_ms=duration_ms,
                    error=str(exc),
                )
                raise
            finally:
                _correlation_id.reset(token)

    return LoggingMiddleware
