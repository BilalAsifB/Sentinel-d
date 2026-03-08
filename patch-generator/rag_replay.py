"""RAG Replay path — spec-required location.

See agents/patch_generator/rag_replay.py for the canonical implementation.
This module re-exports for compatibility with the /patch-generator/ directory layout.
"""

import sys
import os

# Add agents directory to path for imports
_agents_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agents")
if _agents_dir not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.patch_generator.rag_replay import (  # noqa: E402
    RAGReplayResult,
    attempt_replay,
    build_solutions_tried_entry,
)

__all__ = ["RAGReplayResult", "attempt_replay", "build_solutions_tried_entry"]
