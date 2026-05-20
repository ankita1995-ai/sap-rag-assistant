"""Shared test fixtures for the SAP RAG Assistant test suite."""
import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Inject a dummy key before any src import touches pydantic-settings
os.environ.setdefault("GOOGLE_API_KEY", "test-google-key-not-real")

from src.config import get_settings  # noqa: E402
from src.main import app, get_pipeline  # noqa: E402
from src.models import QueryResult, SourceDocument  # noqa: E402
from src.services.rag_pipeline import RAGPipeline  # noqa: E402


@pytest.fixture(autouse=True)
def clear_settings_cache():
    """Ensure each test starts with a fresh settings object."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def mock_pipeline() -> MagicMock:
    """A fully-mocked RAGPipeline instance."""
    pipeline = MagicMock(spec=RAGPipeline)
    pipeline.document_count = 0
    return pipeline


@pytest.fixture()
def sample_query_result() -> QueryResult:
    return QueryResult(
        question="What is SAP MM?",
        answer="SAP MM (Materials Management) handles procurement and inventory management.",
        sources=[
            SourceDocument(
                source="sap_mm_guide.pdf",
                page=3,
                content_preview="SAP MM is the Materials Management module responsible for...",
                relevance_score=0.142,
            )
        ],
        processing_time_ms=850.0,
    )


@pytest.fixture()
def client(mock_pipeline: MagicMock) -> TestClient:
    """TestClient with the RAG pipeline dependency overridden."""
    with patch("src.main.RAGPipeline", return_value=mock_pipeline):
        app.dependency_overrides[get_pipeline] = lambda: mock_pipeline
        with TestClient(app) as c:
            yield c
    app.dependency_overrides.clear()
