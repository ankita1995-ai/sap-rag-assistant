"""Unit tests for RAGPipeline — all external I/O is mocked."""
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("GOOGLE_API_KEY", "test-google-key-not-real")

from src.config import Settings
from src.models import QueryResult
from src.services.rag_pipeline import RAGPipeline


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_pipeline(tmp_path: Path, *, index_exists: bool = False) -> RAGPipeline:
    """Build a RAGPipeline with mocked OpenAI clients."""
    index_dir = tmp_path / "faiss_index"
    if index_exists:
        index_dir.mkdir()
        (index_dir / "index.faiss").touch()

    settings = Settings(
        google_api_key="test-key",
        faiss_index_path=str(index_dir),
        chunk_size=512,
        chunk_overlap=100,
    )

    with (
        patch("src.services.rag_pipeline.GoogleGenerativeAIEmbeddings"),
        patch("src.services.rag_pipeline.ChatGoogleGenerativeAI"),
        patch("src.services.rag_pipeline.FAISS") as mock_faiss_cls,
    ):
        mock_faiss_cls.load_local.return_value = MagicMock()
        pipeline = RAGPipeline(settings)

    return pipeline


# ── Initialisation ─────────────────────────────────────────────────────────────

class TestRAGPipelineInit:
    def test_starts_with_no_store_when_directory_empty(self, tmp_path: Path) -> None:
        pipeline = _make_pipeline(tmp_path, index_exists=False)
        assert pipeline._vector_store is None

    def test_loads_existing_index_on_startup(self, tmp_path: Path) -> None:
        with (
            patch("src.services.rag_pipeline.GoogleGenerativeAIEmbeddings"),
            patch("src.services.rag_pipeline.ChatGoogleGenerativeAI"),
            patch("src.services.rag_pipeline.FAISS") as mock_faiss_cls,
        ):
            index_dir = tmp_path / "faiss_index"
            index_dir.mkdir()
            (index_dir / "index.faiss").touch()

            mock_store = MagicMock()
            mock_faiss_cls.load_local.return_value = mock_store

            settings = Settings(
                google_api_key="test-key",
                faiss_index_path=str(index_dir),
            )
            pipeline = RAGPipeline(settings)

        assert pipeline._vector_store is mock_store
        mock_faiss_cls.load_local.assert_called_once()

    def test_recovers_gracefully_when_index_corrupt(self, tmp_path: Path) -> None:
        with (
            patch("src.services.rag_pipeline.GoogleGenerativeAIEmbeddings"),
            patch("src.services.rag_pipeline.ChatGoogleGenerativeAI"),
            patch("src.services.rag_pipeline.FAISS") as mock_faiss_cls,
        ):
            index_dir = tmp_path / "faiss_index"
            index_dir.mkdir()
            (index_dir / "index.faiss").touch()
            mock_faiss_cls.load_local.side_effect = RuntimeError("corrupt index")

            settings = Settings(
                google_api_key="test-key",
                faiss_index_path=str(index_dir),
            )
            pipeline = RAGPipeline(settings)

        assert pipeline._vector_store is None


# ── Ingestion ──────────────────────────────────────────────────────────────────

class TestIngestPDF:
    def test_returns_correct_chunk_count(self, tmp_path: Path) -> None:
        pipeline = _make_pipeline(tmp_path)
        fake_pdf = tmp_path / "sap_mm.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4")

        mock_doc = MagicMock()
        mock_doc.metadata = {}
        mock_chunks = [MagicMock(), MagicMock(), MagicMock()]

        with (
            patch("src.services.rag_pipeline.PyPDFLoader") as mock_loader,
            patch("src.services.rag_pipeline.FAISS") as mock_faiss_cls,
        ):
            mock_loader.return_value.load.return_value = [mock_doc]
            pipeline.text_splitter = MagicMock()
            pipeline.text_splitter.split_documents.return_value = mock_chunks
            mock_faiss_cls.from_documents.return_value = MagicMock()

            count = pipeline.ingest_pdf(str(fake_pdf), "sap_mm.pdf")

        assert count == 3

    def test_attaches_filename_to_chunk_metadata(self, tmp_path: Path) -> None:
        pipeline = _make_pipeline(tmp_path)
        fake_pdf = tmp_path / "guide.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4")

        mock_doc = MagicMock()
        mock_doc.metadata = {}
        mock_chunk = MagicMock()
        mock_chunk.metadata = {}

        with (
            patch("src.services.rag_pipeline.PyPDFLoader") as mock_loader,
            patch("src.services.rag_pipeline.FAISS") as mock_faiss_cls,
        ):
            mock_loader.return_value.load.return_value = [mock_doc]
            pipeline.text_splitter = MagicMock()
            pipeline.text_splitter.split_documents.return_value = [mock_chunk]
            mock_faiss_cls.from_documents.return_value = MagicMock()
            pipeline.ingest_pdf(str(fake_pdf), "guide.pdf")

        assert mock_doc.metadata["source"] == "guide.pdf"

    def test_raises_value_error_when_no_text_extracted(self, tmp_path: Path) -> None:
        pipeline = _make_pipeline(tmp_path)
        fake_pdf = tmp_path / "blank.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4")

        with patch("src.services.rag_pipeline.PyPDFLoader") as mock_loader:
            mock_loader.return_value.load.return_value = [MagicMock(metadata={})]
            pipeline.text_splitter = MagicMock()
            pipeline.text_splitter.split_documents.return_value = []

            with pytest.raises(ValueError, match="No extractable text"):
                pipeline.ingest_pdf(str(fake_pdf), "blank.pdf")

    def test_merges_into_existing_store(self, tmp_path: Path) -> None:
        pipeline = _make_pipeline(tmp_path)
        pipeline._vector_store = MagicMock()
        fake_pdf = tmp_path / "extra.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4")

        with patch("src.services.rag_pipeline.PyPDFLoader") as mock_loader:
            mock_loader.return_value.load.return_value = [MagicMock(metadata={})]
            pipeline.text_splitter = MagicMock()
            pipeline.text_splitter.split_documents.return_value = [MagicMock()]
            pipeline.ingest_pdf(str(fake_pdf), "extra.pdf")

        pipeline._vector_store.add_documents.assert_called_once()


