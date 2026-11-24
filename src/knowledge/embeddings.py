"""
Multilingual Embeddings Service.
Provides high-quality semantic vector representations for Hindi, Marathi, and English.
Uses Google Gemini text-embedding-004 when available, with a deterministic local multilingual fallback for offline use.
"""
import os
import hashlib
import numpy as np
from typing import List, Union
from dotenv import load_dotenv

load_dotenv()


class MultilingualEmbeddingService:
    """
    Generates normalized dense vectors for Indic text (Hindi, Marathi, English).
    Supports dual-mode:
    1. Gemini API (text-embedding-004) when valid GEMINI_API_KEY is configured.
    2. Deterministic multilingual n-gram vectorizer for offline/test environments.
    """

    def __init__(self, dimension: int = 768):
        self.dimension = dimension
        self.api_key = os.getenv("GEMINI_API_KEY", "")
        self.use_api = bool(self.api_key and self.api_key != "your_gemini_api_key_here")
        self._client = None

        if self.use_api:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
            except Exception as e:
                print(f"Notice: Gemini client init skipped ({e}). Using local multilingual vectorizer.")
                self.use_api = False

    def _local_multilingual_embed(self, text: str) -> np.ndarray:
        """
        Deterministic, multilingual subword n-gram vectorizer.
        Captures semantic & character-level similarities across Hindi, Marathi, and English
        without requiring heavy 2GB neural weights on laptop.
        """
        vec = np.zeros(self.dimension, dtype=np.float32)
        if not text:
            return vec

        text_clean = text.lower().strip()
        tokens = text_clean.split()

        # Word-level features
        for token in tokens:
            # Hash to index
            h = int(hashlib.sha256(token.encode('utf-8')).hexdigest(), 16)
            idx = h % self.dimension
            sign = 1.0 if (h // self.dimension) % 2 == 0 else -1.0
            vec[idx] += sign * 1.5

        # Character 3-gram and 4-gram features (critical for Indic inflections like Marathi कपाशी / कापूस)
        for n in (3, 4):
            for i in range(len(text_clean) - n + 1):
                ngram = text_clean[i:i + n]
                h = int(hashlib.md5(ngram.encode('utf-8')).hexdigest(), 16)
                idx = h % self.dimension
                sign = 1.0 if (h // self.dimension) % 2 == 0 else -1.0
                vec[idx] += sign * 0.5

        # L2 Normalization
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec

    def embed_text(self, text: str) -> np.ndarray:
        """Embeds a single query or text passage."""
        if self.use_api and self._client:
            try:
                response = self._client.models.embed_content(
                    model="text-embedding-004",
                    contents=text
                )
                embedding = np.array(response.embeddings[0].values, dtype=np.float32)
                norm = np.linalg.norm(embedding)
                if norm > 0:
                    embedding = embedding / norm
                return embedding
            except Exception as e:
                # Fallback to local vectorizer if network fails
                return self._local_multilingual_embed(text)
        return self._local_multilingual_embed(text)

    def embed_batch(self, texts: List[str]) -> np.ndarray:
        """Embeds a list of texts into a 2D float32 numpy array."""
        embeddings = [self.embed_text(t) for t in texts]
        return np.vstack(embeddings).astype(np.float32)
