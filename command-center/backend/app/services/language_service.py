"""
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
