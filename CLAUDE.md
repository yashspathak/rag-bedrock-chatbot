# rag-bedrock-chatbot

Small Python RAG chatbot. S3 is the document source of truth; OpenSearch stores chunk embeddings (`knn_vector`). Locally, S3 and OpenSearch run on LocalStack Community. Embeddings and generation are pluggable: MiniLM + Ollama by default, Amazon Bedrock (Titan Embed + Converse) on real AWS. LocalStack Community does not host Titan or Claude — never send `bedrock-runtime` to the LocalStack endpoint.

There is no LangChain (or similar) layer. Keep the pipeline as explicit modules: ingest → chunk → embed → index; query embed → k-NN → grounded prompt → LLM.

## Stack

| Layer | Choice |
|---|---|
| Language | Python 3.11+ |
| AWS SDK | boto3 (`s3`, `opensearch` control plane, `bedrock-runtime`) |
| Vector DB | OpenSearch (`opensearch-py`, `knn_vector`) |
| Local AWS | LocalStack 4.3 (`docker-compose.yml`, services `s3,opensearch`) |
| Embeddings | `sentence-transformers` (`all-MiniLM-L6-v2`, 384-d) or Titan Embed V2 (1024-d) |
| LLM | Ollama HTTP (`/api/chat`) or Bedrock `converse` |
| Docs | UTF-8 `.txt`/`.md`; PDFs via `pypdf` |
| Config | `python-dotenv` → repo-root `.env` (see `.env.example`) |

No test suite, linter config, or Makefile in this repo. Smoke the pipeline with ingest + chat.

## Commands

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

docker compose up -d
./scripts/bootstrap_local.sh          # S3 bucket rag-docs + OpenSearch domain rag-vectors

ollama pull llama3.2                  # or: docker compose --profile ollama up -d

python -m src.ingest                  # upload data/sample, parse, chunk, embed, rebuild index
python -m src.ingest --skip-upload    # re-index from objects already in S3
python -m src.ingest --path /other/docs
python -m src.chat                    # REPL; quit with q / quit / exit
```

Switch to Bedrock: set `EMBEDDING_PROVIDER=bedrock`, `LLM_PROVIDER=bedrock`, real credentials, enable models in the Bedrock console. Leave `AWS_ENDPOINT_URL` set if S3/OpenSearch stay on LocalStack; clear it for full AWS. Changing embedding model or dimension **requires a full re-ingest** — do not mix dimensions in one index.

## Layout

```
.env.example                 # env contract
docker-compose.yml           # LocalStack; optional ollama profile
scripts/bootstrap_local.sh   # aws CLI against LocalStack
data/sample/                 # tiny Nimbus Desk corpus
src/config.py                # Settings dataclass; provider validation
src/aws_clients.py           # boto3; LocalStack endpoint only when AWS_ENDPOINT_URL is set
src/chunking.py              # recursive split + overlap; Chunk metadata
src/embeddings.py            # EmbeddingProvider: local MiniLM | Bedrock Titan
src/vectorstore.py           # index create/reset, bulk, k-NN
src/llm.py                   # LlmProvider: Ollama | Bedrock Converse
src/ingest.py                # CLI: upload → S3 → chunk → embed → index
src/rag.py                   # retrieve + system prompt + generate
src/chat.py                  # CLI loop over RagPipeline
```

## Architecture rules

- **Thin modules, no framework.** Add behavior in the existing provider/pipeline files. Do not introduce LangChain, LlamaIndex, FastAPI, or a second config system unless the task explicitly asks for it.
- **Settings live in `src/config.py`.** New knobs go on `Settings` + `.env.example`. `EMBEDDING_PROVIDER` is `local` or `bedrock`; `LLM_PROVIDER` is `ollama` or `bedrock`.
- **S3 vs OpenSearch vs Bedrock.** `s3_client` and `opensearch_control_plane` honor `AWS_ENDPOINT_URL`. `bedrock_runtime()` always talks to real AWS (no LocalStack endpoint). OpenSearch data plane is `opensearch-py` via `DescribeDomain` (`src/aws_clients.opensearch_endpoint`).
- **Same embedding model for ingest and query.** `RagPipeline.ask` must use `build_embedding_provider` with the same settings as ingest. Index mapping `embedding.dimension` must match `Settings.embedding_dim`; `VectorStore.ensure_index` already rejects mismatches.
- **k-NN mapping stays simple.** Create `knn_vector` with dimension only — extra HNSW/engine params break some LocalStack versions.
- **Ingest rebuilds the index.** `index_chunks` calls `reset_index` then bulk-indexes `{text, source, chunk_id, offset, embedding}`. Supported suffixes: `.txt`, `.md`, `.pdf`.
- **LLM does not search.** Retrieval is OpenSearch k-NN (`TOP_K`). `src/rag.py` answers only from numbered snippets and cites filenames; empty retrieval must say it does not know.
- **Providers are ABC + factory.** `EmbeddingProvider.embed_texts` / `embed_query`; `LlmProvider.generate(system, user)`. Extend by implementing the ABC and branching in `build_*_provider`.
- **LocalStack OpenSearch** uses `OPENSEARCH_ENDPOINT_STRATEGY=path` in compose. Bootstrap with AWS CLI v2 against `AWS_ENDPOINT_URL` (dummy `test`/`test` keys locally).
