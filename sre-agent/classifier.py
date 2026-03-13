"""Three-way classifier for SRE Agent telemetry results.

Produces a ``telemetry_classification`` conforming to the shared schema.
"""

from datetime import datetime, timezone
from typing import Any, Optional


def classify(
    telemetry_result: dict[str, Any],
    event: dict[str, Any],
    kql_query: str,
    existing_deferral: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Classify a telemetry result as ACTIVE, DORMANT, or DEFERRED.

    Args:
        telemetry_result: Dict with ``call_count``, ``last_called``, and
            optionally ``error``.
        event: The original webhook_payload event dict.
        kql_query: The KQL query that was used.
        existing_deferral: Optional existing deferral record from Table Storage.
            If present and ``defer_until`` is in the future, status is DEFERRED.

    Returns:
        A ``telemetry_classification`` dict per the shared schema.
    """
    # Check for existing deferral that hasn't expired
    if existing_deferral and _is_still_deferred(existing_deferral):
        status = "DEFERRED"
    else:
        status = "ACTIVE" if telemetry_result["call_count"] > 0 else "DORMANT"

    blast_radius: str = compute_blast_radius(event["severity"])
    confidence: float = compute_confidence(telemetry_result)

    return {
        "event_id": event["event_id"],
        "status": status,
        "call_count_30d": telemetry_result["call_count"],
        "last_called": telemetry_result.get("last_called"),
        "blast_radius": blast_radius,
        "kql_query_used": kql_query,
        "confidence": confidence,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _is_still_deferred(deferral: dict[str, Any]) -> bool:
    """Check if a deferral record is still active (defer_until in the future).

    Args:
        deferral: Deferral record with ``defer_until`` ISO 8601 timestamp.

    Returns:
        True if the deferral is still active.
    """
    defer_until_str = deferral.get("defer_until") or deferral.get("deferralTimestamp")
    if not defer_until_str:
        return False
    try:
        defer_until = datetime.fromisoformat(defer_until_str.replace("Z", "+00:00"))
        return datetime.now(timezone.utc) < defer_until
    except (ValueError, TypeError):
        return False


def compute_blast_radius(severity: str) -> str:
    """Map alert severity to blast_radius.

    Args:
        severity: One of CRITICAL, HIGH, MEDIUM, LOW.

    Returns:
        HIGH, MEDIUM, LOW, or UNKNOWN.
    """
    mapping: dict[str, str] = {
        "CRITICAL": "HIGH",
        "HIGH": "HIGH",
        "MEDIUM": "MEDIUM",
        "LOW": "LOW",
    }
    return mapping.get(severity, "UNKNOWN")


def compute_confidence(telemetry_result: dict[str, Any]) -> float:
    """Compute confidence based on the telemetry result quality.

    Args:
        telemetry_result: Dict with ``call_count``, ``last_called``, and
            optionally ``error``.

    Returns:
        Confidence value between 0 and 1.
    """
    if telemetry_result.get("error"):
        return 0.3
    if telemetry_result["call_count"] > 100:
        return 0.95
    if telemetry_result["call_count"] > 0:
        return 0.85
    return 0.7
