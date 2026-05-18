"""Streamlit interface for PolicyRAG."""

from __future__ import annotations

import html
from typing import Dict, List, Optional

import streamlit as st

from src.answering import (
    RAG_MODE,
    STRICT_MODE,
    AnswerResult,
    answer_rag_synthesis,
    answer_strict_retrieval,
)
from src.config import (
    DEFAULT_RELEVANCE_THRESHOLD,
    DEFAULT_TOP_K,
    EMBEDDING_MODEL_NAME,
    FAISS_INDEX_DIR,
    MOCK_POLICY_DIR,
)
from src.indexing import build_faiss_index, index_exists, list_policy_pdfs, read_index_manifest
from src.ollama_client import list_ollama_models, select_ollama_model
from src.utils import truncate_text


EXAMPLE_QUESTIONS = [
    "What documents are required for corporate onboarding?",
    "When is enhanced due diligence required?",
    "What are the rules for confidential client data?",
    "What should happen during a SEV1 incident?",
    "Can the AI assistant answer using information outside approved documents?",
]


@st.cache_data(ttl=10)
def cached_index_manifest() -> Optional[Dict[str, object]]:
    return read_index_manifest()


@st.cache_data(ttl=10)
def cached_ollama_models() -> List[str]:
    return list_ollama_models()


def clear_app_caches() -> None:
    cached_index_manifest.clear()
    cached_ollama_models.clear()


