"""Sentinel-D NLP Pipeline Orchestrator."""

import os
import json
from datetime import datetime
from typing import Dict, Any
import spacy
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer
from huggingface_hub import snapshot_download

from agents.nlp_pipeline.ml_models import EntityExtractor, IntentClassifier


class SentinelPipeline:
    """
    End-to-end NLP orchestrator for Sentinel-D DevSecOps pipeline.
    
    Combines spaCy NER (Stage 1) and DistilBERT classification (Stage 2)
    to analyze vulnerability patch requirements from security alerts.
    """
    
    # Intent classification labels (must match DistilBERT fine-tuning)
    INTENT_LABELS = {
        0: "VERSION_PIN",
        1: "API_MIGRATION",
        2: "MONKEY_PATCH",
        3: "FULL_REFACTOR"
    }
    
    # NER entity types extracted by spaCy
    NER_ENTITIES = ["VERSION_RANGE", "API_SYMBOL", "BREAKING_CHANGE", "FIX_ACTION"]
    
    def __init__(self):
        """
        Initialize the Sentinel Pipeline by loading both fine-tuned models from Hugging Face Hub.
        
        Models are streamed directly into memory using snapshot_download for efficient caching
        and model loading without manual ZIP extraction.
        
        Raises:
            Exception: If model download or loading fails
        """
        print("[SentinelPipeline] Initializing NLP orchestrator...")
        
        # ============ Stage 1: Load spaCy NER Model ============
        print("[Stage 1] Loading spaCy NER model from Hugging Face Hub...")
        try:
            spacy_repo_path = snapshot_download(
                repo_id="mojad121/spacy-classes-finetune",
                cache_dir=os.getenv("HF_CACHE_DIR", None),
                force_download=False
            )
            
            # Load the spaCy model (handles various directory structures)
            self.spacy_nlp = self._load_spacy_model_from_path(spacy_repo_path)
            print(f"[Stage 1] [OK] spaCy NER model loaded successfully from {spacy_repo_path}\n")
        except Exception as e:
            print(f"[Stage 1] [FAILED] Could not load spaCy model: {e}")
            raise
        
        # ============ Stage 2: Load DistilBERT Intent Classifier ============
        print("[Stage 2] Loading DistilBERT intent classifier from Hugging Face Hub...")
        try:
            model_repo = "mojad121/distill-bert-intent-classifer"
            self.distilbert_model = AutoModelForSequenceClassification.from_pretrained(model_repo)
            self.distilbert_tokenizer = AutoTokenizer.from_pretrained(model_repo)
            
            # Set to evaluation mode (disable dropout, batch norm)
            self.distilbert_model.eval()
            
            print("[Stage 2] [OK] DistilBERT intent classifier loaded successfully\n")
        except Exception as e:
            print(f"[Stage 2] [FAILED] Could not load DistilBERT model: {e}")
            raise
        
        # ============ Stage 3: Initialize ML Model Wrappers ============
        print("[Stage 3] Wiring ML model wrappers...")
        self.entity_extractor = EntityExtractor(self.spacy_nlp)
        self.intent_classifier = IntentClassifier(self.distilbert_model, self.distilbert_tokenizer)
        print("[Stage 3] [OK] ML model wrappers initialized\n")
        
        print("[SentinelPipeline] [OK] Pipeline initialization complete\n")
    
    def _load_spacy_model_from_path(self, model_path: str) -> spacy.Language:
        """
        Load a spaCy model from a local path, handling various directory structures.
        
        Supports:
        - Standard spaCy models with config.cfg
        - HF-hosted models with meta.json and component directories
        - Nested model directories
        
        Args:
            model_path: Path to the model directory
        
        Returns:
            Loaded spaCy Language model
        
        Raises:
            FileNotFoundError: If a valid model cannot be loaded
        """
        # Try standard spaCy model format first (with config.cfg)
        if os.path.exists(os.path.join(model_path, "config.cfg")):
            print(f"  [spaCy] Loading standard model format from {model_path}")
            return spacy.load(model_path)
        
        # Try common nested structures
        for subdir in ["spacy_model", "model", "spacy-model"]:
            subdir_path = os.path.join(model_path, subdir)
            if os.path.isdir(subdir_path) and os.path.exists(os.path.join(subdir_path, "config.cfg")):
                print(f"  [spaCy] Loading model from nested directory: {subdir_path}")
                return spacy.load(subdir_path)
        
        # Try HF-style model with meta.json and component directories
        meta_path = os.path.join(model_path, "meta.json")
        if os.path.exists(meta_path):
            print(f"  [spaCy] Loading HF-style model with meta.json from {model_path}")
            try:
                # Load as a spaCy model directory (spaCy may support this format)
                # If this fails, we'll need to create a config.cfg
                return spacy.load(model_path)
            except (OSError, ValueError) as e:
                print(f"  [spaCy] Standard load failed, creating config.cfg: {e}")
                # Create a minimal config.cfg if it doesn't exist
                self._create_minimal_spacy_config(model_path, meta_path)
                return spacy.load(model_path)
        
        # Fallback: search for config.cfg recursively
        for root, dirs, files in os.walk(model_path):
            if "config.cfg" in files:
                print(f"  [spaCy] Found model at: {root}")
                return spacy.load(root)
        
        raise FileNotFoundError(
            f"Could not load spaCy model from {model_path}. "
            "Expected either config.cfg or meta.json with components."
        )
    
    def _create_minimal_spacy_config(self, model_path: str, meta_path: str) -> None:
        """
        Create a minimal but complete config.cfg for HF-style spaCy models.
        
        Works with models that have meta.json but lack config.cfg,
        which is common for HF-hosted spaCy models. Includes all required
        spaCy configuration fields with sensible defaults.
        
        Args:
            model_path: Root path of the model
            meta_path: Path to meta.json
        """
        config_path = os.path.join(model_path, "config.cfg")
        if os.path.exists(config_path):
            return
        
        # Read metadata to determine pipeline configuration
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
        except Exception as e:
            print(f"  [Warning] Could not read meta.json: {e}")
            return
        
        # Get the pipeline components and format as a list
        pipeline_list = meta.get("pipeline", [])
        pipeline_str = json.dumps(pipeline_list)
        
        # Create a complete spaCy config with all required sections and fields
        config_content = f"""[nlp]
lang = "{meta.get('lang', 'en')}"
pipeline = {pipeline_str}
disabled = []
batch_size = 128

[nlp.tokenizer]
@tokenizers = "spacy.Tokenizer.v1"

[components]

[system]
gpu_allocator = null
seed = 0
"""
        
        # Add component configuration sections
        for component_name in pipeline_list:
            component_dir = os.path.join(model_path, component_name)
            if os.path.isdir(component_dir):
                config_content += f'\n[components.{component_name}]\nfactory = "{component_name}"\n'
        
        # Append required lifecycle callbacks
        config_content += f"""
[initialize]

[initialize.components]

[initialize.tokenizer]
"""
        
        # Write the config file
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(config_content)
            print(f"  [OK] Created config.cfg with all required fields")
        except Exception as e:
            print(f"  [Warning] Could not create config.cfg: {e}")
    
    def analyze_text(self, text: str) -> Dict[str, Any]:
        """
        Analyze vulnerability patch requirements using NER and intent classification.
        
        Processing pipeline:
        1. Entity Extraction (Stage 1): Uses EntityExtractor to identify VERSION_RANGE, 
           API_SYMBOL, BREAKING_CHANGE, FIX_ACTION entities in the input text.
        2. Intent Classification (Stage 2): Uses IntentClassifier to predict the repair 
           intent (VERSION_PIN, API_MIGRATION, MONKEY_PATCH, FULL_REFACTOR) with confidence.
        
        Args:
            text: Input text describing the vulnerability or required patch
        
        Returns:
            Dictionary with structured analysis results:
            {
                "status": "success",
                "timestamp": "<iso_format_timestamp>",
                "input_text": "<original_text>",
                "analysis": {
                    "intent": {
                        "prediction": "<e.g., VERSION_PIN>",
                        "confidence": <float_0_to_1>
                    },
                    "breaking_changes": [list of breaking change dicts],
                    "migration_steps": [list of step strings]
                }
            }
        
        On error:
            {
                "status": "error",
                "timestamp": "<iso_format_timestamp>",
                "input_text": "<original_text>",
                "error": "<error_message>"
            }
        """
        try:
            # ============ Stage 1: Entity Extraction ============
            breaking_changes, migration_steps = self.entity_extractor.extract(text)
            
            # ============ Stage 2: Intent Classification ============
            intent_label, confidence_score = self.intent_classifier.classify(text)
            
            # ============ Build Structured Response ============
            result = {
                "status": "success",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "input_text": text,
                "analysis": {
                    "intent": {
                        "prediction": intent_label,
                        "confidence": round(confidence_score, 4)
                    },
                    "breaking_changes": breaking_changes,
                    "migration_steps": migration_steps
                }
            }
            
            return result
        
        except Exception as error:
            # Return error response maintaining schema
            return {
                "status": "error",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "input_text": text,
                "error": f"{type(error).__name__}: {str(error)}"
            }


