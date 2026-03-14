"""Asynchronous NVD 2.0 API fetcher with caching and rate-limit handling."""

import asyncio
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import aiohttp

logger = logging.getLogger(__name__)


class NVDFetcher:
    """Fetches CVE data from NIST NVD 2.0 API.

    Features:
        - In-memory response caching (24-hour TTL)
        - Exponential backoff on 429 rate-limit responses (max 3 retries)
        - Structured error handling for all HTTP/network failures
    """

    BASE_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"
    CACHE_DURATION = timedelta(hours=24)
    MAX_RETRIES = 3
    BASE_DELAY_S = 2.0

    def __init__(self, api_key: Optional[str] = None) -> None:
        """Initialize NVDFetcher.

        Args:
            api_key: Optional NVD API key for higher rate limits.
        """
        self.api_key = api_key
        self._cache: Dict[str, tuple] = {}

    async def fetch(self, cve_id: str) -> Dict[str, Any]:
        """Fetch CVE data from NVD API with caching and retry.

        Args:
            cve_id: CVE identifier (e.g., CVE-2024-1234).

        Returns:
            Dictionary containing CVE details from NVD, or empty dict on failure.
        """
        cache_key = hashlib.md5(cve_id.encode()).hexdigest()

        if cache_key in self._cache:
            cached_data, timestamp = self._cache[cache_key]
            if datetime.utcnow() - timestamp < self.CACHE_DURATION:
                logger.debug("Cache hit for CVE %s", cve_id)
                return cached_data

        headers: Dict[str, str] = {}
        params: Dict[str, str] = {"cveId": cve_id}
        if self.api_key:
            headers["apiKey"] = self.api_key

        last_error: Optional[Exception] = None
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        self.BASE_URL,
                        params=params,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=15),
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            self._cache[cache_key] = (data, datetime.utcnow())
                            logger.info("Fetched NVD data for %s", cve_id)
                            return data

                        if response.status == 429:
                            delay = self.BASE_DELAY_S * (2 ** (attempt - 1))
                            logger.warning(
                                "NVD 429 rate limit for %s — retry %d/%d in %.1fs",
                                cve_id, attempt, self.MAX_RETRIES, delay,
                            )
                            await asyncio.sleep(delay)
                            continue

                        logger.warning("NVD API %d for %s", response.status, cve_id)
                        return {}

            except asyncio.TimeoutError:
                last_error = TimeoutError(f"NVD timeout for {cve_id}")
                logger.error("Timeout fetching NVD data for %s (attempt %d)", cve_id, attempt)
            except aiohttp.ClientError as exc:
                last_error = exc
                logger.error("Client error for %s: %s", cve_id, exc)
            except Exception as exc:
                last_error = exc
                logger.error("Unexpected error for %s: %s", cve_id, exc)
                break

            if attempt < self.MAX_RETRIES:
                delay = self.BASE_DELAY_S * (2 ** (attempt - 1))
                await asyncio.sleep(delay)

        logger.error("All %d NVD retries exhausted for %s", self.MAX_RETRIES, cve_id)
        return {}
