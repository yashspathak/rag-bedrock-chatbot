"""boto3 clients that target LocalStack when AWS_ENDPOINT_URL is set."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse, urlunparse

import boto3
from botocore.config import Config as BotoConfig

from src.config import Settings

_BOTO_CONFIG = BotoConfig(retries={"max_attempts": 8, "mode": "standard"})


def _client_kwargs(settings: Settings) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "region_name": settings.aws_region,
        "aws_access_key_id": settings.aws_access_key_id,
        "aws_secret_access_key": settings.aws_secret_access_key,
        "config": _BOTO_CONFIG,
    }
    if settings.aws_endpoint_url:
        kwargs["endpoint_url"] = settings.aws_endpoint_url
    return kwargs


def s3_client(settings: Settings):
    return boto3.client("s3", **_client_kwargs(settings))


def opensearch_control_plane(settings: Settings):
    return boto3.client("opensearch", **_client_kwargs(settings))


def bedrock_runtime(settings: Settings):
    """Bedrock data plane. Do not send this client to LocalStack Community."""
    return boto3.client(
        "bedrock-runtime",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        config=_BOTO_CONFIG,
    )


def opensearch_endpoint(settings: Settings) -> str:
    """Resolve the data-plane URL from DescribeDomain (LocalStack or AWS)."""
    client = opensearch_control_plane(settings)
    status = client.describe_domain(DomainName=settings.opensearch_domain)["DomainStatus"]
    endpoint = status.get("Endpoint") or (status.get("Endpoints") or {}).get("vpc")
    if not endpoint:
        raise RuntimeError(
            f"OpenSearch domain '{settings.opensearch_domain}' has no endpoint yet. "
            "Run scripts/bootstrap_local.sh and wait until the domain is active."
        )

    scheme = "http" if settings.uses_localstack else "https"
    raw = endpoint if endpoint.startswith(("http://", "https://")) else f"{scheme}://{endpoint}"
    parsed = urlparse(raw)
    if settings.uses_localstack and parsed.port is None and parsed.hostname:
        local_port = _localstack_port(settings)
        parsed = parsed._replace(netloc=f"{parsed.hostname}:{local_port}")
    return urlunparse(parsed).rstrip("/")


def _localstack_port(settings: Settings) -> int:
    parsed = urlparse(settings.aws_endpoint_url or "http://localhost:4566")
    return parsed.port or 4566
