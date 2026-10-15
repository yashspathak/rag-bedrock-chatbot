"""Retrieve top-k chunks and ask the LLM to answer from that context only."""

from __future__ import annotations

from dataclasses import dataclass

from src.config import Settings
from src.embeddings import EmbeddingProvider
from src.llm import LlmProvider
from src.vectorstore import RetrievedChunk, VectorStore

SYSTEM_PROMPT = (
    "You are a support assistant. Answer using only the numbered context snippets. "
    "If the context does not contain the answer, say you do not know. "
    "Cite sources by filename when you use a snippet."
)


@dataclass(frozen=True)
class RagAnswer:
    text: str
    chunks: list[RetrievedChunk]


class RagPipeline:
    def __init__(
        self,
        settings: Settings,
        embeddings: EmbeddingProvider,
        store: VectorStore,
        llm: LlmProvider,
    ) -> None:
        self._settings = settings
        self._embeddings = embeddings
        self._store = store
        self._llm = llm

    def ask(self, question: str) -> RagAnswer:
        question = question.strip()
        if not question:
            raise ValueError("Question cannot be empty")
        vector = self._embeddings.embed_query(question)
        chunks = self._store.knn_search(vector, self._settings.top_k)
        user_prompt = _build_user_prompt(question, chunks)
        answer = self._llm.generate(SYSTEM_PROMPT, user_prompt)
        return RagAnswer(text=answer, chunks=chunks)


def _build_user_prompt(question: str, chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return (
            "Context:\n(no matching documents)\n\n"
            f"Question: {question}\n\n"
            "Say you do not know because no context was retrieved."
        )
    blocks = []
    for index, chunk in enumerate(chunks, start=1):
        blocks.append(
            f"[{index}] source={chunk.source} score={chunk.score:.4f}\n{chunk.text}"
        )
    context = "\n\n".join(blocks)
    return f"Context:\n{context}\n\nQuestion: {question}"
