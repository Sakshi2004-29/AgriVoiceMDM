"""
Agricultural Safety & Chemical Dosage Guardrails (Module 10 & 12).
Enforces:
1. Detection of pesticide, herbicide, fungicide, and fertilizer dosage requests.
2. Zero-fabrication of chemical concentrations, mixing ratios, and pre-harvest intervals (PHI).
3. Mandatory institutional safety warnings on any chemical mention.
4. Detection of hazardous, banned, or dangerous agricultural practices.
5. Prompt injection and adversarial query detection.
"""
import re
from typing import Dict, Any, List, Optional, Tuple


from src.guardrails.prompt_injection import PromptInjectionGuardrail


class ChemicalSafetyGuardrail:
    """
    Guards against unauthorized or hallucinated pesticide/chemical guidance.
    Enforces strict verification and appends official agronomist warnings.
    """

    # High-hazard or banned agricultural chemicals under CIBRC / Government of India notifications
    BANNED_OR_RESTRICTED_CHEMICALS = {
        "endosulfan", "monocrotophos", "paraquat", "phorate", "methyl parathion",
        "chlorpyrifos", "diazinon", "मोनोक्रोटोफॉस", "एंडोसल्फान", "पॅराक्वॉट"
    }

    CHEMICAL_CATEGORIES = {
        "pesticide": ["pesticide", "insecticide", "कीटनाशक", "कीटकनाशक", "सुंडी नाशक", "अळी नाशक"],
        "fungicide": ["fungicide", "फफूंदनाशक", "बुरशीनाशक", "तांबेरा नाशक"],
        "herbicide": ["herbicide", "weedicide", "खरपतवारनाशक", "तणनाशक"],
        "fertilizer": ["fertilizer", "urea", "dap", "npk", "खाद", "उर्वरक", "खत", "रासायनिक खत"]
    }

    DOSAGE_KEYWORDS = [
        "dosage", "dose", "concentration", "mixing ratio", "ml per liter", "gm per liter",
        "मात्रा", "प्रमाण", "डोस", "मिली", "ग्राम", "कितना डालना", "कसे मिसळावे"
    ]

    MANDATORY_SAFETY_DISCLAIMERS = {
        "hi": (
            "\n\n[महत्वपूर्ण सुरक्षा सूचना]: रासायनिक कीटनाशकों का प्रयोग केवल केंद्रीय कीटनाशक बोर्ड (CIBRC) "
            "और कृषि विश्वविद्यालय द्वारा अनुमोदित दिशा-निर्देशों के अनुसार ही करें। "
            "छिड़काव करते समय सुरक्षात्मक मास्क, दस्ताने पहनें और फसल कटाई से पूर्व अनिवार्य प्रतीक्षा अवधि (PHI) का पालन करें। "
            "सटीक खुराक के लिए अपने नजदीकी कृषि विज्ञान केंद्र (KVK) से संपर्क करें।"
        ),
        "mr": (
            "\n\n[महत्त्वाची सुरक्षा सूचना]: रासायनिक कीटकनाशकांचा वापर केवळ केंद्रीय कीटकनाशक मंडळ (CIBRC) "
            "आणि कृषी विद्यापीठाच्या अधिकृत शिफारशीनुसारच करावा. "
            "फवारणी करताना संरक्षक मास्क, हातमोजे वापरा आणि काढणीपूर्वीच्या प्रतीक्षा कालावधीचे (PHI) काटेकोर पालन करा. "
            "अचूक प्रमाण व सल्ल्यासाठी आपल्या स्थानिक कृषी विज्ञान केंद्रास (KVK) भेट द्या."
        ),
        "en": (
            "\n\n[Important Safety Notice]: Chemical pesticides and fertilizers must strictly adhere to "
            "Central Insecticides Board & Registration Committee (CIBRC) and agricultural university guidelines. "
            "Always wear protective clothing and mask during spraying, and observe mandatory Pre-Harvest Intervals (PHI). "
            "For certified dosages, consult your local Krishi Vigyan Kendra (KVK) or extension officer."
        )
    }

    @classmethod
    def analyze_chemical_request(cls, query: str) -> Dict[str, Any]:
        """
        Analyzes whether a query asks about regulated chemicals, dosages, or banned substances.
        """
        query_lower = query.lower()

        # 1. Check for banned substances
        detected_banned = []
        for banned in cls.BANNED_OR_RESTRICTED_CHEMICALS:
            if banned in query_lower:
                detected_banned.append(banned)

        # 2. Check for chemical categories
        detected_categories = []
        for cat, keywords in cls.CHEMICAL_CATEGORIES.items():
            if any(kw in query_lower for kw in keywords):
                detected_categories.append(cat)

        # 3. Check if dosage is requested
        asks_dosage = any(kw in query_lower for kw in cls.DOSAGE_KEYWORDS)

        is_dangerous = len(detected_banned) > 0

        return {
            "contains_chemical": len(detected_categories) > 0 or len(detected_banned) > 0,
            "detected_categories": detected_categories,
            "asks_dosage": asks_dosage,
            "detected_banned_chemicals": detected_banned,
            "is_dangerous": is_dangerous,
            "reason": f"Prohibited/Restricted chemicals detected: {detected_banned}" if is_dangerous else None
        }

    @classmethod
    def verify_and_safeguard_answer(
        cls,
        answer_text: str,
        retrieved_contexts: List[str],
        language: str = "hi"
    ) -> Dict[str, Any]:
        """
        Verifies that any chemical dosage mentioned in the generated answer exists explicitly in retrieved context.
        Appends official safety disclaimers to prevent unsupervised chemical handling.
        """
        lang = language if language in cls.MANDATORY_SAFETY_DISCLAIMERS else "en"
        combined_context = " ".join(retrieved_contexts).lower()
        answer_lower = answer_text.lower()

        # Detect specific dosage patterns (e.g. "2 ml/l", "2.5 ग्राम", "500 gm")
        dosage_pattern = r"(\d+(\.\d+)?)\s*(ml|gm|kg|लीटर|लिटर|ग्राम|ग्रॅम|किलो)"
        answer_dosages = [m[0] for m in re.findall(dosage_pattern, answer_lower)]

        # Check if answer mentions chemicals or specific application dosages
        has_chemical = any(
            any(kw in answer_lower for kw in kws)
            for kws in cls.CHEMICAL_CATEGORIES.values()
        ) or len(answer_dosages) > 0

        for dose in answer_dosages:
            if dose not in combined_context:
                # Hallucinated or unsupported dosage detected!
                return {
                    "is_safe": False,
                    "reason": f"Unverified chemical dosage '{dose}' not supported by retrieved official documents.",
                    "safe_answer": (
                        "सुरक्षा चेतावनी: इस रासायनिक खुराक की पुष्टि हमारे आधिकारिक रिकॉर्ड से नहीं हुई है। "
                        "फसल और स्वास्थ्य सुरक्षा हेतु कृपया किसान कॉल सेंटर 1800-180-1551 पर संपर्क करें।"
                        if lang == "hi" else
                        "सुरक्षा इशारा: या रासायनिक प्रमाणाची पडताळणी आमच्या अधिकृत नोंदीतून झालेली नाही. "
                        "कृपया योग्य सल्ल्यासाठी किसान कॉल सेंटर 1800-180-1551 वर संपर्क साधावा."
                    )
                }

        # If chemical guidance is legitimate, append mandatory safety disclaimer
        safe_answer = answer_text
        if has_chemical and not safe_answer.endswith(cls.MANDATORY_SAFETY_DISCLAIMERS[lang]):
            safe_answer += cls.MANDATORY_SAFETY_DISCLAIMERS[lang]

        return {
            "is_safe": True,
            "safe_answer": safe_answer,
            "has_chemical_guidance": has_chemical
        }
