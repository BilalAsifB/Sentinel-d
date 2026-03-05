# Day 9 — 10-CVE Integration Test Results

**Date:** 2026-03-05
**Engineers:** Dev A + Dev B
**Mode:** MOCK / LIVE (circle one)

---

## Per-CVE Results

| # | CVE ID | Type | Expected Path | Webhook | Classification | Routing | Sandbox | PR/Issue | Time (s) |
|---|--------|------|---------------|---------|----------------|---------|---------|----------|----------|
| 0 | CVE-2021-44228 | ACTIVE + SEEDED | EXACT_MATCH → RAG replay | | | | | | |
| 1 | CVE-2020-9547 | ACTIVE + SEEDED | EXACT_MATCH → RAG replay | | | | | | |
| 2 | CVE-2023-44487 | ACTIVE | Full pipeline | | | | | | |
| 3 | CVE-2024-3094 | ACTIVE | Full pipeline | | | | | | |
| 4 | CVE-2023-34362 | DORMANT | Decision Gate issue | | | | | | |
| 5 | CVE-2023-0286 | ACTIVE | Full pipeline | | | | | | |
| 6 | CVE-2022-22965 | ACTIVE | Full pipeline | | | | | | |
| 7 | CVE-2023-36884 | DORMANT | Decision Gate issue | | | | | | |
| 8 | CVE-2024-21626 | ACTIVE | Full pipeline | | | | | | |
| 9 | CVE-2023-32315 | ACTIVE | Full pipeline | | | | | | |

---

## RAG Replay vs Full Pipeline Comparison

| Metric | RAG Replay (seeded CVEs) | Full Pipeline (new CVEs) |
|--------|--------------------------|--------------------------|
| Webhook → PR time | | |
| Foundry API called? | NO (verify in App Insights) | YES |
| Historical DB match type | EXACT_MATCH | NO_MATCH |

---

## Container App Spin-up Times

| CVE # | Spin-up (s) | Teardown confirmed? |
|-------|-------------|---------------------|
| 0 | | |
| 1 | | |
| 2 | | |
| 3 | | |
| 5 | | |
| 6 | | |
| 8 | | |
| 9 | | |

---

## Timing Summary

| Metric | Min | Max | Median |
|--------|-----|-----|--------|
| Webhook → PR (all) | | | |
| Webhook → PR (RAG replay) | | | |
| Webhook → PR (full pipeline) | | | |
| Container App spin-up | | | |
| SRE Agent classification | | | |

---

## Decision Gate Verification

| CVE # | Issue created? | Issue # | Label applied | Result |
|-------|----------------|---------|---------------|--------|
| 4 (CVE-2023-34362) | | | `sentinel/fix-now` | Re-entered pipeline? |
| 7 (CVE-2023-36884) | | | `sentinel/defer` | DEFERRED in Table Storage? |

---

## Dead-Letter Queue

- **Messages at end of test:** ___
- **Expected:** 0

---

## Success Criteria

- [ ] 10/10 CVEs processed without infrastructure failures
- [ ] 2/2 DORMANT events created GitHub Issues with correct templates
- [ ] `fix-now` label re-triggered the pipeline correctly
- [ ] `defer` label wrote DEFERRED record to Table Storage
- [ ] 2/2 seeded CVEs used RAG replay path (Foundry not called)
- [ ] All benchmarks documented above
- [ ] Dead-letter queue empty at EOD
- [ ] Both engineers sign off on results

---

## Sign-off

- **Dev A:** _________________ Date: _________
- **Dev B:** _________________ Date: _________

## Notes

_Record any issues, bugs, or observations here._
