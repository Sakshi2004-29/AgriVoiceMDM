"""
Multilingual Entity Extractor (Module 3).
Extracts key agricultural entities from queries:
- crop (Cotton, Wheat, Soybean, Onion, Rice)
- district/location (Nagpur, Pune, Akola, Nashik, Ludhiana, Indore, etc.)
- disease_or_pest (Pink Bollworm, Yellow Rust, etc.)
- date (today, tomorrow)
"""
import re
from typing import Dict, Any, Optional

from src.translation.glossary_manager import AgriculturalGlossaryManager


class EntityExtractor:
    """
    Extracts structured entities across English, Hindi, and Marathi text.
    """

    DISTRICT_MAP = {
        # Maharashtra
        "nagpur": "Nagpur", "नागपुर": "Nagpur", "नागपूर": "Nagpur", "नागपुरात": "Nagpur", "नागपूरमधील": "Nagpur",
        "pune": "Pune", "poona": "Pune", "पुणे": "Pune", "पुना": "Pune", "पूना": "Pune", "पुण्यात": "Pune", "पुण्यातील": "Pune", "पुण्याचा": "Pune", "पुण्याचे": "Pune", "पुण्याला": "Pune",
        "nashik": "Nashik", "nasik": "Nashik", "नाशिक": "Nashik", "नाशिकात": "Nashik", "नाशिकमधील": "Nashik", "लासलगाव": "Nashik", "lasalgaon": "Nashik",
        "akola": "Akola", "अकोला": "Akola", "अकोल्यात": "Akola", "अकोल्यामधील": "Akola",
        "amravati": "Amravati", "अमरावती": "Amravati", "अमरावतीत": "Amravati",
        "latur": "Latur", "लातूर": "Latur", "लातुरात": "Latur",
        "kolhapur": "Kolhapur", "कोल्हापूर": "Kolhapur", "कोल्हापुरात": "Kolhapur",
        "solapur": "Solapur", "सोलापूर": "Solapur", "सोलापुरात": "Solapur",
        "aurangabad": "Chhatrapati Sambhajinagar", "संभाजीनगर": "Chhatrapati Sambhajinagar", "औरंगाबाद": "Chhatrapati Sambhajinagar",
        "jalgaon": "Jalgaon", "जळगाव": "Jalgaon",
        "ahmednagar": "Ahilyanagar", "अहमदनगर": "Ahilyanagar", "अहिल्यानगर": "Ahilyanagar",
        # Punjab
        "ludhiana": "Ludhiana", "लुधियाना": "Ludhiana", "लुधियाने": "Ludhiana",
        "karnal": "Karnal", "करनाल": "Karnal",
        # Madhya Pradesh
        "indore": "Indore", "इंदौर": "Indore",
        # Rajasthan
        "jaipur": "Jaipur", "जयपुर": "Jaipur",
        # Karnataka
        "bengaluru": "Bengaluru", "बैंगलोर": "Bengaluru", "बेंगळुरू": "Bengaluru"
    }

    CROP_MAP = {
        # Cotton
        "cotton": "Cotton", "कपास": "Cotton", "कपाशी": "Cotton", "कापूस": "Cotton", "कापसा": "Cotton", "कापसाचे": "Cotton", "कापसाचा": "Cotton", "कापसाला": "Cotton", "नरमा": "Cotton",
        # Wheat
        "wheat": "Wheat", "गेहूं": "Wheat", "गेहुं": "Wheat", "गहू": "Wheat", "गव्हा": "Wheat", "गव्हाचे": "Wheat", "गव्हाचा": "Wheat", "गव्हाला": "Wheat",
        # Onion
        "onion": "Onion", "onions": "Onion", "प्याज": "Onion", "प्याज़": "Onion", "प्याजा": "Onion", "कांदा": "Onion", "कांद्या": "Onion", "कांदे": "Onion", "कांद्याचे": "Onion", "कांद्याचा": "Onion", "कांद्याला": "Onion",
        # Soybean
        "soybean": "Soybean", "soya": "Soybean", "सोयाबीन": "Soybean", "सोयाबीनचे": "Soybean", "सोयाबीनचा": "Soybean", "सोयाबीनला": "Soybean",
        # Rice
        "rice": "Rice", "paddy": "Rice", "चावल": "Rice", "धान": "Rice", "भात": "Rice", "तांदूळ": "Rice", "तांदळाचे": "Rice", "तांदळाचा": "Rice",
        # Dragon Fruit
        "dragon fruit": "Dragon Fruit", "dragonfruit": "Dragon Fruit", "ड्रैगन फ्रूट": "Dragon Fruit", "ड्रॅगन फ्रूट": "Dragon Fruit", "ड्रैगनफ्रूट": "Dragon Fruit", "कमलम": "Dragon Fruit",
        # Other Common Crops
        "sugarcane": "Sugarcane", "गन्ना": "Sugarcane", "ऊस": "Sugarcane", "उसाचा": "Sugarcane", "उसाचे": "Sugarcane",
        "tomato": "Tomato", "टमाटर": "Tomato", "टोमॅटो": "Tomato",
        "potato": "Potato", "आलू": "Potato", "बटाटा": "Potato", "बटाटे": "Potato",
        "mango": "Mango", "आम": "Mango", "आंबा": "Mango", "आंबे": "Mango",
        "maize": "Maize", "corn": "Maize", "मक्का": "Maize", "मका": "Maize",
        "gram": "Gram", "chana": "Gram", "चना": "Gram", "हरभरा": "Gram",
        "tur": "Tur", "arhar": "Tur", "तूर": "Tur", "अरहर": "Tur"
    }

    DISEASE_MAP = {
        "pink bollworm": "Pink Bollworm", "गुलाबी सुंडी": "Pink Bollworm", "बोंडअळी": "Pink Bollworm",
        "yellow rust": "Yellow Rust", "पीला रतुआ": "Yellow Rust", "पिवळा तांबेरा": "Yellow Rust",
        "whitefly": "Whitefly", "सफेद मक्खी": "Whitefly", "पांढरी माशी": "Whitefly"
    }

    def __init__(self, glossary_manager: Optional[AgriculturalGlossaryManager] = None):
        self.glossary = glossary_manager or AgriculturalGlossaryManager()

    @staticmethod
    def _match_term(term: str, text: str) -> bool:
        """
        Matches an entity term against text using boundary checks appropriate for ASCII and Indic scripts.
        Prevents substring collisions (e.g. 'price' matching 'rice', or 'धान' in 'प्रधानमंत्री')
        while supporting Marathi/Hindi case inflections (e.g. 'कपाशीवरील', 'गव्हावरील').
        """
        if term.isascii():
            pattern = rf"(?:\b|^){re.escape(term)}(?:\b|$)"
            return bool(re.search(pattern, text, re.IGNORECASE))
        else:
            pattern = rf"(?:^|[^\u0900-\u097F]){re.escape(term)}(?:$|[^\u0900-\u097F]|वरील|वर|तील|च्या|चा|ची|चे|साठी|ला|ने|मधील)"
            return bool(re.search(pattern, text, re.IGNORECASE))

    def extract_entities(self, query: str) -> Dict[str, Optional[str]]:
        """
        Extracts structured entities from user query.

        Returns:
            Dict containing:
                crop: Optional[str]
                district: Optional[str]
                disease_or_pest: Optional[str]
                date: Optional[str]
        """
        if not query:
            return {"crop": None, "district": None, "disease_or_pest": None, "date": None}

        query_clean = query.lower()

        # 1. Extract Crop using boundary-aware matching (longest phrases first)
        extracted_crop = None
        for key, crop_name in sorted(self.CROP_MAP.items(), key=lambda x: len(x[0]), reverse=True):
            if self._match_term(key, query_clean):
                extracted_crop = crop_name
                break

        # Fallback to glossary detection if not in static map
        if not extracted_crop:
            extracted_crop = self.glossary.detect_crop_entity(query)

        # Fallback: Pattern-based candidate commodity extraction for mandi price questions
        if not extracted_crop:
            # Pattern: "price/rate of <commodity>"
            m_en = re.search(r"(?:mandi\s+)?(?:price|rate)\s+of\s+([a-zA-Z\s]+?)(?:\s+in|\s+at|\s+mandi|\s+today|\?|$|[\.,])", query_clean)
            if m_en:
                cand = m_en.group(1).strip()
                if cand and cand not in ["the", "this", "that", "a", "an", "current", "live"]:
                    extracted_crop = cand.title()

            # Pattern: "<commodity> (mandi) price/rate"
            if not extracted_crop:
                m_en2 = re.search(r"([a-zA-Z\s]+?)\s+(?:mandi\s+)?(?:price|rate)(?:\s+in|\s+at|\s+today|\?|$|[\.,])", query_clean)
                if m_en2:
                    cand = m_en2.group(1).strip()
                    if cand and cand not in ["what", "what is", "tell me", "the", "current", "live", "today"]:
                        extracted_crop = cand.title()

            # Pattern: Hindi "<commodity> का/के/की भाव/दाम"
            if not extracted_crop:
                m_hi = re.search(r"([^\s]+(?: [^\s]+)?)\s+(?:का|के|की)\s+(?:मंडी\s+)?(?:भाव|रेट|दाम|कीमत)", query_clean)
                if m_hi:
                    cand = m_hi.group(1).strip()
                    if cand not in ["आज", "कल", "मंडी", "बाजार", "फसल"]:
                        extracted_crop = cand

            # Pattern: Marathi "<commodity> चा/चे/ची भाव/दर"
            if not extracted_crop:
                m_mr = re.search(r"([^\s]+(?: [^\s]+)?)\s+(?:चा|चे|ची)\s+(?:मंडी\s+)?(?:बाजारभाव|दर|भाव)", query_clean)
                if m_mr:
                    cand = m_mr.group(1).strip()
                    if cand not in ["आज", "आजचे", "उद्या", "बाजार", "पीक", "पिका"]:
                        extracted_crop = cand

        # 2. Extract District / Location using boundary-aware matching (longest names first)
        extracted_district = None
        for key, dist_name in sorted(self.DISTRICT_MAP.items(), key=lambda x: len(x[0]), reverse=True):
            if self._match_term(key, query_clean):
                extracted_district = dist_name
                break

        # 3. Extract Disease or Pest using boundary-aware matching (longest names first)
        extracted_disease = None
        for key, disease_name in sorted(self.DISEASE_MAP.items(), key=lambda x: len(x[0]), reverse=True):
            if self._match_term(key, query_clean):
                extracted_disease = disease_name
                break

        # 4. Extract Date / Relative Time
        extracted_date = None
        if any(w in query_clean for w in ["today", "आज"]):
            extracted_date = "today"
        elif any(w in query_clean for w in ["tomorrow", "कल", "उद्या"]):
            extracted_date = "tomorrow"

        return {
            "crop": extracted_crop,
            "district": extracted_district,
            "disease_or_pest": extracted_disease,
            "date": extracted_date
        }
