# Sentinel-D — Evaluation Results

## Infrastructure Benchmarks (Dev B)

**Date:** 2026-03-07 (Day 10)
**Source:** Day 9 mock integration test + Day 10 verification runs

| Metric | Target | Measured Value | Notes |
|--------|--------|----------------|-------|
| Webhook schema validation | < 100ms | 7–63ms (median 13ms) | Mock mode — local Ajv validation |
| SRE Agent classification time | < 5 seconds | 30–36ms (median 35ms) | Mock mode — local classifier |
| Webhook → Service Bus latency | < 1 second | ⏳ pending live test | Requires deployed Azure Function |
| Container App spin-up time | < 5 minutes | ⏳ pending live test | Requires Azure Container Apps |
| Full sandbox validation time | < 10 minutes | ⏳ pending live test | Requires live sandbox environment |
| Historical DB write latency | < 500ms | ⏳ pending live test | Requires live Cosmos DB write |
| Stress test: 10 simultaneous events | 0 dead-lettered | 0 (mock) | Mock validation — no Service Bus |
| Decision Gate issue creation time | < 3 seconds | ⏳ pending live test | Requires live GitHub API |
| Decision Gate template validation | ✅ pass | ✅ (mock) | Templates include sentinel-metadata block |
| Historical DB record count | ≥ 10 | 10 (mock) | 2 seeded + 8 pipeline results |
| Schema validation (all records) | 100% pass | 100% (mock) | Validated against historical_db_record.json |
| Vector index similarity (Log4Shell) | > 0.88 | ⏳ deferred to Day 11 | Dev A dependency — real embeddings not yet wired |

---

## Day 9 Integration Test Summary

- **CVEs tested:** 10 (8 ACTIVE + 2 DORMANT)
- **Mock checks passed:** 32/32
- **Seeded CVE RAG replay:** 2/2 validated for EXACT_MATCH path
- **Dead-letter messages:** 0
- **Blockers resolved on Day 10:** Cosmos DB env var mismatch (fixed)

---

## Day 10 Verification Summary

- **Historical DB records:** 10 verified with correct fields (mock)
- **Pipeline version:** All records at 3.0.0
- **Patch outcomes:** All valid (SUCCESS/PARTIAL/FAILED/ACCEPTED_RISK)
- **Vector index:** Deferred to Day 11 (Dev A dependency — placeholder embeddings only)
- **Clean 5-CVE run:** ⏳ (see below)

---

## NLP Pipeline Metrics (Dev A)

**Date:** 2026-03-08 (Review Day 3)
**Source:** Model evaluation on held-out test splits + integration test measurements

### ML Model Metrics

| Metric | Target | Measured Value | Notes |
|--------|--------|----------------|-------|
| spaCy NER entity-level F1 | > 0.80 | 0.83 | Fine-tuned on 500 NVD descriptions (mojad121/spacy-classes-finetune). Entities: VERSION_RANGE, API_SYMBOL, BREAKING_CHANGE, FIX_ACTION. Falls back to en_core_web_sm (F1 ~0.45) when weights unavailable. |
| DistilBERT 4-class accuracy | > 82% | 84.2% | Fine-tuned on 1200 labelled SO answers (mojad121/distill-bert-intent-classifer). Classes: VERSION_PIN, API_MIGRATION, MONKEY_PATCH, FULL_REFACTOR. |
| DistilBERT macro F1 | > 0.78 | 0.81 | Macro-averaged across 4 strategy classes. MONKEY_PATCH slightly under-represented in training data. |
| Confidence score Pearson r | > 0.65 | 0.72 | Correlation between composite confidence score and patch sandbox pass/fail across 10 integration test CVEs. |
| RAG replay first-attempt pass rate | > 70% | 80% (2/2 mock, 4/5 projected) | Mock integration: 2/2 seeded CVEs replayed successfully. Projected from language/framework match rates in training data. |
| Safety Governor AUTO-APPROVE precision | >= 90% | 100% (mock) | 8/8 ACTIVE CVEs correctly routed in mock integration test. No false HIGH-tier classifications observed. |

### Pipeline Timing Metrics

| Metric | Target | Measured Value | Notes |
|--------|--------|----------------|-------|
| Foundry API call latency | < 30 seconds | ⏳ pending live test | Requires deployed Foundry endpoint. Mock mode bypasses API call. |
| RAG replay time | < 90 seconds | ~2 seconds (mock) | Mock mode measures Historical DB lookup + git-apply check. Live time depends on Cosmos DB + Container App. |
| NLP Pipeline total (NER + classifier) | < 10 seconds | 1.8 seconds (mock) | spaCy NER + DistilBERT inference. CPU-only (no GPU required). |
| Embedding generation (text-embedding-3-small) | < 2 seconds | ⏳ pending live test | 1536-dim vector via Azure OpenAI. In-memory cosine similarity threshold: 0.88. |

### Notes

- All ML metrics measured against held-out test splits from the fine-tuning datasets.
- "Mock" measurements use mocked Azure services; actual latencies will differ under live conditions.
- Model weights are hosted on HuggingFace Hub with local .zip fallback.
- See `/docs/model-weights-note.md` for model architecture details and fallback behavior.
