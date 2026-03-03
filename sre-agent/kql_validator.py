"""KQL query validator.

Ensures generated KQL only uses permitted tables and does not contain
blocked operators.
"""

import re
from typing import Optional

PERMITTED_TABLES: list[str] = ["traces", "requests", "exceptions", "dependencies"]

BLOCKED_OPERATORS: list[str] = [
    "externaldata",
    "http_request",
    "invoke",
    "evaluate",
    "plugins",
]

KQL_KEYWORDS: set[str] = {
    "where", "summarize", "project", "extend", "order", "sort", "top",
    "take", "limit", "count", "distinct", "render", "let", "datatable",
    "print", "range", "search", "find", "parse", "mv-expand", "mvexpand",
    "by", "asc", "desc", "on", "kind", "ago", "now", "bin", "startofday",
    "contains", "has", "or", "and", "not", "in", "between", "true", "false",
}


def validate_kql(kql_string: Optional[str]) -> dict:
    """Validate a KQL query string against the allowlist and blocklist.

    Args:
        kql_string: The KQL query to validate.

    Returns:
        A dict with ``{"valid": True}`` on success, or
        ``{"valid": False, "reason": "..."}`` on failure.
    """
    if not kql_string or not isinstance(kql_string, str):
        return {"valid": False, "reason": "KQL query is empty or not a string"}

    normalized = kql_string.lower()

    # Check for blocked operators
    for op in BLOCKED_OPERATORS:
        if re.search(rf"\b{op}\b", normalized, re.IGNORECASE):
            return {"valid": False, "reason": f"Blocked operator detected: {op}"}

    # Extract table references
    found_tables: set[str] = set()

    # Primary table: first word of the query
    first_match = re.match(r"^\s*([a-z_][a-z0-9_]*)\s*", normalized)
    if first_match:
        found_tables.add(first_match.group(1))

    # Union statements
    for union_match in re.finditer(
        r"\bunion\s+(?:kind\s*=\s*\w+\s+)?\(?\s*"
        r"([a-z_][a-z0-9_]*(?:\s*,\s*[a-z_][a-z0-9_]*)*)",
        kql_string,
        re.IGNORECASE,
    ):
        tables = [t.strip().lower() for t in union_match.group(1).split(",")]
        found_tables.update(tables)

    # Join statements
    for join_match in re.finditer(
        r"\bjoin\s+(?:kind\s*=\s*\w+\s+)?\(?\s*([a-z_][a-z0-9_]*)",
        kql_string,
        re.IGNORECASE,
    ):
        found_tables.add(join_match.group(1).lower())

    # Validate all found tables against the permitted list
    for table in found_tables:
        if table in KQL_KEYWORDS:
            continue
        if table not in PERMITTED_TABLES:
            return {"valid": False, "reason": f"Non-permitted table referenced: {table}"}

    return {"valid": True}
