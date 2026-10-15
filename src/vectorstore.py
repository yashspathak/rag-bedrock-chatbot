"""OpenSearch k-NN index: create, bulk load, and similarity search."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

import boto3
from opensearchpy import AWSV4SignerAuth, OpenSearch, RequestsHttpConnection, helpers

from src.aws_clients import opensearch_endpoint
from src.config import Settings


@dataclass(frozen=True)
class RetrievedChunk:
    text: str
    source: str
    chunk_id: str
    score: float


class VectorStore:
    def __init__(self, settings: Settings, client: OpenSearch | None = None) -> None:
        self._settings = settings
        self._client = client or build_opensearch_client(settings)

    def reset_index(self, embedding_dim: int) -> None:
        index = self._settings.opensearch_index
        if self._client.indices.exists(index=index):
            self._client.indices.delete(index=index)
        self.ensure_index(embedding_dim)

    def ensure_index(self, embedding_dim: int) -> None:
        index = self._settings.opensearch_index
        if self._client.indices.exists(index=index):
            mapping = self._client.indices.get_mapping(index=index)
            properties = mapping[index]["mappings"]["properties"]
            existing_dim = properties["embedding"]["dimension"]
            if existing_dim != embedding_dim:
                raise ValueError(
                    f"Index '{index}' was created with dim {existing_dim}, "
                    f"but the embedding provider uses {embedding_dim}. "
                    "Delete the index or re-ingest after changing models."
                )
            return
        body = {
            "settings": {"index": {"knn": True}},
            "mappings": {
                "properties": {
                    "text": {"type": "text"},
                    "source": {"type": "keyword"},
                    "chunk_id": {"type": "keyword"},
                    "offset": {"type": "integer"},
                    "embedding": {"type": "knn_vector", "dimension": embedding_dim},
                }
            },
        }
        self._client.indices.create(index=index, body=body)

    def replace_documents(self, documents: list[dict]) -> int:
        index = self._settings.opensearch_index
        helpers.bulk(
            self._client,
            (
                {
                    "_op_type": "index",
                    "_index": index,
                    "_id": doc["chunk_id"],
                    "_source": doc,
                }
                for doc in documents
            ),
            refresh=True,
        )
        return len(documents)

    def knn_search(self, vector: list[float], k: int) -> list[RetrievedChunk]:
        query = {"size": k, "query": {"knn": {"embedding": {"vector": vector, "k": k}}}}
        response = self._client.search(index=self._settings.opensearch_index, body=query)
        hits = []
        for hit in response.get("hits", {}).get("hits", []):
            source = hit["_source"]
            hits.append(
                RetrievedChunk(
                    text=source["text"],
                    source=source["source"],
                    chunk_id=source["chunk_id"],
                    score=float(hit.get("_score") or 0.0),
                )
            )
        return hits


def build_opensearch_client(settings: Settings) -> OpenSearch:
    url = opensearch_endpoint(settings)
    parsed = urlparse(url)
    use_ssl = parsed.scheme == "https"
    kwargs: dict = {
        "hosts": [url],
        "use_ssl": use_ssl,
        "verify_certs": not settings.uses_localstack,
        "ssl_show_warn": not settings.uses_localstack,
        "connection_class": RequestsHttpConnection,
        "timeout": 30,
    }
    if not settings.uses_localstack:
        session = boto3.Session(
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region,
        )
        credentials = session.get_credentials()
        kwargs["http_auth"] = AWSV4SignerAuth(credentials, settings.aws_region, "es")
    return OpenSearch(**kwargs)
