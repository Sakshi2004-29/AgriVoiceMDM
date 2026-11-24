"""
Hybrid Retrieval Engine.
Combines Dense Vector Search (FAISS) and Sparse Lexical Search (BM25)
using Reciprocal Rank Fusion (RRF).
Enforces metadata filtering and returns ranked evidence with full source references.
"""
from typing import List, Optional, Dict
from src.knowledge.models import DocumentChunk, SearchResult
from src.retrieval.vector_search import FAISSVectorIndex
from src.retrieval.bm25_search import BM25Index


class HybridRetriever:
    """
    Combines FAISS dense retrieval and BM25 sparse retrieval via Reciprocal Rank Fusion (RRF).
    Formula:
        RRF_score(doc) = 1 / (k + rank_dense) + 1 / (k + rank_bm25)
        (standard constant k = 60)
    """

    def __init__(self, vector_index: FAISSVectorIndex, bm25_index: BM25Index, rrf_k: int = 60):
        self.vector_index = vector_index
        self.bm25_index = bm25_index
        self.rrf_k = rrf_k

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        only_approved: bool = True,
        crop_filter: Optional[str] = None,
        region_filter: Optional[str] = None
    ) -> List[SearchResult]:
        """
        Executes hybrid search and returns deduplicated, ranked SearchResults.
        """
        # Fetch candidate pools from both retrievers
        candidate_k = max(top_k * 2, 10)

        dense_results = self.vector_index.search(
            query=query,
            top_k=candidate_k,
            only_approved=only_approved,
            crop_filter=crop_filter,
            region_filter=region_filter
        )

        sparse_results = self.bm25_index.search(
            query=query,
            top_k=candidate_k,
            only_approved=only_approved,
            crop_filter=crop_filter,
            region_filter=region_filter
        )

        # Track chunk mappings, ranks, and raw scores
        chunks_by_id: Dict[str, DocumentChunk] = {}
        dense_ranks: Dict[str, int] = {}
        dense_scores: Dict[str, float] = {}
        sparse_ranks: Dict[str, int] = {}
        sparse_scores: Dict[str, float] = {}

        for rank, (chunk, score) in enumerate(dense_results, start=1):
            cid = chunk.chunk_id
            chunks_by_id[cid] = chunk
            dense_ranks[cid] = rank
            dense_scores[cid] = score

        for rank, (chunk, score) in enumerate(sparse_results, start=1):
            cid = chunk.chunk_id
            chunks_by_id[cid] = chunk
            sparse_ranks[cid] = rank
            sparse_scores[cid] = score

        # Compute RRF score
        rrf_scores: Dict[str, float] = {}
        for cid in chunks_by_id.keys():
            dense_comp = 1.0 / (self.rrf_k + dense_ranks[cid]) if cid in dense_ranks else 0.0
            sparse_comp = 1.0 / (self.rrf_k + sparse_ranks[cid]) if cid in sparse_ranks else 0.0
            rrf_scores[cid] = dense_comp + sparse_comp

        # Sort chunks by RRF score descending
        sorted_cids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)

        final_results: List[SearchResult] = []
        for rank, cid in enumerate(sorted_cids[:top_k], start=1):
            chunk = chunks_by_id[cid]
            final_results.append(
                SearchResult(
                    chunk=chunk,
                    dense_score=dense_scores.get(cid, 0.0),
                    sparse_score=sparse_scores.get(cid, 0.0),
                    combined_score=rrf_scores[cid],
                    rank=rank
                )
            )

        return final_results
