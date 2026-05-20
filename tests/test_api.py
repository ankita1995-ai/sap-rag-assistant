"""Integration-style tests for the FastAPI endpoints."""
import io
from unittest.mock import MagicMock

import pytest

from src.models import QueryResult, SourceDocument


# ── /health ───────────────────────────────────────────────────────────────────

class TestHealthEndpoint:
    def test_returns_200_with_healthy_status(self, client, mock_pipeline) -> None:
        mock_pipeline.document_count = 0
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_reports_current_indexed_chunk_count(self, client, mock_pipeline) -> None:
        mock_pipeline.document_count = 73
        response = client.get("/health")
        assert response.json()["indexed_chunks"] == 73


# ── /upload ───────────────────────────────────────────────────────────────────

class TestUploadEndpoint:
    def _pdf_upload(self, client, filename: str = "guide.pdf", content: bytes = b"%PDF-1.4"):
        return client.post(
            "/upload",
            files={"file": (filename, io.BytesIO(content), "application/pdf")},
        )

    def test_returns_201_for_valid_pdf(self, client, mock_pipeline) -> None:
        mock_pipeline.ingest_pdf.return_value = 18
        response = self._pdf_upload(client)
        assert response.status_code == 201

    def test_response_body_contains_chunk_count_and_filename(
        self, client, mock_pipeline
    ) -> None:
        mock_pipeline.ingest_pdf.return_value = 18
        response = self._pdf_upload(client, filename="sap_mm.pdf")
        data = response.json()
        assert data["chunks_created"] == 18
        assert data["filename"] == "sap_mm.pdf"
        assert "18" in data["message"]

    def test_rejects_non_pdf_with_400(self, client) -> None:
        response = client.post(
            "/upload",
            files={"file": ("notes.txt", io.BytesIO(b"some text"), "text/plain")},
        )
        assert response.status_code == 400
        assert "PDF" in response.json()["detail"]

    def test_returns_422_when_pipeline_raises_value_error(
        self, client, mock_pipeline
    ) -> None:
        mock_pipeline.ingest_pdf.side_effect = ValueError("No extractable text found.")
        response = self._pdf_upload(client, filename="blank.pdf")
        assert response.status_code == 422
        assert "No extractable text" in response.json()["detail"]

    def test_returns_500_on_unexpected_pipeline_error(
        self, client, mock_pipeline
    ) -> None:
        mock_pipeline.ingest_pdf.side_effect = RuntimeError("disk full")
        response = self._pdf_upload(client)
        assert response.status_code == 500


# ── /query ────────────────────────────────────────────────────────────────────

class TestQueryEndpoint:
    def test_returns_200_with_answer_and_sources(
        self, client, mock_pipeline, sample_query_result
    ) -> None:
        mock_pipeline.query.return_value = sample_query_result
        response = client.post("/query", json={"question": "What is SAP MM?", "k": 4})
        assert response.status_code == 200
        data = response.json()
        assert "Materials Management" in data["answer"]
        assert len(data["sources"]) == 1
        assert data["sources"][0]["source"] == "sap_mm_guide.pdf"

    def test_response_includes_processing_time(
        self, client, mock_pipeline, sample_query_result
    ) -> None:
        mock_pipeline.query.return_value = sample_query_result
        response = client.post("/query", json={"question": "What is SAP?", "k": 2})
        assert response.json()["processing_time_ms"] == 850.0

    def test_rejects_empty_question_with_400(self, client) -> None:
        response = client.post("/query", json={"question": "   "})
        assert response.status_code == 400

    def test_rejects_missing_question_field_with_422(self, client) -> None:
        response = client.post("/query", json={"k": 4})
        assert response.status_code == 422

    def test_rejects_k_greater_than_10_with_422(self, client) -> None:
        response = client.post("/query", json={"question": "What?", "k": 99})
        assert response.status_code == 422

    def test_returns_422_when_no_documents_ingested(
        self, client, mock_pipeline
    ) -> None:
        mock_pipeline.query.side_effect = ValueError(
            "No documents have been ingested yet."
        )
        response = client.post("/query", json={"question": "What is SAP?"})
        assert response.status_code == 422
        assert "No documents" in response.json()["detail"]

    def test_returns_500_on_unexpected_error(self, client, mock_pipeline) -> None:
        mock_pipeline.query.side_effect = RuntimeError("OpenAI timeout")
        response = client.post("/query", json={"question": "What is SAP?"})
        assert response.status_code == 500

    def test_passes_k_parameter_to_pipeline(
        self, client, mock_pipeline, sample_query_result
    ) -> None:
        mock_pipeline.query.return_value = sample_query_result
        client.post("/query", json={"question": "What is SAP SD?", "k": 7})
        mock_pipeline.query.assert_called_once_with("What is SAP SD?", k=7)
