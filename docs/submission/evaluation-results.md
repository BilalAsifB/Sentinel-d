# Evaluation Results

Detailed evaluation metrics are maintained in [`/docs/eval-results.md`](/docs/eval-results.md).

## Summary

### ML Model Performance

| Model | Metric | Target | Achieved |
|-------|--------|--------|----------|
| spaCy NER | Entity-level F1 | > 0.80 | 0.83 |
| DistilBERT | 4-class accuracy | > 82% | 84.2% |
| DistilBERT | Macro F1 | > 0.78 | 0.81 |
| Confidence Score | Pearson r with validity | > 0.65 | 0.72 |
| RAG Replay | First-attempt pass rate | > 70% | 80% |
| Safety Governor | AUTO-APPROVE precision | ≥ 90% | 100% (mock) |

### Infrastructure Performance

| Metric | Target | Achieved |
|--------|--------|----------|
| Webhook schema validation | < 100ms | 7–63ms (median 13ms) |
| SRE Agent classification | < 5 seconds | 30–36ms (median 35ms) |
| Stress test (10 concurrent) | 0 dead-lettered | 0 |
| Schema validation rate | 100% pass | 100% |

### Test Suite

| Component | Tests | Status |
|-----------|-------|--------|
| shared/ (retry) | 16 | ✅ All pass |
| webhook-receiver | 14 | ✅ All pass |
| dead-letter-handler | 6 | ✅ All pass |
| safety-governor | 50 | ✅ All pass |
| historical-db | 4 (1 pass + 3 skipped) | ✅ Integration tests need live Cosmos |
| patch-generator | 10 | ✅ All pass |
| sandbox-validator | 9 | ✅ All pass |
| sre-agent (Python) | 48 | ✅ All pass |
| **Total** | **158** | **155 pass, 3 skipped** |

See [`/docs/eval-results.md`](/docs/eval-results.md) for full details including
integration test results and infrastructure benchmarks.
