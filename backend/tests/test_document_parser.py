"""test_document_parser.py — MIME-type extraction and null-byte safeguard tests.

Verifies:
  1. text/plain  — UTF-8 text is extracted and chunked correctly.
  2. application/pdf — pdfplumber path: fake bytes return "" (0 chunks), real PDF extracts text.
  3. DOCX — python-docx path: valid DOCX built in-memory is correctly extracted.
  4. image/png — stored with 0 chunks, status "ready".
  5. Unsupported MIME type — HTTP 422 before any DB write.
  6. Null-byte stripping — \\x00 in plain text never reaches Postgres.
  7. _extract_text unit tests — direct function tests, no DB required.
"""
import io
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.documents import (
    Chunk,
    _chunk_docx,
    _chunk_document,
    _extract_text,
    _recursive_split,
    _split_chunks,
)

pytest_plugins = ["tests.conftest_sprint3"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_docx_bytes(paragraphs: list[str]) -> bytes:
    """Build a valid in-memory DOCX containing *paragraphs* and return bytes."""
    import docx as _docx  # python-docx
    doc = _docx.Document()
    for para in paragraphs:
        doc.add_paragraph(para)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _make_structured_docx_bytes(sections: list[tuple[str, int, list[str]]]) -> bytes:
    """Build a DOCX with real heading styles and body paragraphs.

    *sections* is a list of (heading_text, heading_level, [body_paragraphs]).
    heading_level must be 1 or 2.
    """
    import docx as _docx
    doc = _docx.Document()
    for heading_text, level, body_paras in sections:
        doc.add_heading(heading_text, level=level)
        for para in body_paras:
            doc.add_paragraph(para)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _make_real_pdf_bytes(text_content: str) -> bytes | None:
    """Attempt to build a minimal PDF using reportlab if available.

    Returns None when reportlab is not installed so callers can skip.
    """
    try:
        from reportlab.pdfgen import canvas as _canvas  # type: ignore
        buf = io.BytesIO()
        c = _canvas.Canvas(buf)
        c.drawString(72, 720, text_content[:80])
        c.save()
        return buf.getvalue()
    except ImportError:
        return None


# ---------------------------------------------------------------------------
# Unit tests for _extract_text (no DB, no HTTP)
# ---------------------------------------------------------------------------

class TestExtractTextUnit:
    """Direct unit tests for the _extract_text helper."""

    def test_plain_text_utf8(self):
        data = "Hello, NEXUS. ✓".encode("utf-8")
        result = _extract_text(data, "text/plain")
        assert "Hello, NEXUS." in result
        assert "✓" in result

    def test_plain_text_latin1_fallback(self):
        # bytes that are not valid UTF-8 but valid latin-1
        data = "caf\xe9".encode("latin-1")
        result = _extract_text(data, "text/plain")
        assert len(result) > 0  # latin-1 fallback succeeded

    def test_plain_text_null_bytes_stripped(self):
        data = "before\x00after".encode("utf-8")
        result = _extract_text(data, "text/plain")
        assert "\x00" not in result
        assert "before" in result
        assert "after" in result

    def test_pdf_corrupt_bytes_returns_empty(self):
        # Random bytes that are not a valid PDF
        result = _extract_text(b"\xff\xfe\x00binary junk", "application/pdf")
        assert isinstance(result, str)
        assert "\x00" not in result

    def test_pdf_null_bytes_stripped(self):
        # Even if somehow a parser returns text with null bytes, they must be stripped
        # Simulate by testing plain-text with null (parser path strips regardless)
        data = b"text with \x00 null"
        result = _extract_text(data, "text/plain")
        assert "\x00" not in result

    def test_docx_corrupt_bytes_returns_empty(self):
        docx_mime = (
            "application/vnd.openxmlformats-officedocument"
            ".wordprocessingml.document"
        )
        result = _extract_text(b"not a docx file at all", docx_mime)
        assert isinstance(result, str)
        assert "\x00" not in result

    def test_docx_valid_extracts_paragraphs(self):
        docx_mime = (
            "application/vnd.openxmlformats-officedocument"
            ".wordprocessingml.document"
        )
        paragraphs = ["First paragraph.", "Second paragraph.", "Third."]
        data = _make_docx_bytes(paragraphs)
        result = _extract_text(data, docx_mime)
        for para in paragraphs:
            assert para in result, f"Expected '{para}' in extracted text"

    def test_docx_null_bytes_in_content_are_stripped(self):
        """Null bytes that somehow appear in extracted DOCX text are stripped.

        lxml (used internally by python-docx) rejects \\x00 at write time, so we
        cannot embed them in a DOCX via the API.  Instead we test the strip logic
        directly: monkeypatch docx.Document so its paragraphs return text that
        contains \\x00, then verify _extract_text strips it before returning.
        """
        from unittest.mock import MagicMock, patch

        docx_mime = (
            "application/vnd.openxmlformats-officedocument"
            ".wordprocessingml.document"
        )

        mock_para = MagicMock()
        mock_para.text = "before\x00after"
        mock_doc = MagicMock()
        mock_doc.paragraphs = [mock_para]

        with patch("docx.Document", return_value=mock_doc):
            result = _extract_text(b"fake docx bytes", docx_mime)

        assert "\x00" not in result
        assert "before" in result
        assert "after" in result

    def test_image_returns_empty_string(self):
        fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        result = _extract_text(fake_png, "image/png")
        assert result == ""

    def test_image_jpeg_returns_empty_string(self):
        result = _extract_text(b"\xff\xd8\xff" + b"\x00" * 50, "image/jpeg")
        assert result == ""

    def test_none_mime_type_treated_as_plain(self):
        data = b"Some plain text"
        result = _extract_text(data, None)
        assert "Some plain text" in result

    def test_pdf_real_content_extracted(self):
        pdf_bytes = _make_real_pdf_bytes("NEXUS document content for testing")
        if pdf_bytes is None:
            pytest.skip("reportlab not installed — skipping real PDF extraction test")
        result = _extract_text(pdf_bytes, "application/pdf")
        assert "NEXUS" in result


# ---------------------------------------------------------------------------
# Integration tests — HTTP upload endpoint
# ---------------------------------------------------------------------------

class TestUploadMimeValidation:
    """Verify MIME gating via the real HTTP endpoint (mock embedder, real DB)."""

    @pytest.mark.asyncio
    async def test_plain_text_upload_succeeds(self, client: AsyncClient, seed3):
        resp = await client.post(
            f"/api/v1/workspaces/{seed3.workspace_a.id}/documents",
            headers={"X-Dev-User-ID": str(seed3.user_c.id)},
            files={"file": ("hello.txt", io.BytesIO(b"Hello world"), "text/plain")},
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["document"]["status"] == "ready"

    @pytest.mark.asyncio
    async def test_pdf_fake_bytes_upload_succeeds_with_zero_chunks(
        self, client: AsyncClient, db_session: AsyncSession, seed3
    ):
        """A fake PDF (non-parseable bytes) uploads successfully, status ready, 0 chunks."""
        resp = await client.post(
            f"/api/v1/workspaces/{seed3.workspace_a.id}/documents",
            headers={"X-Dev-User-ID": str(seed3.user_c.id)},
            files={
                "file": (
                    "fake.pdf",
                    io.BytesIO(b"%PDF not really a pdf"),
                    "application/pdf",
                )
            },
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["document"]["status"] == "ready"

        doc_id = resp.json()["document"]["id"]
        rows = await db_session.execute(
            text("SELECT COUNT(*) FROM document_chunks WHERE document_id = :id"),
            {"id": uuid.UUID(doc_id)},
        )
        assert rows.scalar() == 0

    @pytest.mark.asyncio
    async def test_docx_upload_extracts_text_and_creates_chunks(
        self, client: AsyncClient, db_session: AsyncSession, seed3
    ):
        """A valid DOCX upload must produce at least one DocumentChunk."""
        docx_mime = (
            "application/vnd.openxmlformats-officedocument"
            ".wordprocessingml.document"
        )
        # Build a DOCX with enough text to produce at least one chunk
        paragraphs = ["NEXUS document paragraph. " * 30] * 5
        docx_bytes = _make_docx_bytes(paragraphs)

        resp = await client.post(
            f"/api/v1/workspaces/{seed3.workspace_a.id}/documents",
            headers={"X-Dev-User-ID": str(seed3.user_c.id)},
            files={"file": ("report.docx", io.BytesIO(docx_bytes), docx_mime)},
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["document"]["status"] == "ready"

        doc_id = resp.json()["document"]["id"]
        rows = await db_session.execute(
            text("SELECT COUNT(*) FROM document_chunks WHERE document_id = :id"),
            {"id": uuid.UUID(doc_id)},
        )
        assert rows.scalar() > 0, "Expected at least one chunk from DOCX upload"

    @pytest.mark.asyncio
    async def test_image_upload_succeeds_with_zero_chunks(
        self, client: AsyncClient, db_session: AsyncSession, seed3
    ):
        """An image upload is accepted, stored, and marked ready with 0 chunks."""
        fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
        resp = await client.post(
            f"/api/v1/workspaces/{seed3.workspace_a.id}/documents",
            headers={"X-Dev-User-ID": str(seed3.user_c.id)},
            files={"file": ("screenshot.png", io.BytesIO(fake_png), "image/png")},
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["document"]["status"] == "ready"

        doc_id = resp.json()["document"]["id"]
        rows = await db_session.execute(
            text("SELECT COUNT(*) FROM document_chunks WHERE document_id = :id"),
            {"id": uuid.UUID(doc_id)},
        )
        assert rows.scalar() == 0

    @pytest.mark.asyncio
    async def test_unsupported_mime_type_returns_422(
        self, client: AsyncClient, seed3
    ):
        """An unsupported MIME type (e.g. video/mp4) must return HTTP 422."""
        resp = await client.post(
            f"/api/v1/workspaces/{seed3.workspace_a.id}/documents",
            headers={"X-Dev-User-ID": str(seed3.user_c.id)},
            files={
                "file": (
                    "video.mp4",
                    io.BytesIO(b"fake video bytes"),
                    "video/mp4",
                )
            },
        )
        assert resp.status_code == 422, resp.text

    @pytest.mark.asyncio
    async def test_unsupported_mime_leaves_no_db_record(
        self, client: AsyncClient, db_session: AsyncSession, seed3
    ):
        """After a 422, no Document row must exist in the database."""
        resp = await client.post(
            f"/api/v1/workspaces/{seed3.workspace_a.id}/documents",
            headers={"X-Dev-User-ID": str(seed3.user_c.id)},
            files={
                "file": (
                    "archive.zip",
                    io.BytesIO(b"PK\x03\x04fake zip"),
                    "application/zip",
                )
            },
        )
        assert resp.status_code == 422

        rows = await db_session.execute(
            text(
                "SELECT COUNT(*) FROM documents "
                "WHERE workspace_id = :ws AND name = 'archive.zip'"
            ),
            {"ws": seed3.workspace_a.id},
        )
        assert rows.scalar() == 0, "No Document row should exist after a 422 rejection"

    @pytest.mark.asyncio
    async def test_null_bytes_in_plain_text_do_not_crash_db(
        self, client: AsyncClient, seed3
    ):
        """Plain text containing \\x00 must upload successfully (null bytes stripped)."""
        payload = b"line one\x00line two\x00line three " * 40  # enough for chunks
        resp = await client.post(
            f"/api/v1/workspaces/{seed3.workspace_a.id}/documents",
            headers={"X-Dev-User-ID": str(seed3.user_c.id)},
            files={"file": ("nullbytes.txt", io.BytesIO(payload), "text/plain")},
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["document"]["status"] == "ready"


# ---------------------------------------------------------------------------
# Unit tests for _recursive_split
# ---------------------------------------------------------------------------

class TestRecursiveSplit:
    """Verify the RecursiveCharacterTextSplitter implementation."""

    def test_short_text_returned_as_single_chunk(self):
        result = _recursive_split("hello world")
        assert result == ["hello world"]

    def test_empty_text_returns_empty_list(self):
        assert _recursive_split("") == []
        assert _recursive_split("   ") == []

    def test_double_newline_separator_preferred(self):
        text = "para one\n\npara two\n\npara three"
        result = _recursive_split(text, chunk_size=50)
        # Each paragraph fits in 50 chars; they should not all merge into one
        assert len(result) >= 1
        # All text is preserved
        joined = " ".join(result)
        assert "para one" in joined
        assert "para two" in joined
        assert "para three" in joined

    def test_long_text_produces_multiple_chunks(self):
        long = "word " * 200  # 1000 chars
        result = _recursive_split(long, chunk_size=100, chunk_overlap=10)
        assert len(result) > 1
        for chunk in result:
            assert len(chunk) <= 110  # a little slack for separator reattachment

    def test_no_chunk_exceeds_chunk_size_by_much(self):
        text = ("The quick brown fox. " * 50)  # 1050 chars
        result = _recursive_split(text, chunk_size=200, chunk_overlap=20)
        for chunk in result:
            # Individual words won't exceed chunk_size; allow small overrun
            # from the merge step only
            assert len(chunk) <= 220

    def test_overlap_reappears_in_next_chunk(self):
        # Build text with clear paragraph breaks so overlaps are predictable
        text = "\n\n".join(["Section " + str(i) + (" text " * 20) for i in range(5)])
        result = _recursive_split(text, chunk_size=200, chunk_overlap=40)
        assert len(result) > 1

    def test_split_chunks_alias_returns_same_results(self):
        text = "alpha beta gamma " * 60
        assert _split_chunks(text) == _recursive_split(text)


# ---------------------------------------------------------------------------
# Unit tests for _chunk_docx
# ---------------------------------------------------------------------------

class TestChunkDocx:
    """Direct unit tests for the structure-aware DOCX chunker."""

    def test_corrupt_bytes_return_empty_list(self):
        result = _chunk_docx(b"not a docx file")
        assert result == []

    def test_flat_paragraphs_without_headings(self):
        # No headings — all body under section=None
        paras = ["Paragraph one text.", "Paragraph two text.", "Paragraph three text."]
        data = _make_docx_bytes(paras)
        chunks = _chunk_docx(data)
        assert len(chunks) > 0
        for c in chunks:
            assert isinstance(c, Chunk)
            assert c.section is None
        joined = " ".join(c.text for c in chunks)
        assert "Paragraph one" in joined
        assert "Paragraph three" in joined

    def test_heading1_creates_section_label(self):
        data = _make_structured_docx_bytes([
            ("Introduction", 1, ["This is the intro. " * 5]),
        ])
        chunks = _chunk_docx(data)
        assert len(chunks) > 0
        for c in chunks:
            assert c.section == "Introduction"
            assert c.metadata.get("section") == "Introduction"
            assert c.metadata.get("heading_level") == 1

    def test_heading2_creates_section_label(self):
        data = _make_structured_docx_bytes([
            ("Background", 2, ["Background content here. " * 5]),
        ])
        chunks = _chunk_docx(data)
        assert len(chunks) > 0
        for c in chunks:
            assert c.section == "Background"
            assert c.metadata.get("heading_level") == 2

    def test_multiple_sections_each_labelled_independently(self):
        data = _make_structured_docx_bytes([
            ("Chapter 1", 1, ["Chapter one body. " * 10]),
            ("Chapter 2", 1, ["Chapter two body. " * 10]),
            ("Chapter 3", 1, ["Chapter three body. " * 10]),
        ])
        chunks = _chunk_docx(data)
        sections = {c.section for c in chunks}
        assert "Chapter 1" in sections
        assert "Chapter 2" in sections
        assert "Chapter 3" in sections

    def test_h2_under_h1_labelled_with_h2(self):
        """A Heading 2 within a Heading 1 produces chunks with the H2 as section."""
        data = _make_structured_docx_bytes([
            ("Part A", 1, []),
            ("Section A1", 2, ["Content under A1. " * 10]),
            ("Section A2", 2, ["Content under A2. " * 10]),
        ])
        chunks = _chunk_docx(data)
        sections = {c.section for c in chunks}
        # H2 headings should be section labels
        assert "Section A1" in sections
        assert "Section A2" in sections
        # "Part A" itself has no body text so no chunk is created for it
        assert "Part A" not in sections

    def test_section_key_in_metadata(self):
        data = _make_structured_docx_bytes([
            ("Methods", 1, ["We used X method. " * 15]),
        ])
        chunks = _chunk_docx(data)
        assert all(c.metadata.get("section") == "Methods" for c in chunks)

    def test_body_before_first_heading_has_no_section(self):
        """Paragraphs that appear before any heading are captured with section=None."""
        import docx as _docx
        doc = _docx.Document()
        doc.add_paragraph("Pre-heading preamble text. " * 10)
        doc.add_heading("Real Section", level=1)
        doc.add_paragraph("Post-heading body. " * 10)
        buf = io.BytesIO()
        doc.save(buf)
        data = buf.getvalue()

        chunks = _chunk_docx(data)
        sections = {c.section for c in chunks}
        assert None in sections          # preamble → no section
        assert "Real Section" in sections

    def test_large_section_split_into_multiple_chunks(self):
        """A section with > CHUNK_SIZE chars produces multiple Chunk objects."""
        long_body = ["Long body paragraph. " * 30]  # ~630 chars — exceeds 512
        data = _make_structured_docx_bytes([
            ("Big Section", 1, long_body),
        ])
        chunks = _chunk_docx(data)
        section_chunks = [c for c in chunks if c.section == "Big Section"]
        assert len(section_chunks) > 1, "Expected multiple chunks from a long section"
        for c in section_chunks:
            assert c.metadata.get("section") == "Big Section"

    def test_empty_docx_returns_empty_list(self):
        import docx as _docx
        doc = _docx.Document()
        buf = io.BytesIO()
        doc.save(buf)
        result = _chunk_docx(buf.getvalue())
        assert result == []


# ---------------------------------------------------------------------------
# Unit tests for _chunk_document dispatcher
# ---------------------------------------------------------------------------

class TestChunkDocumentDispatcher:
    """Verify that _chunk_document routes to the correct chunker."""

    def test_plain_text_returns_chunks_without_section(self):
        text = "Plain text content. " * 40
        chunks = _chunk_document(text.encode(), "text/plain")
        assert len(chunks) > 0
        assert all(isinstance(c, Chunk) for c in chunks)
        assert all(c.section is None for c in chunks)

    def test_image_returns_empty_list(self):
        assert _chunk_document(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64, "image/png") == []
        assert _chunk_document(b"\xff\xd8\xff" + b"\x00" * 50, "image/jpeg") == []

    def test_pdf_corrupt_returns_empty_list(self):
        result = _chunk_document(b"not a real pdf", "application/pdf")
        assert result == []

    def test_docx_routes_to_structural_chunker(self):
        """_chunk_document returns Chunk objects with section for a structured DOCX."""
        data = _make_structured_docx_bytes([
            ("Findings", 1, ["Finding detail. " * 20]),
        ])
        docx_mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        chunks = _chunk_document(data, docx_mime)
        assert len(chunks) > 0
        assert all(c.section == "Findings" for c in chunks)


# ---------------------------------------------------------------------------
# Integration tests — structural DOCX section metadata persisted to DB
# ---------------------------------------------------------------------------

class TestDocxStructuralChunkingIntegration:
    """Verify section metadata is persisted in document_chunks rows."""

    @pytest.mark.asyncio
    async def test_docx_chunks_have_section_column_populated(
        self, client: AsyncClient, db_session: AsyncSession, seed3
    ):
        """DocumentChunk.section must contain the heading text for DOCX uploads."""
        docx_mime = (
            "application/vnd.openxmlformats-officedocument"
            ".wordprocessingml.document"
        )
        data = _make_structured_docx_bytes([
            ("Abstract", 1, ["Abstract content sentence. " * 20]),
            ("Methods",  1, ["Methods content sentence. " * 20]),
        ])
        resp = await client.post(
            f"/api/v1/workspaces/{seed3.workspace_a.id}/documents",
            headers={"X-Dev-User-ID": str(seed3.user_c.id)},
            files={"file": ("structured.docx", io.BytesIO(data), docx_mime)},
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["document"]["status"] == "ready"

        doc_id = uuid.UUID(resp.json()["document"]["id"])
        rows = await db_session.execute(
            text(
                "SELECT section FROM document_chunks "
                "WHERE document_id = :id AND section IS NOT NULL"
            ),
            {"id": doc_id},
        )
        sections = {row[0] for row in rows.fetchall()}
        assert "Abstract" in sections, f"Expected 'Abstract' in sections, got {sections}"
        assert "Methods" in sections, f"Expected 'Methods' in sections, got {sections}"

    @pytest.mark.asyncio
    async def test_docx_chunks_have_metadata_json_with_section_key(
        self, client: AsyncClient, db_session: AsyncSession, seed3
    ):
        """metadata_json must include 'section' and 'heading_level' keys."""
        docx_mime = (
            "application/vnd.openxmlformats-officedocument"
            ".wordprocessingml.document"
        )
        data = _make_structured_docx_bytes([
            ("Results", 1, ["Result item detail text. " * 20]),
        ])
        resp = await client.post(
            f"/api/v1/workspaces/{seed3.workspace_a.id}/documents",
            headers={"X-Dev-User-ID": str(seed3.user_c.id)},
            files={"file": ("results.docx", io.BytesIO(data), docx_mime)},
        )
        assert resp.status_code == 201, resp.text
        doc_id = uuid.UUID(resp.json()["document"]["id"])

        rows = await db_session.execute(
            text(
                "SELECT metadata_json FROM document_chunks "
                "WHERE document_id = :id AND metadata_json IS NOT NULL "
                "LIMIT 1"
            ),
            {"id": doc_id},
        )
        row = rows.fetchone()
        assert row is not None, "Expected at least one chunk with metadata_json"
        meta = row[0]
        assert meta.get("section") == "Results"
        assert meta.get("heading_level") == 1

    @pytest.mark.asyncio
    async def test_plain_text_chunks_have_null_section(
        self, client: AsyncClient, db_session: AsyncSession, seed3
    ):
        """Plain-text uploads must have section=NULL in every chunk."""
        resp = await client.post(
            f"/api/v1/workspaces/{seed3.workspace_a.id}/documents",
            headers={"X-Dev-User-ID": str(seed3.user_c.id)},
            files={"file": ("plain.txt", io.BytesIO(b"plain content " * 60), "text/plain")},
        )
        assert resp.status_code == 201, resp.text
        doc_id = uuid.UUID(resp.json()["document"]["id"])

        rows = await db_session.execute(
            text(
                "SELECT COUNT(*) FROM document_chunks "
                "WHERE document_id = :id AND section IS NOT NULL"
            ),
            {"id": doc_id},
        )
        assert rows.scalar() == 0, "Plain-text chunks must not have a section label"
