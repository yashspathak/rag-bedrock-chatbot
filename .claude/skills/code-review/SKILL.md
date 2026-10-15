---
name: code-review
description: >-
  Reviews diffs and PRs in rag-bedrock-chatbot against the LocalStack/Bedrock
  RAG architecture, provider contracts, and secret-handling rules. Use when the
  user asks for a code review, PR review, or to inspect uncommitted changes.
---

# Code review (rag-bedrock-chatbot)

Review only. Do not edit files or commit unless the user asks for fixes after the review.

## Scope

1. Collect the change set: `git status`, `git diff` (staged + unstaged), and `git log` / `git diff <base>...HEAD` when a branch or PR is named.
2. Read neighboring modules, not only the hunk. A change in `src/embeddings.py` must be checked against ingest and `RagPipeline.ask`.
3. Do not read `.env` or `~/.aws/**`. Judge env handling from `.env.example` and `src/config.py`.

## Architecture gates (fail the review if violated)

- No LangChain, LlamaIndex, FastAPI, or a second config/settings system.
- New knobs land on `Settings` in `src/config.py` and `.env.example` together.
- `s3_client` / `opensearch_control_plane` may use `AWS_ENDPOINT_URL`. `bedrock_runtime()` must not.
- Query embeddings use the same `build_embedding_provider` path as ingest. Dimension must match `Settings.embedding_dim` and the OpenSearch `knn_vector` mapping.
- OpenSearch index mapping stays `knn_vector` + `dimension` only (no extra HNSW/engine params).
- Ingest still rebuilds via `reset_index` then bulk `{text, source, chunk_id, offset, embedding}`.
- LLM does not search. Answers come from numbered k-NN snippets; empty retrieval says it does not know.
- New embedding/LLM backends implement the existing ABC and `build_*_provider` factory.

## Also check

- Secrets, tokens, or real AWS keys in source, logs, or compose files.
- `CHUNK_OVERLAP < CHUNK_SIZE`; supported ingest suffixes remain `.txt`, `.md`, `.pdf`.
- LocalStack compose still uses `OPENSEARCH_ENDPOINT_STRATEGY=path`.
- Syntax: `python -m py_compile` on changed `src/*.py`. There is no project test suite; do not invent CI that is not in the repo.

## Report format

```markdown
## Summary
[1–3 sentences: what the change does and whether it is mergeable]

## Findings
- 🔴 **Critical** — `path`: must fix (architecture, secrets, data loss)
- 🟡 **Suggestion** — `path`: should fix
- 🟢 **Nit** — optional

## Residual risk
[ingest/index rebuild, Bedrock vs LocalStack mix, dimension change]
```

If there are no findings, say so and still note residual risk (for example: re-ingest required).
