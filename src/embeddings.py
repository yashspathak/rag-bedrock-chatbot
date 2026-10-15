"""Embedding providers: local MiniLM or Amazon Titan on Bedrock."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import Sequence

from src.aws_clients import bedrock_runtime
from src.config import Settings


class EmbeddingProvider(ABC):
    dim: int

    @abstractmethod
    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        raise NotImplementedError

    def embed_query(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]


class LocalSentenceTransformer(EmbeddingProvider):
    def __init__(self, model_name: str, dim: int) -> None:
        self._model_name = model_name
        self.dim = dim

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        model = _sentence_model(self._model_name)
        vectors = model.encode(list(texts), normalize_embeddings=True)
        embeddings = [vector.tolist() for vector in vectors]
        self._assert_dim(embeddings)
        return embeddings

    def _assert_dim(self, embeddings: list[list[float]]) -> None:
        if embeddings and len(embeddings[0]) != self.dim:
            raise ValueError(
                f"Local embedding dim is {len(embeddings[0])}, expected {self.dim}. "
                "Update LOCAL_EMBEDDING_DIM and re-ingest."
            )


class BedrockTitan(EmbeddingProvider):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = bedrock_runtime(settings)
        self.dim = settings.bedrock_embedding_dim

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        body = {"inputText": text, "dimensions": self.dim, "normalize": True}
        response = self._client.invoke_model(
            modelId=self._settings.bedrock_embedding_model,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(body),
        )
        payload = json.loads(response["body"].read())
        embedding = payload.get("embedding")
        if not embedding:
            raise RuntimeError("Bedrock Titan response did not include an embedding")
        if len(embedding) != self.dim:
            raise ValueError(
                f"Bedrock embedding dim is {len(embedding)}, expected {self.dim}. "
                "Update BEDROCK_EMBEDDING_DIM and re-ingest."
            )
        return embedding


@lru_cache(maxsize=1)
def _sentence_model(model_name: str):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


def build_embedding_provider(settings: Settings) -> EmbeddingProvider:
    if settings.embedding_provider == "bedrock":
        return BedrockTitan(settings)
    return LocalSentenceTransformer(settings.local_embedding_model, settings.local_embedding_dim)
