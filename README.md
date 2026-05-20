# SAP RAG Assistant

An intelligent SAP documentation Q&A system built with **FastAPI**, **LangChain**, and **FAISS**.  
Upload SAP PDF manuals → ask natural-language questions → receive grounded answers with source citations.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                         Client (curl / browser / Python)             │
└───────────────────┬──────────────────────────────┬───────────────────┘
                    │ POST /upload (PDF)            │ POST /query
                    ▼                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│                        FastAPI (src/main.py)                         │
│  ┌─────────────────────────┐   ┌──────────────────────────────────┐  │
│  │   UploadDocument route  │   │       QueryDocuments route       │  │
│  └────────────┬────────────┘   └──────────────┬───────────────────┘  │
└───────────────┼────────────────────────────────┼─────────────────────┘
                │                                │
                ▼                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                   RAGPipeline (src/services/rag_pipeline.py)         │
│                                                                      │
│  ingest_pdf()                        query()                         │
│  ┌──────────────────────┐            ┌───────────────────────────┐   │
│  │ 1. PyPDFLoader       │            │ 1. similarity_search()    │   │
│  │ 2. Chunk (512t/100o) │            │    → top-k chunks         │   │
│  │ 3. OpenAI Embeddings │            │ 2. Build context string   │   │
│  │ 4. FAISS.add_docs()  │            │ 3. ChatOpenAI (gpt-4o)    │   │
│  │ 5. save_local()      │            │ 4. Return answer+sources  │   │
│  └──────────────────────┘            └───────────────────────────┘   │
└──────────────────────────────────┬───────────────────────────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │   FAISS Index (disk-backed)  │
                    │   ./data/faiss_index/        │
                    └─────────────────────────────┘
```

**Data flow summary**

| Step | Action |
|------|--------|
| Upload | PDF → PyPDFLoader → 512-token chunks (100-token overlap) → OpenAI embeddings → FAISS index |
| Query  | Question → embed → FAISS similarity search → top-k chunks → GPT-4o → cited answer |

---

## Project Structure

```
sap-rag-assistant/
├── src/
│   ├── main.py              # FastAPI app + lifespan + endpoints
│   ├── config.py            # Pydantic Settings (reads .env)
│   ├── models.py            # Request / response Pydantic models
│   └── services/
│       └── rag_pipeline.py  # RAGPipeline class (core logic)
├── tests/
│   ├── conftest.py          # Shared fixtures (mock pipeline, TestClient)
│   ├── test_rag_pipeline.py # Unit tests for RAGPipeline
│   └── test_api.py          # Endpoint integration tests
├── examples/
│   ├── sample_documents/
│   │   └── sap_overview.md  # Convert to PDF for test uploads
│   └── query_examples.py    # Demo client script
├── data/                    # FAISS index (git-ignored, auto-created)
├── uploads/                 # Temp staging for uploads (git-ignored)
├── Dockerfile
├── docker-compose.yml       # API + optional PostgreSQL
├── .env.example
└── requirements.txt
```

---

## Quick Start

### 1 — Clone and configure

```bash
git clone <repo-url>
cd sap-rag-assistant
cp .env.example .env
# Edit .env and set OPENAI_API_KEY=sk-...
```

### 2 — Install dependencies

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

### 3 — Run locally

```bash
uvicorn src.main:app --reload
```

Open the interactive docs at **http://localhost:8000/docs**

### 4 — Upload a SAP document

```bash
curl -X POST http://localhost:8000/upload \
  -F "file=@/path/to/sap_mm_guide.pdf"
```

Response:
```json
{
  "filename": "sap_mm_guide.pdf",
  "chunks_created": 87,
  "message": "Successfully ingested 87 chunks from 'sap_mm_guide.pdf'."
}
```

### 5 — Ask a question

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the procure-to-pay process in SAP MM?", "k": 4}'
```

Response:
```json
{
  "question": "What is the procure-to-pay process in SAP MM?",
  "answer": "The procure-to-pay process in SAP MM begins with a Purchase Requisition...",
  "sources": [
    {
      "source": "sap_mm_guide.pdf",
      "page": 12,
      "content_preview": "The standard procurement cycle starts with a purchase requisition...",
      "relevance_score": 0.1423
    }
  ],
  "processing_time_ms": 1340.5
}
```

### 6 — Run the demo script

```bash
# Upload and query in one go:
python examples/query_examples.py path/to/sap_doc.pdf
```

---

## Docker

```bash
# Start the full stack (API + PostgreSQL)
docker-compose up --build

# API-only (no Postgres)
docker-compose up api --build
```

---

## API Reference

| Method | Path      | Description |
|--------|-----------|-------------|
| `GET`  | `/health` | Liveness probe — returns status and indexed chunk count |
| `POST` | `/upload` | Ingest a PDF document into the FAISS vector store |
| `POST` | `/query`  | Ask a question; returns an answer with source citations |

### POST /upload

| Field | Type | Description |
|-------|------|-------------|
| `file` | `multipart/form-data` | A `.pdf` file |

### POST /query

```json
{
  "question": "string (1–1000 chars)",
  "k": "integer (1–10, default 4)"
}
```

---

## Configuration

All settings are read from environment variables or a `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | — | **Required.** Your OpenAI API key |
| `OPENAI_MODEL` | `gpt-4o` | Chat completion model |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding model |
| `FAISS_INDEX_PATH` | `./data/faiss_index` | Directory for the persisted FAISS index |
| `CHUNK_SIZE` | `512` | Tokens per chunk |
| `CHUNK_OVERLAP` | `100` | Overlap tokens between consecutive chunks |
| `API_HOST` | `0.0.0.0` | Bind host |
| `API_PORT` | `8000` | Bind port |
| `LOG_LEVEL` | `INFO` | Python logging level |

---

## Running Tests

```bash
pytest tests/ -v
```

The test suite mocks all OpenAI and FAISS calls — no API key required for tests.

---

## Chunking Strategy

Documents are split using `RecursiveCharacterTextSplitter` with tiktoken encoding:

- **Chunk size**: 512 tokens — large enough for semantic coherence, small enough for precise retrieval
- **Overlap**: 100 tokens — ensures context is not lost at chunk boundaries
- **Splitter hierarchy**: paragraph → sentence → word → character (tries to respect natural text boundaries)

---

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| FAISS (local) | Zero-infrastructure vector store; perfect for a portfolio demo. Replace with Pinecone/Weaviate for production scale. |
| Thread lock on index writes | Concurrent uploads would corrupt the FAISS index without a lock. |
| `temperature=0.0` | SAP documentation Q&A requires factual, deterministic answers. |
| Separate `QueryResult` model | Keeps the pipeline decoupled from FastAPI's serialisation layer. |
| `allow_dangerous_deserialization=True` | Required by LangChain's FAISS loader; safe because we wrote the file ourselves. |

---

## Roadmap

- [ ] PostgreSQL query history with async SQLAlchemy
- [ ] Multi-tenant index partitioning by SAP module (MM, SD, FI…)
- [ ] Streaming responses via `StreamingResponse`
- [ ] Re-ranker pass (Cohere Rerank) for higher-precision retrieval
- [ ] Authentication (API key header)
