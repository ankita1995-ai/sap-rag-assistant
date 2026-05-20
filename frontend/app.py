import requests
import streamlit as st

API_BASE = "http://localhost:8000"

st.set_page_config(
    page_title="SAP RAG Assistant",
    page_icon="📘",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Session state defaults ─────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
if "uploaded_docs" not in st.session_state:
    st.session_state.uploaded_docs = []
if "processed_files" not in st.session_state:
    st.session_state.processed_files = set()


# ── Helper ─────────────────────────────────────────────────────────────────────
def get_health() -> dict | None:
    try:
        r = requests.get(f"{API_BASE}/health", timeout=3)
        return r.json() if r.ok else None
    except requests.exceptions.ConnectionError:
        return None


# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("📘 SAP RAG Assistant")
    st.caption("Upload SAP documentation, then ask questions.")

    st.divider()

    # Status
    health = get_health()
    if health:
        st.success(f"Backend connected  ·  **{health['indexed_chunks']}** chunks indexed")
    else:
        st.error("Backend not reachable — start the FastAPI server first.")

    st.divider()

    # Upload
    st.subheader("Upload Documents")
    uploaded_file = st.file_uploader(
        "Drop a SAP PDF here",
        type=["pdf"],
        help="Only PDF files are accepted.",
    )

    if uploaded_file is not None:
        file_key = f"{uploaded_file.name}_{uploaded_file.size}"
        if file_key not in st.session_state.processed_files:
            with st.spinner(f"Ingesting **{uploaded_file.name}**…"):
                try:
                    resp = requests.post(
                        f"{API_BASE}/upload",
                        files={
                            "file": (
                                uploaded_file.name,
                                uploaded_file.getvalue(),
                                "application/pdf",
                            )
                        },
                        timeout=120,
                    )
                    if resp.ok:
                        data = resp.json()
                        st.success(data["message"])
                        st.session_state.processed_files.add(file_key)
                        st.session_state.uploaded_docs.append(
                            {"name": data["filename"], "chunks": data["chunks_created"]}
                        )
                        st.rerun()
                    else:
                        detail = resp.json().get("detail", "Unknown error")
                        st.error(f"Upload failed: {detail}")
                except requests.exceptions.ConnectionError:
                    st.error("Cannot reach the backend.")

    st.divider()

    # Document list
    st.subheader("Loaded Documents")
    if st.session_state.uploaded_docs:
        for doc in st.session_state.uploaded_docs:
            st.markdown(f"📄 **{doc['name']}**  \n`{doc['chunks']} chunks`")
    else:
        st.caption("No documents uploaded this session.")

    st.divider()
    if st.button("🗑 Clear chat history"):
        st.session_state.messages = []
        st.rerun()


# ── Helpers ───────────────────────────────────────────────────────────────────
def sources_label(sources: list[dict]) -> str:
    unique_docs = len({s["source"] for s in sources})
    doc_word = "document" if unique_docs == 1 else "documents"
    return f"📎 {len(sources)} passage(s) from {unique_docs} {doc_word}"


# ── Main area ──────────────────────────────────────────────────────────────────
st.header("Ask a Question")

if not st.session_state.uploaded_docs and health and health["indexed_chunks"] == 0:
    st.info("Upload a SAP PDF in the sidebar to get started.")

# Chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("sources"):
            with st.expander(sources_label(msg["sources"])):
                for i, src in enumerate(msg["sources"], 1):
                    page_label = f"p. {src['page']}" if src.get("page") is not None else "page unknown"
                    score_label = f"score {src['relevance_score']:.4f}"
                    st.markdown(f"**{i}. {src['source']}** — {page_label} · {score_label}")
                    st.caption(src["content_preview"])
                    if i < len(msg["sources"]):
                        st.divider()
        if msg.get("processing_time_ms") is not None:
            st.caption(f"⏱ {msg['processing_time_ms']:.0f} ms")

# Query input
if prompt := st.chat_input("What would you like to know about SAP?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        if not health:
            st.error("Backend is not reachable. Please start the FastAPI server.")
            st.session_state.messages.append(
                {"role": "assistant", "content": "Backend not reachable."}
            )
        else:
            with st.spinner("Searching documents and generating answer…"):
                try:
                    resp = requests.post(
                        f"{API_BASE}/query",
                        json={"question": prompt, "k": 4},
                        timeout=60,
                    )
                    if resp.ok:
                        data = resp.json()
                        st.markdown(data["answer"])
                        if data["sources"]:
                            with st.expander(sources_label(data["sources"])):
                                for i, src in enumerate(data["sources"], 1):
                                    page_label = (
                                        f"p. {src['page']}"
                                        if src.get("page") is not None
                                        else "page unknown"
                                    )
                                    score_label = f"score {src['relevance_score']:.4f}"
                                    st.markdown(
                                        f"**{i}. {src['source']}** — {page_label} · {score_label}"
                                    )
                                    st.caption(src["content_preview"])
                                    if i < len(data["sources"]):
                                        st.divider()
                        st.caption(f"⏱ {data['processing_time_ms']:.0f} ms")
                        st.session_state.messages.append(
                            {
                                "role": "assistant",
                                "content": data["answer"],
                                "sources": data["sources"],
                                "processing_time_ms": data["processing_time_ms"],
                            }
                        )
                    else:
                        detail = resp.json().get("detail", "Unknown error")
                        st.error(f"Error: {detail}")
                        st.session_state.messages.append(
                            {"role": "assistant", "content": f"Error: {detail}"}
                        )
                except requests.exceptions.ConnectionError:
                    st.error("Lost connection to the backend.")
                except Exception as exc:
                    st.error(f"Unexpected error: {exc}")
