"""Upload documents to S3, chunk, embed, and index into OpenSearch."""

from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

from src.aws_clients import s3_client
from src.chunking import Chunk, split_text
from src.config import Settings, load_settings
from src.embeddings import EmbeddingProvider, build_embedding_provider
from src.vectorstore import VectorStore

SUPPORTED_SUFFIXES = {".txt", ".md", ".pdf"}


def parse_bytes(key: str, payload: bytes) -> str:
    suffix = Path(key).suffix.lower()
    if suffix == ".pdf":
        reader = PdfReader(BytesIO(payload))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n\n".join(pages)
    return payload.decode("utf-8")


def iter_local_files(root: Path) -> list[Path]:
    files = [
        path
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
    ]
    if not files:
        raise FileNotFoundError(f"No .txt, .md, or .pdf files found under {root}")
    return files


def upload_directory(settings: Settings, root: Path) -> list[str]:
    client = s3_client(settings)
    keys: list[str] = []
    for path in iter_local_files(root):
        key = path.relative_to(root).as_posix()
        client.upload_file(str(path), settings.s3_bucket, key)
        keys.append(key)
        print(f"Uploaded s3://{settings.s3_bucket}/{key}")
    return keys


def load_s3_documents(settings: Settings) -> list[tuple[str, str]]:
    client = s3_client(settings)
    paginator = client.get_paginator("list_objects_v2")
    documents: list[tuple[str, str]] = []
    for page in paginator.paginate(Bucket=settings.s3_bucket):
        for item in page.get("Contents", []):
            key = item["Key"]
            if Path(key).suffix.lower() not in SUPPORTED_SUFFIXES:
                continue
            payload = client.get_object(Bucket=settings.s3_bucket, Key=key)["Body"].read()
            text = parse_bytes(key, payload).strip()
            if text:
                documents.append((key, text))
    if not documents:
        raise RuntimeError(
            f"No readable documents in s3://{settings.s3_bucket}. "
            "Upload files first or pass --path to a local folder."
        )
    return documents


def chunk_documents(documents: list[tuple[str, str]], settings: Settings) -> list[Chunk]:
    chunks: list[Chunk] = []
    for source, text in documents:
        chunks.extend(
            split_text(
                text,
                source=source,
                chunk_size=settings.chunk_size,
                chunk_overlap=settings.chunk_overlap,
            )
        )
    return chunks


def index_chunks(
    chunks: list[Chunk],
    embeddings: EmbeddingProvider,
    store: VectorStore,
) -> int:
    store.reset_index(embeddings.dim)
    vectors = embeddings.embed_texts([chunk.text for chunk in chunks])
    documents = [
        {
            "chunk_id": chunk.chunk_id,
            "source": chunk.source,
            "text": chunk.text,
            "offset": chunk.offset,
            "embedding": vector,
        }
        for chunk, vector in zip(chunks, vectors, strict=True)
    ]
    return store.replace_documents(documents)


def run_ingest(settings: Settings, source_path: Path | None) -> None:
    if source_path is not None:
        upload_directory(settings, source_path)
    documents = load_s3_documents(settings)
    chunks = chunk_documents(documents, settings)
    print(f"Parsed {len(documents)} document(s) into {len(chunks)} chunk(s)")
    embeddings = build_embedding_provider(settings)
    store = VectorStore(settings)
    count = index_chunks(chunks, embeddings, store)
    print(f"Indexed {count} chunk(s) into '{settings.opensearch_index}'")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest documents into S3 and OpenSearch")
    parser.add_argument(
        "--path",
        type=Path,
        default=Path("data/sample"),
        help="Local folder to upload before indexing (default: data/sample)",
    )
    parser.add_argument(
        "--skip-upload",
        action="store_true",
        help="Index whatever is already in the S3 bucket",
    )
    args = parser.parse_args()
    settings = load_settings()
    source = None if args.skip_upload else args.path
    run_ingest(settings, source)


if __name__ == "__main__":
    main()
