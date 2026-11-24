"""
Phase 2 Interactive Demonstration Script.
Demonstrates:
1. Ingestion of ICAR and KVK agricultural advisory PDFs using PyMuPDF.
2. Structure-aware chunking and metadata preservation.
3. Human/Expert approval workflow (approved vs. unapproved documents).
4. Hybrid Retrieval (FAISS Dense Vector + BM25 Sparse with RRF).
5. Multilingual Indic queries (English, Hindi, Marathi).
6. Evidence-grounded answers with exact institutional citations.
7. Safe refusal and Kisan Call Centre referral (1800-180-1551) on out-of-scope questions.
"""
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.knowledge.models import DocumentMetadata
from src.knowledge.rag_service import AgriculturalRAGService


def print_banner(text: str):
    print("\n" + "=" * 80)
    print(f" {text}")
    print("=" * 80)


def main():
    print_banner("PHASE 2 DEMONSTRATION: AGRICULTURAL KNOWLEDGE INGESTION & HYBRID RAG")

    rag_service = AgriculturalRAGService(data_dir="data")

    # 1. Ingest Approved ICAR Cotton Advisory
    print("\n[Step 1] Ingesting & Approving Official ICAR Cotton Advisory...")
    meta_cotton = DocumentMetadata(
        doc_id="DOC_ICAR_COTTON_001",
        title="ICAR-CICR Cotton Advisory: Pink Bollworm Management",
        source="ICAR-CICR Advisory Bulletin 2026",
        publisher="Indian Council of Agricultural Research",
        crop="Cotton",
        region="Maharashtra",
        season="Kharif",
        language="en",
        publication_date="2026-05-15"
    )
    cotton_chunks = rag_service.ingest_pdf(
        "data/raw_documents/cotton_pink_bollworm_icar_advisory.pdf",
        meta_cotton,
        auto_approve=True
    )
    print(f"  -> Ingested {len(cotton_chunks)} chunks from ICAR Cotton Advisory.")
    print(f"  -> Status: {meta_cotton.approval_status.upper()} by Agronomist.")

    # 2. Ingest Approved KVK Wheat Advisory
    print("\n[Step 2] Ingesting & Approving Official KVK Wheat Advisory...")
    meta_wheat = DocumentMetadata(
        doc_id="DOC_KVK_WHEAT_001",
        title="KVK Wheat Advisory: Yellow Rust Surveillance & Field Guidance",
        source="KVK Agricultural Extension Bulletin 2026",
        publisher="Krishi Vigyan Kendra (KVK)",
        crop="Wheat",
        region="Punjab",
        season="Rabi",
        language="en",
        publication_date="2026-01-20"
    )
    wheat_chunks = rag_service.ingest_pdf(
        "data/raw_documents/wheat_yellow_rust_kvk_bulletin.pdf",
        meta_wheat,
        auto_approve=True
    )
    print(f"  -> Ingested {len(wheat_chunks)} chunks from KVK Wheat Advisory.")
    print(f"  -> Status: {meta_wheat.approval_status.upper()} by Agronomist.")

    # 3. Ingest Unapproved Draft File (Intentionally kept 'pending')
    print("\n[Step 3] Ingesting Unverified Draft Document (Pending Approval)...")
    meta_draft = DocumentMetadata(
        doc_id="DOC_UNVERIFIED_DRAFT_001",
        title="DRAFT: Unverified Field Notes on Chemical Application",
        source="Unverified Local Shop Flyer",
        publisher="Unverified Shop",
        crop="Cotton",
        publication_date="2026-01-01",
        approval_status="pending"
    )
    draft_chunks = rag_service.ingest_pdf(
        "data/raw_documents/unapproved_draft_notes.pdf",
        meta_draft,
        auto_approve=False
    )
    print(f"  -> Ingested {len(draft_chunks)} chunks.")
    print(f"  -> Status: {meta_draft.approval_status.upper()} (Excluded from search indexes).")

    # 4. English Query on Cotton Pest Management
    print_banner("DEMO QUERY 1: English Question on Cotton Pest Monitoring")
    q1 = "How many pheromone traps are recommended to monitor pink bollworm in cotton?"
    print(f"Farmer Query: '{q1}' (Language: en)")
    res1 = rag_service.query(q1, language="en")
    print(f"Status: {res1['status'].upper()}")
    print(f"Answer: {res1['answer_text']}")
    print(f"Citations: {res1.get('citations')}")

    # 5. Hindi Query on Cotton Pink Bollworm
    print_banner("DEMO QUERY 2: Hindi Question (कपास में गुलाबी सुंडी)")
    q2 = "कपास में गुलाबी सुंडी की रोकथाम के लिए क्या उपाय करें?"
    print(f"Farmer Query: '{q2}' (Language: hi)")
    res2 = rag_service.query(q2, language="hi")
    print(f"Status: {res2['status'].upper()}")
    print(f"Answer: {res2['answer_text']}")
    print(f"Citations: {res2.get('citations')}")

    # 6. Marathi Query on Wheat Yellow Rust
    print_banner("DEMO QUERY 3: Marathi Question (गहू पिकावरील पिवळा तांबेरा)")
    q3 = "गहू पिकावरील पिवळा तांबेरा रोगाची लक्षणे काय आहेत?"
    print(f"Farmer Query: '{q3}' (Language: mr)")
    res3 = rag_service.query(q3, language="mr")
    print(f"Status: {res3['status'].upper()}")
    print(f"Answer: {res3['answer_text']}")
    print(f"Citations: {res3.get('citations')}")

    # 7. Safety Test: Unsupported / Out-of-Scope Query
    print_banner("DEMO QUERY 4: Out-of-Scope Query (Zero-Guessing Safe Refusal)")
    q4 = "What are the latest cryptocurrency prices in Mumbai?"
    print(f"Query: '{q4}' (Language: en)")
    res4 = rag_service.query(q4, language="en")
    print(f"Status: {res4['status'].upper()} (Reason: {res4.get('reason_code')})")
    print(f"Spoken Refusal: {res4.get('spoken_text')}")
    print(f"Referral Helpline: {res4.get('referrals', {}).get('kisan_call_centre')}")

    # 8. Security Gate Test: Querying unapproved content
    print_banner("DEMO QUERY 5: Querying Unapproved Draft Notes (Security Gate)")
    q5 = "What is the recommended informal pesticide mix from the unverified notes?"
    print(f"Query: '{q5}' (Language: en)")
    res5 = rag_service.query(q5, language="en")
    print(f"Status: {res5['status'].upper()}")
    print(f"Retrieved Sources: {res5.get('citations')}")
    # Verify unapproved doc is not in evidence
    retrieved_doc_ids = [ep["chunk_id"].split("_chunk_")[0] for ep in res5.get("evidence_passages", [])]
    assert "DOC_UNVERIFIED_DRAFT_001" not in retrieved_doc_ids
    print("Verification: 'DOC_UNVERIFIED_DRAFT_001' (Draft) was STRICTLY BLOCKED from retrieval!")

    print_banner("PHASE 2 DEMONSTRATION COMPLETE - ALL SYSTEMS FUNCTIONING PROPERLY")


if __name__ == "__main__":
    main()
