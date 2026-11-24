"""
Agricultural Domain Glossary Manager (Module 4).
Safeguards crop names, pests, diseases, and technical interventions across Hindi, Marathi, and English.
Provides offline term normalization for cross-lingual hybrid retrieval without external network APIs.
"""
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Set


class AgriculturalGlossaryManager:
    """
    Manages agricultural terms across Hindi, Marathi, and English.
    Translates/enriches queries with standardized canonical terms.
    """

    def __init__(self, glossary_path: str = "data/glossary/agri_glossary.json"):
        self.glossary_path = Path(glossary_path)
        self.term_to_canonical: Dict[str, str] = {}
        self.canonical_to_terms: Dict[str, List[str]] = {}
        self._load_glossary()

    def _load_glossary(self):
        if not self.glossary_path.exists():
            return

        with open(self.glossary_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for category, terms_map in data.items():
            for canonical, variants in terms_map.items():
                canon_lower = canonical.lower()
                self.canonical_to_terms[canon_lower] = [canon_lower]
                self.term_to_canonical[canon_lower] = canon_lower

                for var in variants:
                    var_lower = var.lower()
                    self.term_to_canonical[var_lower] = canon_lower
                    if var_lower not in self.canonical_to_terms[canon_lower]:
                        self.canonical_to_terms[canon_lower].append(var_lower)

    @staticmethod
    def _match_term(term: str, text: str) -> bool:
        """
        Matches a term against text using boundary checks appropriate for ASCII and Indic scripts.
        Prevents substring collisions (e.g. 'price' matching 'rice', or 'धान' in 'प्रधानमंत्री')
        while supporting Marathi/Hindi case inflections.
        """
        if term.isascii():
            pattern = rf"(?:\b|^){re.escape(term)}(?:\b|$)"
            return bool(re.search(pattern, text, re.IGNORECASE))
        else:
            pattern = rf"(?:^|[^\u0900-\u097F]){re.escape(term)}(?:$|[^\u0900-\u097F]|वरील|वर|तील|च्या|चा|ची|चे|साठी|ला|ने|मधील)"
            return bool(re.search(pattern, text, re.IGNORECASE))

    def normalize_and_expand_query(self, query: str) -> str:
        """
        Enriches a query by identifying Indic regional terms (e.g., 'गुलाबी सुंडी', 'कपाशी')
        and appending their canonical English equivalents (e.g., 'pink bollworm', 'cotton').
        Enables cross-lingual BM25 and vector search on institutional documents.
        Uses word-boundary matching so English words like 'price' never match 'rice'.
        """
        if not query:
            return ""

        query_lower = query.lower()
        matched_canonicals: Set[str] = set()

        # Sort terms by length descending to match multi-word phrases first
        for term, canonical in sorted(self.term_to_canonical.items(), key=lambda x: len(x[0]), reverse=True):
            if self._match_term(term, query_lower):
                matched_canonicals.add(canonical)

        if matched_canonicals:
            expansion = " ".join(matched_canonicals)
            return f"{query} {expansion}".strip()

        return query

    def detect_crop_entity(self, query: str) -> Optional[str]:
        """
        Detects if a known crop is mentioned in the query in English, Hindi, or Marathi.
        Enforces word-boundary matching to prevent substring false-positives (e.g. 'price' matching 'rice').
        """
        if not query:
            return None
        query_lower = query.lower()
        for term, canonical in sorted(self.term_to_canonical.items(), key=lambda x: len(x[0]), reverse=True):
            if self._match_term(term, query_lower) and canonical in ["cotton", "wheat", "rice", "soybean", "sugarcane", "dragon fruit"]:
                return canonical.capitalize()
        return None
