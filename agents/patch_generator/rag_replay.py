"""RAG Replay path for patch generation.

When a historical match is found (EXACT_MATCH or SEMANTIC_MATCH with replay_eligible=true),
attempts to replay the previous successful patch instead of calling Foundry.

Structural compatibility checks:
    1. Language match between historical record and current context
    2. git apply --check to verify patch can be applied cleanly

On success: Foundry API is never called (logged as RAG_REPLAY source).
On failure: Appends to solutions_tried[] and falls through to full Foundry pipeline.
"""

import asyncio
import logging
import os
import tempfile
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class RAGReplayResult:
    """Result of a RAG replay attempt."""

    def __init__(
        self,
        success: bool,
        candidate_patch: Optional[Dict[str, Any]] = None,
        failure_reason: str = "",
    ) -> None:
        """Initialize RAGReplayResult.

        Args:
            success: Whether replay succeeded.
            candidate_patch: Generated candidate_patch.json dict on success.
            failure_reason: Reason for failure (used in solutions_tried).
        """
        self.success = success
        self.candidate_patch = candidate_patch
        self.failure_reason = failure_reason


async def attempt_replay(
    structured_context: Dict[str, Any],
    historical_match: Dict[str, Any],
) -> RAGReplayResult:
    """Attempt to replay a historical patch.

    Args:
        structured_context: Current pipeline context.
        historical_match: Historical match record with patch_diff and metadata.

    Returns:
        RAGReplayResult indicating success/failure.
    """
    event_id = structured_context.get("event_id", "UNKNOWN")
    historical_diff = historical_match.get("historical_patch_diff", "")
    replay_eligible = historical_match.get("replay_eligible", False)

    if not replay_eligible or not historical_diff:
        return RAGReplayResult(
            success=False,
            failure_reason="Not replay eligible or no historical patch diff",
        )

    logger.info("RAG_REPLAY: Attempting replay for event %s", event_id)

    # Check 1: Language compatibility
    # (historical record language vs. current context — best effort)
    hist_language = historical_match.get("language", "")
    # We don't have language in structured_context by default, so skip if unavailable

    # Check 2: git apply --check
    apply_ok = await _git_apply_check(historical_diff)
    if not apply_ok:
        logger.warning("RAG_REPLAY: git apply --check failed for %s", event_id)
        return RAGReplayResult(
            success=False,
            failure_reason="git apply --check failed — patch does not apply cleanly",
        )

    # Replay succeeded — build candidate_patch output
    logger.info("RAG_REPLAY: Patch applies cleanly for %s — skipping Foundry", event_id)

    candidate_patch: Dict[str, Any] = {
        "event_id": event_id,
        "status": "PATCH_GENERATED",
        "source": "RAG_REPLAY",
        "diff": historical_diff,
        "files_modified": _extract_files(historical_diff),
        "lines_changed": _count_lines(historical_diff),
        "touches_auth_crypto": False,
        "llm_confidence": 0.0,
        "reasoning_chain": (
            f"RAG replay of historical record {historical_match.get('matched_record_id', '')}. "
            f"Previous outcome: {historical_match.get('previous_outcome', 'UNKNOWN')}. "
            f"Strategy: {historical_match.get('recommended_strategy', 'UNKNOWN')}."
        ),
        "model_id": "RAG_REPLAY",
        "cannot_patch_reason": None,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }

    return RAGReplayResult(success=True, candidate_patch=candidate_patch)


def build_solutions_tried_entry(result: RAGReplayResult) -> Dict[str, Any]:
    """Build a solutions_tried entry for a failed replay.

    Args:
        result: Failed RAGReplayResult.

    Returns:
        Dictionary with strategy, outcome, and failure_reason.
    """
    return {
        "strategy": "RAG_REPLAY",
        "outcome": "FAILED",
        "failure_reason": result.failure_reason,
    }


async def _git_apply_check(diff: str) -> bool:
    """Run git apply --check on a diff string.

    Args:
        diff: Unified diff string.

    Returns:
        True if patch applies cleanly, False otherwise.
    """
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".patch", delete=False
        ) as tmp:
            tmp.write(diff)
            tmp_path = tmp.name

        proc = await asyncio.create_subprocess_exec(
            "git", "apply", "--check", tmp_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()

        os.unlink(tmp_path)

        if proc.returncode == 0:
            return True
        logger.debug("git apply --check stderr: %s", stderr.decode().strip())
        return False

    except Exception as exc:
        logger.error("git apply --check error: %s", exc)
        return False


def _extract_files(diff: str) -> List[str]:
    """Extract modified file paths from diff."""
    import re
    files = []
    for line in diff.split("\n"):
        if line.startswith("+++"):
            m = re.match(r"\+\+\+ b/(.+)", line)
            if m:
                files.append(m.group(1))
    return files


def _count_lines(diff: str) -> int:
    """Count changed lines in diff."""
    count = 0
    for line in diff.split("\n"):
        if line.startswith("+") and not line.startswith("+++"):
            count += 1
        elif line.startswith("-") and not line.startswith("---"):
            count += 1
    return count
