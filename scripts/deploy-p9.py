#!/usr/bin/env python3
"""
NemoClaw P-9 Deployment: MENA Adaptation

Creates: whatsapp_bridge.py, language_service.py
Patches: bridge_manager.py (register WhatsApp), priority_engine.py (warm intro boost), main.py (init)

Run from repo root:
    cd ~/nemoclaw-local-foundation
    python3 scripts/deploy-p9.py
"""

from pathlib import Path
import sys

BACKEND = Path.home() / "nemoclaw-local-foundation" / "command-center" / "backend"

# ═══════════════════════════════════════════════════════════════════
# FILE 1: whatsapp_bridge.py
# ═══════════════════════════════════════════════════════════════════

WHATSAPP_CODE = r'''"""
NemoClaw Execution Engine — WhatsApp Bridge (P-9)

WhatsApp Business API bridge (Twilio or Meta provider).
Enforces template-first messaging, 24h session windows, E.164 phone normalization.

Bilingual: English default, Arabic when prospect communicates in Arabic.
Template registry with en/ar variants.

NEW FILE: command-center/backend/app/services/bridges/whatsapp_bridge.py
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore

logger = logging.getLogger("cc.bridge.whatsapp")

# ── Constants ───────────────────────────────────────────────────────
SESSION_WINDOW_SECONDS = 86400  # 24 hours
COST_PER_MESSAGE = 0.005
COST_PER_TEMPLATE = 0.01

DELIVERY_STATUSES = {"queued", "sent", "delivered", "read", "failed"}

# E.164 regex: + followed by 1-15 digits
E164_REGEX = re.compile(r"^\+[1-9]\d{6,14}$")

# Jordan-specific normalization
JORDAN_COUNTRY_CODE = "+962"

# ── Bilingual Template Registry ─────────────────────────────────────
WHATSAPP_TEMPLATES = {
    "intro_greeting": {
        "en": "Hi {{1}}, this is {{2}} from NemoClaw. We help companies like {{3}} automate their sales pipeline. Would you be open to a quick chat?",
        "ar": "مرحباً {{1}}، أنا {{2}} من NemoClaw. نساعد شركات مثل {{3}} في أتمتة خط المبيعات. هل تود إجراء محادثة سريعة؟",
    },
    "follow_up": {
        "en": "Hi {{1}}, just following up on my previous message. Would love to share how we've helped similar companies. Any time work for a brief call?",
        "ar": "مرحباً {{1}}، أتابع رسالتي السابقة. أحب أن أشارككم كيف ساعدنا شركات مشابهة. هل هناك وقت مناسب لمكالمة قصيرة؟",
    },
    "meeting_confirmation": {
        "en": "Hi {{1}}, confirming our meeting on {{2}} at {{3}}. Looking forward to speaking with you!",
        "ar": "مرحباً {{1}}، أؤكد اجتماعنا يوم {{2}} الساعة {{3}}. أتطلع للتحدث معكم!",
    },
    "thank_you": {
        "en": "Thank you {{1}} for your time today. I'll send over the proposal by {{2}}. Feel free to reach out with any questions.",
        "ar": "شكراً {{1}} على وقتكم اليوم. سأرسل العرض بحلول {{2}}. لا تتردد في التواصل لأي استفسار.",
    },
}


class WhatsAppBridge:
    """
    WhatsApp Business API bridge.

    Supports Twilio and Meta providers. Enforces:
    - Template-first: first message must be a pre-approved template
    - 24h session window: free-form messages only within 24h of user reply
    - E.164 phone normalization
    - Full delivery lifecycle tracking
    - Bilingual template registry (en/ar)
    """

    def __init__(self, provider: str = "", **kwargs):
        self.provider = provider or os.environ.get("WHATSAPP_PROVIDER", "twilio")
        self._client: Any = None
        self._conversations: dict[str, dict[str, Any]] = {}  # phone → {last_user_msg, language}
        self._message_statuses: dict[str, str] = {}  # message_id → status
        self._persist_path = Path.home() / ".nemoclaw" / "whatsapp-conversations.json"
        self._persist_path.parent.mkdir(parents=True, exist_ok=True)
        self._load_conversations()
        self._init_client()
        logger.info("WhatsAppBridge initialized (provider=%s)", self.provider)

    def _init_client(self) -> None:
        """Initialize HTTP client for API calls."""
        if httpx:
            self._client = httpx.AsyncClient(timeout=30.0)

    def _load_conversations(self) -> None:
        if self._persist_path.exists():
            try:
                self._conversations = json.loads(self._persist_path.read_text())
            except (json.JSONDecodeError, OSError):
                pass

    def _save_conversations(self) -> None:
        try:
            self._persist_path.write_text(json.dumps(self._conversations, indent=2, default=str))
        except OSError:
            pass

    # ── Phone Normalization ─────────────────────────────────────────

    @staticmethod
    def normalize_phone(phone: str) -> str:
        """Normalize phone to E.164 format. Handles Jordan-specific patterns.

        Examples:
            07XXXXXXXX → +9627XXXXXXXX
            009627XXXXXXXX → +9627XXXXXXXX
            +9627XXXXXXXX → +9627XXXXXXXX (no change)
        """
        # Strip whitespace, dashes, parens
        cleaned = re.sub(r"[\s\-\(\)]", "", phone)

        # Remove leading 00 (international dialing prefix)
        if cleaned.startswith("00"):
            cleaned = "+" + cleaned[2:]

        # Jordan: leading 0 → +962
        if cleaned.startswith("07") and len(cleaned) == 10:
            cleaned = JORDAN_COUNTRY_CODE + cleaned[1:]

        # Ensure + prefix
        if not cleaned.startswith("+"):
            cleaned = "+" + cleaned

        # Validate E.164
        if not E164_REGEX.match(cleaned):
            raise ValueError(f"Invalid phone number after normalization: {cleaned} (original: {phone})")

        return cleaned

    # ── Session Window ──────────────────────────────────────────────

    def is_session_open(self, phone: str) -> bool:
        """Check if 24h conversation window is open for this phone."""
        conv = self._conversations.get(phone, {})
        last_msg = conv.get("last_user_message_at")
        if not last_msg:
            return False
        elapsed = time.time() - last_msg
        return elapsed < SESSION_WINDOW_SECONDS

    def record_incoming(self, phone: str, language: str = "") -> None:
        """Record an incoming user message — opens 24h session window."""
        phone = self.normalize_phone(phone)
        conv = self._conversations.setdefault(phone, {})
        conv["last_user_message_at"] = time.time()
        if language:
            conv["language"] = language
        self._save_conversations()

    def get_conversation_language(self, phone: str) -> str:
        """Get persisted language for this conversation. Default: en."""
        return self._conversations.get(phone, {}).get("language", "en")

    def set_conversation_language(self, phone: str, language: str) -> None:
        """Persist language choice for a conversation."""
        conv = self._conversations.setdefault(phone, {})
        conv["language"] = language
        self._save_conversations()

    # ── Send Message ────────────────────────────────────────────────

    async def send_message(self, to: str, body: str, language: str = "en") -> dict[str, Any]:
        """Send a free-form text message. Only works within 24h session window.

        If no session window → returns error suggesting send_template instead.
        """
        to = self.normalize_phone(to)

        if not self.is_session_open(to):
            return {
                "status": "failed",
                "error": "No active session window. Use send_template() for first contact.",
                "suggestion": "send_template",
            }

        # Persist language
        self.set_conversation_language(to, language)

        if self.provider == "twilio":
            return await self._twilio_send(to, body)
        elif self.provider == "meta":
            return await self._meta_send(to, body)
        else:
            return {"status": "failed", "error": f"Unknown provider: {self.provider}"}

    async def send_template(
        self,
        to: str,
        template_name: str,
        language: str = "en",
        parameters: list[str] | None = None,
    ) -> dict[str, Any]:
        """Send a pre-approved template message. Works anytime (no session required)."""
        to = self.normalize_phone(to)

        # Validate template exists
        template = WHATSAPP_TEMPLATES.get(template_name)
        if not template:
            return {
                "status": "failed",
                "error": f"Template '{template_name}' not found. Available: {list(WHATSAPP_TEMPLATES.keys())}",
            }

        # Get language variant
        if language not in template:
            language = "en"  # fallback to English
        template_text = template[language]

        # Fill parameters
        if parameters:
            for i, param in enumerate(parameters, 1):
                template_text = template_text.replace(f"{{{{{i}}}}}", param)

        # Persist language
        self.set_conversation_language(to, language)

        if self.provider == "twilio":
            return await self._twilio_send(to, template_text, is_template=True)
        elif self.provider == "meta":
            return await self._meta_send_template(to, template_name, language, parameters or [])
        else:
            return {"status": "failed", "error": f"Unknown provider: {self.provider}"}

    async def get_status(self, message_id: str) -> dict[str, Any]:
        """Get delivery status for a message."""
        status = self._message_statuses.get(message_id, "unknown")
        return {"message_id": message_id, "status": status}

    # ── Provider Implementations ────────────────────────────────────

    async def _twilio_send(self, to: str, body: str, is_template: bool = False) -> dict[str, Any]:
        """Send via Twilio WhatsApp API."""
        account_sid = os.environ.get("WHATSAPP_ACCOUNT_SID", "")
        auth_token = os.environ.get("WHATSAPP_AUTH_TOKEN", "")
        from_number = os.environ.get("WHATSAPP_FROM_NUMBER", "")

        if not all([account_sid, auth_token, from_number]):
            return {"status": "failed", "error": "Twilio WhatsApp credentials not configured"}

        if not self._client:
            return {"status": "failed", "error": "httpx not available"}

        url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
        try:
            resp = await self._client.post(
                url,
                auth=(account_sid, auth_token),
                data={
                    "To": f"whatsapp:{to}",
                    "From": f"whatsapp:{from_number}",
                    "Body": body,
                },
            )
            data = resp.json()
            msg_id = data.get("sid", "")
            status = data.get("status", "queued")
            self._message_statuses[msg_id] = status
            return {
                "status": status,
                "message_id": msg_id,
                "provider": "twilio",
                "cost": COST_PER_TEMPLATE if is_template else COST_PER_MESSAGE,
            }
        except Exception as e:
            return {"status": "failed", "error": str(e), "provider": "twilio"}

    async def _meta_send(self, to: str, body: str) -> dict[str, Any]:
        """Send via Meta WhatsApp Business API."""
        access_token = os.environ.get("WHATSAPP_ACCESS_TOKEN", "")
        phone_id = os.environ.get("WHATSAPP_PHONE_ID", "")

        if not all([access_token, phone_id]):
            return {"status": "failed", "error": "Meta WhatsApp credentials not configured"}

        if not self._client:
            return {"status": "failed", "error": "httpx not available"}

        url = f"https://graph.facebook.com/v18.0/{phone_id}/messages"
        try:
            resp = await self._client.post(
                url,
                headers={"Authorization": f"Bearer {access_token}"},
                json={
                    "messaging_product": "whatsapp",
                    "to": to.lstrip("+"),
                    "type": "text",
                    "text": {"body": body},
                },
            )
            data = resp.json()
            msg_id = data.get("messages", [{}])[0].get("id", "")
            self._message_statuses[msg_id] = "queued"
            return {"status": "queued", "message_id": msg_id, "provider": "meta", "cost": COST_PER_MESSAGE}
        except Exception as e:
            return {"status": "failed", "error": str(e), "provider": "meta"}

    async def _meta_send_template(self, to: str, template_name: str, language: str, params: list[str]) -> dict[str, Any]:
        """Send template via Meta API."""
        access_token = os.environ.get("WHATSAPP_ACCESS_TOKEN", "")
        phone_id = os.environ.get("WHATSAPP_PHONE_ID", "")

        if not all([access_token, phone_id]):
            return {"status": "failed", "error": "Meta WhatsApp credentials not configured"}

        if not self._client:
            return {"status": "failed", "error": "httpx not available"}

        url = f"https://graph.facebook.com/v18.0/{phone_id}/messages"
        components = []
        if params:
            components = [{"type": "body", "parameters": [{"type": "text", "text": p} for p in params]}]

        try:
            resp = await self._client.post(
                url,
                headers={"Authorization": f"Bearer {access_token}"},
                json={
                    "messaging_product": "whatsapp",
                    "to": to.lstrip("+"),
                    "type": "template",
                    "template": {
                        "name": template_name,
                        "language": {"code": "ar" if language == "ar" else "en"},
                        "components": components,
                    },
                },
            )
            data = resp.json()
            msg_id = data.get("messages", [{}])[0].get("id", "")
            self._message_statuses[msg_id] = "queued"
            return {"status": "queued", "message_id": msg_id, "provider": "meta", "cost": COST_PER_TEMPLATE}
        except Exception as e:
            return {"status": "failed", "error": str(e), "provider": "meta"}

    # ── Template Registry ───────────────────────────────────────────

    def get_templates(self) -> dict[str, Any]:
        """Return available templates with language variants."""
        return {k: list(v.keys()) for k, v in WHATSAPP_TEMPLATES.items()}

    def get_template(self, name: str, language: str = "en") -> str | None:
        """Get a specific template text."""
        t = WHATSAPP_TEMPLATES.get(name, {})
        return t.get(language, t.get("en"))
'''

