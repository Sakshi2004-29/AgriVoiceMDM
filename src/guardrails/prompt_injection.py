"""
Prompt Injection and Adversarial Query Defense (Module 10 & 12).
Detects attempts to bypass safety guardrails, override system instructions,
or perform jailbreaks in English, Hindi, and Marathi.
"""
import re
from typing import Tuple, Optional


class PromptInjectionGuardrail:
    """
    Detects and blocks prompt injection, system prompt override, and jailbreak attempts.
    """

    INJECTION_PATTERNS = [
        r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions",
        r"system\s+prompt",
        r"pretend\s+you\s+are",
        r"act\s+as\s+(an?\s+)?(unrestricted|dan|hacker|bot)",
        r"forget\s+(all\s+)?rules",
        r"bypass\s+(safety|guardrail|filter)",
        r"disregard\s+(the\s+)?safety",
        r"jailbreak",
        r"drop\s+table",
        # Hindi & Marathi patterns
        r"पिछले\s+निर्देश\s+भूल\s+जाओ",
        r"सभी\s+नियम\s+रद्द\s+करो",
        r"आधीच्या\s+सूचना\s+दुर्लक्षित\s+करा",
        r"सर्व\s+नियम\s+विसरा"
    ]

    @classmethod
    def check_for_injection(cls, text: str) -> Tuple[bool, Optional[str]]:
        """
        Checks if text contains prompt injection attempts.
        Returns:
            Tuple of (is_safe: bool, flagged_reason: Optional[str])
        """
        if not text:
            return True, None

        clean_lower = text.lower()
        for pattern in cls.INJECTION_PATTERNS:
            if re.search(pattern, clean_lower, re.IGNORECASE):
                return False, f"Prompt injection attempt detected matching: {pattern}"

        return True, None
