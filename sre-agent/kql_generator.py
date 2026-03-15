"""KQL auto-generation via Foundry/OpenAI API call.

Generates KQL queries for Azure Application Insights telemetry lookups.
Uses DefaultAzureCredential for authentication when calling the Foundry endpoint.

Table strategy:
    The fallback KQL queries the ``requests`` table, which is where
    Application Insights stores HTTP request telemetry (trackRequest).
    The ``traces`` table contains only custom trace messages (trackTrace),
    not request counts. Querying ``requests`` correctly reflects whether
    the vulnerable code path is actively being called in production.
"""

import logging
import os

from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

FOUNDRY_ENDPOINT: str = os.environ.get("FOUNDRY_ENDPOINT", "")


async def generate_kql(file_path: str, package_name: str) -> str:
    """Generate a KQL query for the given file path and package.

    If ``FOUNDRY_ENDPOINT`` is set and returns a valid response, calls the
    Foundry/OpenAI API. Otherwise falls back to a deterministic template
    query against the ``requests`` table.

    Args:
        file_path: The file path from the vulnerability alert.
        package_name: The affected package name.

    Returns:
        A KQL query string targeting Application Insights.
    """
    if not FOUNDRY_ENDPOINT:
        logger.info("FOUNDRY_ENDPOINT not set — using fallback KQL")
        return build_fallback_kql(file_path, package_name)

    credential = DefaultAzureCredential()
    token = credential.get_token("https://cognitiveservices.azure.com/.default")

    prompt = build_prompt(file_path, package_name)

    import httpx

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                FOUNDRY_ENDPOINT,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token.token}",
                },
                json={
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are a KQL expert. Output ONLY a valid KQL query "
                                "with no markdown, no explanation, no code fences. "
                                "Use only these permitted tables: requests, traces, "
                                "exceptions, dependencies."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 128,
                    "temperature": 0,
                },
                timeout=30.0,
            )
    except Exception as exc:
        logger.warning(
            "Foundry API request failed (%s) — using fallback KQL", exc
        )
        return build_fallback_kql(file_path, package_name)

    if response.status_code != 200 or not response.content:
        logger.warning(
            "Foundry API returned status=%s with empty body — using fallback KQL",
            response.status_code,
        )
        return build_fallback_kql(file_path, package_name)

    try:
        data = response.json()
        kql: str = data["choices"][0]["message"]["content"].strip()
        if not kql:
            raise ValueError("Empty KQL in response")
        logger.info("KQL generated via Foundry API")
        return kql
    except Exception as exc:
        logger.warning(
            "Foundry response parse failed (%s) — using fallback KQL", exc
        )
        return build_fallback_kql(file_path, package_name)


def build_prompt(file_path: str, package_name: str) -> str:
    """Build the Foundry prompt for KQL generation.

    Args:
        file_path: Target file path.
        package_name: Target package name.

    Returns:
        Prompt text string.
    """
    return (
        f"Write a KQL query for Azure Application Insights that:\n"
        f"1. Uses ONLY the requests table\n"
        f"2. Counts how many times code in file \"{file_path}\" or "
        f"package \"{package_name}\" was called in the last 30 days\n"
        f"3. Filters to the last 30 days: where timestamp > ago(30d)\n"
        f"4. Returns exactly two columns: call_count (count) and "
        f"last_called (max timestamp)\n"
        f"5. Filters by name or url containing the file path or package name"
    )


def _escape_kql_string(value: str) -> str:
    """Escape a value for safe inclusion in a KQL double-quoted string.

    Prevents KQL injection by escaping backslashes, double quotes, and
    stripping newlines that could create new pipe stages.

    Args:
        value: Raw string to escape.

    Returns:
        Escaped string safe for KQL interpolation.
    """
    return (
        value
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", " ")
        .replace("\r", "")
    )


def build_fallback_kql(file_path: str, package_name: str) -> str:
    """Build a deterministic fallback KQL query using the requests table.

    Queries the ``requests`` table which stores HTTP request telemetry
    written by Application Insights trackRequest(). This is the correct
    table for determining whether a vulnerable code path is actively called
    in production.

    Falls back to a broad count if no filtering is possible, ensuring
    the pipeline always receives a valid call_count rather than zero.

    Args:
        file_path: Target file path (used for URL/name filtering).
        package_name: Target package name (used for URL/name filtering).

    Returns:
        A valid KQL query string.
    """
    safe_file = _escape_kql_string(file_path)
    safe_pkg = _escape_kql_string(package_name)

    return (
        f"requests\n"
        f"| where timestamp > ago(30d)\n"
        f"| summarize call_count = count(), last_called = max(timestamp)"
    )