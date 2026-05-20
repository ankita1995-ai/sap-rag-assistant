import logging
import threading
import time
from pathlib import Path
from typing import Optional

from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.config import Settings
from src.models import QueryResult, SourceDocument

logger = logging.getLogger(__name__)

_SAP_PROMPT = ChatPromptTemplate.from_template(
    """You are an expert SAP consultant with deep knowledge of SAP products, \
modules, and best practices. Answer questions based strictly on the \
documentation excerpts provided below.

Rules:
- Be precise and reference specific SAP module names (e.g. SAP MM, SD, FI, CO, HCM).
- Structure your answer clearly; use bullet points or numbered steps where appropriate.
- If the answer cannot be determined from the context, say exactly: \
  "This information is not covered in the available documentation."
- Never fabricate SAP transaction codes or configuration paths.

Context:
{context}

Question: {question}

Answer:"""
)


class RAGPipeline:
    """End-to-end RAG pipeline: ingest PDFs → embed → store → retrieve → answer."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._lock = threading.Lock()
        self._vector_store: Optional[FAISS] = None

        self.embeddings = GoogleGenerativeAIEmbeddings(
            model=settings.google_embedding_model,
            google_api_key=settings.google_api_key,
        )
        self.llm = ChatGoogleGenerativeAI(
            model=settings.google_model,
            temperature=0.0,
            google_api_key=settings.google_api_key,
        )
        # Use cl100k_base (tiktoken) as a model-agnostic tokeniser for chunking
        self.text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            encoding_name="cl100k_base",
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )
        self._initialize_store()

    # ── Initialisation ─────────────────────────────────────────────────────────

    def _initialize_store(self) -> None:
        """Load a persisted FAISS index from disk, or start with an empty store."""
        index_path = Path(self.settings.faiss_index_path)
        if index_path.exists() and any(index_path.iterdir()):
            try:
                self._vector_store = FAISS.load_local(
                    str(index_path),
                    self.embeddings,
                    allow_dangerous_deserialization=True,  # safe: we wrote this file
                )
                logger.info("Loaded FAISS index from %s (%d vectors)", index_path, self.document_count)
            except Exception as exc:
                logger.warning("Could not load FAISS index (%s); starting fresh.", exc)
        else:
            index_path.mkdir(parents=True, exist_ok=True)
            logger.info("No existing index found — will create on first upload.")

    # ── Ingestion ──────────────────────────────────────────────────────────────

    def ingest_pdf(self, file_path: str, original_filename: str) -> int:
        """Load a PDF, chunk it, embed chunks, and merge into the FAISS index.

        Returns the number of document chunks created.
        Raises ValueError if no text could be extracted from the file.
        """
        loader = PyPDFLoader(file_path)
        raw_docs = loader.load()

        for doc in raw_docs:
            doc.metadata["source"] = original_filename

        chunks = self.text_splitter.split_documents(raw_docs)

        if not chunks:
            raise ValueError(f"No extractable text found in '{original_filename}'.")

        with self._lock:
            if self._vector_store is None:
                self._vector_store = FAISS.from_documents(chunks, self.embeddings)
            else:
                self._vector_store.add_documents(chunks)

            self._vector_store.save_local(self.settings.faiss_index_path)

        logger.info("Ingested %d chunks from '%s'.", len(chunks), original_filename)
        return len(chunks)

    # ── Querying ───────────────────────────────────────────────────────────────

    def query(self, question: str, k: int = 4) -> QueryResult:
        """Retrieve the top-k relevant chunks and generate a cited answer.

        Raises ValueError if no documents have been ingested yet.
        """
        if self._vector_store is None:
            raise ValueError(
                "No documents have been ingested yet. "
                "Upload at least one PDF via POST /upload before querying."
            )

        t0 = time.perf_counter()

        docs_with_scores = self._vector_store.similarity_search_with_score(question, k=k)

        context_parts: list[str] = []
        sources: list[SourceDocument] = []

        for doc, score in docs_with_scores:
            context_parts.append(doc.page_content)
            sources.append(
                SourceDocument(
                    source=doc.metadata.get("source", "unknown"),
                    page=doc.metadata.get("page"),
                    content_preview=doc.page_content[:200].strip(),
                    relevance_score=round(float(score), 4),
                )
            )

        context = "\n\n---\n\n".join(context_parts)
        chain = _SAP_PROMPT | self.llm | StrOutputParser()
        answer: str = chain.invoke({"context": context, "question": question})

        elapsed_ms = (time.perf_counter() - t0) * 1000

        return QueryResult(
            question=question,
            answer=answer,
            sources=sources,
            processing_time_ms=round(elapsed_ms, 2),
        )

    # ── Helpers ────────────────────────────────────────────────────────────────

    @property
    def document_count(self) -> int:
        """Total number of embedded vectors currently in the index."""
        if self._vector_store is None:
            return 0
        return self._vector_store.index.ntotal
