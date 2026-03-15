"""NLP Pipeline orchestrator — v3.0.

Execution order (spec-mandated):
    1. Historical DB lookup (BEFORE API calls)
    2. NVD + Stack Overflow fetchers in PARALLEL (asyncio.gather)
    3. spaCy NER entity extraction
    4. DistilBERT intent classification
    5. Assemble structured_context.json with all v3.0 fields
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fetchers.nvd_fetcher import NVDFetcher
from fetchers.stackoverflow_fetcher import StackOverflowFetcher
from ner.model import EntityExtractor
from classifier.model import IntentClassifier
from historical_db.read_client import HistoricalDBReadClient
from historical_db.embedding import EmbeddingService

logger = logging.getLogger(__name__)

PIPELINE_VERSION = "3.0.0"

# Markers indicating auth/crypto-sensitive code paths.
# If file_path or package contains any of these, touches_auth_crypto is True,
# forcing the Safety Governor to a LOW tier minimum regardless of confidence.
_AUTH_CRYPTO_MARKERS = [
    "auth", "oauth", "jwt", "token", "secret", "password", "credential",
    "crypto", "cipher", "encrypt", "decrypt", "hash", "ssl", "tls", "cert",
    "saml", "oidc", "hmac", "rsa", "aes", "bcrypt", "pbkdf", "keystore",
    "signing", "signature", "private_key", "public_key",
]


def _detect_auth_crypto(file_path: str, package: str) -> bool:
    """Return True if file_path or package touches auth or crypto code.

    Used by the Safety Governor override logic: if True, the tier is forced
    to LOW minimum regardless of composite confidence score.

    Args:
        file_path: Path to the affected file from the webhook payload.
        package: Affected package name.

    Returns:
        True if auth or crypto markers are found in either argument.
    """
    combined = f"{file_path} {package}".lower()
    return any(marker in combined for marker in _AUTH_CRYPTO_MARKERS)


class NLPPipeline:
    """Orchestrates the full NLP context pipeline.

    Produces a structured_context.json dictionary with all v3.0 fields
    including historical_match_status, historical_patch_available,
    solutions_to_avoid, historical_record_id, and touches_auth_crypto.
    """

    def __init__(
        self,
        nvd_api_key: Optional[str] = None,
        so_api_key: Optional[str] = None,
        spacy_model_path: str = "",
        distilbert_model_path: str = "",
        historical_db_client: Optional[HistoricalDBReadClient] = None,
    ) -> None:
        """Initialize all pipeline components.

        Args:
            nvd_api_key: Optional NVD API key.
            so_api_key: Optional Stack Exchange API key.
            spacy_model_path: Path to fine-tuned spaCy model.
            distilbert_model_path: Path to fine-tuned DistilBERT model.
            historical_db_client: Pre-configured historical DB read client.
        """
        self.nvd_fetcher = NVDFetcher(api_key=nvd_api_key)
        self.so_fetcher = StackOverflowFetcher(api_key=so_api_key)
        self.entity_extractor = EntityExtractor(model_path=spacy_model_path)
        self.intent_classifier = IntentClassifier(model_path=distilbert_model_path)
        self.historical_db = historical_db_client or HistoricalDBReadClient()
        logger.info("NLPPipeline v%s initialized", PIPELINE_VERSION)

    async def process(self, webhook_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process webhook payload into structured context.

        Pipeline order:
            1. Historical DB lookup (BEFORE API calls — spec requirement)
            2. NVD + Stack Overflow fetch in parallel (asyncio.gather)
            3. spaCy NER extraction
            4. DistilBERT classification
            5. Assemble structured_context

        Args:
            webhook_payload: Dictionary with event_id, cve_id, severity,
                affected_package, current_version, fix_version_range,
                file_path, line_range, repo, timestamp.

        Returns:
            structured_context.json dictionary with all required fields.
        """
        event_id: str = webhook_payload.get("event_id", "")
        cve_id: str = webhook_payload.get("cve_id", "")
        affected_package: str = webhook_payload.get("affected_package", "")
        file_path: str = webhook_payload.get("file_path", "")

        logger.info("Processing event %s (CVE %s)", event_id, cve_id)

        # Step 1: Historical DB lookup FIRST (spec mandates before API calls).
        # Use cve_id + package + fix range as description to improve embedding
        # quality for Stage 2 semantic similarity — NVD text is not yet available.
        description_for_lookup = " ".join(filter(None, [
            cve_id,
            affected_package,
            webhook_payload.get("fix_version_range", ""),
            webhook_payload.get("current_version", ""),
        ]))
        historical_match = await self.historical_db.lookup(
            event_id=event_id,
            cve_id=cve_id,
            description=description_for_lookup,
            affected_package=affected_package,
        )

        # Step 2: NVD + SO fetchers in PARALLEL (asyncio.gather required by spec).
        nvd_result, so_result = await asyncio.gather(
            self.nvd_fetcher.fetch(cve_id),
            self.so_fetcher.fetch(affected_package),
            return_exceptions=True,
        )

        if isinstance(nvd_result, Exception):
            logger.error("NVD fetch failed: %s", nvd_result)
            nvd_result = {}
        if isinstance(so_result, Exception):
            logger.error("SO fetch failed: %s", so_result)
            so_result = {}

        nvd_text = self._extract_nvd_text(nvd_result)
        so_text = self._extract_so_text(so_result)

        # Step 3: spaCy NER
        breaking_changes, migration_steps = self.entity_extractor.extract(nvd_text)

        # Step 4: DistilBERT classification (returns label, confidence, log_prob)
        intent_label, intent_confidence, intent_log_prob = (
            self.intent_classifier.classify(so_text)
        )

        # Step 5: Assemble structured_context with ALL required fields.
        # solutions_to_avoid: failed strategies from historical DB, injected into
        # Patch Generator Section 4 to prevent repeating known-bad approaches.
        solutions_to_avoid = [
            {
                "strategy": s.get("strategy", ""),
                "failure_reason": s.get("failure_reason", ""),
            }
            for s in historical_match.get("solutions_tried_previously", [])
        ]

        structured_context: Dict[str, Any] = {
            # ── Identity fields (required by Patch Generator and Safety Governor)
            "event_id": event_id,
            "cve_id": cve_id,
            "severity": webhook_payload.get("severity", ""),
            "affected_package": affected_package,
            "current_version": webhook_payload.get("current_version", ""),
            "fix_version_range": webhook_payload.get("fix_version_range", ""),
            "file_path": file_path,
            "line_range": webhook_payload.get("line_range", [0, 0]),
            "repo": webhook_payload.get("repo", ""),

            # ── Safety Governor override flag
            # If True: forces LOW tier minimum regardless of composite score.
            "touches_auth_crypto": _detect_auth_crypto(file_path, affected_package),

            # ── NLP output fields
            "fix_strategy": self._determine_fix_strategy(intent_label),
            "breaking_changes": breaking_changes,
            "community_intent_class": intent_label,
            "intent_confidence": intent_confidence,
            "intent_log_prob": intent_log_prob,
            "nvd_context": {
                "cvss_score": self._extract_cvss(nvd_result),
                "description": nvd_text[:500] if nvd_text else "",
                "attack_vector": "NETWORK",
                "auth_required": False,
            },
            "migration_steps": migration_steps,

            # ── v3.0 Historical DB fields
            "historical_match_status": historical_match.get(
                "lookup_status", "NO_MATCH"
            ),
            "historical_patch_available": historical_match.get(
                "replay_eligible", False
            ),
            "historical_record_id": historical_match.get(
                "matched_record_id", None
            ) or None,
            "solutions_to_avoid": solutions_to_avoid,

            # ── Metadata
            "pipeline_version": PIPELINE_VERSION,
            "timestamp": datetime.utcnow().isoformat(),
        }

        logger.info(
            "Context assembled for %s — historical=%s, intent=%s, "
            "touches_auth_crypto=%s",
            event_id,
            structured_context["historical_match_status"],
            intent_label,
            structured_context["touches_auth_crypto"],
        )
        return structured_context

    async def close(self) -> None:
        """Close underlying clients."""
        await self.historical_db.close()

    # ── helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _extract_nvd_text(nvd_data: Dict[str, Any]) -> str:
        """Extract descriptive text from NVD 2.0 response."""
        try:
            vulns = nvd_data.get("vulnerabilities", [])
            if vulns:
                descs = vulns[0].get("cve", {}).get("descriptions", [])
                for d in descs:
                    if d.get("value"):
                        return d["value"]
        except (KeyError, IndexError, TypeError):
            pass
        return ""

    @staticmethod
    def _extract_so_text(so_data: Dict[str, Any]) -> str:
        """Extract concatenated text from Stack Overflow items."""
        if not so_data or "items" not in so_data:
            return ""
        parts: List[str] = []
        for item in so_data.get("items", [])[:5]:
            parts.append(item.get("title", ""))
            parts.append(item.get("body", ""))
        return " ".join(parts)

    @staticmethod
    def _extract_cvss(nvd_data: Dict[str, Any]) -> float:
        """Extract CVSS base score from NVD data."""
        try:
            vulns = nvd_data.get("vulnerabilities", [])
            if vulns:
                metrics = vulns[0].get("cve", {}).get("metrics", {})
                for key in ("cvssMetricV31", "cvssMetricV30"):
                    if key in metrics and metrics[key]:
                        return float(
                            metrics[key][0]
                            .get("cvssData", {})
                            .get("baseScore", 0.0)
                        )
        except (KeyError, IndexError, TypeError, ValueError):
            pass
        return 0.0

    @staticmethod
    def _determine_fix_strategy(intent_label: str) -> str:
        """Map intent classification to fix strategy."""
        mapping = {
            "VERSION_PIN": "PIN_COMPATIBLE_VERSION",
            "API_MIGRATION": "MIGRATE_TO_NEW_API",
            "MONKEY_PATCH": "APPLY_TEMPORARY_PATCH",
            "FULL_REFACTOR": "FULL_REFACTOR",
        }
        return mapping.get(intent_label, "EVALUATE_OPTIONS")