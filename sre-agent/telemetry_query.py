"""App Insights telemetry query execution.

Executes validated KQL queries against Azure Application Insights using the
``azure-monitor-query`` SDK and ``DefaultAzureCredential``.

Query strategy:
    Uses ``query_resource`` with the App Insights resource ID
    (APP_INSIGHTS_RESOURCE_ID env var) as the primary query method.
    This is the correct approach for querying Application Insights directly,
    as opposed to ``query_workspace`` which targets a Log Analytics workspace
    and may not have the App Insights tables linked.

    Falls back to ``query_workspace`` if APP_INSIGHTS_RESOURCE_ID is not set.
"""

import logging
import os
import sys
from datetime import timedelta
from typing import Any, Optional

from azure.identity import DefaultAzureCredential
from azure.monitor.query import LogsQueryClient, LogsQueryStatus

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.retry import with_retry

logger = logging.getLogger(__name__)

# App Insights resource ID — preferred over workspace ID
APP_INSIGHTS_RESOURCE_ID: str = os.environ.get("APP_INSIGHTS_RESOURCE_ID", "")


async def query_telemetry(
    kql_query: str,
    workspace_id: Optional[str],
) -> dict[str, Any]:
    """Execute a KQL query against Azure Application Insights.

    Never raises — returns a dict with an ``error`` field on failure so
    the classifier can still produce a result (defaulting to DORMANT).

    Primary: queries via APP_INSIGHTS_RESOURCE_ID using query_resource.
    Fallback: queries via workspace_id using query_workspace.

    Args:
        kql_query: The validated KQL query to execute.
        workspace_id: Log Analytics workspace ID (fallback only).

    Returns:
        Dict with:
            call_count (int): Number of matching records. 0 on failure.
            last_called (str | None): ISO timestamp of most recent call.
            error (str | None): Error message if query failed.
    """
    resource_id = APP_INSIGHTS_RESOURCE_ID or os.environ.get(
        "APP_INSIGHTS_RESOURCE_ID", ""
    )

    if not resource_id and not workspace_id:
        return {
            "call_count": 0,
            "last_called": None,
            "error": "Neither APP_INSIGHTS_RESOURCE_ID nor workspace_id configured",
        }

    try:
        credential = DefaultAzureCredential()
        client = LogsQueryClient(credential)

        async def _do_query() -> Any:
            if resource_id:
                logger.debug(
                    "Querying App Insights via resource_id: %s",
                    resource_id,
                )
                return client.query_resource(
                    resource_id=resource_id,
                    query=kql_query,
                    timespan=timedelta(days=30),
                )
            logger.debug(
                "Querying App Insights via workspace_id: %s",
                workspace_id,
            )
            return client.query_workspace(
                workspace_id=workspace_id,
                query=kql_query,
                timespan=timedelta(days=30),
            )

        result = await with_retry(
            _do_query,
            label="app-insights-query",
            max_attempts=3,
        )

        if result.status not in (
            LogsQueryStatus.SUCCESS,
            LogsQueryStatus.PARTIAL,
        ):
            return {
                "call_count": 0,
                "last_called": None,
                "error": f"Query returned status: {result.status}",
            }

        tables = result.tables
        if not tables or not tables[0].rows:
            return {"call_count": 0, "last_called": None}

        row = tables[0].rows[0]
        columns = [col.name if hasattr(col, "name") else col for col in tables[0].columns]

        count_idx = columns.index("call_count") if "call_count" in columns else -1
        last_called_idx = (
            columns.index("last_called") if "last_called" in columns else -1
        )

        call_count = int(row[count_idx]) if count_idx >= 0 else 0
        last_called: Optional[str] = None
        if last_called_idx >= 0 and row[last_called_idx]:
            last_called = row[last_called_idx].isoformat()

        logger.info(
            "Telemetry query result: call_count=%d, last_called=%s",
            call_count,
            last_called,
        )
        return {"call_count": call_count, "last_called": last_called}

    except Exception as exc:
        logger.error("Telemetry query failed: %s", exc, exc_info=True)
        return {"call_count": 0, "last_called": None, "error": str(exc)}