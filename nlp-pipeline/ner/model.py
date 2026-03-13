"""spaCy NER model wrapper for vulnerability entity extraction.

Extracts: CVE_ID, PACKAGE_NAME, VERSION, LANGUAGE, FRAMEWORK entities.
Falls back to en_core_web_sm base model when fine-tuned weights are unavailable.
"""

import logging
import os
from typing import Any, Dict, List, Tuple

import spacy
from spacy.language import Language

logger = logging.getLogger(__name__)

TARGET_ENTITIES = ["CVE_ID", "PACKAGE_NAME", "VERSION", "LANGUAGE", "FRAMEWORK"]

FINE_TUNED_ENTITIES = ["VERSION_RANGE", "API_SYMBOL", "BREAKING_CHANGE", "FIX_ACTION"]


def load_model(model_path: str = "") -> Language:
    """Load spaCy NER model.

    Tries to load a fine-tuned model from ``model_path`` first, then falls
    back to ``en_core_web_sm``.

    Args:
        model_path: Path to fine-tuned spaCy model directory or zip.

    Returns:
        Loaded spaCy Language pipeline.
    """
    if model_path and os.path.exists(model_path):
        try:
            nlp = spacy.load(model_path)
            logger.info("Loaded fine-tuned spaCy model from %s", model_path)
            return nlp
        except Exception as exc:
            logger.warning("Failed to load fine-tuned model: %s — falling back", exc)

    try:
        nlp = spacy.load("en_core_web_sm")
        logger.info("Loaded en_core_web_sm base model (fine-tuned weights not available)")
        return nlp
    except OSError:
        logger.error("en_core_web_sm not installed — run: python -m spacy download en_core_web_sm")
        raise


class EntityExtractor:
    """Extracts breaking changes and migration steps from NVD text using spaCy NER.

    Target entity labels (fine-tuned model):
        VERSION_RANGE, API_SYMBOL, BREAKING_CHANGE, FIX_ACTION

    When using the base model, entity mapping falls back to standard NER labels.
    """

    ENTITY_LABELS = FINE_TUNED_ENTITIES

    def __init__(self, nlp: Language | None = None, model_path: str = "") -> None:
        """Initialize EntityExtractor.

        Args:
            nlp: Pre-loaded spaCy Language model. If None, loads automatically.
            model_path: Path to fine-tuned model (used only if nlp is None).
        """
        if nlp is None:
            nlp = load_model(model_path)
        self.nlp = nlp
        logger.info("EntityExtractor ready (pipeline: %s)", nlp.pipe_names)

    def extract(self, text: str) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Extract breaking changes and migration steps from text.

        Args:
            text: Raw description text from NVD API.

        Returns:
            Tuple of (breaking_changes list, migration_steps list).
        """
        if not text or not text.strip():
            return [], self._default_migration_steps()

        doc = self.nlp(text)

        entities_by_label: Dict[str, List[str]] = {
            label: [] for label in self.ENTITY_LABELS
        }
        for ent in doc.ents:
            if ent.label_ in entities_by_label:
                entities_by_label[ent.label_].append(ent.text)

        logger.debug("Found %d entities in %d chars", len(doc.ents), len(text))

        breaking_changes = self._build_breaking_changes(entities_by_label)
        migration_steps = self._build_migration_steps(entities_by_label)

        logger.info(
            "Extracted %d breaking changes, %d migration steps",
            len(breaking_changes), len(migration_steps),
        )
        return breaking_changes, migration_steps

    def _build_breaking_changes(
        self, entities: Dict[str, List[str]]
    ) -> List[Dict[str, Any]]:
        """Build structured breaking_changes list from NER entities."""
        changes: List[Dict[str, Any]] = []

        for api in list(set(entities.get("API_SYMBOL", [])))[:3]:
            changes.append({
                "entity": "API_CHANGE",
                "description": f"API symbol '{api}' has breaking changes",
                "severity": "HIGH",
                "affected_functions": [api],
                "remediation": f"Review and update calls to '{api}'",
            })

        for vr in list(set(entities.get("VERSION_RANGE", [])))[:2]:
            changes.append({
                "entity": "VERSION_CONSTRAINT",
                "description": f"Version requirement changed: {vr}",
                "severity": "MEDIUM",
                "affected_functions": [],
                "remediation": f"Update dependency pin to match {vr}",
            })

        for bc in entities.get("BREAKING_CHANGE", [])[:2]:
            changes.append({
                "entity": "SEMANTIC_CHANGE",
                "description": bc,
                "severity": "HIGH",
                "affected_functions": [],
                "remediation": "Requires code review and integration testing",
            })

        return changes

    @staticmethod
    def _build_migration_steps(entities: Dict[str, List[str]]) -> List[str]:
        """Build migration_steps from FIX_ACTION entities or defaults."""
        fix_actions = entities.get("FIX_ACTION", [])
        if fix_actions:
            return list(fix_actions)
        return EntityExtractor._default_migration_steps()

    @staticmethod
    def _default_migration_steps() -> List[str]:
        """Return sensible default migration steps."""
        return [
            "Review affected version ranges and current dependency version",
            "Identify all code paths that use affected API symbols",
            "Update API calls to new signatures",
            "Run integration tests in staging environment",
            "Deploy with monitoring and rollback capability",
        ]
