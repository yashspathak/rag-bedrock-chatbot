"""Environment-driven settings for local LocalStack and AWS Bedrock paths."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def _optional(name: str) -> str | None:
    value = os.getenv(name, "").strip()
    return value or None


def _int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


@dataclass(frozen=True)
class Settings:
    aws_endpoint_url: str | None
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_region: str
    s3_bucket: str
    opensearch_domain: str
    opensearch_index: str
    embedding_provider: str
    local_embedding_model: str
    local_embedding_dim: int
    bedrock_embedding_model: str
    bedrock_embedding_dim: int
    llm_provider: str
    ollama_base_url: str
    ollama_model: str
    bedrock_llm_model: str
    chunk_size: int
    chunk_overlap: int
    top_k: int

    @property
    def embedding_dim(self) -> int:
        if self.embedding_provider == "bedrock":
            return self.bedrock_embedding_dim
        return self.local_embedding_dim

    @property
    def uses_localstack(self) -> bool:
        return bool(self.aws_endpoint_url)


def load_settings() -> Settings:
    embedding_provider = os.getenv("EMBEDDING_PROVIDER", "local").strip().lower()
    llm_provider = os.getenv("LLM_PROVIDER", "ollama").strip().lower()
    if embedding_provider not in {"local", "bedrock"}:
        raise ValueError("EMBEDDING_PROVIDER must be 'local' or 'bedrock'")
    if llm_provider not in {"ollama", "bedrock"}:
        raise ValueError("LLM_PROVIDER must be 'ollama' or 'bedrock'")

    return Settings(
        aws_endpoint_url=_optional("AWS_ENDPOINT_URL"),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", "test"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", "test"),
        aws_region=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
        s3_bucket=os.getenv("S3_BUCKET", "rag-docs"),
        opensearch_domain=os.getenv("OPENSEARCH_DOMAIN", "rag-vectors"),
        opensearch_index=os.getenv("OPENSEARCH_INDEX", "rag-chunks"),
        embedding_provider=embedding_provider,
        local_embedding_model=os.getenv(
            "LOCAL_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
        ),
        local_embedding_dim=_int("LOCAL_EMBEDDING_DIM", 384),
        bedrock_embedding_model=os.getenv(
            "BEDROCK_EMBEDDING_MODEL", "amazon.titan-embed-text-v2:0"
        ),
        bedrock_embedding_dim=_int("BEDROCK_EMBEDDING_DIM", 1024),
        llm_provider=llm_provider,
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/"),
        ollama_model=os.getenv("OLLAMA_MODEL", "llama3.2"),
        bedrock_llm_model=os.getenv(
            "BEDROCK_LLM_MODEL", "anthropic.claude-3-5-sonnet-20241022-v2:0"
        ),
        chunk_size=_int("CHUNK_SIZE", 800),
        chunk_overlap=_int("CHUNK_OVERLAP", 120),
        top_k=_int("TOP_K", 4),
    )
