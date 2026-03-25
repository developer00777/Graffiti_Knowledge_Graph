"""
Ollama Embedder — implements EmbedderClient using a local Ollama instance.

Calls the Ollama /api/embeddings endpoint with the embeddinggemma:latest model
(or any other model configured via OLLAMA_EMBED_MODEL env var).
"""
import logging
from typing import Iterable

import httpx

from graphiti_core.embedder import EmbedderClient

logger = logging.getLogger(__name__)


class OllamaEmbedder(EmbedderClient):
    """
    Embedder that calls a local Ollama instance for vector embeddings.

    Parameters
    ----------
    model : str
        Ollama model name (default: "embeddinggemma:latest").
        Must be pulled first: `ollama pull embeddinggemma`
    base_url : str
        Base URL for the Ollama server (default: "http://localhost:11434").
    timeout : float
        HTTP request timeout in seconds (default: 30.0).
    """

    def __init__(
        self,
        model: str = "embeddinggemma:latest",
        base_url: str = "http://localhost:11434",
        timeout: float = 30.0,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=timeout)
        logger.info("OllamaEmbedder initialized — model=%s base_url=%s", model, base_url)

    async def create(
        self,
        input_data: str | list[str] | Iterable[int] | Iterable[Iterable[int]],
    ) -> list[float]:
        """Generate an embedding for a single input string."""
        text = input_data if isinstance(input_data, str) else str(input_data)
        response = await self._client.post(
            f"{self.base_url}/api/embeddings",
            json={"model": self.model, "prompt": text},
        )
        response.raise_for_status()
        return response.json()["embedding"]

    async def create_batch(self, input_data_list: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of strings (sequential Ollama calls)."""
        results: list[list[float]] = []
        for text in input_data_list:
            results.append(await self.create(text))
        return results

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()
