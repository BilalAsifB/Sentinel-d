"""App Insights telemetry query execution.

Executes validated KQL queries against Azure Application Insights using the
``azure-monitor-query`` SDK and ``DefaultAzureCredential``.
"""

import logging
from datetime import timedelta
from typing import Any, Optional

from azure.identity import DefaultAzureCredential
from azure.monitor.query import LogsQueryClient, LogsQueryStatus

logger = logging.getLogger(__name__)


async def query_telemetry(
    kql_query: str, workspace_id: Optional[str]
) -> dict[str, Any]:
    """Execute a KQL query against Azure Application Insights.

    Never raises — returns an error field on failure.

    Args:
        kql_query: The validated KQL query to execute.
        workspace_id: The Log Analytics workspace ID.

    Returns:
        A dict with ``call_count``, ``last_called``, and optionally ``error``.
    """
    try:
        if not workspace_id:
            return {"call_count": 0, "last_called": None, "error": "Missing workspace_id"}

        credential = DefaultAzureCredential()
        client = LogsQueryClient(credential)

        result = client.query_workspace(
            workspace_id=workspace_id,
            query=kql_query,
            timespan=timedelta(days=30),
        )

        if result.status in (LogsQueryStatus.SUCCESS, LogsQueryStatus.PARTIAL):
            tables = result.tables
            if tables and tables[0].rows:
                row = tables[0].rows[0]
                columns = [col.name for col in tables[0].columns]

                count_idx = columns.index("call_count") if "call_count" in columns else -1
                last_called_idx = (
                    columns.index("last_called") if "last_called" in columns else -1
                )

                call_count = int(row[count_idx]) if count_idx >= 0 else 0
                last_called: Optional[str] = None
                if last_called_idx >= 0 and row[last_called_idx]:
                    last_called = row[last_called_idx].isoformat()

                return {"call_count": call_count, "last_called": last_called}

            return {"call_count": 0, "last_called": None}

        return {
            "call_count": 0,
            "last_called": None,
            "error": f"Query returned status: {result.status}",
        }
    except Exception as exc:
        return {"call_count": 0, "last_called": None, "error": str(exc)}
