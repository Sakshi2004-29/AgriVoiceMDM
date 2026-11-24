"""
Agricultural Document Repository and Approval Manager.
Enforces the strict rule that ONLY approved documents can be retrieved by the RAG pipeline.
"""
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from src.knowledge.models import DocumentMetadata, DocumentChunk
from src.knowledge.doc_parser import PDFDocumentParser
from src.knowledge.chunker import AgriculturalChunker


class DocumentRepository:
    """
    Manages document ingestion, storage, metadata persistence, and human/expert approval workflow.
    """

    def __init__(self, storage_dir: str = "data/processed_chunks"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.registry_file = self.storage_dir / "documents_registry.json"

        self.parser = PDFDocumentParser()
        self.chunker = AgriculturalChunker()

        # In-memory document and chunk storage
        self.documents: Dict[str, DocumentMetadata] = {}
        self.chunks: Dict[str, List[DocumentChunk]] = {}

        self._load_registry()

    def _load_registry(self):
        """Loads previously saved documents and chunks if available."""
        if self.registry_file.exists():
            try:
                with open(self.registry_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for doc_id, doc_data in data.get("documents", {}).items():
                        self.documents[doc_id] = DocumentMetadata(**doc_data)
                    for doc_id, chunk_list in data.get("chunks", {}).items():
                        self.chunks[doc_id] = [DocumentChunk(**c) for c in chunk_list]
            except Exception as e:
                print(f"Warning: Could not load existing document registry: {e}")

    def save_registry(self):
        """Persists document metadata and chunks to disk."""
        data = {
            "documents": {doc_id: doc.model_dump() for doc_id, doc in self.documents.items()},
            "chunks": {
                doc_id: [chunk.model_dump() for chunk in chunk_list]
                for doc_id, chunk_list in self.chunks.items()
            }
        }
        with open(self.registry_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def ingest_pdf(self, pdf_path: str, metadata: DocumentMetadata) -> List[DocumentChunk]:
        """
        Parses and chunks a PDF document.
        Defaults document status to 'pending' if not explicitly approved.
        """
        # Store metadata
        self.documents[metadata.doc_id] = metadata

        # Parse PDF text
        parsed = self.parser.parse_pdf(pdf_path, metadata)

        # Chunk parsed text
        doc_chunks = self.chunker.chunk_document(metadata.doc_id, parsed["full_text"], metadata)
        self.chunks[metadata.doc_id] = doc_chunks

        self.save_registry()
        return doc_chunks

    def ingest_text(self, text: str, metadata: DocumentMetadata) -> List[DocumentChunk]:
        """
        Ingests direct verified text with metadata (for advisories or circulars).
        """
        self.documents[metadata.doc_id] = metadata
        cleaned_text = self.parser.clean_text(text)
        doc_chunks = self.chunker.chunk_document(metadata.doc_id, cleaned_text, metadata)
        self.chunks[metadata.doc_id] = doc_chunks

        self.save_registry()
        return doc_chunks

    def approve_document(self, doc_id: str, approved_by: str = "Certified Agronomist", notes: Optional[str] = None) -> bool:
        """
        Formally marks a document as 'approved'.
        Propagates approval status to all its chunks, making them eligible for RAG retrieval.
        """
        if doc_id not in self.documents:
            raise KeyError(f"Document ID '{doc_id}' not found in registry.")

        doc_meta = self.documents[doc_id]
        doc_meta.approval_status = "approved"
        doc_meta.approved_by = approved_by
        doc_meta.approval_date = datetime.now().isoformat()
        if notes:
            doc_meta.notes = notes

        # Update all chunks for this document
        if doc_id in self.chunks:
            for chunk in self.chunks[doc_id]:
                chunk.metadata.approval_status = "approved"
                chunk.metadata.approved_by = approved_by
                chunk.metadata.approval_date = doc_meta.approval_date

        self.save_registry()
        return True

    def reject_document(self, doc_id: str, reason: str = "Unverified or flawed guidance") -> bool:
        """
        Formally marks a document as 'rejected', preventing any chunk from being retrieved.
        """
        if doc_id not in self.documents:
            raise KeyError(f"Document ID '{doc_id}' not found in registry.")

        doc_meta = self.documents[doc_id]
        doc_meta.approval_status = "rejected"
        doc_meta.notes = reason

        if doc_id in self.chunks:
            for chunk in self.chunks[doc_id]:
                chunk.metadata.approval_status = "rejected"
                chunk.metadata.notes = reason

        self.save_registry()
        return True

    def get_document(self, doc_id: str) -> Optional[DocumentMetadata]:
        return self.documents.get(doc_id)

    def get_all_chunks(self) -> List[DocumentChunk]:
        """Returns all chunks regardless of approval status."""
        all_chunks = []
        for chunk_list in self.chunks.values():
            all_chunks.extend(chunk_list)
        return all_chunks

    def get_approved_chunks(self, crop: Optional[str] = None, region: Optional[str] = None) -> List[DocumentChunk]:
        """
        CRITICAL SAFETY GATE:
        Returns ONLY chunks belonging to approved documents.
        Optionally filters by crop and region if specified.
        """
        approved_chunks = []
        for doc_id, meta in self.documents.items():
            if meta.approval_status == "approved":
                for chunk in self.chunks.get(doc_id, []):
                    # Filter by crop if provided and not 'General' / 'All'
                    if crop and crop.lower() != "all" and chunk.metadata.crop.lower() not in [crop.lower(), "general", "all"]:
                        continue
                    # Filter by region if provided and not 'National' / 'All'
                    if region and region.lower() != "all" and chunk.metadata.region.lower() not in [region.lower(), "national", "all"]:
                        continue
                    approved_chunks.append(chunk)

        return approved_chunks
