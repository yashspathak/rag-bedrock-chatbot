---
name: release
description: >-
  Prepares a rag-bedrock-chatbot release: local smoke path, env contract,
  Bedrock vs LocalStack notes, and git hygiene. Use when the user asks to
  release, tag, ship, cut a version, or write release notes.
---

# Release (rag-bedrock-chatbot)

Ship the explicit Python RAG pipeline (S3 → chunk → embed → OpenSearch; query → k-NN → LLM). There is no app server, container image for the chatbot itself, or CI in this repo — do not invent them.

Do not commit, tag, or push unless the user explicitly asks.

## Preflight

1. `git status` and `git diff` — working tree should match what you intend to ship.
2. Confirm `.env` is gitignored and untracked. Never include `.env`, AWS keys, or Bedrock tokens in the tag, notes, or sample commands.
3. Diff `.env.example` against `src/config.py` `Settings` / `load_settings()`. Every knob the code reads must be documented there with the local default.
4. `python -m py_compile` on `src/*.py`.
5. If LocalStack is available (user-approved):
   - `docker compose up -d`
   - `./scripts/bootstrap_local.sh`
   - `python -m src.ingest` (or `--skip-upload` if the bucket already has docs)
6. Skip `python -m src.chat` as an automated gate (interactive REPL). Mention it in notes as a manual check.

## Release notes must state

- **Local path:** Python 3.11+, Docker LocalStack (`s3,opensearch`), Ollama (`llama3.2` or compose profile), dummy `test`/`test` keys, `AWS_ENDPOINT_URL=http://localhost:4566`.
- **AWS path:** unset `AWS_ENDPOINT_URL` for real S3/OpenSearch; `EMBEDDING_PROVIDER=bedrock` and/or `LLM_PROVIDER=bedrock`; enable Titan Embed + the Converse model in the same region as `AWS_DEFAULT_REGION`.
- **Incompatible changes:** embedding model or dimension change requires a full re-ingest; do not mix dims in `rag-chunks`.
- **Non-goals:** LocalStack Community does not host Titan/Claude; `bedrock-runtime` stays on real AWS.

## Docs to keep in sync

| File | Why |
|---|---|
| `README.md` | Human setup |
| `CLAUDE.md` | Agent contract (commands, layout, rules) |
| `.env.example` | Env contract |
| `requirements.txt` | Pinned-range deps actually imported |
| `docker-compose.yml` | LocalStack 4.3 + optional `ollama` profile |
| `scripts/bootstrap_local.sh` | Bucket `rag-docs`, domain `rag-vectors` |

Update `CLAUDE.md` only if commands, paths, or architecture rules changed.

## Git / tag (only when asked)

- Conventional commit style: `feat:`, `fix:`, `docs:`, `refactor:` — short why, not a file list.
- Tag `vX.Y.Z` when the user wants a version. Breaking ingest/index/env → bump minor or major, and say “re-ingest required” in the notes.
- Do not `git push --force`. Do not skip hooks.

## Notes template

```markdown
## rag-bedrock-chatbot vX.Y.Z

### Changes
- 

### Upgrade
- [ ] Re-ingest if embedding model or dimension changed: `python -m src.ingest`
- [ ] Copy new keys from `.env.example` into local `.env`

### Verify (local)
- [ ] `docker compose up -d` && `./scripts/bootstrap_local.sh`
- [ ] `python -m src.ingest`
- [ ] Manual: `python -m src.chat`
```
