# NLP Pipeline Technical Design

## Overview

The NLP Pipeline enriches raw CVE data with contextual intelligence from
multiple sources, producing a `structured_context.json` that drives
patch generation. It combines custom NER, intent classification, and
external knowledge retrieval into a single async pipeline.

## Architecture

```
CVE Alert Data
  → Historical DB Lookup (FIRST — before any API calls)
      ├─ EXACT_MATCH → skip to RAG Replay
      └─ NO_MATCH →
          ├─ NVD API Fetcher ──┐
          │                    ├─ asyncio.gather() (PARALLEL)
          └─ SO API Fetcher ──┘
                ↓
          spaCy NER (entity extraction)
                ↓
          DistilBERT Classifier (strategy classification)
                ↓
          structured_context.json
```

## Components

### 1. Historical DB Lookup (First Stage)

The pipeline queries Cosmos DB **before** making any external API calls:

- **Stage 1**: Exact CVE ID lookup via partition key (`/cve_id`)
- **Stage 2**: Cosine similarity search using `text-embedding-3-small`
  embeddings (1536-dim, numpy, threshold 0.88)

If a match is found, the pipeline populates:
- `historical_match_status`: `EXACT_MATCH` or `SEMANTIC_MATCH`
- `historical_patch_available`: `true`
- `solutions_to_avoid`: extracted from `solutions_tried` where outcome = `FAILED`
- `historical_record_id`: ID of the matching record

### 2. NVD API Fetcher

- Async HTTP client with exponential backoff retry
- Fetches CVE details, CVSS scores, affected configurations
- Handles NVD rate limiting (429 responses)
- Caches responses to avoid redundant API calls

### 3. Stack Overflow API Fetcher

- Async HTTP client querying SO Search API
- Returns top 5 answers sorted by score
- Extracts code snippets and accepted answer status
- Runs in PARALLEL with NVD fetcher via `asyncio.gather()`

### 4. spaCy NER Model

- **Base**: `en_core_web_sm`
- **Fine-tuned**: 500 NVD vulnerability descriptions
- **Custom entities**: `VERSION_RANGE`, `API_SYMBOL`, `BREAKING_CHANGE`, `FIX_ACTION`
- **Entity-level F1**: 0.83
- Graceful fallback to base model when fine-tuned weights unavailable

### 5. DistilBERT Intent Classifier

- **Base**: `distilbert-base-uncased`
- **Fine-tuned**: 1200 labelled Stack Overflow answers
- **4-class output**: `VERSION_PIN`, `API_MIGRATION`, `MONKEY_PATCH`, `FULL_REFACTOR`
- **Accuracy**: 84.2% | **Macro F1**: 0.81
- Returns confidence scores per class for downstream weighting

## Confidence Scoring

The composite confidence score combines 5 weighted signals:

| Signal | Weight | Source |
|--------|--------|--------|
| Log-probability | 40% | Foundry LLM response log-probs |
| Constraint adherence | 35% | Validates patch respects all constraints |
| NLP alignment | 25% | DistilBERT strategy matches generated approach |
| RAG replay bonus | +0.05 | Applied when source is RAG_REPLAY |
| solutions_to_avoid penalty | -0.20 | Applied when reasoning chain mentions avoided solutions |

## Output Schema

The pipeline produces `structured_context.json` with all v3.0 fields:

```json
{
  "cve_id": "CVE-2021-44228",
  "severity": "CRITICAL",
  "affected_package": "log4j-core",
  "affected_versions": "<2.15.0",
  "cve_description": "...",
  "nvd_data": { ... },
  "stackoverflow_solutions": [ ... ],
  "entities": { ... },
  "recommended_strategy": "API_MIGRATION",
  "strategy_confidence": 0.92,
  "historical_match_status": "EXACT_MATCH",
  "historical_patch_available": true,
  "historical_record_id": "demo-seed-log4shell",
  "solutions_to_avoid": ["VERSION_PIN"]
}
```
