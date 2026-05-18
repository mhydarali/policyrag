"""Shared utility helpers for PolicyRAG."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping


WHITESPACE_RE = re.compile(r"\s+")


def clean_text(text: str) -> str:
    """Collapse noisy PDF whitespace into readable text."""
    return WHITESPACE_RE.sub(" ", text).strip()


def truncate_text(text: str, max_chars: int = 700) -> str:
    """Return a readable excerpt without cutting too aggressively."""
    cleaned = clean_text(text)
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 3].rstrip() + "..."


def citation_from_metadata(metadata: Mapping[str, Any]) -> str:
    source = metadata.get("source_file") or Path(str(metadata.get("source", "unknown"))).name
    page = metadata.get("page_number") or metadata.get("page") or "?"
    chunk_id = metadata.get("chunk_id", "chunk-unknown")
    return f"{source}, p. {page}, {chunk_id}"


def project_relative(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)