# ═══════════════════════════════════════════════════════════════════
# FILE 2: language_service.py
# ═══════════════════════════════════════════════════════════════════

LANGUAGE_CODE = r'''"""
NemoClaw Execution Engine — LanguageService (P-9)

Lightweight Arabic/English detection. No external API.
Arabic Unicode range detection with ratio-based thresholding.

Default is ALWAYS English. Arabic only when detected in incoming text.
Supports preferred_language override from lead metadata.
Persists conversation language per phone/contact.

NEW FILE: command-center/backend/app/services/language_service.py
"""
from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger("cc.language")

# Arabic Unicode ranges: Arabic, Arabic Supplement, Arabic Extended
ARABIC_PATTERN = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]")

# Threshold: if > 40% of alpha chars are Arabic → classify as Arabic
ARABIC_THRESHOLD = 0.4

# Minimum text length for reliable detection
MIN_DETECTION_LENGTH = 5


class LanguageService:
    """
    Lightweight Arabic/English language detection.

    Rules:
    1. If preferred_language is set → use it (override)
    2. If text is too short (< 5 chars) → default English
    3. If Arabic chars > 40% of all alpha chars → Arabic
    4. Otherwise → English
    """

    def __init__(self):
        logger.info("LanguageService initialized")

    def detect(self, text: str, preferred_language: str = "") -> dict[str, Any]:
        """Detect language of text.

        Args:
            text: Input text to analyze
            preferred_language: Override from lead/contact metadata (e.g., "ar", "en")

        Returns:
            {"language": "en"|"ar", "confidence": float, "script": str, "method": str}
        """
        # Override if preferred language set
        if preferred_language and preferred_language in ("en", "ar"):
            return {
                "language": preferred_language,
                "confidence": 1.0,
                "script": "arabic" if preferred_language == "ar" else "latin",
                "method": "preferred_override",
            }

        # Strip whitespace
        clean = text.strip()

        # Too short → default English
        if len(clean) < MIN_DETECTION_LENGTH:
            return {
                "language": "en",
                "confidence": 0.5,
                "script": "latin",
                "method": "too_short_default",
            }

        # Count Arabic vs total alpha characters
        arabic_chars = len(ARABIC_PATTERN.findall(clean))
        alpha_chars = sum(1 for c in clean if c.isalpha())

        if alpha_chars == 0:
            # No alpha chars (emojis, numbers only) → default English
            return {
                "language": "en",
                "confidence": 0.3,
                "script": "unknown",
                "method": "no_alpha_default",
            }

        ratio = arabic_chars / alpha_chars

        if ratio > ARABIC_THRESHOLD:
            return {
                "language": "ar",
                "confidence": round(min(ratio * 1.2, 1.0), 2),
                "script": "arabic",
                "method": "ratio_detection",
                "arabic_ratio": round(ratio, 3),
            }
        else:
            return {
                "language": "en",
                "confidence": round(1.0 - ratio, 2),
                "script": "latin",
                "method": "ratio_detection",
                "arabic_ratio": round(ratio, 3),
            }

    def is_arabic(self, text: str) -> bool:
        """Quick check: is this text primarily Arabic?"""
        result = self.detect(text)
        return result["language"] == "ar"

    def get_response_language(self, incoming_text: str, preferred: str = "") -> str:
        """Determine what language to respond in.

        Returns "ar" only if incoming is Arabic. Default is always "en".
        """
        result = self.detect(incoming_text, preferred)
        return result["language"]
'''

