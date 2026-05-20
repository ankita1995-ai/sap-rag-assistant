from typing import Optional

from pydantic import BaseModel, Field


# ── Request models ─────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    """Payload for the /query endpoint."""

    question: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Natural-language question about SAP documentation.",
    )
    k: int = Field(
        default=4,
        ge=1,
        le=10,
        description="Number of source chunks to retrieve.",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "question": "What is the SAP MM module and what are its main components?",
                "k": 4,
            }
        }
    }


# ── Citation / source models ───────────────────────────────────────────────────

class SourceDocument(BaseModel):
    """A single retrieved document chunk returned as a citation."""

    source: str = Field(..., description="Original PDF filename.")
    page: Optional[int] = Field(None, description="Page number within the source document.")
    content_preview: str = Field(..., description="First 200 characters of the retrieved chunk.")
    relevance_score: float = Field(
        ...,
        description="L2 similarity distance — lower means more relevant.",
    )


# ── Response models ────────────────────────────────────────────────────────────

class QueryResult(BaseModel):
    """Internal + API response for a RAG query."""

    question: str
    answer: str
    sources: list[SourceDocument]
    processing_time_ms: float

    model_config = {
        "json_schema_extra": {
            "example": {
                "question": "What is SAP MM?",
                "answer": "SAP MM (Materials Management) handles procurement and inventory...",
                "sources": [
                    {
                        "source": "sap_mm_guide.pdf",
                        "page": 3,
                        "content_preview": "SAP MM is the Materials Management module responsible for...",
                        "relevance_score": 0.142,
                    }
                ],
                "processing_time_ms": 1250.5,
            }
        }
    }


class UploadResponse(BaseModel):
    """Response after successfully ingesting a PDF."""

    filename: str
    chunks_created: int
    message: str


class HealthResponse(BaseModel):
    """Basic liveness + readiness probe response."""

    status: str
    indexed_chunks: int
