"""Prompt builder — four-section prompt architecture for patch generation.

Spec-required location: /patch-generator/prompt_builder.py
Re-exports from canonical implementation in /agents/patch_generator/prompt_builder.py.
"""

import sys
import os

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from agents.patch_generator.prompt_builder import PromptBuilder  # noqa: E402

__all__ = ["PromptBuilder"]
