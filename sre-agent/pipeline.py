"""Main orchestrator for the SRE Agent pipeline.

Wires together KQL generation, validation, telemetry querying, and
three-way classification into a single callable pipeline.
"""

import asyncio
import logging
import os
from typing import Any

from dotenv import load_dotenv

from kql_generator import generate_kql
from kql_validator import validate_kql
from telemetry_query import query_telemetry
from classifier import classify

load_dotenv()

logger = logging.getLogger(__name__)

WORKSPACE_ID: str = os.environ.get("APP_INSIGHTS_WORKSPACE_ID", "")


async def run_pipeline(event: dict[str, Any]) -> dict[str, Any]:
    """Run the full SRE Agent pipeline on a single event.

    Steps:
        1. Generate a KQL query from the event's file_path and affected_package.
        2. Validate the KQL query against the allowlist.
        3. Execute the query against App Insights.
        4. Classify the telemetry result as ACTIVE / DORMANT / DEFERRED.

    Args:
        event: A webhook_payload dict conforming to the shared schema.

    Returns:
        A telemetry_classification dict conforming to the shared schema.

    Raises:
        ValueError: If KQL validation fails.
    """
    file_path: str = event["file_path"]
    package_name: str = event["affected_package"]

    # Step 1: Generate KQL
    kql_query = await generate_kql(file_path, package_name)
    logger.info("Generated KQL for event_id=%s", event.get("event_id"))

    # Step 2: Validate KQL
    validation = validate_kql(kql_query)
    if not validation["valid"]:
        raise ValueError(f"KQL validation failed: {validation['reason']}")
    logger.info("KQL validation passed for event_id=%s", event.get("event_id"))

    # Step 3: Query telemetry
    telemetry_result = await query_telemetry(kql_query, WORKSPACE_ID)
    logger.info(
        "Telemetry query complete for event_id=%s: call_count=%d",
        event.get("event_id"),
        telemetry_result["call_count"],
    )

    # Step 4: Classify
    classification = classify(telemetry_result, event, kql_query)
    logger.info(
        "Classification for event_id=%s: %s (confidence=%.2f)",
        event.get("event_id"),
        classification["status"],
        classification["confidence"],
    )

    return classification


if __name__ == "__main__":
    import json
    import sys

    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 2:
        logger.error("Usage: python pipeline.py <event.json>")
        raise SystemExit(1)

    with open(sys.argv[1]) as f:
        event_data = json.load(f)

    result = asyncio.run(run_pipeline(event_data))
    print(json.dumps(result, indent=2))
