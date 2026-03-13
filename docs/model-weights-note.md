# Model Weights Note

## spaCy NER Model

The NLP pipeline uses a **fine-tuned spaCy NER model** trained on 500 NVD descriptions.

- **Production model**: `spacy-nvd-ner-v1.zip` (hosted at `mojad121/spacy-classes-finetune`)
- **Target entities**: `VERSION_RANGE`, `API_SYMBOL`, `BREAKING_CHANGE`, `FIX_ACTION`
- **Training script**: `/nvd_spacy.py` (Stage 1 fine-tuning pipeline)
- **Fallback**: `en_core_web_sm` base model when fine-tuned weights unavailable

When running with the base model, custom entity types (VERSION_RANGE, etc.) will
not be extracted. The pipeline returns sensible defaults in this case.

## DistilBERT Intent Classifier

The classifier uses a **fine-tuned DistilBERT** model for 4-class strategy classification.

- **Production model**: `distilbert-intent-classifier-v1.zip` (hosted at `mojad121/distill-bert-intent-classifer`)
- **Intent classes**: `VERSION_PIN`, `API_MIGRATION`, `MONKEY_PATCH`, `FULL_REFACTOR`
- **Training script**: `/ml_model_fine_tuning.py` (Stage 2 fine-tuning pipeline)
- **Training data**: 1200 labelled Stack Overflow answers in `/nlp-pipeline/data/labelled/`
- **Fallback**: Random classifier head on `distilbert-base-uncased` — outputs are valid
  but untrained, suitable for demo/integration testing

Both models are downloaded automatically from HuggingFace Hub at pipeline startup,
with local `.zip` fallback if network is unavailable.
