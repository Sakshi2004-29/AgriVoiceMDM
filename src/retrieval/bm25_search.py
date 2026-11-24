"""
Multilingual BM25 Keyword Search Engine.
Implements Okapi BM25 with specialized tokenization for Indic scripts (Hindi, Marathi) and Latin/English,
including stop-word filtering to prevent spurious matches on auxiliary words.
"""
import math
import re
from collections import Counter
from typing import List, Dict, Tuple, Optional

from src.knowledge.models import DocumentChunk

# Common stop words across English, Hindi, and Marathi that carry no agricultural domain semantics
STOP_WORDS = {
    # English
    "is", "in", "the", "of", "and", "to", "a", "an", "for", "on", "with", "at", "by", "from",
    "it", "this", "that", "what", "how", "when", "where", "which", "who", "are", "was", "were",
    "be", "been", "being", "have", "has", "had", "do", "does", "did", "but", "if", "or", "because",
    "as", "until", "while", "about", "against", "between", "into", "through", "during", "before",
    "after", "above", "below", "up", "down", "out", "off", "over", "under", "again", "further",
    # Hindi
    "का", "की", "के", "में", "से", "को", "पर", "है", "हैं", "था", "थी", "थे", "और", "या",
    "तो", "भी", "ही", "एक", "यह", "वह", "इस", "उस", "कि", "जो", "कर", "करें", "रहा", "रही",
    # Marathi
    "आणि", "व", "या", "चे", "ची", "च्या", "आहे", "आहेत", "होता", "होती", "होते", "मध्ये",
    "वरून", "कडून", "ने", "नी", "ला", "ना", "हे", "ती", "ते", "त्या", "ज्या", "की", "पण"
}


class BM25Index:
    """
    Okapi BM25 keyword search engine supporting Indic Devanagari and English terms.
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.chunks_map: List[DocumentChunk] = []
        self.corpus_size = 0
        self.avg_doc_len = 0.0
        self.doc_lengths: List[int] = []
        self.doc_freqs: Dict[str, int] = {}
        self.idf: Dict[str, float] = {}
        self.doc_term_freqs: List[Counter] = []

    @staticmethod
    def tokenize(text: str) -> List[str]:
        """
        Tokenizes text capturing Hindi/Marathi Devanagari words (\u0900-\u097F)
        as well as alphanumeric English terms, filtering out domain-agnostic stop words.
        """
        if not text:
            return []
        raw_tokens = re.findall(r"[\u0900-\u097Fa-zA-Z0-9]+", text.lower())
        tokens = [t for t in raw_tokens if len(t) > 1 and t not in STOP_WORDS]
        return tokens

    def build_index(self, chunks: List[DocumentChunk]):
        """
        Indexes a list of DocumentChunks for BM25 search.
        """
        self.chunks_map = list(chunks)
        self.corpus_size = len(chunks)
        self.doc_lengths = []
        self.doc_term_freqs = []
        self.doc_freqs = Counter()

        if self.corpus_size == 0:
            self.avg_doc_len = 0.0
            return

        total_tokens = 0
        for chunk in chunks:
            tokens = self.tokenize(chunk.text)
            length = len(tokens)
            self.doc_lengths.append(length)
            total_tokens += length

            tf = Counter(tokens)
            self.doc_term_freqs.append(tf)

            for term in tf.keys():
                self.doc_freqs[term] += 1

        self.avg_doc_len = total_tokens / self.corpus_size if self.corpus_size > 0 else 0.0

        # Calculate IDF with standard Okapi BM25 Laplace smoothing
        self.idf = {}
        for term, df in self.doc_freqs.items():
            self.idf[term] = math.log(1.0 + (self.corpus_size - df + 0.5) / (df + 0.5))

    def search(
        self,
        query: str,
        top_k: int = 5,
        only_approved: bool = True,
        crop_filter: Optional[str] = None,
        region_filter: Optional[str] = None
    ) -> List[Tuple[DocumentChunk, float]]:
        """
        Executes BM25 keyword search with metadata pre-filtering.

        Returns:
            List of (DocumentChunk, bm25_score) sorted descending by relevance.
        """
        if self.corpus_size == 0 or not self.chunks_map:
            return []

        query_tokens = self.tokenize(query)
        if not query_tokens:
            return []

        scores: List[Tuple[int, float]] = []

        for idx, chunk in enumerate(self.chunks_map):
            meta = chunk.metadata

            # 1. Enforce approval gate
            if only_approved and meta.approval_status != "approved":
                continue

            # 2. Enforce crop filter
            if crop_filter and crop_filter.lower() != "all":
                if meta.crop.lower() not in [crop_filter.lower(), "general", "all"]:
                    continue

            # 3. Enforce region filter
            if region_filter and region_filter.lower() != "all":
                if meta.region.lower() not in [region_filter.lower(), "national", "all"]:
                    continue

            doc_len = self.doc_lengths[idx]
            tf = self.doc_term_freqs[idx]
            score = 0.0

            for q_term in query_tokens:
                if q_term not in tf:
                    continue
                term_freq = tf[q_term]
                term_idf = self.idf.get(q_term, 0.0)

                # Standard Okapi BM25 formula
                numerator = term_freq * (self.k1 + 1.0)
                denominator = term_freq + self.k1 * (1.0 - self.b + self.b * (doc_len / (self.avg_doc_len + 1e-6)))
                score += term_idf * (numerator / denominator)

            if score > 0.0:
                scores.append((idx, score))

        # Sort descending by score
        scores.sort(key=lambda x: x[1], reverse=True)

        results: List[Tuple[DocumentChunk, float]] = []
        for idx, score in scores[:top_k]:
            results.append((self.chunks_map[idx], score))

        return results
