"""
Language Identification and Dialect Detection (Module 3).
Accurately identifies whether user input is Hindi, Marathi, or English.
Detects distinctive Indic script markers and regional grammatical tokens.
"""
import re
from typing import Dict, Any, Tuple


class LanguageDetector:
    """
    Identifies language from text transcripts.
    Specialized for differentiating Marathi ('mr') from Hindi ('hi') and English ('en').
    """

    # Distinctive Marathi characters and letter sequences
    MARATHI_DISTINCTIVE_CHARS = {"ळ", "ॲ", "ऑ"}

    # Common Marathi grammatical tokens and postpositions
    MARATHI_MARKERS = {
        "आहे", "आहेत", "होता", "होती", "होते", "करावे", "करावी", "करावा",
        "रोगाची", "रोगाचे", "पिकावरील", "पिकाची", "सांगा", "च्या", "चे", "ची",
        "वरून", "कडून", "पाहिजे", "कसा", "कशी", "कसे", "काय", "आणि", "व",
        "गव्हावरील", "कपाशीवरील", "उपाय", "लक्षणे"
    }

    # Common Hindi grammatical tokens and postpositions
    HINDI_MARKERS = {
        "है", "हैं", "था", "थी", "थे", "करें", "करे", "करना", "चाहिए",
        "का", "की", "के", "में", "से", "को", "पर", "बताएं", "बताओ", "कैसे",
        "क्या", "और", "उपाय", "लक्षण", "फसल", "नियंत्रण", "रोकथाम"
    }

    @classmethod
    def detect_language(cls, text: str, default: str = "hi") -> Tuple[str, float]:
        """
        Detects language of input text.

        Returns:
            Tuple of (language_code, confidence_score)
            Language code is 'mr' (Marathi), 'hi' (Hindi), or 'en' (English).
        """
        if not text or not text.strip():
            return default, 0.0

        clean_text = text.strip()

        # Check for Latin alphabet predominance (English)
        latin_chars = len(re.findall(r"[a-zA-Z]", clean_text))
        devanagari_chars = len(re.findall(r"[\u0900-\u097F]", clean_text))

        if latin_chars > devanagari_chars and latin_chars > 3:
            confidence = min(1.0, latin_chars / (latin_chars + devanagari_chars + 1e-6))
            return "en", round(confidence, 2)

        # If Devanagari script is present, distinguish Marathi vs Hindi
        tokens = set(re.findall(r"[\u0900-\u097F]+", clean_text.lower()))

        # 1. Distinctive character check (e.g. ळ in Marathi)
        for char in cls.MARATHI_DISTINCTIVE_CHARS:
            if char in clean_text:
                return "mr", 0.95

        # 2. Token overlap check
        marathi_hits = len(tokens.intersection(cls.MARATHI_MARKERS))
        hindi_hits = len(tokens.intersection(cls.HINDI_MARKERS))

        if marathi_hits > hindi_hits:
            confidence = min(0.95, 0.70 + (marathi_hits * 0.1))
            return "mr", round(confidence, 2)
        elif hindi_hits > marathi_hits:
            confidence = min(0.95, 0.70 + (hindi_hits * 0.1))
            return "hi", round(confidence, 2)

        # Default fallback to Hindi for general Devanagari if ambiguous
        return default, 0.60
