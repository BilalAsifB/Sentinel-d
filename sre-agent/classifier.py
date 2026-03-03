"""Three-way classifier for SRE Agent telemetry results.

Produces a ``telemetry_classification`` conforming to the shared schema.
"""

from typing import Any, Optional


def classify(
    telemetry_result: dict[str, Any],
    event: dict[str, Any],
    kql_query: str,
) -> dict[str, Any]:
    """Classify a telemetry result as ACTIVE, DORMANT, or DEFERRED.

    Args:
        telemetry_result: Dict with ``call_count``, ``last_called``, and
            optionally ``error``.
        event: The original webhook_payload event dict.
        kql_query: The KQL query that was used.

    Returns:
        A ``telemetry_classification`` dict per the shared schema.
    """
    status: str = "ACTIVE" if telemetry_result["call_count"] > 0 else "DORMANT"
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
    }


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
