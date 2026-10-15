---
name: refactor
description: >-
  Refactors rag-bedrock-chatbot without changing RAG behavior: keep S3 ingest,
  OpenSearch k-NN, and pluggable MiniLM/Ollama vs Bedrock providers. Use when
  the user asks to refactor, clean up, extract, or reorganize Python modules.
---

# Refactor (rag-bedrock-chatbot)

Preserve behavior. Prefer the smallest correct change. Do not add features, dependencies, or frameworks unless the user asked for them in the same request.

## Before changing code

1. Name the behavior that must stay the same (CLI flags, index document shape, prompts, provider names).
2. Read the current module and its callers. Typical wiring:
   - `src/ingest.py` → S3 → `chunking` → `embeddings` → `vectorstore.reset_index` / bulk
   - `src/chat.py` → `RagPipeline` → embed query → k-NN → `llm.generate`
3. If the user only wanted a review, stop and use the `code-review` skill instead.

## Where code belongs

| Change | Put it here |
|---|---|
| Env / defaults / provider names | `src/config.py` + `.env.example` |
| boto3 / LocalStack vs AWS / OS endpoint | `src/aws_clients.py` |
| Split windows / `Chunk` metadata | `src/chunking.py` |
| Vectors | `EmbeddingProvider` + `build_embedding_provider` in `src/embeddings.py` |
| Index / bulk / k-NN | `src/vectorstore.py` |
| Completions | `LlmProvider` + `build_llm_provider` in `src/llm.py` |
| Retrieve + grounded prompt | `src/rag.py` |
| Upload / parse / CLI ingest | `src/ingest.py` |
| REPL | `src/chat.py` |

Do not introduce a `src/Service` layer, repository package, or LangChain graph. Extend ABCs; do not fork a parallel provider stack.

## Hard constraints

- `bedrock_runtime()` never receives `endpoint_url` from LocalStack.
- Do not mix embedding dimensions in one index. After a dim or model change, ingest must still rebuild (`reset_index`).
- Keep k-NN mapping to `knn_vector` + dimension only.
- `RagPipeline` must keep using the same embedding factory as ingest.
- Do not log secrets. Do not commit `.env`.
- New settings: `EMBEDDING_PROVIDER` is `local` \| `bedrock`; `LLM_PROVIDER` is `ollama` \| `bedrock`.

## How to refactor

1. Extract helpers inside the owning module first. Move across files only when two modules already share a contract (ABC, `Settings`, `Chunk`, `RetrievedChunk`).
2. Keep public CLI: `python -m src.ingest` (`--path`, `--skip-upload`) and `python -m src.chat`.
3. Match existing style: `from __future__ import annotations`, dataclasses, factories, no unused deps in `requirements.txt`.
4. After edits, `python -m py_compile` on touched files. Smoke ingest only if the user wants a runtime check and LocalStack is up — do not treat chat REPL as an automated test.

## Handoff

State what moved, what was intentionally unchanged (prompts, index fields, provider env names), and any follow-up (re-ingest, `.env.example` keys).
