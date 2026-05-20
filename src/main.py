import logging
import shutil
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware

from src.config import get_settings
from src.models import HealthResponse, QueryResult, QueryRequest, UploadResponse
from src.services.rag_pipeline import RAGPipeline

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)

_pipeline: RAGPipeline | None = None

UPLOAD_DIR = Path("uploads")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _pipeline
    settings = get_settings()
    logging.getLogger().setLevel(settings.log_level.upper())
    _pipeline = RAGPipeline(settings)
    UPLOAD_DIR.mkdir(exist_ok=True)
    logger.info("SAP RAG Assistant ready.")
    yield
    logger.info("Shutting down.")


app = FastAPI(
    title="SAP RAG Assistant",
    description=(
        "Intelligent SAP documentation Q&A powered by LangChain, FAISS, and OpenAI. "
        "Upload SAP PDF manuals via `/upload`, then ask questions via `/query`."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Dependency ─────────────────────────────────────────────────────────────────

def get_pipeline() -> RAGPipeline:
    if _pipeline is None:
        raise HTTPException(status_code=503, detail="Pipeline is not yet initialised.")
    return _pipeline


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness and readiness probe",
    tags=["ops"],
)
async def health(pipeline: RAGPipeline = Depends(get_pipeline)) -> HealthResponse:
    """Return service status and the number of indexed document chunks."""
    return HealthResponse(
        status="healthy",
        indexed_chunks=pipeline.document_count,
    )


@app.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a SAP PDF document",
    tags=["documents"],
)
async def upload_document(
    file: UploadFile = File(..., description="A PDF file containing SAP documentation."),
    pipeline: RAGPipeline = Depends(get_pipeline),
) -> UploadResponse:
    """Upload a PDF, chunk it into 512-token segments with 100-token overlap,
    embed each chunk with OpenAI embeddings, and persist to the FAISS index."""
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported. Please upload a .pdf file.",
        )

    temp_path = UPLOAD_DIR / f"{uuid.uuid4()}_{file.filename}"
    try:
        with temp_path.open("wb") as fh:
            shutil.copyfileobj(file.file, fh)

        chunks_created = pipeline.ingest_pdf(str(temp_path), file.filename)

        return UploadResponse(
            filename=file.filename,
            chunks_created=chunks_created,
            message=f"Successfully ingested {chunks_created} chunks from '{file.filename}'.",
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except Exception:
        logger.exception("Unexpected error while ingesting '%s'.", file.filename)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process the uploaded document.",
        )
    finally:
        if temp_path.exists():
            temp_path.unlink()
        await file.close()


@app.post(
    "/query",
    response_model=QueryResult,
    summary="Ask a question about ingested SAP documentation",
    tags=["rag"],
)
async def query_documents(
    request: QueryRequest,
    pipeline: RAGPipeline = Depends(get_pipeline),
) -> QueryResult:
    """Retrieve the most relevant document chunks from FAISS, then generate
    a grounded answer with source citations using the configured LLM."""
    if not request.question.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question must not be empty or whitespace.",
        )

    try:
        return pipeline.query(request.question, k=request.k)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except Exception:
        logger.exception("Unexpected error while processing query.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process the query.",
        )
