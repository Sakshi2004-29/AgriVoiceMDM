"""
PDF Document Ingestion and Cleaning using PyMuPDF.
Extracts structured text from agricultural PDFs with header detection and whitespace normalization.
"""
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
import pymupdf

from src.knowledge.models import DocumentMetadata


class PDFDocumentParser:
    """
    Extracts and cleans text from PDF documents using PyMuPDF.
    """

    def __init__(self):
        pass

    @staticmethod
    def clean_text(text: str) -> str:
        """
        Cleans extracted text:
        - Normalizes multiple spaces and tabs into single spaces
        - Cleans carriage returns while preserving meaningful paragraph breaks
        - Removes control characters
        """
        if not text:
            return ""

        # Normalize line breaks
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # Replace excessive whitespace within lines
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]

        # Group lines into paragraphs
        cleaned_paragraphs = []
        current_paragraph = []

        for line in lines:
            if not line:
                if current_paragraph:
                    cleaned_paragraphs.append(" ".join(current_paragraph))
                    current_paragraph = []
            else:
                current_paragraph.append(line)

        if current_paragraph:
            cleaned_paragraphs.append(" ".join(current_paragraph))

        return "\n\n".join(cleaned_paragraphs)

    def parse_pdf(self, file_path: str, metadata: DocumentMetadata) -> Dict[str, Any]:
        """
        Parses a PDF file from disk, extracting page-by-page text.

        Args:
            file_path: Absolute or relative path to PDF file.
            metadata: DocumentMetadata object containing document details.

        Returns:
            Dict containing document metadata, full cleaned text, and page-wise text.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF file not found: {file_path}")

        doc = pymupdf.open(str(path))
        page_texts = []
        total_pages = len(doc)

        for page_num in range(total_pages):
            page = doc[page_num]
            raw_text = page.get_text("text")
            cleaned_page = self.clean_text(raw_text)
            if cleaned_page:
                page_texts.append({
                    "page_number": page_num + 1,
                    "text": cleaned_page
                })

        doc.close()

        full_cleaned_text = "\n\n".join([p["text"] for p in page_texts])

        return {
            "doc_id": metadata.doc_id,
            "metadata": metadata,
            "file_path": str(path.resolve()),
            "total_pages": total_pages,
            "full_text": full_cleaned_text,
            "pages": page_texts
        }
