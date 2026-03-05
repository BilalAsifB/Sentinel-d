# Day 9 — 10-CVE Integration Test Results

**Date:** 2026-03-05
**Engineers:** Dev A + Dev B
**Mode:** MOCK (local validation — no deployed Azure infra)

---

## Per-CVE Results

| # | CVE ID | Type | Expected Path | Webhook | Classification | Routing | Sandbox | PR/Issue | Time (ms) |
|---|--------|------|---------------|---------|----------------|---------|---------|----------|-----------|
| 0 | CVE-2021-44228 | ACTIVE + SEEDED | EXACT_MATCH → RAG replay | ✅ | ✅ ACTIVE (0.95) | ✅ nlp-pipeline-input | ⏳ | ⏳ | 98 |
| 1 | CVE-2020-9547 | ACTIVE + SEEDED | EXACT_MATCH → RAG replay | ✅ | ✅ ACTIVE (0.95) | ✅ nlp-pipeline-input | ⏳ | ⏳ | 61 |
| 2 | CVE-2023-44487 | ACTIVE | Full pipeline | ✅ | ✅ ACTIVE (0.95) | ✅ nlp-pipeline-input | ⏳ | ⏳ | 48 |
| 3 | CVE-2024-3094 | ACTIVE | Full pipeline | ✅ | ✅ ACTIVE (0.95) | ✅ nlp-pipeline-input | ⏳ | ⏳ | 47 |
| 4 | CVE-2023-34362 | DORMANT | Decision Gate issue | ✅ | ✅ DORMANT (0.70) | ✅ Decision Gate | N/A | ⏳ | 49 |
| 5 | CVE-2023-0286 | ACTIVE | Full pipeline | ✅ | ✅ ACTIVE (0.95) | ✅ nlp-pipeline-input | ⏳ | ⏳ | 49 |
| 6 | CVE-2022-22965 | ACTIVE | Full pipeline | ✅ | ✅ ACTIVE (0.95) | ✅ nlp-pipeline-input | ⏳ | ⏳ | 47 |
| 7 | CVE-2023-36884 | DORMANT | Decision Gate issue | ✅ | ✅ DORMANT (0.70) | ✅ Decision Gate | N/A | ⏳ | 43 |
| 8 | CVE-2024-21626 | ACTIVE | Full pipeline | ✅ | ✅ ACTIVE (0.95) | ✅ nlp-pipeline-input | ⏳ | ⏳ | 41 |
| 9 | CVE-2023-32315 | ACTIVE | Full pipeline | ✅ | ✅ ACTIVE (0.95) | ✅ nlp-pipeline-input | ⏳ | ⏳ | 44 |

**Legend:** ✅ = passed, ⏳ = requires live Azure infra (not tested in mock)

---

## RAG Replay vs Full Pipeline Comparison

| Metric | RAG Replay (seeded CVEs) | Full Pipeline (new CVEs) |
|--------|--------------------------|--------------------------|
| Webhook → PR time | ⏳ (live test required) | ⏳ (live test required) |
| Foundry API called? | NO (verify in App Insights) | YES |
| Historical DB match type | EXACT_MATCH | NO_MATCH |

---

## Container App Spin-up Times

> ⏳ Requires live Azure Container Apps deployment. Not measured in mock mode.

| CVE # | Spin-up (s) | Teardown confirmed? |
|-------|-------------|---------------------|
| 0 | ⏳ | ⏳ |
| 1 | ⏳ | ⏳ |
| 2 | ⏳ | ⏳ |
| 3 | ⏳ | ⏳ |
| 5 | ⏳ | ⏳ |
| 6 | ⏳ | ⏳ |
| 8 | ⏳ | ⏳ |
| 9 | ⏳ | ⏳ |

---

## Timing Summary (Mock Mode — Local Validation Only)

| Metric | Min | Max | Median |
|--------|-----|-----|--------|
| Webhook schema validation | 7ms | 63ms | 13ms |
| SRE Agent classification | 30ms | 36ms | 35ms |
| Webhook → PR (all) | ⏳ | ⏳ | ⏳ |
| Webhook → PR (RAG replay) | ⏳ | ⏳ | ⏳ |
| Webhook → PR (full pipeline) | ⏳ | ⏳ | ⏳ |
| Container App spin-up | ⏳ | ⏳ | ⏳ |

---

## Decision Gate Verification

| CVE # | Issue template valid? | Issue # | Label applied | Result |
|-------|----------------------|---------|---------------|--------|
| 4 (CVE-2023-34362) | ✅ (mock) | ⏳ | `sentinel/fix-now` | ⏳ Re-enter pipeline (live test) |
| 7 (CVE-2023-36884) | ✅ (mock) | ⏳ | `sentinel/defer` | ⏳ DEFERRED record (live test) |

---

## Dead-Letter Queue

- **Messages at end of test:** 0 (mock — assumed)
- **Expected:** 0

---

## Historical DB Seeding Status

- **CVE-2021-44228 (Log4Shell):** ✅ Schema validated, strategy: API_MIGRATION, outcome: SUCCESS
- **CVE-2020-9547 (Jackson):** ✅ Schema validated, strategy: VERSION_PIN, outcome: SUCCESS
- **Live Cosmos DB write:** ❌ Blocked — `COSMOS_DB_ENDPOINT` env var not set in write-client (`.env` uses `COSMOS_ENDPOINT`). Fix: align env var names or add `COSMOS_DB_ENDPOINT` to `.env`.

---

## Success Criteria

- [x] 10/10 CVEs processed without infrastructure failures (mock mode)
- [x] 2/2 DORMANT events produced valid Decision Gate issue templates
- [ ] `fix-now` label re-triggered the pipeline correctly (requires live GitHub)
- [ ] `defer` label wrote DEFERRED record to Table Storage (requires live Azure)
- [x] 2/2 seeded CVEs validated for Historical DB match path
- [x] Benchmarks documented above (mock timing only)
- [x] Dead-letter queue empty (mock)
- [ ] Both engineers sign off on results

---

## Blockers for Live Test

1. **Cosmos DB env var mismatch:** `write-client.js` reads `COSMOS_DB_ENDPOINT`, but `.env` defines `COSMOS_ENDPOINT`. Need to add `COSMOS_DB_ENDPOINT` alias or update write-client.
2. **No WEBHOOK_URL configured:** Azure Function webhook not deployed or URL not in `.env`.
3. **No SERVICE_BUS_NAMESPACE configured:** Service Bus not set up for live routing verification.
4. **Dev A coordination required:** Joint test needs both engineers monitoring simultaneously.

---

## Sign-off

- **Dev A:** _________________ Date: _________
- **Dev B:** _________________ Date: _________

## Notes

- Mock integration test: **32/32 checks passed** on 2026-03-05T23:55:26Z
- All webhook payloads pass `webhook_payload.json` schema validation
- SRE Agent classifier correctly identifies ACTIVE (call_count > 0) and DORMANT (call_count = 0)
- Decision Gate issue templates include `sentinel-metadata` block and all three label options
- Historical DB seed records pass `historical_db_record.json` schema validation
- Placeholder 384-dim zero vector used for `cve_description_embedding` (Dev A owns real embeddings)
