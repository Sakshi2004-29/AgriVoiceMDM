"""
Safe Fallback and Refusal Handler.
Enforces the Zero-Guessing policy when evidence is missing, unapproved, or confidence is insufficient.
Directs farmers to the Kisan Call Centre (1800-180-1551) and local Krishi Vigyan Kendras (KVK).
"""
from typing import Dict, Any, Optional


class FallbackHandler:
    """
    Generates respectful, localized refusal responses when safe grounded answers cannot be made.
    """

    REFUSAL_MESSAGES = {
        "en": (
            "I could not find verified agricultural advice for this question in our approved records. "
            "To protect your crops from incorrect guidance, please contact the Kisan Call Centre "
            "(Toll-Free 1800-180-1551, 6:00 AM to 10:00 PM) or visit your nearest Krishi Vigyan Kendra (KVK)."
        ),
        "hi": (
            "मुझे हमारे प्रमाणित रिकॉर्ड में इस प्रश्न के लिए कोई सत्यापित कृषि जानकारी नहीं मिली है। "
            "फसल सुरक्षा और सही सलाह के लिए, कृपया किसान कॉल सेंटर के टोल-फ्री नंबर 1800-180-1551 "
            "(सुबह 6 से रात 10 बजे) पर संपर्क करें या अपने नजदीकी कृषि विज्ञान केंद्र (KVK) के विशेषज्ञ से मिलें।"
        ),
        "mr": (
            "मला आमच्या प्रमाणित नोंदींमध्ये या प्रश्नासाठी कोणतीही पडताळलेली कृषी माहिती मिळालेली नाही. "
            "पिकांच्या सुरक्षेसाठी, कृपया किसान कॉल सेंटरच्या टोल-फ्री क्रमांक 1800-180-1551 "
            "(सकाळी ६ ते रात्री १०) वर संपर्क साधा किंवा आपल्या जवळच्या कृषी विज्ञान केंद्रास (KVK) भेट द्या."
        )
    }

    CHEMICAL_SAFETY_WARNINGS = {
        "en": (
            "Important Safety Warning: Chemical pesticides must be handled strictly according to certified agronomist instructions. "
            "Always wear protective gear and adhere to prescribed waiting periods before harvest."
        ),
        "hi": (
            "महत्वपूर्ण सुरक्षा चेतावनी: रासायनिक कीटनाशकों का प्रयोग केवल प्रमाणित कृषि विशेषज्ञ की सलाह अनुसार ही करें। "
            "दवा छिड़काव करते समय सुरक्षात्मक उपकरण पहनें और निर्धारित प्रतीक्षा अवधि का पालन करें।"
        ),
        "mr": (
            "महत्त्वाची सुरक्षा सूचना: रासायनिक कीटकनाशकांचा वापर केवळ अधिकृत कृषी तज्ज्ञांच्या सल्ल्यानुसारच करावा. "
            "फवारणी करताना संरक्षक साधने वापरा आणि काढणीपूर्वीच्या प्रतीक्षा कालावधीचे पालन करा."
        )
    }

    def generate_refusal(self, language: str = "en", reason_code: str = "NO_APPROVED_EVIDENCE") -> Dict[str, Any]:
        """
        Returns a structured refusal response with official helpline referral.
        """
        lang = language.lower() if language.lower() in self.REFUSAL_MESSAGES else "en"
        text = self.REFUSAL_MESSAGES[lang]

        return {
            "status": "refused",
            "reason_code": reason_code,
            "language": lang,
            "spoken_text": text,
            "referrals": {
                "kisan_call_centre": "1800-180-1551 (Toll-Free)",
                "local_expert": "Krishi Vigyan Kendra (KVK)"
            },
            "source_cited": "Kisan Call Centre Advisory Directorate"
        }

    def get_chemical_safety_note(self, language: str = "en") -> str:
        """Returns the mandatory chemical safety disclaimer."""
        lang = language.lower() if language.lower() in self.CHEMICAL_SAFETY_WARNINGS else "en"
        return self.CHEMICAL_SAFETY_WARNINGS[lang]
