#!/usr/bin/env python3
"""rag_replay_runner.py — CLI bridge between consumer.js and agents/patch_generator/rag_replay.py

Reads structured_context JSON from stdin.
Writes candidate_patch JSON to stdout.
Exits 0 on success, 1 on failure (consumer.js falls through to Foundry).

Expects structured_context to contain:
    historical_patch_diff   — unified diff string from Cosmos record
    replay_eligible         — True/False
    historical_record_id    — matched_record_id for logging
    (plus all standard structured_context fields)
"""

import asyncio
import json
import sys
import os
import logging

logging.basicConfig(level=logging.WARNING, stream=sys.stderr)

# Ensure repo root is on path so agents/ and shared/ are importable
_repo_root = os.path.dirname(os.path.abspath(__file__))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from agents.patch_generator.rag_replay import attempt_replay, RAGReplayResult


async def main() -> None:
    raw = sys.stdin.read().strip()
    if not raw:
        print(json.dumps({
            "status": "CANNOT_PATCH",
            "cannot_patch_reason": "Empty stdin"
        }))
        sys.exit(1)

    try:
        structured_context = json.loads(raw)
    except json.JSONDecodeError as e:
        print(json.dumps({
            "status": "CANNOT_PATCH",
            "cannot_patch_reason": f"JSON parse error: {e}"
        }))
        sys.exit(1)

    # Build historical_match dict from fields embedded in structured_context
    # (these are set by nlp-pipeline/historical_db/read_client.py and forwarded
    # by nlp_consumer.py after the fix applied in this session)
    historical_match = {
        "historical_patch_diff": structured_context.get("historical_patch_diff", ""),
        "replay_eligible": structured_context.get("replay_eligible", False),
        "matched_record_id": structured_context.get("historical_record_id", ""),
        "previous_outcome": structured_context.get("historical_match_status", "UNKNOWN"),
        "recommended_strategy": structured_context.get("fix_strategy", ""),
        "language": "",  # not required for apply check
    }

    result: RAGReplayResult = await attempt_replay(structured_context, historical_match)

    if result.success and result.candidate_patch:
        print(json.dumps(result.candidate_patch))
        sys.exit(0)
    else:
        # Non-zero exit → consumer.js falls through to Foundry
        print(json.dumps({
            "status": "CANNOT_PATCH",
            "cannot_patch_reason": result.failure_reason,
        }), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())