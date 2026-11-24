"""
FAISS Vector Search Engine for Agricultural Knowledge Chunks.
Enforces cosine similarity search with strict metadata filtering (approval status, crop, region).
"""
import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ.setdefault("OMP_NUM_THREADS", "1")

import faiss
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple, Optional

from src.knowledge.models import DocumentChunk
from src.knowledge.embeddings import MultilingualEmbeddingService


class FAISSVectorIndex:
    """
    Manages FAISS vector indexing and similarity retrieval.
    """

    def __init__(self, dimension: int = 768, index_dir: str = "data/vector_db"):
        self.dimension = dimension
        self.index_dir = Path(index_dir)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.index_dir / "faiss_index.bin"

        # IndexFlatIP computes inner product (which equals cosine similarity for L2-normalized vectors)
        self.index = faiss.IndexFlatIP(self.dimension)
        self.chunks_map: List[DocumentChunk] = []
        self.embed_service = MultilingualEmbeddingService(dimension=self.dimension)

    def build_index(self, chunks: List[DocumentChunk]):
        """
        Indexes a list of DocumentChunks into FAISS.
        """
        if not chunks:
            self.index.reset()
            self.chunks_map = []
            return

        texts = [chunk.text for chunk in chunks]
        embeddings = self.embed_service.embed_batch(texts)

        # Reset and populate index
        self.index = faiss.IndexFlatIP(self.dimension)
        self.index.add(embeddings)
        self.chunks_map = list(chunks)

    def save_index(self):
        """Saves FAISS index to disk."""
        faiss.write_index(self.index, str(self.index_file))

    def load_index(self, chunks_map: List[DocumentChunk]):
        """Loads FAISS index from disk and rebinds chunk mapping."""
        if self.index_file.exists():
            self.index = faiss.read_index(str(self.index_file))
            self.chunks_map = list(chunks_map)

    def search(
        self,
        query: str,
        top_k: int = 5,
        only_approved: bool = True,
        crop_filter: Optional[str] = None,
        region_filter: Optional[str] = None
    ) -> List[Tuple[DocumentChunk, float]]:
        """
        Performs semantic vector search with strict metadata filtering.

        Returns:
            List of (DocumentChunk, similarity_score) sorted in descending order of score.
        """
        if self.index.ntotal == 0 or not self.chunks_map:
            return []

        query_vec = self.embed_service.embed_text(query).reshape(1, -1)
        # Fetch more candidates to allow for post-filtering
        fetch_k = min(self.index.ntotal, max(top_k * 3, 20))
        scores, indices = self.index.search(query_vec, fetch_k)

        results: List[Tuple[DocumentChunk, float]] = []

        for score, idx in zip(scores[0], indices[0]):
            if idx == -1 or idx >= len(self.chunks_map):
                continue

            chunk = self.chunks_map[idx]
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

            results.append((chunk, float(score)))

            if len(results) >= top_k:
                break

        return results
