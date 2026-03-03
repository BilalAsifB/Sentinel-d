"""Pytest unit tests for classifier module."""

import sys
import os

# Ensure the sre-agent root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from classifier import classify, compute_blast_radius, compute_confidence


BASE_EVENT: dict = {
    "event_id": "550e8400-e29b-41d4-a716-446655440000",
    "cve_id": "CVE-2024-1234",
    "severity": "HIGH",
    "affected_package": "express",
    "current_version": "4.17.1",
    "fix_version_range": ">=4.18.0",
    "file_path": "src/app.js",
    "line_range": [10, 20],
    "repo": "org/repo",
    "timestamp": "2024-01-01T00:00:00Z",
}

KQL_QUERY: str = "traces | where timestamp > ago(30d) | summarize count()"


# ── classify ──────────────────────────────────────────────────────────────


class TestClassify:
    """Tests for the classify function."""

    def test_returns_active_when_call_count_positive(self) -> None:
        telemetry = {"call_count": 42, "last_called": "2024-01-15T10:00:00Z"}
        result = classify(telemetry, BASE_EVENT, KQL_QUERY)

        assert result["status"] == "ACTIVE"
        assert result["event_id"] == BASE_EVENT["event_id"]
        assert result["call_count_30d"] == 42
        assert result["last_called"] == "2024-01-15T10:00:00Z"
        assert result["kql_query_used"] == KQL_QUERY

    def test_returns_dormant_when_call_count_zero(self) -> None:
        telemetry = {"call_count": 0, "last_called": None}
        result = classify(telemetry, BASE_EVENT, KQL_QUERY)

        assert result["status"] == "DORMANT"
        assert result["call_count_30d"] == 0
        assert result["last_called"] is None

    def test_includes_blast_radius_based_on_severity(self) -> None:
        telemetry = {"call_count": 1, "last_called": "2024-01-15T10:00:00Z"}
        result = classify(telemetry, BASE_EVENT, KQL_QUERY)

        assert result["blast_radius"] == "HIGH"


# ── compute_blast_radius ──────────────────────────────────────────────────


class TestComputeBlastRadius:
    """Tests for the compute_blast_radius function."""

    def test_critical_maps_to_high(self) -> None:
        assert compute_blast_radius("CRITICAL") == "HIGH"

    def test_high_maps_to_high(self) -> None:
        assert compute_blast_radius("HIGH") == "HIGH"

    def test_medium_maps_to_medium(self) -> None:
        assert compute_blast_radius("MEDIUM") == "MEDIUM"

    def test_low_maps_to_low(self) -> None:
        assert compute_blast_radius("LOW") == "LOW"

    def test_unknown_severity_maps_to_unknown(self) -> None:
        assert compute_blast_radius("UNKNOWN_VALUE") == "UNKNOWN"


# ── compute_confidence ────────────────────────────────────────────────────


class TestComputeConfidence:
    """Tests for the compute_confidence function."""

    def test_returns_0_3_on_error(self) -> None:
        assert compute_confidence({"call_count": 0, "last_called": None, "error": "fail"}) == 0.3

    def test_returns_0_95_for_high_call_count(self) -> None:
        assert compute_confidence({"call_count": 200, "last_called": "2024-01-01T00:00:00Z"}) == 0.95

    def test_returns_0_85_for_positive_call_count(self) -> None:
        assert compute_confidence({"call_count": 5, "last_called": "2024-01-01T00:00:00Z"}) == 0.85

    def test_returns_0_7_for_zero_call_count(self) -> None:
        assert compute_confidence({"call_count": 0, "last_called": None}) == 0.7
