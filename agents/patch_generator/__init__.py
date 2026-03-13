"""
Patch Generator Module

Generates security patches using Microsoft Foundry (Azure OpenAI) with confidence scoring.
"""

from agents.patch_generator.prompt_builder import PromptBuilder
from agents.patch_generator.confidence_scorer import ConfidenceScorer
from agents.patch_generator.agent import PatchGeneratorAgent
from agents.patch_generator.rag_replay import attempt_replay, RAGReplayResult

__all__ = [
    "PromptBuilder",
    "ConfidenceScorer",
    "PatchGeneratorAgent",
    "attempt_replay",
    "RAGReplayResult",
]
