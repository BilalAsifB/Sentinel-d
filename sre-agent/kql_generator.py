"""KQL auto-generation via Foundry/OpenAI API call.

Generates KQL queries for Azure Application Insights telemetry lookups.
Uses DefaultAzureCredential for authentication when calling the Foundry endpoint.
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

    If ``FOUNDRY_ENDPOINT`` is set, calls the Foundry/OpenAI API.
    Otherwise falls back to a deterministic template query.

    Args:
        file_path: The file path from the vulnerability alert.
        package_name: The affected package name.

    Returns:
        A KQL query string.
    """
    if not FOUNDRY_ENDPOINT:
        return build_fallback_kql(file_path, package_name)

    credential = DefaultAzureCredential()
    token = credential.get_token("https://cognitiveservices.azure.com/.default")

    prompt = build_prompt(file_path, package_name)

    # Use httpx for async HTTP calls
    import httpx

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
                            "with no markdown, no explanation, no code fences."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 128,
                "temperature": 0,
            },
            timeout=30.0,
        )

    if response.status_code != 200:
        raise RuntimeError(
            f"Foundry API error: {response.status_code} {response.reason_phrase}"
        )

    data = response.json()
    kql: str = data["choices"][0]["message"]["content"].strip()
    return kql


def build_prompt(file_path: str, package_name: str) -> str:
    """Build the prompt for KQL generation.

    Args:
        file_path: Target file path.
        package_name: Target package name.

    Returns:
        Prompt text string.
    """
    return (
        f'Write a KQL query for Azure Application Insights that:\n'
        f'1. Uses ONLY the traces table\n'
        f'2. Counts how many times code in file "{file_path}" or '
        f'package "{package_name}" was called\n'
        f'3. Filters to the last 30 days using: where timestamp > ago(30d)\n'
        f'4. Returns two columns: call_count (count of matching traces) '
        f'and last_called (max timestamp)\n'
        f'5. Use where clause to filter by message or customDimensions '
        f'containing the file path or package name'
    )


def build_fallback_kql(file_path: str, package_name: str) -> str:
    """Build a deterministic fallback KQL query when no AI endpoint is available.

    Args:
        file_path: Target file path.
        package_name: Target package name.

    Returns:
        A KQL query string.
    """
    return (
        f"traces\n"
        f"| where timestamp > ago(30d)\n"
        f'| where message contains "{file_path}" or '
        f'message contains "{package_name}" or '
        f'customDimensions contains "{file_path}" or '
        f'customDimensions contains "{package_name}"\n'
        f"| summarize call_count = count(), last_called = max(timestamp)"
    )
