"""Shared project configuration."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
MOCK_POLICY_DIR = DATA_DIR / "mock_policies"
INDEX_DIR = PROJECT_ROOT / "indexes"
LOG_DIR = PROJECT_ROOT / "logs"
FAISS_INDEX_DIR = INDEX_DIR / "faiss_policy_index"
INDEX_MANIFEST_PATH = FAISS_INDEX_DIR / "manifest.json"

EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
CHUNK_SIZE = 900
CHUNK_OVERLAP = 150
DEFAULT_TOP_K = 4
DEFAULT_RELEVANCE_THRESHOLD = 0.35

OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "llama3.2:latest"
OLLAMA_MODEL_FALLBACKS = [
    "llama3.2:latest",
    "phi3:latest",
    "qwen3:0.6b",
    "llama3.2:1b",
]
