"""
Multilingual Intent Classifier (Module 3).
Classifies agricultural user queries in Hindi, Marathi, and English into:
- mandi_price
- weather
- pest_disease
- crop_advice
- government_scheme
- out_of_scope
"""
import re
from typing import Dict, Any, Tuple


class IntentClassifier:
    """
    Multilingual Intent Classifier supporting Hindi, Marathi, and English.
    """

    INTENT_KEYWORDS = {
        "mandi_price": [
            # Hindi
            "मंडी", "भाव", "रेट", "दाम", "बाजार", "कीमत",
            # Marathi
            "बाजारभाव", "दर", "भाव", "मार्केट",
            # English
            "mandi", "price", "rate", "market price", "modal price", "apmc"
        ],
        "weather": [
            # Hindi
            "मौसम", "बारिश", "तापमान", "हवा", "आंधी", "वर्षा",
            # Marathi
            "हवामान", "पाऊस", "तापमान", "गारपीट",
            # English
            "weather", "rain", "rainfall", "temperature", "forecast", "humidity"
        ],
        "pest_disease": [
            # Hindi
            "सुंडी", "कीट", "रोग", "फफूंद", "कीड़ा", "रोकथाम", "छिड़काव",
            # Marathi
            "बोंडअळी", "अळी", "तांबेरा", "रोग", "कीड", "फवारणी", "लक्षणे",
            # English
            "pest", "disease", "insect", "bollworm", "rust", "fungus", "symptom"
        ],
        "government_scheme": [
            # Hindi
            "योजना", "सब्सिडी", "अनुदान", "बीमा", "मुआवजा", "कर्ज", "किसान सम्मान",
            # Marathi
            "योजना", "अनुदान", "विमा", "नुकसानभरपाई", "कर्जमाफी",
            # English
            "scheme", "subsidy", "insurance", "pm kisan", "kcc", "fasal bima", "loan"
        ],
        "crop_advice": [
            # Hindi
            "बुवाई", "रोपण", "खाद", "उर्वरक", "किस्म", "पैदावार", "सिंचाई",
            # Marathi
            "लागवड", "पेरणी", "खत", "वाण", "उत्पादन", "सिंचन",
            # English
            "sowing", "planting", "fertilizer", "variety", "irrigation", "yield", "cultivation"
        ],
        "out_of_scope": [
            "crypto", "bitcoin", "share market", "stock", "cricket", "cinema", "movie",
            "शेयर", "क्रिकेट", "फिल्म", "सिनेमा", "क्रिप्टो"
        ]
    }

    @classmethod
    def classify_intent(cls, query: str) -> Tuple[str, float]:
        """
        Classifies query intent.

        Returns:
            Tuple of (intent_label, confidence_score)
        """
        if not query or not query.strip():
            return "out_of_scope", 0.0

        query_lower = query.lower()

        # Check explicit out of scope first
        for keyword in cls.INTENT_KEYWORDS["out_of_scope"]:
            if keyword in query_lower:
                return "out_of_scope", 0.95

        intent_scores = {}
        for intent, keywords in cls.INTENT_KEYWORDS.items():
            if intent == "out_of_scope":
                continue
            hits = 0
            for kw in keywords:
                if kw in query_lower:
                    hits += 1
            if hits > 0:
                intent_scores[intent] = hits

        if not intent_scores:
            # Default fallback: general crop advice if indeterminate
            return "crop_advice", 0.50

        # Select highest scoring intent
        best_intent = max(intent_scores.keys(), key=lambda k: intent_scores[k])
        confidence = min(0.95, 0.60 + (intent_scores[best_intent] * 0.15))
        return best_intent, round(confidence, 2)
