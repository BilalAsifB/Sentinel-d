"""ML model inference wrappers for NLP Context Pipeline."""

import logging
from typing import Dict, Any, List, Tuple

import torch
import spacy
from transformers import DistilBertForSequenceClassification, DistilBertTokenizer

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class EntityExtractor:
    """
    spaCy NER model wrapper for entity extraction.
    
    Extracts breaking changes and migration steps from raw text using a fine-tuned
    spaCy NER model that recognizes: VERSION_RANGE, API_SYMBOL, BREAKING_CHANGE, FIX_ACTION.
    """

    ENTITY_LABELS = ["VERSION_RANGE", "API_SYMBOL", "BREAKING_CHANGE", "FIX_ACTION"]

    def __init__(self, spacy_nlp: spacy.Language | None = None, model_path: str = ""):
        """
        Initialize EntityExtractor with a loaded spaCy model.

        Args:
            spacy_nlp: Loaded spaCy Language model with NER component.
                       If None, loads en_core_web_sm automatically.
            model_path: Path to fine-tuned model (used only if spacy_nlp is None).
        """
        if spacy_nlp is None:
            import os
            if model_path and os.path.exists(model_path):
                try:
                    spacy_nlp = spacy.load(model_path)
                    logger.info("Loaded fine-tuned spaCy model from %s", model_path)
                except Exception:
                    spacy_nlp = spacy.load("en_core_web_sm")
                    logger.info("Fallback to en_core_web_sm base model")
            else:
                spacy_nlp = spacy.load("en_core_web_sm")
                logger.info("Loaded en_core_web_sm base model")
        
        self.nlp = spacy_nlp
        logger.info("EntityExtractor initialized (pipeline: %s)", spacy_nlp.pipe_names)

    def extract(self, text: str) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Extract breaking changes and migration steps from text using spaCy NER.

        Args:
            text: Raw text from NVD API or community sources.

        Returns:
            Tuple of (breaking_changes list, migration_steps list).
        """
        logger.debug(f"EntityExtractor.extract() processing {len(text)} chars")
        
        # Run spaCy NER pipeline
        doc = self.nlp(text)
        
        # Group entities by label
        entities_by_label: Dict[str, List[str]] = {label: [] for label in self.ENTITY_LABELS}
        for ent in doc.ents:
            if ent.label_ in entities_by_label:
                entities_by_label[ent.label_].append(ent.text)
        
        logger.debug(f"Found {len(doc.ents)} total entities")
        
        # Build structured breaking_changes list
        breaking_changes = []
        
        # Map NER entities to breaking change records
        if entities_by_label["API_SYMBOL"]:
            api_symbols = list(set(entities_by_label["API_SYMBOL"]))
            for api in api_symbols[:3]:
                breaking_changes.append({
                    "entity": "API_CHANGE",
                    "description": f"API symbol '{api}' has breaking changes",
                    "severity": "HIGH",
                    "affected_functions": [api],
                    "remediation": f"Review and update calls to '{api}' against new signature"
                })
        
        if entities_by_label["VERSION_RANGE"]:
            version_ranges = list(set(entities_by_label["VERSION_RANGE"]))
            for version_range in version_ranges[:2]:
                breaking_changes.append({
                    "entity": "VERSION_CONSTRAINT",
                    "description": f"Version requirement changed: {version_range}",
                    "severity": "MEDIUM",
                    "affected_functions": [],
                    "remediation": f"Update dependency pin to match {version_range}"
                })
        
        if entities_by_label["BREAKING_CHANGE"]:
            for change_text in entities_by_label["BREAKING_CHANGE"][:2]:
                breaking_changes.append({
                    "entity": "SEMANTIC_CHANGE",
                    "description": change_text,
                    "severity": "HIGH",
                    "affected_functions": [],
                    "remediation": "Requires code review and integration testing"
                })
        
        # Build migration_steps from FIX_ACTION entities
        migration_steps = []
        if entities_by_label["FIX_ACTION"]:
            migration_steps.extend(entities_by_label["FIX_ACTION"])
        
        if not migration_steps:
            migration_steps = [
                "Review affected version ranges and current dependency version",
                "Identify all code paths that use affected API symbols",
                "Update API calls to new signatures",
                "Run integration tests in staging environment",
                "Deploy with monitoring and rollback capability"
            ]
        
        logger.info(f"Extracted {len(breaking_changes)} breaking changes, {len(migration_steps)} migration steps")
        return breaking_changes, migration_steps


class IntentClassifier:
    """
    DistilBERT intent classifier wrapper for community sentiment analysis.
    
    Classifies developer intent: VERSION_PIN, API_MIGRATION, MONKEY_PATCH, FULL_REFACTOR.
    """

    INTENT_LABELS = {
        0: "VERSION_PIN",
        1: "API_MIGRATION",
        2: "MONKEY_PATCH",
        3: "FULL_REFACTOR"
    }

    def __init__(
        self,
        distilbert_model: DistilBertForSequenceClassification | None = None,
        distilbert_tokenizer: DistilBertTokenizer | None = None,
        model_path: str = "",
    ):
        """
        Initialize IntentClassifier with loaded DistilBERT model and tokenizer.

        Args:
            distilbert_model: Loaded DistilBertForSequenceClassification model.
                              If None, loads automatically.
            distilbert_tokenizer: Associated tokenizer. If None, loads automatically.
            model_path: Path to fine-tuned model (used only if model is None).
        """
        if distilbert_model is None or distilbert_tokenizer is None:
            import os
            if model_path and os.path.isdir(model_path):
                try:
                    distilbert_tokenizer = DistilBertTokenizer.from_pretrained(model_path)
                    distilbert_model = DistilBertForSequenceClassification.from_pretrained(
                        model_path, num_labels=4
                    )
                    logger.info("Loaded fine-tuned DistilBERT from %s", model_path)
                except Exception:
                    distilbert_tokenizer = DistilBertTokenizer.from_pretrained("distilbert-base-uncased")
                    distilbert_model = DistilBertForSequenceClassification.from_pretrained(
                        "distilbert-base-uncased", num_labels=4
                    )
                    logger.info("Fallback to base DistilBERT with random head")
            else:
                distilbert_tokenizer = DistilBertTokenizer.from_pretrained("distilbert-base-uncased")
                distilbert_model = DistilBertForSequenceClassification.from_pretrained(
                    "distilbert-base-uncased", num_labels=4
                )
                logger.info("Loaded base DistilBERT with random classifier head")
        
        self.model = distilbert_model
        self.tokenizer = distilbert_tokenizer
        self.model.eval()
        logger.info("IntentClassifier initialized")

    def classify(
        self, text: str
    ) -> Tuple[str, float]:
        """
        Classify community intent from text using DistilBERT.

        Args:
            text: Raw community text from Stack Overflow or other sources.

        Returns:
            Tuple of (intent_class, confidence_score) where confidence is 0.0-1.0.
        """
        logger.debug(f"IntentClassifier.classify() processing {len(text)} chars")
        
        try:
            # Tokenize input (truncate to 512 tokens max for DistilBERT)
            inputs = self.tokenizer(
                text,
                truncation=True,
                max_length=512,
                return_tensors="pt",
                padding=True
            )
            logger.debug(f"Tokenized to {inputs['input_ids'].shape[1]} tokens")
            
            # Run model inference (no gradients needed)
            with torch.no_grad():
                outputs = self.model(**inputs)
                logits = outputs.logits
            
            # Apply softmax to get probabilities (dim=1 for class dimension)
            probabilities = torch.softmax(logits, dim=1)
            confidence_score, predicted_class = torch.max(probabilities, dim=1)
            
            # Convert to Python scalars
            intent_idx = predicted_class.item()
            confidence = confidence_score.item()
            intent_label = self.INTENT_LABELS.get(intent_idx, "API_MIGRATION")
            
            logger.info(f"Classified as {intent_label} (confidence: {confidence:.3f})")
            return intent_label, confidence
        
        except Exception as e:
            logger.error(f"Classification failed: {str(e)}", exc_info=True)
            return "API_MIGRATION", 0.5