def render_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --policy-accent: #2563eb;
            --policy-muted: #64748b;
            --policy-border: #d9e2ec;
            --policy-surface: #f8fafc;
        }
        .main .block-container {
            max-width: 1160px;
            padding-top: 2.2rem;
        }
        h1 {
            letter-spacing: 0 !important;
        }
        .subtitle {
            color: var(--policy-muted);
            font-size: 1rem;
            margin-top: -0.75rem;
            margin-bottom: 1.2rem;
        }
        .answer-box {
            border-left: 4px solid var(--policy-accent);
            background: var(--policy-surface);
            padding: 1rem 1.1rem;
            margin: 0.4rem 0 1rem 0;
        }
        .refusal-box {
            border-left: 4px solid #b45309;
            background: #fffbeb;
            padding: 1rem 1.1rem;
            margin: 0.4rem 0 1rem 0;
        }
        .chunk-meta {
            color: var(--policy-muted);
            font-size: 0.86rem;
            margin-bottom: 0.35rem;
        }
        .citation-list li {
            margin-bottom: 0.25rem;
        }
        div[data-testid="stMetricValue"] {
            font-size: 1.3rem;
        }
        div[data-testid="stTextInput"] div[data-baseweb="input"] {
            display: none;
        }
        div[data-testid="stTextInput"] {
            margin-bottom: -0.45rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def initialize_question_state() -> None:
    if "question" not in st.session_state:
        st.session_state.question = EXAMPLE_QUESTIONS[0]


def set_question(question: str) -> None:
    st.session_state.question = question


def render_sidebar() -> Dict[str, object]:
    st.sidebar.header("Controls")

    mode = st.sidebar.radio(
        "Answer mode",
        [STRICT_MODE, RAG_MODE],
        help="Strict Retrieval quotes excerpts only. RAG Synthesis sends retrieved context to Ollama.",
    )

    available_models = cached_ollama_models()
    model_options = ["Auto fallback"] + available_models
    model_disabled = mode == STRICT_MODE
    selected_model_label = st.sidebar.selectbox(
        "Ollama model",
        model_options,
        disabled=model_disabled,
        help="Used only in RAG Synthesis mode.",
    )
    selected_model = None if selected_model_label == "Auto fallback" else selected_model_label

    top_k = st.sidebar.slider(
        "Retrieved chunks",
        min_value=1,
        max_value=8,
        value=DEFAULT_TOP_K,
        step=1,
        help=(
            "How many top-matching policy chunks to retrieve for each question. "
            "Higher values show more evidence but may include less relevant context."
        ),
    )
    threshold = st.sidebar.slider(
        "Relevance threshold",
        min_value=0.0,
        max_value=0.9,
        value=DEFAULT_RELEVANCE_THRESHOLD,
        step=0.05,
        help="Answers refuse when the best retrieved chunk is below this score.",
    )

    st.sidebar.divider()
    rebuild_help = (
        "Recreate the local FAISS vector index from the PDFs in data/mock_policies. "
        "Use this after adding, removing, or regenerating policy PDFs. "
        "The app uses the rebuilt index for future retrieval and answers."
    )
    st.sidebar.text_input(
        "Rebuild index",
        value="",
        key="rebuild_index_info_label",
        help=rebuild_help,
    )
    rebuild_clicked = st.sidebar.button("Rebuild index", use_container_width=True)
    if rebuild_clicked:
        with st.spinner("Rebuilding FAISS index from policy PDFs..."):
            result = build_faiss_index(force=True)
        clear_app_caches()
        st.sidebar.success(f"Indexed {result.chunk_count} chunks from {result.pdf_count} PDFs.")

    st.sidebar.subheader("Example questions")
    for idx, example in enumerate(EXAMPLE_QUESTIONS, start=1):
        st.sidebar.button(
            example,
            key=f"example_{idx}",
            use_container_width=True,
            on_click=set_question,
            args=(example,),
        )

    return {
        "mode": mode,
        "selected_model": selected_model,
        "available_models": available_models,
        "top_k": top_k,
        "threshold": threshold,
    }


def render_status_panel(controls: Dict[str, object]) -> None:
    manifest = cached_index_manifest()
    pdf_count = len(list_policy_pdfs(MOCK_POLICY_DIR))
    chunk_count = manifest.get("chunk_count", 0) if manifest else 0
    active_selection = select_ollama_model(preferred_model=controls["selected_model"])
    active_model = active_selection.selected_model or "Unavailable"

    st.subheader("Index status")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Indexed PDFs", pdf_count)
    col2.metric("Chunks", chunk_count)
    col3.metric("Embedding model", EMBEDDING_MODEL_NAME.split("/")[-1])
    col4.metric("Active LLM", active_model)

    if not index_exists(FAISS_INDEX_DIR):
        st.warning("No FAISS index found. Use Rebuild index before asking questions.")
    elif manifest:
        st.caption(
            f"Index path: `{manifest.get('index_path')}` | "
            f"chunk size {manifest.get('chunk_size')} | overlap {manifest.get('chunk_overlap')}"
        )

    if not active_selection.ollama_available:
        st.info(
            "Ollama is not reachable or no local model is installed. "
            "Strict Retrieval mode still works; RAG Synthesis will show a clear fallback message."
        )


def run_answer(
    question: str,
    mode: str,
    top_k: int,
    threshold: float,
    selected_model: Optional[str],
) -> AnswerResult:
    if mode == STRICT_MODE:
        return answer_strict_retrieval(
            question=question,
            top_k=top_k,
            min_relevance_score=threshold,
        )
    return answer_rag_synthesis(
        question=question,
        top_k=top_k,
        min_relevance_score=threshold,
        model=selected_model,
    )


def render_answer(result: AnswerResult) -> None:
    st.subheader("Answer")
    css_class = "refusal-box" if result.refused else "answer-box"
    escaped_answer = html.escape(result.answer).replace("\n", "<br>")
    st.markdown(
        f"<div class='{css_class}'>{escaped_answer}</div>",
        unsafe_allow_html=True,
    )
    if result.message:
        st.caption(result.message)
    if result.model:
        st.caption(f"Model: `{result.model}`")

    st.subheader("Source citations")
    if result.citations:
        items = "".join(f"<li><code>{html.escape(citation)}</code></li>" for citation in result.citations)
        st.markdown(f"<ul class='citation-list'>{items}</ul>", unsafe_allow_html=True)
    else:
        st.caption("No citations met the evidence threshold.")


def render_retrieved_chunks(result: AnswerResult) -> None:
    st.subheader("Retrieved chunks")
    if not result.retrieved_chunks:
        st.caption("No chunks were retrieved.")
        return

    for idx, chunk in enumerate(result.retrieved_chunks, start=1):
        title = f"{idx}. {chunk.citation} | relevance {chunk.relevance_score:.2f}"
        with st.expander(title, expanded=idx == 1):
            document_name = html.escape(str(chunk.metadata.get("document_name", "Unknown")))
            st.markdown(
                f"<div class='chunk-meta'>distance {chunk.distance:.3f} | "
                f"document {document_name}</div>",
                unsafe_allow_html=True,
            )
            st.write(truncate_text(chunk.text, max_chars=1600))
            st.json(chunk.metadata, expanded=False)


def main() -> None:
    st.set_page_config(page_title="PolicyRAG", page_icon="PR", layout="wide")
    render_styles()
    initialize_question_state()

    controls = render_sidebar()

    st.title("PolicyRAG")
    st.markdown("<div class='subtitle'>Local RAG over synthetic policy PDFs</div>", unsafe_allow_html=True)

    render_status_panel(controls)

    st.divider()
    st.subheader("Ask a policy question")
    question = st.text_area(
        "Question",
        key="question",
        height=100,
        label_visibility="collapsed",
        placeholder="Ask about onboarding, client data, AI assistant use, model risk, vendor risk, or incidents.",
    )

    ask_clicked = st.button("Ask", type="primary", use_container_width=False)

    if ask_clicked:
        if not question.strip():
            st.warning("Enter a question first.")
            return

        try:
            with st.spinner("Retrieving policy evidence..."):
                result = run_answer(
                    question=question,
                    mode=str(controls["mode"]),
                    top_k=int(controls["top_k"]),
                    threshold=float(controls["threshold"]),
                    selected_model=controls["selected_model"],
                )
        except FileNotFoundError as exc:
            st.error(str(exc))
            return
        except Exception as exc:  # pragma: no cover - UI defensive fallback
            st.error(f"Unable to answer because the backend raised an error: {exc}")
            return

        render_answer(result)
        render_retrieved_chunks(result)

    else:
        st.caption("Choose an example or enter a question, then ask to retrieve evidence.")


if __name__ == "__main__":
    main()
