"""Confidence scoring — composite confidence score for generated patches.

Spec-required location: /patch-generator/confidence.py
Re-exports from canonical implementation in /agents/patch_generator/confidence_scorer.py.
"""

import sys
import os

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from agents.patch_generator.confidence_scorer import ConfidenceScorer  # noqa: E402

__all__ = ["ConfidenceScorer"]
