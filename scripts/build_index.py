"""Build the local FAISS index from synthetic policy PDFs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import CHUNK_OVERLAP, CHUNK_SIZE, FAISS_INDEX_DIR, MOCK_POLICY_DIR
from src.indexing import build_faiss_index


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the PolicyRAG FAISS index.")
    parser.add_argument("--pdf-dir", type=Path, default=MOCK_POLICY_DIR)
    parser.add_argument("--index-dir", type=Path, default=FAISS_INDEX_DIR)
    parser.add_argument("--chunk-size", type=int, default=CHUNK_SIZE)
    parser.add_argument("--chunk-overlap", type=int, default=CHUNK_OVERLAP)
    args = parser.parse_args()

    result = build_faiss_index(
        pdf_dir=args.pdf_dir,
        index_dir=args.index_dir,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        force=True,
    )
    print("Built FAISS policy index")
    print(f"- PDFs: {result.pdf_count}")
    print(f"- Pages: {result.page_count}")
    print(f"- Chunks: {result.chunk_count}")
    print(f"- Embeddings: {result.embedding_model}")
    print(f"- Index path: {result.index_path}")


if __name__ == "__main__":
    main()
