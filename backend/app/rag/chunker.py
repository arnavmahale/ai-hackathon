"""Document chunking for RAG pipeline.
Supports two chunking strategies:
1. **Recursive character splitting** 
2. **Semantic chunking**:
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from .embeddings import EmbeddingClient


class ChunkingStrategy(str, Enum):
    """Chunking strategy selection.

    RECURSIVE: Fast, deterministic, character-based splitting with overlap.
    SEMANTIC: Embedding-based splitting that respects topic boundaries.
    """
    RECURSIVE = "recursive"
    SEMANTIC = "semantic"


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

# Abbreviations to avoid false sentence splits
_ABBREVIATIONS = {
    "mr", "mrs", "ms", "dr", "prof", "sr", "jr", "st", "ave",
    "inc", "ltd", "co", "corp", "dept", "univ", "govt",
    "vs", "etc", "approx", "appt", "apt", "dept", "est",
    "min", "max", "misc", "no", "vol", "rev", "fig",
    "e.g", "i.e", "al",
}


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
                # Part itself is too large -- recurse with finer separators
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


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors. """
    dot = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a < 1e-12 or norm_b < 1e-12:
        return 0.0
    return float(dot / (norm_a * norm_b))


def _split_into_sentences(text: str) -> List[str]:
    """Split text into sentences, handling abbreviations and edge cases."""
    # First split on newlines that look like sentence boundaries
    text = re.sub(r'\n{2,}', ' [PARA_BREAK] ', text)
    text = re.sub(r'\n', ' ', text)

    # Split on sentence-ending punctuation followed by space + uppercase
    # Negative lookbehind for common abbreviations
    abbr_pattern = '|'.join(re.escape(a) for a in _ABBREVIATIONS)
    pattern = rf'(?<!(?:{abbr_pattern}))\.\s+(?=[A-Z])|[!?]\s+(?=[A-Z])|\[PARA_BREAK\]'

    parts = re.split(pattern, text)
    sentences = [s.strip() for s in parts if s.strip()]
    return sentences


def semantic_chunk_document(
    text: str,
    doc_id: str,
    embedding_client: "EmbeddingClient",
    breakpoint_percentile: float = 25.0,
    min_chunk_size: int = 100,
    max_chunk_size: int = 2000,
    metadata: Optional[dict] = None,
) -> List[Chunk]:
    """Split a document into chunks based on semantic similarity between sentences.

    Algorithm:
    1. Split text into sentences
    2. Embed each sentence
    3. Compute cosine similarity between consecutive sentence pairs
    4. Identify breakpoints where similarity drops below the Nth percentile
       (low similarity = topic shift = good place to split)
    5. Group sentences between breakpoints into chunks
    6. Post-process: merge tiny chunks, split oversized ones

    """
    if not text or not text.strip():
        return []

    sentences = _split_into_sentences(text.strip())
    if not sentences:
        return []

    # For very short documents, fall back to recursive splitting
    if len(sentences) <= 3:
        return chunk_document(
            text=text, doc_id=doc_id, chunk_size=max_chunk_size,
            chunk_overlap=200, metadata=metadata,
        )

    # Step 2: Embed all sentences
    embeddings = embedding_client.embed_texts(sentences)

    # Step 3: Compute consecutive cosine similarities
    similarities = []
    for i in range(len(embeddings) - 1):
        sim = _cosine_similarity(embeddings[i], embeddings[i + 1])
        similarities.append(sim)

    # Step 4: Find breakpoints (similarity drops below threshold)
    # Lower similarity = bigger topic shift = good split point
    threshold = float(np.percentile(similarities, breakpoint_percentile))
    breakpoints = [i + 1 for i, sim in enumerate(similarities) if sim < threshold]

    # Step 5: Group sentences between breakpoints
    raw_groups = []
    start = 0
    for bp in breakpoints:
        group = " ".join(sentences[start:bp])
        if group.strip():
            raw_groups.append(group)
        start = bp
    # Last group
    last_group = " ".join(sentences[start:])
    if last_group.strip():
        raw_groups.append(last_group)

    # Step 6: Post-process - merge small chunks, split large ones
    processed = []
    buffer = ""
    for group in raw_groups:
        if len(buffer) + len(group) < min_chunk_size:
            buffer = (buffer + " " + group).strip()
        else:
            if buffer:
                processed.append(buffer)
            buffer = group
    if buffer:
        if processed and len(buffer) < min_chunk_size:
            processed[-1] = processed[-1] + " " + buffer
        else:
            processed.append(buffer)

    # Split any oversized chunks using recursive splitting
    final_chunks = []
    for group in processed:
        if len(group) > max_chunk_size:
            sub = _recursive_split(group, max_chunk_size, list(_SEPARATORS))
            final_chunks.extend(sub)
        else:
            final_chunks.append(group)

    base_meta = metadata or {}
    base_meta["chunking_strategy"] = "semantic"
    chunks = []
    for i, chunk_text in enumerate(final_chunks):
        chunks.append(Chunk(
            text=chunk_text.strip(),
            doc_id=doc_id,
            chunk_index=i,
            metadata={**base_meta, "total_chunks": len(final_chunks)},
        ))

    return chunks


def chunk_document(
    text: str,
    doc_id: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    metadata: Optional[dict] = None,
    strategy: ChunkingStrategy = ChunkingStrategy.RECURSIVE,
    embedding_client: Optional["EmbeddingClient"] = None,
    breakpoint_percentile: float = 25.0,
) -> List[Chunk]:
    """Split a document into chunks for embedding.
    Returns:
        List of Chunk objects with text, source info, and position.
    """
    if not text or not text.strip():
        return []

    # Semantic chunking path
    if strategy == ChunkingStrategy.SEMANTIC:
        if embedding_client is None:
            raise ValueError("embedding_client is required for SEMANTIC chunking strategy")
        return semantic_chunk_document(
            text=text,
            doc_id=doc_id,
            embedding_client=embedding_client,
            breakpoint_percentile=breakpoint_percentile,
            min_chunk_size=100,
            max_chunk_size=chunk_size * 2,
            metadata=metadata,
        )

    # Recursive character splitting path (default)
    raw_chunks = _recursive_split(text.strip(), chunk_size, list(_SEPARATORS))
    overlapped = _add_overlap(raw_chunks, chunk_overlap)

    base_meta = metadata or {}
    base_meta["chunking_strategy"] = "recursive"
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
        r'^(?:#{1,6}\s+|(?:Section|Chapter|Part)\s*[\d.:]*\s*[-\u2013\u2014:]?\s*)(.+)',
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
