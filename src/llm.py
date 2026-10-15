"""Chat completion providers: Ollama locally or Bedrock Converse on AWS."""

from __future__ import annotations

from abc import ABC, abstractmethod

import httpx

from src.aws_clients import bedrock_runtime
from src.config import Settings


class LlmProvider(ABC):
    @abstractmethod
    def generate(self, system: str, user: str) -> str:
        raise NotImplementedError


class OllamaChat(LlmProvider):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def generate(self, system: str, user: str) -> str:
        url = f"{self._settings.ollama_base_url}/api/chat"
        payload = {
            "model": self._settings.ollama_model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        try:
            response = httpx.post(url, json=payload, timeout=120.0)
            response.raise_for_status()
        except httpx.ConnectError as exc:
            raise RuntimeError(
                f"Ollama is not reachable at {self._settings.ollama_base_url}. "
                f"Install Ollama, run `ollama pull {self._settings.ollama_model}`, "
                "or start it with `docker compose --profile ollama up -d`."
            ) from exc
        data = response.json()
        message = (data.get("message") or {}).get("content")
        if not message:
            raise RuntimeError(f"Unexpected Ollama response: {data}")
        return message.strip()


class BedrockConverse(LlmProvider):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = bedrock_runtime(settings)

    def generate(self, system: str, user: str) -> str:
        response = self._client.converse(
            modelId=self._settings.bedrock_llm_model,
            system=[{"text": system}],
            messages=[{"role": "user", "content": [{"text": user}]}],
            inferenceConfig={"maxTokens": 512, "temperature": 0.2},
        )
        blocks = response["output"]["message"]["content"]
        text = "".join(block.get("text", "") for block in blocks)
        if not text.strip():
            raise RuntimeError("Bedrock Converse returned an empty message")
        return text.strip()


def build_llm_provider(settings: Settings) -> LlmProvider:
    if settings.llm_provider == "bedrock":
        return BedrockConverse(settings)
    return OllamaChat(settings)
