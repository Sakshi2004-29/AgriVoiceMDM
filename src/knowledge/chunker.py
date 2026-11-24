"""
Structure-aware Chunking for Agricultural Advisories.
Splits documents into meaningful chunks while preserving sentences, section context, and metadata.
"""
import re
from typing import List
from src.knowledge.models import DocumentMetadata, DocumentChunk


class AgriculturalChunker:
    """
    Splits agricultural documents into overlapping, context-preserving chunks.
    Ensures warnings, dosages, and recommendations are not sliced in the middle of sentences.
    """

    def __init__(self, target_chunk_size: int = 500, overlap_size: int = 100):
        """
        Args:
            target_chunk_size: Target character length per chunk.
            overlap_size: Character overlap between consecutive chunks for context continuity.
        """
        self.target_chunk_size = target_chunk_size
        self.overlap_size = overlap_size

    def split_into_sentences(self, text: str) -> List[str]:
        """
        Splits text into sentences supporting English, Hindi, and Marathi punctuation
        (handles full stop '.', purna viram '।', and question marks).
        """
        sentence_endings = re.compile(r"([।\.!?\n]+)")
        tokens = sentence_endings.split(text)
        sentences = []
        for i in range(0, len(tokens) - 1, 2):
            s = (tokens[i] + tokens[i + 1]).strip()
            if s:
                sentences.append(s)
        if len(tokens) % 2 == 1 and tokens[-1].strip():
            sentences.append(tokens[-1].strip())
        return sentences if sentences else [text.strip()]

    def chunk_document(self, doc_id: str, text: str, metadata: DocumentMetadata) -> List[DocumentChunk]:
        """
        Chunks full document text into structured DocumentChunk objects with inherited metadata.
        """
        if not text or not text.strip():
            return []

        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        chunks: List[DocumentChunk] = []
        chunk_idx = 0

        current_sentences: List[str] = []
        current_len = 0
        current_header = None

        for paragraph in paragraphs:
            # Check if paragraph looks like a short heading
            if len(paragraph) < 80 and not paragraph.endswith((".", "।", "?", "!")):
                current_header = paragraph

            sentences = self.split_into_sentences(paragraph)

            for sentence in sentences:
                sentence_len = len(sentence)
                if current_len + sentence_len > self.target_chunk_size and current_sentences:
                    chunk_text = " ".join(current_sentences).strip()
                    chunk_id = f"{doc_id}_chunk_{chunk_idx:03d}"
                    chunks.append(
                        DocumentChunk(
                            chunk_id=chunk_id,
                            doc_id=doc_id,
                            text=chunk_text,
                            chunk_index=chunk_idx,
                            metadata=metadata,
                            section_header=current_header
                        )
                    )
                    chunk_idx += 1

                    # Retain last 1 or 2 sentences for overlap
                    overlap_sentences = []
                    overlap_len = 0
                    for s in reversed(current_sentences):
                        if overlap_len + len(s) <= self.overlap_size:
                            overlap_sentences.insert(0, s)
                            overlap_len += len(s)
                        else:
                            break
                    current_sentences = overlap_sentences
                    current_len = overlap_len

                current_sentences.append(sentence)
                current_len += sentence_len

        # Remaining sentences
        if current_sentences:
            chunk_text = " ".join(current_sentences).strip()
            chunk_id = f"{doc_id}_chunk_{chunk_idx:03d}"
            chunks.append(
                DocumentChunk(
                    chunk_id=chunk_id,
                    doc_id=doc_id,
                    text=chunk_text,
                    chunk_index=chunk_idx,
                    metadata=metadata,
                    section_header=current_header
                )
            )

        return chunks
