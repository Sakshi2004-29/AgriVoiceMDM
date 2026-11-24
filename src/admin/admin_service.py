"""
Admin Console & Expert Review Loop Service (Module 14).
Provides:
1. Administrator authentication.
2. Agricultural document upload, review queue, and approval/rejection.
3. User feedback collection (thumbs up/down, corrections) and audit logs.
4. Telemetry, usage statistics, and retrieval index inspection.
"""
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from src.knowledge.models import DocumentMetadata
from src.knowledge.rag_service import AgriculturalRAGService


class AdminService:
    """
    Manages institutional content review, administrator authentication, and feedback loops.
    """

    # SHA-256 hash for default admin password ("admin@agri2026")
    DEFAULT_ADMIN_HASH = hashlib.sha256("admin@agri2026".encode("utf-8")).hexdigest()

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.feedback_file = self.data_dir / "processed_chunks/feedback_logs.json"
        self.telemetry_file = self.data_dir / "processed_chunks/telemetry_logs.json"
        self.feedback_file.parent.mkdir(parents=True, exist_ok=True)
        self.rag_service = AgriculturalRAGService(data_dir=str(self.data_dir))

    @classmethod
    def verify_credentials(cls, username: str, password: str) -> bool:
        """
        Authenticates an administrator.
        Username: admin
        Default Password: admin@agri2026
        """
        if username.strip().lower() != "admin":
            return False
        pwd_hash = hashlib.sha256(password.strip().encode("utf-8")).hexdigest()
        return pwd_hash == cls.DEFAULT_ADMIN_HASH

    def get_document_inventory(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Returns all registered documents grouped by approval status.
        """
        docs = self.rag_service.repo.documents
        pending = []
        approved = []
        rejected = []

        for doc_id, meta in docs.items():
            item = meta.model_dump()
            chunk_count = len(self.rag_service.repo.chunks.get(doc_id, []))
            item["chunk_count"] = chunk_count

            if meta.approval_status == "approved":
                approved.append(item)
            elif meta.approval_status == "rejected":
                rejected.append(item)
            else:
                pending.append(item)

        return {
            "pending": pending,
            "approved": approved,
            "rejected": rejected,
            "total_documents": len(docs)
        }

    def upload_and_ingest_pdf(
        self,
        file_bytes: bytes,
        filename: str,
        metadata: DocumentMetadata,
        auto_approve: bool = False
    ) -> Dict[str, Any]:
        """
        Saves uploaded PDF to data/raw_documents and ingests it into repository.
        """
        raw_dir = self.data_dir / "raw_documents"
        raw_dir.mkdir(parents=True, exist_ok=True)
        dest_path = raw_dir / filename

        with open(dest_path, "wb") as f:
            f.write(file_bytes)

        chunks = self.rag_service.ingest_pdf(str(dest_path), metadata, auto_approve=auto_approve)

        return {
            "status": "success",
            "doc_id": metadata.doc_id,
            "filename": filename,
            "chunks_created": len(chunks),
            "approval_status": metadata.approval_status
        }

    def approve_document(self, doc_id: str, approved_by: str = "Chief Agronomist", notes: Optional[str] = None) -> bool:
        """Approves a document and immediately rebuilds search indexes."""
        self.rag_service.approve_document(doc_id, approved_by=approved_by, notes=notes)
        return True

    def reject_document(self, doc_id: str, reason: str = "Unverified advisory") -> bool:
        """Rejects a document and removes its chunks from active search indexes."""
        self.rag_service.reject_document(doc_id, reason=reason)
        return True

    def record_user_feedback(
        self,
        user_hash: str,
        query: str,
        answer_status: str,
        rating: str,  # 'thumbs_up' or 'thumbs_down'
        comments: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Records farmer feedback for expert review.
        """
        logs = []
        if self.feedback_file.exists():
            try:
                with open(self.feedback_file, "r", encoding="utf-8") as f:
                    logs = json.load(f)
            except Exception:
                logs = []

        entry = {
            "feedback_id": f"FB_{len(logs) + 1:04d}",
            "timestamp": datetime.now().isoformat(),
            "user_hash": user_hash,
            "query": query,
            "answer_status": answer_status,
            "rating": rating,
            "comments": comments or ""
        }
        logs.append(entry)

        with open(self.feedback_file, "w", encoding="utf-8") as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)

        return entry

    def get_feedback_logs(self) -> List[Dict[str, Any]]:
        """Returns all recorded user feedback."""
        if self.feedback_file.exists():
            try:
                with open(self.feedback_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def get_system_telemetry(self) -> Dict[str, Any]:
        """
        Returns real-time system metrics: index stats, approved chunks, and feedback stats.
        """
        inv = self.get_document_inventory()
        feedback = self.get_feedback_logs()

        thumbs_up = sum(1 for fb in feedback if fb.get("rating") == "thumbs_up")
        thumbs_down = sum(1 for fb in feedback if fb.get("rating") == "thumbs_down")

        approved_chunks = len(self.rag_service.repo.get_approved_chunks())
        total_chunks = len(self.rag_service.repo.get_all_chunks())

        return {
            "total_documents": inv["total_documents"],
            "pending_documents_count": len(inv["pending"]),
            "approved_documents_count": len(inv["approved"]),
            "rejected_documents_count": len(inv["rejected"]),
            "total_chunks_in_registry": total_chunks,
            "approved_chunks_in_faiss": approved_chunks,
            "faiss_index_entries": self.rag_service.vector_index.index.ntotal,
            "bm25_corpus_size": self.rag_service.bm25_index.corpus_size,
            "feedback_total": len(feedback),
            "feedback_positive": thumbs_up,
            "feedback_negative": thumbs_down
        }
