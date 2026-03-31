"""
NemoClaw Execution Engine — Resend Bridge (E-8)

Real email sending via Resend API.
Actions: send_email, list_emails, get_email

NEW FILE: command-center/backend/app/services/bridges/resend_bridge.py
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

logger = logging.getLogger("cc.bridge.resend")


class ResendBridge:
    """Real Resend API bridge for email sending."""

    BASE_URL = "https://api.resend.com"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        logger.info("ResendBridge initialized")

    async def execute(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        """Execute a Resend action."""
        actions = {
            "send_email": self._send_email,
            "list_emails": self._list_emails,
            "get_email": self._get_email,
            "list_domains": self._list_domains,
            "health": self._health_check,
        }

        handler = actions.get(action)
        if not handler:
            raise ValueError(f"Unknown Resend action: {action}. Available: {list(actions.keys())}")

        return await handler(params)

    async def _send_email(self, params: dict[str, Any]) -> dict[str, Any]:
        """Send an email via Resend."""
        required = ["from_email", "to", "subject"]
        for field in required:
            if field not in params:
                raise ValueError(f"Missing required field: {field}")

        payload = {
            "from": params["from_email"],
            "to": params["to"] if isinstance(params["to"], list) else [params["to"]],
            "subject": params["subject"],
        }

        if params.get("html"):
            payload["html"] = params["html"]
        elif params.get("text"):
            payload["text"] = params["text"]
        else:
            payload["text"] = params.get("body", "")

        if params.get("reply_to"):
            payload["reply_to"] = params["reply_to"]

        try:
            resp = await self._client.post(f"{self.BASE_URL}/emails", json=payload)
            resp.raise_for_status()
            data = resp.json()
            logger.info("Email sent via Resend: %s → %s", params["from_email"], params["to"])
            return {"sent": True, "id": data.get("id"), "status": "sent"}
        except httpx.HTTPStatusError as e:
            error_body = e.response.text
            logger.error("Resend send failed (%d): %s", e.response.status_code, error_body[:200])
            raise RuntimeError(f"Resend API error ({e.response.status_code}): {error_body[:200]}")
        except httpx.RequestError as e:
            logger.error("Resend request failed: %s", e)
            raise RuntimeError(f"Resend connection error: {e}")

    async def _list_emails(self, params: dict[str, Any]) -> dict[str, Any]:
        """List sent emails."""
        try:
            resp = await self._client.get(f"{self.BASE_URL}/emails")
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"Resend list error ({e.response.status_code}): {e.response.text[:200]}")

    async def _get_email(self, params: dict[str, Any]) -> dict[str, Any]:
        """Get email by ID."""
        email_id = params.get("email_id", "")
        if not email_id:
            raise ValueError("Missing email_id")
        try:
            resp = await self._client.get(f"{self.BASE_URL}/emails/{email_id}")
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"Resend get error ({e.response.status_code}): {e.response.text[:200]}")

    async def _list_domains(self, params: dict[str, Any]) -> dict[str, Any]:
        """List verified domains."""
        try:
            resp = await self._client.get(f"{self.BASE_URL}/domains")
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"Resend domains error ({e.response.status_code}): {e.response.text[:200]}")

    async def _health_check(self, params: dict[str, Any]) -> dict[str, Any]:
        """Check if Resend API is reachable."""
        try:
            resp = await self._client.get(f"{self.BASE_URL}/domains")
            return {"healthy": resp.status_code in (200, 401, 403), "status_code": resp.status_code}
        except Exception as e:
            return {"healthy": False, "error": str(e)}
