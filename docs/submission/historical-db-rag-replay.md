# Historical Database & RAG Replay — The Learning Flywheel

## The Key Innovation

Most security tools treat every vulnerability as a fresh problem. Sentinel-D
remembers. Every resolved vulnerability — its CVE, the strategy that worked,
the strategies that failed, the patch diff, and the outcome — is stored in a
Historical Database. When a similar vulnerability appears (even in a completely
different repository), Sentinel-D can replay the proven fix without invoking
the LLM at all.

This is the **learning flywheel**: the more vulnerabilities Sentinel-D resolves,
the faster and more accurate it becomes.

## Architecture

```
New CVE Alert
  → Cosmos DB Exact Lookup (partition key: /cve_id)
      ├─ EXACT_MATCH → RAG Replay Path
      │     ├─ Language match? ──┐
      │     ├─ git apply --check ─┤─ Both pass → Skip Foundry, use cached patch
      │     └─ Failure → append to solutions_tried[], fall through
      │
      ├─ In-Memory Cosine Similarity (numpy, threshold 0.88)
      │     └─ SEMANTIC_MATCH → Enrich context with past solutions
      │
      └─ NO_MATCH → Full pipeline (Foundry LLM)

After Resolution:
  → Write record to Cosmos DB (patch_diff, outcome, solutions_tried)
  → Future lookups benefit immediately
```

## RAG Replay Path

When an exact CVE match is found:

1. **Structural compatibility check**:
   - Language match (e.g., both Java)
   - `git apply --check` to verify the cached patch applies cleanly

2. **If replay succeeds**:
   - Foundry API is **never called** (verified via App Insights logs)
   - Confidence score receives +0.05 RAG replay bonus
   - Source field set to `RAG_REPLAY` (visible in PR body)
   - Resolution time drops from ~5 minutes to ~90 seconds

3. **If replay fails**:
   - Failed strategy appended to `solutions_tried[]`
   - `solutions_to_avoid` populated for the full pipeline
   - Falls through to Foundry with enriched context

## Anti-Repetition: solutions_to_avoid

The Historical Database doesn't just remember what worked — it remembers what
*didn't* work. Failed strategies from `solutions_tried` are injected into the
Patch Generator's Section 4 (constraints) as hard blockers:

```
SECTION 4 — CONSTRAINTS
You MUST NOT use any of these strategies (they have been tried and failed):
  - VERSION_PIN: "Test suite failures in auth module"
```

If the LLM's reasoning chain mentions a blocked strategy, a -0.20 penalty is
applied to the confidence score, pushing the patch toward human review.

## Cosmos DB Design

- **Partition key**: `/cve_id` — enables O(1) exact lookups
- **Serverless tier**: No provisioned throughput charges (stays under $20 budget)
- **Embedding field**: `cve_description_embedding` — 1536-dim vector from
  `text-embedding-3-small`, stored as array in document
- **Similarity search**: In-memory cosine similarity (numpy) with 0.88 threshold
  — Azure AI Search removed for cost optimization

## Impact

| Metric | Cold Start (No History) | With Historical DB |
|--------|------------------------|--------------------|
| Resolution time | ~5 minutes | ~90 seconds |
| Foundry API calls | 1 per CVE | 0 (RAG replay) |
| Confidence score | Base | +0.05 bonus |
| Cost per resolution | ~$0.15 (LLM) | ~$0.001 (DB lookup) |
| Failed strategy repetition | Possible | Impossible |
