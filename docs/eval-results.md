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

> _To be filled by Dev A_

| Metric | Target | Measured Value | Notes |
|--------|--------|----------------|-------|
| spaCy NER F1 score | > 0.85 | | |
| DistilBERT intent accuracy | > 0.90 | | |
| Foundry API call latency | < 30 seconds | | |
| RAG replay time | < 90 seconds | | |
| Composite confidence score accuracy | > 0.80 | | |