def main():
    """
    Main execution block: instantiate the pipeline and run test analysis.
    
    Demonstrates end-to-end functionality with a realistic vulnerability
    patch scenario text, then pretty-prints the JSON-structured output.
    """
    try:
        # ============ Initialize Pipeline ============
        print("=" * 80)
        print(" SENTINEL-D NLP PIPELINE ORCHESTRATOR — INITIALIZATION")
        print("=" * 80 + "\n")
        
        pipeline = SentinelPipeline()
        
        # ============ Test Scenario ============
        # Sample text describing a Log4j vulnerability and patch strategy
        test_text = (
            "We need to migrate away from the deprecated JndiLookup class "
            "and pin the Log4j dependency to version >= 2.15.0 to patch the vulnerability."
        )
        
        print("=" * 80)
        print(" TEST SCENARIO")
        print("=" * 80)
        print(f"\n[Input Text]\n{test_text}\n")
        
        # ============ Run Analysis ============
        print("[Processing] Running Stage 1 (spaCy NER) + Stage 2 (DistilBERT)...\n")
        result = pipeline.analyze_text(test_text)
        
        # ============ Output Results ============
        print("=" * 80)
        print(" ANALYSIS OUTPUT (JSON)")
        print("=" * 80)
        print(json.dumps(result, indent=4))
        print("\n" + "=" * 80 + "\n")
        
    except Exception as error:
        print(f"\n[FATAL ERROR] {type(error).__name__}: {str(error)}\n")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()