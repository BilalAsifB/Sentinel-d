"""Embedding generation using Azure OpenAI text-embedding-3-small.

Generates 1536-dimensional vectors for semantic similarity search.
Called once per event — not per-field.
"""

import asyncio
import logging
import os
from typing import List, Optional

import aiohttp

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Generates 1536-dim embeddings via Azure OpenAI text-embedding-3-small."""

    MODEL = "text-embedding-3-small"
    EMBEDDING_DIM = 1536
    API_VERSION = "2024-08-01-preview"
    MAX_RETRIES = 3
    BASE_DELAY_S = 1.0

    def __init__(
        self,
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> None:
        """Initialize EmbeddingService from parameters or env vars.

        Args:
            endpoint: Azure OpenAI endpoint URL.
            api_key: Azure OpenAI API key.
        """
        self.endpoint = (
            endpoint or os.environ.get("AZURE_OPENAI_ENDPOINT", "")
        ).rstrip("/")
        self.api_key = api_key or os.environ.get("AZURE_OPENAI_API_KEY", "")

        if not self.endpoint or not self.api_key:
            logger.warning(
                "AZURE_OPENAI_ENDPOINT / AZURE_OPENAI_API_KEY not set — "
                "embedding calls will fail"
            )

    async def embed_text(self, text: str) -> List[float]:
        """Generate embedding for input text.

        Called once per event with combined CVE description + package name.

        Args:
            text: Raw text string to embed.

        Returns:
            List of 1536 floats representing the embedding vector.

        Raises:
            RuntimeError: If API call fails after retries.
        """
        if not text or not text.strip():
            logger.warning("Empty text — returning zero vector")
            return [0.0] * self.EMBEDDING_DIM

        url = (
            f"{self.endpoint}/openai/deployments/{self.MODEL}/embeddings"
            f"?api-version={self.API_VERSION}"
        )
        headers = {"api-key": self.api_key, "Content-Type": "application/json"}
        payload = {"input": text.strip(), "model": self.MODEL}

        last_error: Optional[Exception] = None
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        url,
                        json=payload,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=15),
                    ) as resp:
                        if resp.status == 200:
                            result = await resp.json()
                            embedding = (
                                result.get("data", [{}])[0].get("embedding", [])
                            )
                            if len(embedding) == self.EMBEDDING_DIM:
                                logger.debug("Generated embedding (%d chars)", len(text))
                                return embedding
                            logger.error(
                                "Invalid dimension %d (expected %d)",
                                len(embedding), self.EMBEDDING_DIM,
                            )
                            return [0.0] * self.EMBEDDING_DIM

                        if resp.status == 429:
                            delay = self.BASE_DELAY_S * (2 ** (attempt - 1))
                            logger.warning(
                                "Embedding 429 — retry %d/%d in %.1fs",
                                attempt, self.MAX_RETRIES, delay,
                            )
                            await asyncio.sleep(delay)
                            continue

                        error_msg = await resp.text()
                        raise RuntimeError(
                            f"Embedding API {resp.status}: {error_msg}"
                        )

            except asyncio.TimeoutError:
                last_error = RuntimeError("Embedding API timeout")
            except aiohttp.ClientError as exc:
                last_error = RuntimeError(f"Embedding client error: {exc}")
            except RuntimeError:
                raise
            except Exception as exc:
                last_error = RuntimeError(f"Embedding failed: {exc}")
                break

            if attempt < self.MAX_RETRIES:
                delay = self.BASE_DELAY_S * (2 ** (attempt - 1))
                await asyncio.sleep(delay)

        raise last_error or RuntimeError("Embedding generation failed")
