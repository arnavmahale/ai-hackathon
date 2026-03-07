"""Document chunking for RAG pipeline.

Splits documents into overlapping chunks using recursive character splitting.
Each chunk retains metadata about its source document and position.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Chunk:
    text: str
    doc_id: str
    chunk_index: int
    metadata: dict = field(default_factory=dict)

    @property
    def char_count(self) -> int:
        return len(self.text)


# Separators ordered from most to least structural
_SEPARATORS = [
    "\n\n\n",    # triple newline (major section break)
    "\n\n",      # paragraph break
    "\n",        # line break
    ". ",        # sentence break
    " ",         # word break
]


def _split_on_separator(text: str, separator: str) -> List[str]:
    parts = text.split(separator)
    # Re-attach separator to end of each part (except last) so context isn't lost
    result = []
    for i, part in enumerate(parts):
        if i < len(parts) - 1:
            result.append(part + separator)
        else:
            result.append(part)
    return [p for p in result if p.strip()]


def _recursive_split(text: str, chunk_size: int, separators: List[str]) -> List[str]:
    if len(text) <= chunk_size:
        return [text]

    if not separators:
        # Fallback: hard split at chunk_size boundary
        chunks = []
        for i in range(0, len(text), chunk_size):
            chunks.append(text[i:i + chunk_size])
        return chunks

    sep = separators[0]
    remaining_seps = separators[1:]

    if sep not in text:
        return _recursive_split(text, chunk_size, remaining_seps)

    parts = _split_on_separator(text, sep)
    chunks = []
    current = ""

    for part in parts:
        if len(current) + len(part) <= chunk_size:
            current += part
        else:
            if current.strip():
                chunks.append(current)
            if len(part) > chunk_size:
                # Part itself is too large — recurse with finer separators
                sub_chunks = _recursive_split(part, chunk_size, remaining_seps)
                chunks.extend(sub_chunks)
                current = ""
            else:
                current = part

    if current.strip():
        chunks.append(current)

    return chunks


def _add_overlap(chunks: List[str], overlap: int) -> List[str]:
    if overlap <= 0 or len(chunks) <= 1:
        return chunks

    result = [chunks[0]]
    for i in range(1, len(chunks)):
        prev = chunks[i - 1]
        overlap_text = prev[-overlap:] if len(prev) > overlap else prev
        result.append(overlap_text + chunks[i])
    return result


def chunk_document(
    text: str,
    doc_id: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    metadata: Optional[dict] = None,
) -> List[Chunk]:
    """Split a document into overlapping chunks for embedding.

    Args:
        text: Full document text.
        doc_id: Unique identifier for the source document.
        chunk_size: Target maximum characters per chunk.
        chunk_overlap: Number of overlapping characters between consecutive chunks.
        metadata: Extra metadata to attach to every chunk.

    Returns:
        List of Chunk objects with text, source info, and position.
    """
    if not text or not text.strip():
        return []

    raw_chunks = _recursive_split(text.strip(), chunk_size, list(_SEPARATORS))
    overlapped = _add_overlap(raw_chunks, chunk_overlap)

    base_meta = metadata or {}
    chunks = []
    for i, chunk_text in enumerate(overlapped):
        chunks.append(Chunk(
            text=chunk_text.strip(),
            doc_id=doc_id,
            chunk_index=i,
            metadata={**base_meta, "total_chunks": len(overlapped)},
        ))

    return chunks


def extract_sections(text: str) -> List[dict]:
    """Extract titled sections from a document using heading-like patterns.

    Returns list of {"title": str, "content": str} dicts.
    """
    heading_pattern = re.compile(
        r'^(?:#{1,6}\s+|(?:Section|Chapter|Part)\s*[\d.:]*\s*[-–—:]?\s*)(.+)',
        re.MULTILINE | re.IGNORECASE,
    )

    matches = list(heading_pattern.finditer(text))
    if not matches:
        return [{"title": "Full Document", "content": text}]

    sections = []
    for i, match in enumerate(matches):
        title = match.group(1).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()
        if content:
            sections.append({"title": title, "content": content})

    return sections
