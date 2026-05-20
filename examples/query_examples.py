"""
Demonstrates interacting with the SAP RAG Assistant API.

Prerequisites:
    1. Start the server: uvicorn src.main:app --reload
    2. Upload a document first (see upload_document below).

Usage:
    python examples/query_examples.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import requests

BASE_URL = "http://localhost:8000"

SAMPLE_QUESTIONS = [
    "What is the SAP MM module and what are its main sub-modules?",
    "Explain the procure-to-pay process in SAP MM step by step.",
    "What is the difference between SAP ECC and SAP S/4HANA?",
    "How does the order-to-cash cycle work in SAP SD?",
    "What is the ACDOCA table in SAP S/4HANA Finance?",
    "What transaction code is used to create a Purchase Order in SAP?",
    "Explain SAP FICO and how FI and CO are integrated.",
    "What is SAP Basis and what are its responsibilities?",
]


def check_health() -> None:
    resp = requests.get(f"{BASE_URL}/health", timeout=10)
    resp.raise_for_status()
    data = resp.json()
    print(f"[health] status={data['status']}  indexed_chunks={data['indexed_chunks']}")


def upload_document(pdf_path: str) -> dict:
    path = Path(pdf_path)
    if not path.exists():
        print(f"[upload] File not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    with path.open("rb") as fh:
        resp = requests.post(
            f"{BASE_URL}/upload",
            files={"file": (path.name, fh, "application/pdf")},
            timeout=120,
        )

    resp.raise_for_status()
    data = resp.json()
    print(f"[upload] {data['message']}")
    return data


def ask_question(question: str, k: int = 4) -> None:
    resp = requests.post(
        f"{BASE_URL}/query",
        json={"question": question, "k": k},
        timeout=60,
    )
    resp.raise_for_status()
    result = resp.json()

    print(f"\n{'─' * 70}")
    print(f"Q: {result['question']}")
    print(f"\nA: {result['answer']}")
    print(f"\nSources ({len(result['sources'])}):")
    for src in result["sources"]:
        page = f"p.{src['page']}" if src.get("page") is not None else "n/a"
        print(f"  [{src['source']} | {page} | score={src['relevance_score']:.4f}]")
        print(f"    …{src['content_preview'][:120]}…")
    print(f"\n  Processing time: {result['processing_time_ms']:.0f} ms")


def main() -> None:
    print("=== SAP RAG Assistant — Example Client ===\n")
    check_health()

    # Upload sample document if provided as a CLI argument
    if len(sys.argv) > 1:
        upload_document(sys.argv[1])
    else:
        print(
            "\n[tip] Pass a PDF path as an argument to upload it first:\n"
            "      python examples/query_examples.py path/to/sap_doc.pdf\n"
        )

    # Run sample queries
    for question in SAMPLE_QUESTIONS:
        try:
            ask_question(question, k=4)
        except requests.HTTPError as exc:
            print(f"[error] {exc.response.status_code}: {exc.response.text}")
        except requests.ConnectionError:
            print("[error] Cannot reach the API — is the server running?")
            sys.exit(1)


if __name__ == "__main__":
    main()
