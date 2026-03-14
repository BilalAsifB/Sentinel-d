"""Historical DB read client — two-stage lookup.

Stage 1: Exact CVE match via Cosmos DB partition key lookup.
Stage 2: In-memory cosine similarity on embeddings (numpy, threshold 0.88).

NOTE: Azure AI Search was removed for cost — cosine similarity is computed
in-memory against all records fetched from Cosmos DB.
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
from azure.cosmos.aio import CosmosClient
from azure.identity.aio import DefaultAzureCredential

from historical_db.embedding import EmbeddingService

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.88


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors.

    Args:
        a: First embedding vector.
        b: Second embedding vector.

    Returns:
        Cosine similarity in [-1, 1].
    """
    va = np.array(a, dtype=np.float64)
    vb = np.array(b, dtype=np.float64)
    norm_a = np.linalg.norm(va)
    norm_b = np.linalg.norm(vb)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(va, vb) / (norm_a * norm_b))


class HistoricalDBReadClient:
    """Two-stage historical DB lookup client.

    Stage 1: Exact CVE ID match in Cosmos DB.
    Stage 2: In-memory cosine similarity against all records' embeddings.
    """

    def __init__(
        self,
        embedding_service: Optional[EmbeddingService] = None,
        cosmos_endpoint: Optional[str] = None,
        database_name: str = "",
        container_name: str = "",
    ) -> None:
        """Initialize HistoricalDBReadClient.

        Args:
            embedding_service: Service for generating query embeddings.
            cosmos_endpoint: Cosmos DB endpoint (or from env COSMOS_ENDPOINT).
            database_name: Cosmos DB database name (or from env COSMOS_DB_NAME).
            container_name: Container name (or from env COSMOS_CONTAINER_NAME).
        """
        self.embedding_service = embedding_service or EmbeddingService()
        self.cosmos_endpoint = cosmos_endpoint or os.environ.get("COSMOS_ENDPOINT", "")
        self.database_name = database_name or os.environ.get("COSMOS_DB_NAME", "sentinel")
        self.container_name = container_name or os.environ.get(
            "COSMOS_CONTAINER_NAME", "cve_patches"
        )
        self._client: Optional[CosmosClient] = None
        self._credential: Optional[DefaultAzureCredential] = None

    async def _get_container(self):
        """Get Cosmos DB container client, initializing if needed."""
        if self._client is None:
            self._credential = DefaultAzureCredential()
            self._client = CosmosClient(self.cosmos_endpoint, credential=self._credential)
        db = self._client.get_database_client(self.database_name)
        return db.get_container_client(self.container_name)

    async def close(self) -> None:
        """Close underlying clients."""
        if self._client:
            await self._client.close()
        if self._credential:
            await self._credential.close()

    async def lookup(
        self,
        event_id: str,
        cve_id: str,
        description: str,
        affected_package: str,
    ) -> Dict[str, Any]:
        """Perform two-stage historical lookup.

        Args:
            event_id: Unique event identifier.
            cve_id: CVE identifier.
            description: CVE description text for embedding.
            affected_package: Affected package name.

        Returns:
            historical_match.json conforming dictionary.
        """
        logger.info("Historical lookup for %s (CVE %s)", event_id, cve_id)

        # Stage 1: Exact match
        exact = await self._exact_lookup(cve_id)
        if exact:
            logger.info("EXACT_MATCH for %s", cve_id)
            return self._build_response(event_id, cve_id, "EXACT_MATCH", exact)

        # Stage 2: In-memory cosine similarity
        logger.debug("No exact match — computing semantic similarity")
        try:
            combined_text = f"{description} {affected_package}"
            query_embedding = await self.embedding_service.embed_text(combined_text)
            best_match = await self._semantic_lookup(query_embedding)
            if best_match:
                logger.info("SEMANTIC_MATCH for %s (score=%.3f)", cve_id, best_match["score"])
                return self._build_response(
                    event_id, cve_id, "SEMANTIC_MATCH", best_match["record"],
                    match_confidence=best_match["score"],
                )
        except Exception as exc:
            logger.warning("Semantic search failed: %s", exc)

        logger.info("NO_MATCH for %s", cve_id)
        return self._build_no_match(event_id, cve_id)

    async def _exact_lookup(self, cve_id: str) -> Optional[Dict[str, Any]]:
        """Stage 1: Query Cosmos DB for exact CVE match with SUCCESS outcome."""
        try:
            container = await self._get_container()
            query = (
                "SELECT * FROM c WHERE c.cve_id = @cve_id "
                "AND c.patch_outcome = @outcome"
            )
            items = []
            async for item in container.query_items(
                query=query,
                parameters=[
                    {"name": "@cve_id", "value": cve_id},
                    {"name": "@outcome", "value": "SUCCESS"},
                ],
                max_item_count=1,
            ):
                items.append(item)
                break
            return items[0] if items else None
        except Exception as exc:
            logger.error("Cosmos DB exact lookup failed: %s", exc)
            return None

    async def _semantic_lookup(
        self, query_embedding: List[float]
    ) -> Optional[Dict[str, Any]]:
        """Stage 2: In-memory cosine similarity against all records."""
        try:
            container = await self._get_container()
            query = (
                "SELECT c.id, c.cve_id, c.cve_description_embedding, "
                "c.patch_outcome, c.patch_diff, c.fix_strategy_used, "
                "c.solutions_tried, c.language, c.framework "
                "FROM c WHERE ARRAY_LENGTH(c.cve_description_embedding) > 0"
            )
            best_score = 0.0
            best_record: Optional[Dict[str, Any]] = None

            async for record in container.query_items(
                query=query, enable_cross_partition_query=True
            ):
                embedding = record.get("cve_description_embedding", [])
                if not embedding:
                    continue
                score = cosine_similarity(query_embedding, embedding)
                if score >= SIMILARITY_THRESHOLD and score > best_score:
                    best_score = score
                    best_record = record

            if best_record:
                return {"record": best_record, "score": best_score}
            return None

        except Exception as exc:
            logger.error("Semantic lookup failed: %s", exc)
            return None

    @staticmethod
    def _build_response(
        event_id: str,
        cve_id: str,
        status: str,
        record: Dict[str, Any],
        match_confidence: float = 1.0,
    ) -> Dict[str, Any]:
        """Build historical_match.json response."""
        all_solutions = record.get("solutions_tried", [])
        failed = [
            {
                "strategy": s.get("strategy", ""),
                "outcome": s.get("outcome", ""),
                "failure_reason": s.get("failure_reason", ""),
            }
            for s in all_solutions
            if s.get("outcome") == "FAILED"
        ]

        replay_eligible = (
            record.get("patch_outcome") == "SUCCESS"
            and status in ("EXACT_MATCH", "SEMANTIC_MATCH")
        )

        return {
            "event_id": event_id,
            "lookup_status": status,
            "match_confidence": match_confidence,
            "matched_cve_id": record.get("cve_id", cve_id),
            "matched_record_id": record.get("id", ""),
            "recommended_strategy": record.get("fix_strategy_used", ""),
            "historical_patch_diff": record.get("patch_diff", ""),
            "previous_outcome": record.get("patch_outcome", ""),
            "solutions_tried_previously": failed,
            "replay_eligible": replay_eligible,
            "replay_ineligible_reason": (
                None if replay_eligible
                else f"Previous outcome: {record.get('patch_outcome')}"
            ),
            "timestamp": datetime.utcnow().isoformat(),
        }

    @staticmethod
    def _build_no_match(event_id: str, cve_id: str) -> Dict[str, Any]:
        """Build NO_MATCH response."""
        return {
            "event_id": event_id,
            "lookup_status": "NO_MATCH",
            "match_confidence": 0.0,
            "matched_cve_id": "",
            "matched_record_id": "",
            "recommended_strategy": "",
            "historical_patch_diff": "",
            "previous_outcome": "",
            "solutions_tried_previously": [],
            "replay_eligible": False,
            "replay_ineligible_reason": "No historical record found",
            "timestamp": datetime.utcnow().isoformat(),
        }
