"""
Comprehensive Automated Test Suite for Phase 2:
Agricultural Knowledge Ingestion, Approval Workflow, Hybrid RAG (FAISS + BM25 with RRF),
and Grounded Generation / Safe Refusal.
Uses Python's standard library `unittest` (no external test runner dependencies needed).
"""
import unittest
import tempfile
import shutil
from pathlib import Path

from src.knowledge.models import DocumentMetadata, DocumentChunk
from src.knowledge.doc_parser import PDFDocumentParser
from src.knowledge.chunker import AgriculturalChunker
from src.knowledge.document_manager import DocumentRepository
from src.knowledge.embeddings import MultilingualEmbeddingService
from src.retrieval.vector_search import FAISSVectorIndex
from src.retrieval.bm25_search import BM25Index
from src.retrieval.hybrid_retriever import HybridRetriever
from src.generation.generator import GroundedAnswerGenerator
from src.guardrails.fallback_handler import FallbackHandler
from src.knowledge.rag_service import AgriculturalRAGService


class TestKnowledgeIngestionAndApproval(unittest.TestCase):
    """Tests PDF parsing, chunking, and the human approval workflow."""

    def test_pdf_parsing_with_pymupdf(self):
        pdf_path = "data/raw_documents/cotton_pink_bollworm_icar_advisory.pdf"
        self.assertTrue(Path(pdf_path).exists(), "Sample PDF must exist")

        meta = DocumentMetadata(
            doc_id="DOC_COTTON_001",
            title="ICAR-CICR Cotton Advisory: Pink Bollworm Management",
            source="ICAR-CICR Advisory Bulletin 2026",
            publisher="Indian Council of Agricultural Research",
            crop="Cotton",
            region="Maharashtra",
            season="Kharif",
            language="en",
            publication_date="2026-05-15"
        )

        parser = PDFDocumentParser()
        parsed = parser.parse_pdf(pdf_path, meta)

        self.assertEqual(parsed["doc_id"], "DOC_COTTON_001")
        self.assertGreaterEqual(parsed["total_pages"], 1)
        self.assertIn("Pink bollworm", parsed["full_text"])
        self.assertIn("pheromone traps", parsed["full_text"])

    def test_structure_aware_chunking(self):
        meta = DocumentMetadata(
            doc_id="DOC_COTTON_001",
            title="ICAR-CICR Cotton Advisory",
            source="ICAR-CICR Bulletin",
            publisher="ICAR",
            crop="Cotton",
            region="Maharashtra",
            publication_date="2026-05-15"
        )
        sample_text = (
            "Pink bollworm is a serious pest in cotton.\n\n"
            "Farmers are advised to install 5 pheromone traps per hectare. "
            "Collect and destroy rosette flowers to break the pest lifecycle."
        )
        chunker = AgriculturalChunker(target_chunk_size=150, overlap_size=30)
        chunks = chunker.chunk_document(meta.doc_id, sample_text, meta)

        self.assertGreaterEqual(len(chunks), 1)
        for chunk in chunks:
            self.assertEqual(chunk.doc_id, "DOC_COTTON_001")
            self.assertEqual(chunk.metadata.crop, "Cotton")
            self.assertGreater(len(chunk.text), 0)

    def test_document_approval_mechanism(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo = DocumentRepository(storage_dir=tmp_dir)

            meta_pending = DocumentMetadata(
                doc_id="DOC_DRAFT_001",
                title="Draft Unverified Notes",
                source="Local Informal Flyer",
                publisher="Unverified",
                crop="Cotton",
                publication_date="2026-01-01",
                approval_status="pending"
            )
            repo.ingest_text("Informal unverified recommendation on cotton.", meta_pending)

            # 1. Unapproved document MUST NOT be returned in approved chunks
            approved_chunks = repo.get_approved_chunks()
            self.assertEqual(len(approved_chunks), 0, "Unapproved documents must never be returned")

            # 2. Formally approve document
            repo.approve_document(doc_id="DOC_DRAFT_001", approved_by="Dr. Sharma, Agronomist")
            doc_after = repo.get_document("DOC_DRAFT_001")
            self.assertEqual(doc_after.approval_status, "approved")
            self.assertEqual(doc_after.approved_by, "Dr. Sharma, Agronomist")

            # 3. Now chunks must be available in approved query
            approved_chunks_after = repo.get_approved_chunks()
            self.assertEqual(len(approved_chunks_after), 1)
            self.assertEqual(approved_chunks_after[0].metadata.approval_status, "approved")


class TestHybridRetrievalAndMultilingual(unittest.TestCase):
    """Tests FAISS, BM25, and Reciprocal Rank Fusion on Indic queries."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.service = AgriculturalRAGService(data_dir=self.tmp_dir)

        # Ingest and approve Cotton document
        meta_cotton = DocumentMetadata(
            doc_id="DOC_COTTON_APPROVED",
            title="ICAR-CICR Cotton Advisory: Pink Bollworm",
            source="ICAR-CICR Bulletin 2026",
            publisher="ICAR",
            crop="Cotton",
            region="Maharashtra",
            season="Kharif",
            language="en",
            publication_date="2026-05-15"
        )
        self.service.ingest_pdf(
            "data/raw_documents/cotton_pink_bollworm_icar_advisory.pdf",
            meta_cotton,
            auto_approve=True
        )

        # Ingest and approve Wheat document
        meta_wheat = DocumentMetadata(
            doc_id="DOC_WHEAT_APPROVED",
            title="KVK Wheat Advisory: Yellow Rust",
            source="KVK Extension Bulletin 2026",
            publisher="KVK",
            crop="Wheat",
            region="Punjab",
            season="Rabi",
            language="en",
            publication_date="2026-01-20"
        )
        self.service.ingest_pdf(
            "data/raw_documents/wheat_yellow_rust_kvk_bulletin.pdf",
            meta_wheat,
            auto_approve=True
        )

        # Ingest unapproved document (stays pending)
        meta_draft = DocumentMetadata(
            doc_id="DOC_DRAFT_UNAPPROVED",
            title="Unapproved Draft Notes",
            source="Informal Notes",
            publisher="Unknown",
            crop="Cotton",
            publication_date="2026-01-01",
            approval_status="pending"
        )
        self.service.ingest_pdf(
            "data/raw_documents/unapproved_draft_notes.pdf",
            meta_draft,
            auto_approve=False
        )

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_faiss_vector_search(self):
        results = self.service.vector_index.search(
            query="pink bollworm pheromone traps in cotton",
            top_k=2,
            only_approved=True
        )
        self.assertGreaterEqual(len(results), 1)
        top_chunk, score = results[0]
        self.assertEqual(top_chunk.metadata.crop, "Cotton")
        self.assertEqual(top_chunk.metadata.approval_status, "approved")

    def test_bm25_keyword_search(self):
        results = self.service.bm25_index.search(
            query="yellow rust wheat surveillance",
            top_k=2,
            only_approved=True
        )
        self.assertGreaterEqual(len(results), 1)
        top_chunk, score = results[0]
        self.assertEqual(top_chunk.metadata.crop, "Wheat")
        self.assertIn("yellow rust", top_chunk.text.lower())

    def test_multilingual_indic_query_processing(self):
        # Hindi query on Cotton (कपास गुलाबी सुंडी फेरोमोन ट्रैप)
        query_hi = "कपास में गुलाबी सुंडी की निगरानी और फेरोमोन ट्रैप"
        res_hi = self.service.query(query_hi, language="hi")
        self.assertEqual(res_hi["status"], "answered")
        self.assertGreaterEqual(len(res_hi["evidence_passages"]), 1)
        self.assertEqual(res_hi["evidence_passages"][0]["crop"], "Cotton")

        # Marathi query on Wheat (गव्हावरील पिवळा तांबेरा)
        query_mr = "गहू पिकावरील पिवळा तांबेरा रोग"
        res_mr = self.service.query(query_mr, language="mr")
        self.assertEqual(res_mr["status"], "answered")
        self.assertGreaterEqual(len(res_mr["evidence_passages"]), 1)
        self.assertEqual(res_mr["evidence_passages"][0]["crop"], "Wheat")

    def test_unapproved_document_never_retrieved(self):
        query = "unverified informal pesticide mixes"
        evidence = self.service.retriever.retrieve(query, top_k=5, only_approved=True)

        for res in evidence:
            self.assertEqual(res.chunk.metadata.approval_status, "approved")
            self.assertNotEqual(res.chunk.doc_id, "DOC_DRAFT_UNAPPROVED")

    def test_metadata_crop_filtering(self):
        # Querying with cotton filter must return only Cotton
        results = self.service.retriever.retrieve(
            query="disease management and surveillance",
            crop_filter="Cotton",
            only_approved=True
        )
        for res in results:
            self.assertIn(res.chunk.metadata.crop.lower(), ["cotton", "general", "all"])


class TestGroundedAnswerAndSafeRefusal(unittest.TestCase):
    """Tests grounded generation, citation fidelity, and safe refusal behavior."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.service = AgriculturalRAGService(data_dir=self.tmp_dir)
        meta = DocumentMetadata(
            doc_id="DOC_COTTON_OFFICIAL",
            title="ICAR Cotton Advisory",
            source="ICAR-CICR Official Advisory 2026",
            publisher="Indian Council of Agricultural Research",
            crop="Cotton",
            region="Maharashtra",
            publication_date="2026-05-15"
        )
        self.service.ingest_pdf(
            "data/raw_documents/cotton_pink_bollworm_icar_advisory.pdf",
            meta,
            auto_approve=True
        )

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_grounded_answer_preserves_citations(self):
        resp = self.service.query(
            question="How many pheromone traps per hectare are recommended for pink bollworm in cotton?",
            language="en"
        )
        self.assertEqual(resp["status"], "answered")
        self.assertIn("citations", resp)
        self.assertGreaterEqual(len(resp["citations"]), 1)
        self.assertIn("Indian Council of Agricultural Research", resp["citations"][0])

    def test_safe_refusal_on_unsupported_question(self):
        # Out-of-scope question that has no approved evidence
        resp = self.service.query(
            question="What is the latest stock market price of tech companies in Bengaluru?",
            language="en"
        )
        self.assertEqual(resp["status"], "refused")
        self.assertIn(resp["reason_code"], ["NO_APPROVED_EVIDENCE", "LOW_CONFIDENCE"])
        self.assertIn("1800-180-1551", resp["spoken_text"])
        self.assertTrue(
            "Kisan Call Centre" in resp["spoken_text"] or "Krishi Vigyan Kendra" in resp["spoken_text"]
        )


if __name__ == "__main__":
    unittest.main()