# ── Query ──────────────────────────────────────────────────────────────────────

class TestQuery:
    def test_raises_when_no_documents_ingested(self, tmp_path: Path) -> None:
        pipeline = _make_pipeline(tmp_path)
        assert pipeline._vector_store is None

        with pytest.raises(ValueError, match="No documents have been ingested"):
            pipeline.query("What is SAP?")

    def test_returns_query_result_with_correct_fields(self, tmp_path: Path) -> None:
        pipeline = _make_pipeline(tmp_path)

        mock_doc = MagicMock()
        mock_doc.page_content = "SAP is an enterprise resource planning system."
        mock_doc.metadata = {"source": "sap_intro.pdf", "page": 1}

        mock_store = MagicMock()
        mock_store.similarity_search_with_score.return_value = [(mock_doc, 0.15)]
        pipeline._vector_store = mock_store

        mock_chain = MagicMock()
        mock_chain.invoke.return_value = "SAP stands for Systems, Applications & Products."

        with patch("src.services.rag_pipeline.StrOutputParser") as mock_parser:
            # Simulate the | chaining: prompt | llm | parser → mock_chain
            pipeline.llm.__or__ = MagicMock(return_value=mock_chain)
            mock_parser.return_value.__ror__ = MagicMock(return_value=mock_chain)

            with patch.object(
                type(pipeline.llm), "__or__", return_value=mock_chain
            ):
                # Patch the chain directly on the prompt
                import src.services.rag_pipeline as rag_mod
                with patch.object(rag_mod, "_SAP_PROMPT") as mock_prompt:
                    mock_prompt.__or__ = MagicMock(return_value=mock_chain)
                    result = pipeline.query("What is SAP?", k=1)

        assert isinstance(result, QueryResult)
        assert result.question == "What is SAP?"
        assert len(result.sources) == 1
        assert result.sources[0].source == "sap_intro.pdf"
        assert result.sources[0].page == 1
        assert result.processing_time_ms >= 0

    def test_source_preview_is_truncated_to_200_chars(self, tmp_path: Path) -> None:
        pipeline = _make_pipeline(tmp_path)

        long_content = "A" * 500
        mock_doc = MagicMock()
        mock_doc.page_content = long_content
        mock_doc.metadata = {"source": "big.pdf"}

        mock_store = MagicMock()
        mock_store.similarity_search_with_score.return_value = [(mock_doc, 0.2)]
        pipeline._vector_store = mock_store

        mock_chain = MagicMock()
        mock_chain.invoke.return_value = "Answer."

        import src.services.rag_pipeline as rag_mod
        with patch.object(rag_mod, "_SAP_PROMPT") as mock_prompt:
            mock_prompt.__or__ = MagicMock(return_value=mock_chain)
            result = pipeline.query("Something?", k=1)

        assert len(result.sources[0].content_preview) <= 200


# ── document_count ─────────────────────────────────────────────────────────────

class TestDocumentCount:
    def test_returns_zero_with_no_store(self, tmp_path: Path) -> None:
        pipeline = _make_pipeline(tmp_path)
        assert pipeline.document_count == 0

    def test_returns_ntotal_from_faiss_index(self, tmp_path: Path) -> None:
        pipeline = _make_pipeline(tmp_path)
        mock_store = MagicMock()
        mock_store.index.ntotal = 42
        pipeline._vector_store = mock_store
        assert pipeline.document_count == 42
