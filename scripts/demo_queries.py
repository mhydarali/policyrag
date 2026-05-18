"""Run a short PolicyRAG terminal demo."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.answering import answer_rag_synthesis, answer_strict_retrieval
from src.config import DEFAULT_RELEVANCE_THRESHOLD, DEFAULT_TOP_K
from src.indexing import build_faiss_index, index_exists
from src.ollama_client import select_ollama_model


DEMO_QUESTIONS = [
    "What documents are required for corporate onboarding?",
    "What are the rules for confidential client data?",
    "What should happen during a SEV1 incident?",
    "What is the cafeteria lunch menu next Tuesday?",
]


def print_result(label: str, answer: str, citations: list[str]) -> None:
    print(f"\n## {label}")
    print(answer)
    if citations:
        print("\nCitations:")
        for citation in citations:
            print(f"- {citation}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run demo questions through PolicyRAG.")
    parser.add_argument("--rag", action="store_true", help="Also run RAG Synthesis if Ollama is available.")
    parser.add_argument("--rebuild", action="store_true", help="Rebuild the FAISS index before the demo.")
    args = parser.parse_args()

    if args.rebuild or not index_exists():
        result = build_faiss_index(force=True)
        print(f"Built index with {result.chunk_count} chunks from {result.pdf_count} PDFs.")

    for question in DEMO_QUESTIONS:
        print(f"\n# Question: {question}")
        strict = answer_strict_retrieval(
            question,
            top_k=DEFAULT_TOP_K,
            min_relevance_score=DEFAULT_RELEVANCE_THRESHOLD,
        )
        print_result("Strict Retrieval", strict.answer, strict.citations)

        if args.rag:
            selection = select_ollama_model()
            if not selection.selected_model:
                print(f"\n## RAG Synthesis\nSkipped: {selection.message}")
                continue
            rag = answer_rag_synthesis(
                question,
                top_k=DEFAULT_TOP_K,
                min_relevance_score=DEFAULT_RELEVANCE_THRESHOLD,
                model=selection.selected_model,
            )
            print_result(f"RAG Synthesis ({rag.model})", rag.answer, rag.citations)


if __name__ == "__main__":
    main()
