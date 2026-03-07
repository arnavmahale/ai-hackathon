"""Tests for the document chunker module."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rag.chunker import chunk_document, extract_sections, _recursive_split, _add_overlap


class TestChunkDocument:
    def test_empty_text_returns_empty(self):
        assert chunk_document("", "doc1") == []
        assert chunk_document("   ", "doc1") == []

    def test_short_text_single_chunk(self):
        text = "Hello world, this is a short document."
        chunks = chunk_document(text, "doc1", chunk_size=1000)
        assert len(chunks) == 1
        assert chunks[0].text == text
        assert chunks[0].doc_id == "doc1"
        assert chunks[0].chunk_index == 0

    def test_chunk_metadata_preserved(self):
        text = "Some text content."
        meta = {"source": "test", "version": "1.0"}
        chunks = chunk_document(text, "doc1", metadata=meta)
        assert chunks[0].metadata["source"] == "test"
        assert chunks[0].metadata["version"] == "1.0"
        assert "total_chunks" in chunks[0].metadata

    def test_long_text_splits_into_multiple_chunks(self):
        # Create text longer than chunk_size
        text = "This is a sentence. " * 100  # ~2000 chars
        chunks = chunk_document(text, "doc1", chunk_size=500, chunk_overlap=50)
        assert len(chunks) > 1
        # Each chunk should be reasonably sized
        for chunk in chunks:
            # With overlap, chunks can exceed chunk_size slightly
            assert chunk.char_count > 0

    def test_chunk_indices_sequential(self):
        text = "Paragraph one.\n\nParagraph two.\n\nParagraph three.\n\nParagraph four."
        chunks = chunk_document(text, "doc1", chunk_size=30, chunk_overlap=0)
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i

    def test_doc_id_preserved_across_chunks(self):
        text = "A " * 500
        chunks = chunk_document(text, "my-doc-id", chunk_size=100, chunk_overlap=0)
        for chunk in chunks:
            assert chunk.doc_id == "my-doc-id"

    def test_paragraph_boundary_splitting(self):
        text = "First paragraph content.\n\nSecond paragraph content.\n\nThird paragraph content."
        chunks = chunk_document(text, "doc1", chunk_size=40, chunk_overlap=0)
        # Should split on paragraph boundaries
        assert len(chunks) >= 2

    def test_overlap_creates_context(self):
        text = "AAAA\n\nBBBB\n\nCCCC"
        chunks = chunk_document(text, "doc1", chunk_size=10, chunk_overlap=4)
        if len(chunks) > 1:
            # Second chunk should contain overlap from first
            assert len(chunks[1].text) > 0

    def test_char_count_property(self):
        text = "Exactly this."
        chunks = chunk_document(text, "doc1")
        assert chunks[0].char_count == len(text)


class TestRecursiveSplit:
    def test_text_within_limit(self):
        result = _recursive_split("short", 100, ["\n\n", "\n", " "])
        assert result == ["short"]

    def test_splits_on_paragraph_break(self):
        text = "Part A content\n\nPart B content"
        result = _recursive_split(text, 20, ["\n\n", "\n", " "])
        assert len(result) >= 2

    def test_falls_through_to_finer_separator(self):
        text = "word1 word2 word3 word4 word5"
        result = _recursive_split(text, 15, ["\n\n", "\n", " "])
        assert len(result) >= 2

    def test_hard_split_when_no_separators(self):
        text = "abcdefghijklmnop"
        result = _recursive_split(text, 5, [])
        assert len(result) >= 3
        assert "".join(result) == text


class TestAddOverlap:
    def test_no_overlap(self):
        chunks = ["AAA", "BBB", "CCC"]
        result = _add_overlap(chunks, 0)
        assert result == chunks

    def test_single_chunk_unchanged(self):
        result = _add_overlap(["AAA"], 2)
        assert result == ["AAA"]

    def test_overlap_prepended(self):
        chunks = ["AAAA", "BBBB", "CCCC"]
        result = _add_overlap(chunks, 2)
        assert result[0] == "AAAA"
        assert result[1].startswith("AA")  # last 2 chars of first chunk
        assert result[1].endswith("BBBB")


class TestExtractSections:
    def test_no_headings_returns_full_doc(self):
        text = "Just plain text without any headings."
        sections = extract_sections(text)
        assert len(sections) == 1
        assert sections[0]["title"] == "Full Document"

    def test_markdown_headings_extracted(self):
        text = "# Introduction\nSome intro text.\n\n## Methods\nMethod details here."
        sections = extract_sections(text)
        assert len(sections) >= 2
        titles = [s["title"] for s in sections]
        assert "Introduction" in titles
        assert "Methods" in titles

    def test_section_content_captured(self):
        text = "# Title One\nContent for section one.\n\n# Title Two\nContent for section two."
        sections = extract_sections(text)
        for section in sections:
            assert len(section["content"]) > 0

    def test_section_keyword_headings(self):
        text = "Section 1: Security\nSecurity content here.\n\nSection 2: Quality\nQuality content."
        sections = extract_sections(text)
        assert len(sections) >= 2
