"""
Data models for the Agricultural Knowledge Base and RAG pipeline.
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class DocumentMetadata(BaseModel):
    """
    Standard metadata schema for all ingested agricultural documents.
    Preserves provenance, approval status, and agricultural categorization.
    """
    doc_id: str = Field(..., description="Unique document identifier")
    title: str = Field(..., description="Human-readable title of the advisory or circular")
    source: str = Field(..., description="Official source publication (e.g., ICAR-CICR, KVK, Ministry)")
    publisher: str = Field(..., description="Institutional publisher (e.g., ICAR, MPKV, DA&FW)")
    crop: str = Field(default="General", description="Target crop (e.g., Cotton, Wheat, Rice, Soybean, General)")
    region: str = Field(default="National", description="Target state or agro-climatic region (e.g., Maharashtra, Punjab)")
    season: str = Field(default="All", description="Crop season (e.g., Kharif, Rabi, Zaid, All)")
    language: str = Field(default="en", description="Document language code (e.g., hi, mr, en)")
    publication_date: str = Field(..., description="Date of publication (YYYY-MM-DD)")
    version: str = Field(default="1.0", description="Document version number")
    licence: str = Field(default="Government Open Data / Public Domain", description="Licence terms of the source")
    approval_status: str = Field(default="pending", description="'pending', 'approved', or 'rejected'")
    approved_by: Optional[str] = Field(default=None, description="Name or role of the reviewing agronomist/admin")
    approval_date: Optional[str] = Field(default=None, description="ISO timestamp of approval")
    notes: Optional[str] = Field(default=None, description="Review notes or warnings")


class DocumentChunk(BaseModel):
    """
    Individual chunk of an agricultural document with full provenance.
    """
    chunk_id: str = Field(..., description="Unique chunk identifier (e.g., doc_id_001)")
    doc_id: str = Field(..., description="Parent document identifier")
    text: str = Field(..., description="Cleaned passage text")
    chunk_index: int = Field(..., description="Sequential index within the document")
    metadata: DocumentMetadata = Field(..., description="Inherited document metadata")
    section_header: Optional[str] = Field(default=None, description="Section heading if detected")


class SearchResult(BaseModel):
    """
    Retrieved evidence passage with ranking scores and metadata.
    """
    chunk: DocumentChunk
    dense_score: float = 0.0
    sparse_score: float = 0.0
    combined_score: float = 0.0
    rank: int = 0
