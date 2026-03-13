"""DistilBERT intent classifier for patch strategy classification.

Four-class output: VERSION_PIN, API_MIGRATION, MONKEY_PATCH, FULL_REFACTOR.
Returns class label + log-probability for downstream confidence scoring.
"""

import logging
import math
import os
from typing import Optional, Tuple

import torch
from transformers import DistilBertForSequenceClassification, DistilBertTokenizer

logger = logging.getLogger(__name__)

INTENT_LABELS = {
    0: "VERSION_PIN",
    1: "API_MIGRATION",
    2: "MONKEY_PATCH",
    3: "FULL_REFACTOR",
}

NUM_CLASSES = len(INTENT_LABELS)


def load_model(
    model_path: str = "",
) -> Tuple[DistilBertForSequenceClassification, DistilBertTokenizer]:
    """Load DistilBERT model and tokenizer.

    Tries ``model_path`` first, falls back to random-weight DistilBERT
    with 4-class head when no trained checkpoint is available.

    Args:
        model_path: Directory containing fine-tuned model weights.

    Returns:
        Tuple of (model, tokenizer).
    """
    if model_path and os.path.isdir(model_path):
        try:
            tokenizer = DistilBertTokenizer.from_pretrained(model_path)
            model = DistilBertForSequenceClassification.from_pretrained(
                model_path, num_labels=NUM_CLASSES
            )
            model.eval()
            logger.info("Loaded fine-tuned DistilBERT from %s", model_path)
            return model, tokenizer
        except Exception as exc:
            logger.warning("Failed to load fine-tuned model: %s — falling back", exc)

    tokenizer = DistilBertTokenizer.from_pretrained("distilbert-base-uncased")
    model = DistilBertForSequenceClassification.from_pretrained(
        "distilbert-base-uncased", num_labels=NUM_CLASSES
    )
    model.eval()
    logger.info(
        "Loaded DistilBERT with random classifier head "
        "(training data in /nlp-pipeline/data/labelled/)"
    )
    return model, tokenizer


class IntentClassifier:
    """DistilBERT-based classifier for developer intent.

    Outputs one of: VERSION_PIN, API_MIGRATION, MONKEY_PATCH, FULL_REFACTOR
    along with the log-probability needed for confidence scoring.
    """

    def __init__(
        self,
        model: Optional[DistilBertForSequenceClassification] = None,
        tokenizer: Optional[DistilBertTokenizer] = None,
        model_path: str = "",
    ) -> None:
        """Initialize IntentClassifier.

        Args:
            model: Pre-loaded DistilBERT model. If None, loads automatically.
            tokenizer: Pre-loaded tokenizer. If None, loads automatically.
            model_path: Path to fine-tuned model (used only if model is None).
        """
        if model is None or tokenizer is None:
            model, tokenizer = load_model(model_path)
        self.model = model
        self.tokenizer = tokenizer
        logger.info("IntentClassifier ready")

    def classify(self, text: str) -> Tuple[str, float, float]:
        """Classify community intent from text.

        Args:
            text: Raw community text (e.g., Stack Overflow answers).

        Returns:
            Tuple of (intent_label, confidence_score, log_probability).
        """
        if not text or not text.strip():
            logger.warning("Empty text — returning default classification")
            return "API_MIGRATION", 0.25, math.log(0.25)

        try:
            inputs = self.tokenizer(
                text,
                truncation=True,
                max_length=512,
                return_tensors="pt",
                padding=True,
            )

            with torch.no_grad():
                outputs = self.model(**inputs)
                logits = outputs.logits

            probabilities = torch.softmax(logits, dim=1)
            log_probs = torch.log_softmax(logits, dim=1)

            confidence_score, predicted_class = torch.max(probabilities, dim=1)
            idx = predicted_class.item()
            log_prob = log_probs[0, idx].item()

            label = INTENT_LABELS.get(idx, "API_MIGRATION")
            confidence = confidence_score.item()

            logger.info("Classified as %s (confidence=%.3f, log_prob=%.3f)", label, confidence, log_prob)
            return label, confidence, log_prob

        except Exception as exc:
            logger.error("Classification failed: %s", exc, exc_info=True)
            return "API_MIGRATION", 0.5, math.log(0.5)
