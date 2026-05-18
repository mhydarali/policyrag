"""PDF loading, chunking, embedding, FAISS indexing, and retrieval."""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from langchain_core.documents import Document

from src.config import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    DEFAULT_RELEVANCE_THRESHOLD,
    DEFAULT_TOP_K,
    EMBEDDING_MODEL_NAME,
    FAISS_INDEX_DIR,
    MOCK_POLICY_DIR,
    PROJECT_ROOT,
)
from src.utils import citation_from_metadata, clean_text, project_relative


@dataclass
class BuildIndexResult:
    pdf_count: int
    page_count: int
    chunk_count: int
    index_path: str
    embedding_model: str
    chunk_size: int
    chunk_overlap: int


@dataclass
class RetrievedChunk:
    text: str
    metadata: Dict[str, Any]
    relevance_score: float
    distance: float

    @property
    def citation(self) -> str:
        return citation_from_metadata(self.metadata)


def list_policy_pdfs(pdf_dir: Path = MOCK_POLICY_DIR) -> List[Path]:
    return sorted(path for path in pdf_dir.glob("*.pdf") if path.is_file())


def get_embeddings():
    """Create the local embedding model used by FAISS.

    Normalized vectors make FAISS L2 distances easier to convert into a
    cosine-like relevance score during retrieval.
    """
    try:
        from langchain_huggingface import HuggingFaceEmbeddings
    except ImportError:
        from langchain_community.embeddings import HuggingFaceEmbeddings

    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL_NAME,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


def _document_title_from_filename(pdf_path: Path) -> str:
    return pdf_path.stem.replace("_", " ").title()


def load_policy_pages(pdf_dir: Path = MOCK_POLICY_DIR) -> List[Document]:
    from langchain_community.document_loaders import PyPDFLoader

    pages: List[Document] = []
    pdf_paths = list_policy_pdfs(pdf_dir)
    if not pdf_paths:
        raise FileNotFoundError(f"No PDFs found in {pdf_dir}")

    for pdf_path in pdf_paths:
        loader = PyPDFLoader(str(pdf_path))
        for page_doc in loader.load():
            raw_page_index = int(page_doc.metadata.get("page", 0))
            metadata = dict(page_doc.metadata)
            metadata.update(
                {
                    "source": str(pdf_path),
                    "source_file": pdf_path.name,
                    "document_name": _document_title_from_filename(pdf_path),
                    "page_number": raw_page_index + 1,
                }
            )
            pages.append(Document(page_content=page_doc.page_content, metadata=metadata))
    return pages


def split_policy_pages(
    pages: Iterable[Document],
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> List[Document]:
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(list(pages))

    counters: Dict[str, int] = {}
    enriched: List[Document] = []
    for chunk in chunks:
        metadata = dict(chunk.metadata)
        source_file = str(metadata.get("source_file", "unknown"))
        counters[source_file] = counters.get(source_file, 0) + 1
        chunk_index = counters[source_file]
        metadata["chunk_index"] = chunk_index
        metadata["chunk_id"] = f"{Path(source_file).stem}-chunk-{chunk_index:03d}"
        metadata["text_length"] = len(chunk.page_content)
        enriched.append(Document(page_content=clean_text(chunk.page_content), metadata=metadata))

    return enriched


def index_exists(index_dir: Path = FAISS_INDEX_DIR) -> bool:
    return (index_dir / "index.faiss").exists() and (index_dir / "index.pkl").exists()


def remove_existing_index(index_dir: Path = FAISS_INDEX_DIR) -> None:
    if index_dir.exists():
        shutil.rmtree(index_dir)


def build_faiss_index(
    pdf_dir: Path = MOCK_POLICY_DIR,
    index_dir: Path = FAISS_INDEX_DIR,
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
    force: bool = True,
) -> BuildIndexResult:
    from langchain_community.vectorstores import FAISS

    if force:
        remove_existing_index(index_dir)

    index_dir.mkdir(parents=True, exist_ok=True)
    pages = load_policy_pages(pdf_dir)
    chunks = split_policy_pages(pages, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    embeddings = get_embeddings()

    vector_store = FAISS.from_documents(chunks, embeddings)
    vector_store.save_local(str(index_dir))

    result = BuildIndexResult(
        pdf_count=len(list_policy_pdfs(pdf_dir)),
        page_count=len(pages),
        chunk_count=len(chunks),
        index_path=project_relative(index_dir, PROJECT_ROOT),
        embedding_model=EMBEDDING_MODEL_NAME,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    _write_manifest(result, index_dir)
    return result


def _write_manifest(result: BuildIndexResult, index_dir: Path) -> None:
    manifest_path = index_dir / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(asdict(result), indent=2) + "\n", encoding="utf-8")


def read_index_manifest(index_dir: Path = FAISS_INDEX_DIR) -> Optional[Dict[str, Any]]:
    manifest_path = index_dir / "manifest.json"
    if not manifest_path.exists():
        return None
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def load_faiss_index(index_dir: Path = FAISS_INDEX_DIR):
    from langchain_community.vectorstores import FAISS

    if not index_exists(index_dir):
        raise FileNotFoundError(
            f"FAISS index not found at {index_dir}. Run scripts/build_index.py first."
        )

    embeddings = get_embeddings()
    return FAISS.load_local(
        str(index_dir),
        embeddings,
        allow_dangerous_deserialization=True,
    )


def faiss_distance_to_relevance(distance: float) -> float:
    """Convert normalized-vector squared L2 distance into a 0-1 score.

    With normalized embeddings, squared L2 distance approximates 2 - 2*cosine.
    This maps close matches toward 1 and unrelated matches toward 0.
    """
    return max(0.0, min(1.0, 1.0 - (float(distance) / 2.0)))


def retrieve_relevant_chunks(
    question: str,
    top_k: int = DEFAULT_TOP_K,
    min_relevance_score: float = DEFAULT_RELEVANCE_THRESHOLD,
    index_dir: Path = FAISS_INDEX_DIR,
    include_below_threshold: bool = True,
) -> List[RetrievedChunk]:
    if not question.strip():
        raise ValueError("Question must not be empty.")
    if top_k < 1:
        raise ValueError("top_k must be at least 1.")

    vector_store = load_faiss_index(index_dir)
    raw_results = vector_store.similarity_search_with_score(question, k=top_k)

    chunks: List[RetrievedChunk] = []
    for document, distance in raw_results:
        relevance = faiss_distance_to_relevance(float(distance))
        if include_below_threshold or relevance >= min_relevance_score:
            chunks.append(
                RetrievedChunk(
                    text=clean_text(document.page_content),
                    metadata=dict(document.metadata),
                    relevance_score=relevance,
                    distance=float(distance),
                )
            )
    return chunks
