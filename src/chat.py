"""Interactive CLI for the RAG chatbot."""

from __future__ import annotations

from src.config import load_settings
from src.embeddings import build_embedding_provider
from src.llm import build_llm_provider
from src.rag import RagPipeline
from src.vectorstore import VectorStore


def main() -> None:
    settings = load_settings()
    pipeline = RagPipeline(
        settings,
        build_embedding_provider(settings),
        VectorStore(settings),
        build_llm_provider(settings),
    )
    print(
        "Nimbus Desk RAG chat. Type a question, or 'quit' to exit.\n"
        f"embeddings={settings.embedding_provider}  llm={settings.llm_provider}  "
        f"index={settings.opensearch_index}"
    )
    while True:
        try:
            question = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            return
        if not question:
            continue
        if question.lower() in {"q", "quit", "exit"}:
            print("Bye.")
            return
        try:
            result = pipeline.ask(question)
        except Exception as exc:
            print(f"Error: {exc}")
            continue
        print("\nAssistant:")
        print(result.text)
        if result.chunks:
            print("\nSources:")
            for chunk in result.chunks:
                print(f"  - {chunk.source} ({chunk.chunk_id}, score={chunk.score:.4f})")


if __name__ == "__main__":
    main()
