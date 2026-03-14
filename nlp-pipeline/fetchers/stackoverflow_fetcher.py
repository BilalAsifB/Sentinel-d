"""Asynchronous Stack Overflow fetcher via Stack Exchange API v2.3."""

import asyncio
import logging
from typing import Any, Dict, Optional

import aiohttp

logger = logging.getLogger(__name__)


class StackOverflowFetcher:
    """Fetches top-voted answers from Stack Overflow for a given package.

    Returns the top 5 answers sorted by vote score, containing title and
    body text for downstream NLP processing.
    """

    BASE_URL = "https://api.stackexchange.com/2.3/search/advanced"
    SITE = "stackoverflow"
    MAX_RETRIES = 3
    BASE_DELAY_S = 1.0

    def __init__(self, api_key: Optional[str] = None) -> None:
        """Initialize StackOverflowFetcher.

        Args:
            api_key: Optional Stack Exchange API key for higher quota.
        """
        self.api_key = api_key

    async def fetch(self, affected_package: str, limit: int = 5) -> Dict[str, Any]:
        """Fetch top answers from Stack Overflow for a package.

        Args:
            affected_package: Package name to search for.
            limit: Maximum number of top-scored answers (default 5).

        Returns:
            Dictionary with 'items' list of answers sorted by score descending,
            or empty dict on failure.
        """
        params: Dict[str, Any] = {
            "q": f"{affected_package} vulnerability fix",
            "sort": "votes",
            "order": "desc",
            "site": self.SITE,
            "pagesize": limit,
            "filter": "withbody",
        }
        if self.api_key:
            params["key"] = self.api_key

        last_error: Optional[Exception] = None
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        self.BASE_URL,
                        params=params,
                        timeout=aiohttp.ClientTimeout(total=10),
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            items = data.get("items", [])
                            items_sorted = sorted(
                                items, key=lambda x: x.get("score", 0), reverse=True
                            )[:limit]
                            result = {"items": items_sorted}
                            logger.info(
                                "Fetched %d SO answers for '%s'",
                                len(items_sorted), affected_package,
                            )
                            return result

                        if response.status == 429:
                            delay = self.BASE_DELAY_S * (2 ** (attempt - 1))
                            logger.warning(
                                "SO 429 rate limit — retry %d/%d in %.1fs",
                                attempt, self.MAX_RETRIES, delay,
                            )
                            await asyncio.sleep(delay)
                            continue

                        logger.warning(
                            "Stack Exchange API %d for '%s'",
                            response.status, affected_package,
                        )
                        return {}

            except asyncio.TimeoutError:
                last_error = TimeoutError(f"SO timeout for {affected_package}")
                logger.error("Timeout for '%s' (attempt %d)", affected_package, attempt)
            except aiohttp.ClientError as exc:
                last_error = exc
                logger.error("Client error for '%s': %s", affected_package, exc)
            except Exception as exc:
                last_error = exc
                logger.error("Unexpected error for '%s': %s", affected_package, exc)
                break

            if attempt < self.MAX_RETRIES:
                delay = self.BASE_DELAY_S * (2 ** (attempt - 1))
                await asyncio.sleep(delay)

        logger.error("All %d SO retries exhausted for '%s'", self.MAX_RETRIES, affected_package)
        return {}
