"""Foundry client — Python wrapper for Microsoft Foundry (Azure OpenAI) API.

Spec-required location: /patch-generator/foundry_client.py
Canonical implementation: /agents/patch_generator/agent.py
"""

import asyncio
import logging
import os
from typing import Any, Dict, Optional

import aiohttp
from azure.identity import DefaultAzureCredential

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
BASE_DELAY_S = 2.0


class FoundryClient:
    """Microsoft Foundry (Azure OpenAI) API client with retry logic.

    Uses DefaultAzureCredential for authentication. Falls back to API key
    from AZURE_OPENAI_API_KEY environment variable.
    """

    def __init__(self) -> None:
        """Initialize Foundry client from environment variables."""
        self.endpoint = os.environ.get(
            "FOUNDRY_ENDPOINT",
            os.environ.get("AZURE_OPENAI_ENDPOINT", ""),
        ).rstrip("/")
        self.api_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
        self.api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")
        self.deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT_ID", "gpt-4o")

        if not self.endpoint:
            raise ValueError("FOUNDRY_ENDPOINT or AZURE_OPENAI_ENDPOINT required")
        if not self.api_key:
            try:
                cred = DefaultAzureCredential()
                token = cred.get_token("https://cognitiveservices.azure.com/.default")
                self._bearer_token = token.token
                self.api_key = None
                logger.info("Using DefaultAzureCredential for Foundry")
            except Exception:
                raise ValueError("AZURE_OPENAI_API_KEY required (DefaultAzureCredential failed)")
        else:
            self._bearer_token = None

        logger.info("FoundryClient initialized (deployment=%s)", self.deployment)

    async def complete(self, prompt: str, max_tokens: int = 4096) -> Dict[str, Any]:
        """Call Foundry chat completion with retry.

        Args:
            prompt: Complete prompt string.
            max_tokens: Maximum tokens to generate.

        Returns:
            Dictionary with 'text' (response content) and 'log_probs' (if available).

        Raises:
            RuntimeError: On API failure after retries.
        """
        url = (
            f"{self.endpoint}/openai/deployments/{self.deployment}"
            f"/chat/completions?api-version={self.api_version}"
        )

        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["api-key"] = self.api_key
        elif self._bearer_token:
            headers["Authorization"] = f"Bearer {self._bearer_token}"

        payload = {
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.2,
            "top_p": 0.95,
        }

        last_error: Optional[Exception] = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        url, headers=headers, json=payload,
                        timeout=aiohttp.ClientTimeout(total=60),
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            text = data["choices"][0]["message"]["content"]
                            logger.info("Foundry response (%d chars)", len(text))
                            return {"text": text, "log_probs": None}

                        if resp.status == 429:
                            delay = BASE_DELAY_S * (2 ** (attempt - 1))
                            logger.warning(
                                "Foundry 429 — retry %d/%d in %.1fs",
                                attempt, MAX_RETRIES, delay,
                            )
                            await asyncio.sleep(delay)
                            continue

                        error = await resp.text()
                        raise RuntimeError(f"Foundry {resp.status}: {error}")

            except asyncio.TimeoutError:
                last_error = RuntimeError("Foundry API timeout")
            except aiohttp.ClientError as exc:
                last_error = RuntimeError(f"Foundry client error: {exc}")
            except RuntimeError:
                raise
            except Exception as exc:
                last_error = RuntimeError(f"Foundry error: {exc}")
                break

            if attempt < MAX_RETRIES:
                delay = BASE_DELAY_S * (2 ** (attempt - 1))
                await asyncio.sleep(delay)

        raise last_error or RuntimeError("Foundry API call failed")