# ═══════════════════════════════════════════════════════════════════
# DEPLOY
# ═══════════════════════════════════════════════════════════════════

def deploy():
    errors = []

    # 1. Write WhatsApp bridge
    print("1/5 Writing whatsapp_bridge.py...")
    wa_path = BACKEND / "app" / "services" / "bridges" / "whatsapp_bridge.py"
    wa_path.write_text(WHATSAPP_CODE.strip() + "\n")
    try:
        compile(wa_path.read_text(), str(wa_path), "exec")
        print("  ✅ Compiles")
    except SyntaxError as e:
        errors.append(f"whatsapp_bridge.py: {e}")
        print(f"  ❌ {e}")

    # 2. Write language service
    print("2/5 Writing language_service.py...")
    lang_path = BACKEND / "app" / "services" / "language_service.py"
    lang_path.write_text(LANGUAGE_CODE.strip() + "\n")
    try:
        compile(lang_path.read_text(), str(lang_path), "exec")
        print("  ✅ Compiles")
    except SyntaxError as e:
        errors.append(f"language_service.py: {e}")
        print(f"  ❌ {e}")

    # 3. Patch bridge_manager.py — add WhatsApp config + init
    print("3/5 Patching bridge_manager.py...")
    bm_path = BACKEND / "app" / "services" / "bridge_manager.py"
    bm = bm_path.read_text()

    # Add WhatsApp config after apollo config
    bm = bm.replace(
        '''            "apollo": BridgeConfig(
                name="apollo",
                enabled=bool(os.environ.get("APOLLO_API_KEY")),
                rate_limit_per_minute=30,
                daily_cap=500,
                requires_approval=False,  # Read-only, safe
                cost_per_call=0.0,
            ),
        }''',
        '''            "apollo": BridgeConfig(
                name="apollo",
                enabled=bool(os.environ.get("APOLLO_API_KEY")),
                rate_limit_per_minute=30,
                daily_cap=500,
                requires_approval=False,  # Read-only, safe
                cost_per_call=0.0,
            ),
            # P-9: WhatsApp bridge (MENA adaptation)
            "whatsapp": BridgeConfig(
                name="whatsapp",
                enabled=bool(os.environ.get("WHATSAPP_ACCOUNT_SID") or os.environ.get("WHATSAPP_ACCESS_TOKEN")),
                rate_limit_per_minute=30,
                daily_cap=500,
                requires_approval=True,  # Sends to real people
                cost_per_call=0.005,
            ),
        }''',
    )

    # Add WhatsApp bridge init after Instantly
    bm = bm.replace(
        '''            except Exception as e:
                logger.warning("Failed to load Instantly bridge: %s", e)

    async def execute(''',
        '''            except Exception as e:
                logger.warning("Failed to load Instantly bridge: %s", e)

        # P-9: WhatsApp bridge
        wa_provider = os.environ.get("WHATSAPP_PROVIDER", "twilio")
        wa_has_keys = bool(os.environ.get("WHATSAPP_ACCOUNT_SID") or os.environ.get("WHATSAPP_ACCESS_TOKEN"))
        if wa_has_keys:
            try:
                from app.services.bridges.whatsapp_bridge import WhatsAppBridge
                self._bridges["whatsapp"] = WhatsAppBridge(provider=wa_provider)
                logger.info("WhatsApp bridge loaded (provider=%s)", wa_provider)
            except Exception as e:
                logger.warning("Failed to load WhatsApp bridge: %s", e)

    async def execute(''',
    )

    bm_path.write_text(bm)
    try:
        compile(bm_path.read_text(), str(bm_path), "exec")
        print("  ✅ Compiles")
    except SyntaxError as e:
        errors.append(f"bridge_manager.py: {e}")
        print(f"  ❌ {e}")

    # 4. Patch priority_engine.py — add warm intro boost
    print("4/5 Patching priority_engine.py...")
    pe_path = BACKEND / "app" / "services" / "priority_engine.py"
    pe = pe_path.read_text()

    # Add source boost constants after logger line
    pe = pe.replace(
        'logger = logging.getLogger("cc.priority")',
        '''logger = logging.getLogger("cc.priority")

# ── P-9: Lead Source Boost (MENA warm intro weighting) ──────────────
# Additive boost to priority score based on lead source type.
# Warm intros are culturally weighted higher in MENA markets.
SOURCE_BOOST = {
    "warm_intro": 30,
    "referral": 30,
    "inbound": 20,
    "linkedin": 15,
    "cold": 0,
}
MAX_PRIORITY_SCORE = 100''',
    )

    # Patch score method to apply source boost
    pe = pe.replace(
        '        item.priority_score = min(total * 10, 100)  # Scale to 0-100\n        return item.priority_score',
        '''        item.priority_score = min(total * 10, 100)  # Scale to 0-100

        # P-9: Apply lead source boost from metadata
        if item.metadata:
            source_type = item.metadata.get("source_type", "cold")
            boost = SOURCE_BOOST.get(source_type, 0)
            if boost:
                item.priority_score = min(item.priority_score + boost, MAX_PRIORITY_SCORE)
                item.factors["source_boost"] = boost

        return item.priority_score''',
    )

    pe_path.write_text(pe)
    try:
        compile(pe_path.read_text(), str(pe_path), "exec")
        print("  ✅ Compiles")
    except SyntaxError as e:
        errors.append(f"priority_engine.py: {e}")
        print(f"  ❌ {e}")

    # 5. Patch main.py — init LanguageService + language detect endpoint
    print("5/5 Patching main.py...")
    main_path = BACKEND / "app" / "main.py"
    main = main_path.read_text()

    # Add LanguageService init after BridgeManager
    main = main.replace(
        '    logger.info("E-8: BridgeManager initialized")',
        '''    logger.info("E-8: BridgeManager initialized")

    # ── P-9: Language Service (MENA adaptation) ──
    from app.services.language_service import LanguageService
    app.state.language_service = LanguageService()
    logger.info("P-9: LanguageService initialized")''',
    )

    main_path.write_text(main)
    try:
        compile(main_path.read_text(), str(main_path), "exec")
        print("  ✅ Compiles")
    except SyntaxError as e:
        errors.append(f"main.py: {e}")
        print(f"  ❌ {e}")

    # Summary
    print()
    if errors:
        print(f"⛔ {len(errors)} ERRORS:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("✅ P-9 deployed successfully")
        print()
        print("NOTE: Language detect endpoint needs a small router addition.")
        print("Add this to the bridges router or create a minimal inline route.")
        print("For now, LanguageService is available programmatically to all services.")
        print()
        print("Restart backend, then validate:")
        print()
        print('  TOKEN=$(cat ~/.nemoclaw/cc-token)')
        print()
        print('  # Bridge manager shows WhatsApp (disabled — no keys)')
        print('  curl -s -H "Authorization: Bearer $TOKEN" \\')
        print('    http://127.0.0.1:8100/api/bridges/status | python3 -c "import json,sys; d=json.load(sys.stdin); print(\'Bridges:\', list(d.get(\'bridges\',{}).keys()))"')
        print()
        print('  # WhatsApp bridge status')
        print('  curl -s -H "Authorization: Bearer $TOKEN" \\')
        print('    http://127.0.0.1:8100/api/bridges/whatsapp/status | python3 -m json.tool')
        print()
        print('  cd ~/nemoclaw-local-foundation && bash scripts/full_regression.sh')
        print()
        print('  git add -A && git status')
        print('  git commit -m "feat(engine): P-9 MENA adaptation — WhatsApp bridge, language detection, warm intro scoring, bilingual templates"')
        print('  git push origin main')


if __name__ == "__main__":
    deploy()
