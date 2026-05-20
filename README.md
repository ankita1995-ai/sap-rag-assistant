# SAP RAG Assistant

An intelligent SAP documentation Q&A system built with **FastAPI**, **Streamlit**, **LangChain**, and **FAISS**.  
Upload SAP PDF manuals → ask natural-language questions → receive grounded answers with source citations.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                    Streamlit UI (frontend/app.py)                    │
│         PDF upload · Chat Q&A · Source citations · Doc list          │
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
│  │ 2. Chunk (512t/100o) │            │    → top-k unique chunks  │   │
│  │ 3. Gemini Embeddings │            │ 2. Build context string   │   │
│  │ 4. FAISS.add_docs()  │            │ 3. gemini-2.5-flash-lite  │   │
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
| Upload | PDF → PyPDFLoader → 512-token chunks (100-token overlap) → `gemini-embedding-001` → FAISS index |
| Query  | Question → embed → FAISS similarity search → deduplicated top-k chunks → `gemini-2.5-flash-lite` → cited answer |

---

## Project Structure

```
sap-rag-assistant/
├── frontend/
│   ├── app.py               # Streamlit UI (upload, chat, citations, doc list)
│   └── requirements.txt     # Frontend dependencies (streamlit, requests)
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
├── docker-compose.yml
├── .env.example
└── requirements.txt
```

---

## Quick Start

### 1 — Clone and configure

```bash
git clone https://github.com/ankita1995-ai/sap-rag-assistant.git
cd sap-rag-assistant
cp .env.example .env
# Edit .env and set GOOGLE_API_KEY (get one at https://aistudio.google.com/apikey)
```

### 2 — Install dependencies

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
pip install -r frontend/requirements.txt
```

### 3 — Start the backend

```bash
uvicorn src.main:app --reload
```

API is now live at **http://localhost:8000** · Interactive docs at **http://localhost:8000/docs**

### 4 — Start the frontend

In a second terminal:

```bash
streamlit run frontend/app.py
```

Open **http://localhost:8501** in your browser.

### 5 — Use the UI

1. Drop a SAP PDF in the **Upload Documents** sidebar panel — it ingests automatically
2. Type a question in the chat box
3. Expand **"X passage(s) from Y document(s)"** to see the source citations

---

## API Usage (without UI)

### Upload a document

```bash
curl -X POST http://localhost:8000/upload \
  -F "file=@/path/to/sap_mm_guide.pdf"
```

```json
{
  "filename": "sap_mm_guide.pdf",
  "chunks_created": 87,
  "message": "Successfully ingested 87 chunks from 'sap_mm_guide.pdf'."
}
```

### Ask a question

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the procure-to-pay process in SAP MM?", "k": 4}'
```

```json
{
  "question": "What is the procure-to-pay process in SAP MM?",
  "answer": "The procure-to-pay process in SAP MM begins with a Purchase Requisition...",
  "sources": [
    {
      "source": "sap_mm_guide.pdf",
      "page": 12,
      "content_preview": "The standard procurement cycle starts with a purchase requisition...",
      "relevance_score": 0.4823
    }
  ],
  "processing_time_ms": 1340.5
}
```

---

## Docker

```bash
# Start the full stack
docker-compose up --build

# API only
docker-compose up api --build
```

---

## API Reference

| Method | Path      | Description |
|--------|-----------|-------------|
| `GET`  | `/health` | Liveness probe — returns status and indexed chunk count |
| `POST` | `/upload` | Ingest a PDF document into the FAISS vector store |
| `POST` | `/query`  | Ask a question; returns an answer with source citations |

### POST /query body

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
| `GOOGLE_API_KEY` | — | **Required.** Get one at [aistudio.google.com/apikey](https://aistudio.google.com/apikey) |
| `GOOGLE_MODEL` | `gemini-2.5-flash-lite` | Gemini chat model for answer generation |
| `GOOGLE_EMBEDDING_MODEL` | `models/gemini-embedding-001` | Gemini embedding model |
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

---

## Chunking Strategy

Documents are split using `RecursiveCharacterTextSplitter` with tiktoken encoding:

- **Chunk size**: 512 tokens — large enough for semantic coherence, small enough for precise retrieval
- **Overlap**: 100 tokens — ensures context is not lost at chunk boundaries
- **Splitter hierarchy**: paragraph → sentence → word → character

---

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| FAISS (local) | Zero-infrastructure vector store; perfect for a portfolio demo. Replace with Pinecone/Weaviate for production scale. |
| Chunk deduplication | Repeated ingestion of the same PDF would otherwise return duplicate source passages; content fingerprinting silently drops them. |
| Thread lock on index writes | Concurrent uploads would corrupt the FAISS index without a lock. |
| `temperature=0.0` | SAP documentation Q&A requires factual, deterministic answers. |
| Streamlit frontend | Rapid UI development in pure Python; no separate JS build pipeline needed for a portfolio demo. |
| `allow_dangerous_deserialization=True` | Required by LangChain's FAISS loader; safe because we wrote the file ourselves. |

---

## Roadmap

- [ ] PostgreSQL query history with async SQLAlchemy
- [ ] Multi-tenant index partitioning by SAP module (MM, SD, FI…)
- [ ] Streaming responses via `StreamingResponse`
- [ ] Re-ranker pass for higher-precision retrieval
- [ ] Authentication (API key header)
