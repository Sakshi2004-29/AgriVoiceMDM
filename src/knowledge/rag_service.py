"""
Unified Agricultural Knowledge RAG Service.
Coordinates document ingestion, approval, hybrid retrieval (FAISS + BM25 with RRF),
and grounded answer generation with safe refusal.
Integrated with AgriculturalGlossaryManager (Module 4) for Indic cross-lingual retrieval.
"""
from typing import List, Dict, Any, Optional
from pathlib import Path

from src.knowledge.models import DocumentMetadata, DocumentChunk, SearchResult
from src.knowledge.document_manager import DocumentRepository
from src.retrieval.vector_search import FAISSVectorIndex
from src.retrieval.bm25_search import BM25Index
from src.retrieval.hybrid_retriever import HybridRetriever
from src.generation.generator import GroundedAnswerGenerator
from src.guardrails.fallback_handler import FallbackHandler
from src.translation.glossary_manager import AgriculturalGlossaryManager


class AgriculturalRAGService:
    """
    Main orchestrator for the Phase 2 Hybrid RAG pipeline.
    """

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.repo = DocumentRepository(storage_dir=str(self.data_dir / "processed_chunks"))
        self.vector_index = FAISSVectorIndex(dimension=768, index_dir=str(self.data_dir / "vector_db"))
        self.bm25_index = BM25Index()
        self.retriever = HybridRetriever(self.vector_index, self.bm25_index)
        self.generator = GroundedAnswerGenerator()
        self.fallback_handler = FallbackHandler()
        self.glossary = AgriculturalGlossaryManager(
            glossary_path=str(Path("data/glossary/agri_glossary.json"))
        )

        # Re-index any existing approved documents on startup
        self.rebuild_indexes()

    def rebuild_indexes(self):
        """
        Rebuilds FAISS and BM25 indexes using approved chunks from the repository.
        """
        approved_chunks = self.repo.get_approved_chunks()
        self.vector_index.build_index(approved_chunks)
        self.bm25_index.build_index(approved_chunks)

    def ingest_pdf(self, pdf_path: str, metadata: DocumentMetadata, auto_approve: bool = False) -> List[DocumentChunk]:
        """
        Ingests a PDF document. By default, stays in 'pending' status unless auto_approve=True.
        """
        chunks = self.repo.ingest_pdf(pdf_path, metadata)
        if auto_approve:
            self.repo.approve_document(metadata.doc_id, approved_by="System Admin")
        self.rebuild_indexes()
        return chunks

    def approve_document(self, doc_id: str, approved_by: str = "Certified Agronomist", notes: Optional[str] = None):
        """
        Approves an ingested document, immediately making its chunks searchable in FAISS and BM25.
        """
        self.repo.approve_document(doc_id, approved_by=approved_by, notes=notes)
        self.rebuild_indexes()

    def reject_document(self, doc_id: str, reason: str = "Unverified or flawed guidance"):
        """
        Rejects a document, removing it from active search indexes.
        """
        self.repo.reject_document(doc_id, reason=reason)
        self.rebuild_indexes()

    def query(
        self,
        question: str,
        language: str = "en",
        top_k: int = 3,
        crop_filter: Optional[str] = None,
        region_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        End-to-end question answering through the hybrid RAG pipeline:
        1. Query normalization and cross-lingual glossary expansion (Module 4).
        2. Hybrid retrieval (FAISS + BM25 using RRF) on APPROVED documents only.
        3. Strict grounded generation citing official sources or safe refusal.
        """
        # Expand regional terms using verified agricultural glossary
        search_query = self.glossary.normalize_and_expand_query(question)

        # Detect crop if not explicitly passed
        active_crop_filter = crop_filter or self.glossary.detect_crop_entity(question)

        evidence = self.retriever.retrieve(
            query=search_query,
            top_k=top_k,
            only_approved=True,
            crop_filter=active_crop_filter,
            region_filter=region_filter
        )

        response = self.generator.generate_answer(
            query=question,
            evidence=evidence,
            language=language
        )

        response["evidence_passages"] = [
            {
                "chunk_id": res.chunk.chunk_id,
                "text": res.chunk.text,
                "source": res.chunk.metadata.source,
                "publisher": res.chunk.metadata.publisher,
                "crop": res.chunk.metadata.crop,
                "region": res.chunk.metadata.region,
                "approval_status": res.chunk.metadata.approval_status,
                "rrf_score": res.combined_score,
                "rank": res.rank
            }
            for res in evidence
        ]

        return response
