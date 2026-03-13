# Sentinel-D — Killer Q&A Answers

Prepared answers for the five most likely judge questions, grounded in the
actual implementation.

---

## Q1: What does Sentinel-D do that no existing tool does today?

Sentinel-D is the first system that **closes the full loop** from vulnerability
detection to validated remediation — autonomously, with graduated safety controls.

Three capabilities that no existing tool combines:

1. **Telemetry-driven triage**: Before generating a patch, Sentinel-D queries
   Application Insights to determine if the vulnerable code is actually called
   in production. Dependabot, Snyk, and Copilot Autofix all treat every
   vulnerability equally. Sentinel-D distinguishes between a critical CVE in a
   hot API endpoint (ACTIVE) and the same CVE in dead code (DORMANT).

2. **Cross-repository learning**: Every resolution is stored in a Historical
   Database (Cosmos DB). When the same CVE appears in a different repo,
   Sentinel-D replays the proven fix via RAG — without calling the LLM. This
   cuts resolution time from ~5 minutes to ~90 seconds and ensures failed
   strategies are never repeated.

3. **Validated, graduated autonomy**: Patches aren't just generated — they're
   tested in ephemeral sandboxes with SSIM visual regression, then routed
   through a four-tier Safety Governor. High-confidence patches auto-merge;
   low-confidence ones escalate to humans. No other tool provides this
   spectrum of trust.

---

## Q2: What happens if the AI generates a patch that passes tests but introduces a subtle logic regression?

This is exactly the scenario our Safety Governor and sandbox validation are
designed to catch at multiple layers:

**Layer 1 — SSIM Visual Regression**: After applying the patch, we capture
screenshots of key UI states and compare them against baseline images using
Structural Similarity Index (SSIM). A visual regression flag forces the
confidence tier to MEDIUM minimum, requiring human review.

**Layer 2 — Coverage Delta Analysis**: We measure test coverage before and
after the patch. A coverage decrease indicates untested code paths were
affected — this lowers the confidence score.

**Layer 3 — Override Conditions**: If the patch touches authentication or
cryptographic code (`touches_auth_crypto === true`), the tier is forced to
LOW minimum regardless of test results. Full refactors are forced to MEDIUM.

**Layer 4 — Historical Anti-Repetition**: If a previous patch for the same
CVE caused a regression, it's recorded in the Historical DB with outcome
`FAILED` and the failure reason. Future patch generation receives this as a
hard constraint in `solutions_to_avoid` — the LLM is explicitly told not to
repeat the approach.

**Layer 5 — Audit Trail**: Every decision is logged to an append-only audit
log in Azure Table Storage. If a regression does slip through, the complete
reasoning chain, confidence score, override conditions, and test results are
available for forensic analysis.

The system is designed so that **the cost of a false positive (unnecessary
human review) is always preferred over a false negative (bad patch auto-merged)**.
Override conditions can only downgrade tiers, never upgrade them.

---

## Q3: What makes this different from GitHub Copilot Autofix?

We love Copilot Autofix — it's one of the best tools in GHAS. But it operates
at a fundamentally different scope:

| Dimension | Copilot Autofix | Sentinel-D |
|-----------|----------------|------------|
| **Scope** | Single-file fix suggestions | Full pipeline: triage → patch → test → merge |
| **Validation** | None — developer must verify | Ephemeral sandbox with full test suite + SSIM |
| **Learning** | Stateless — no memory | Historical DB remembers every resolution |
| **Triage** | None — all alerts treated equally | KQL telemetry classifies ACTIVE/DORMANT/DEFERRED |
| **Autonomy** | Manual — developer applies fix | Graduated: auto-merge → review → escalate → block |
| **Anti-repetition** | None | solutions_to_avoid prevents repeating failed strategies |

Think of Copilot Autofix as a brilliant pair programmer who suggests fixes.
Sentinel-D is an autonomous SRE that triages, fixes, validates, and deploys —
with guardrails. They're complementary: Copilot Autofix handles the "fix this
specific line" cases; Sentinel-D handles the "this CVE affects 50 repos across
the org" cases.

---

## Q4: How do you prevent the KQL generator from being used to exfiltrate telemetry data?

This was a Day 1 security design decision. The KQL generator uses Foundry
(LLM) to produce queries, which means we treat its output as **untrusted input**.

**Allowlist Validator** (`/sre-agent/kql_validator.py`):

Every generated KQL query passes through a strict allowlist validator before
execution. The validator blocks:

- `externaldata` — prevents reading from external URLs
- `http_request` — prevents outbound HTTP calls
- `invoke` — prevents calling external functions
- `evaluate` — prevents dynamic code evaluation
- `plugins` — prevents loading external plugins

It also restricts which tables can be queried:
- **Allowed**: `traces`, `requests`, `exceptions`, `dependencies`
- **Blocked**: Everything else (custom tables, security logs, etc.)

The validator runs **before** the query reaches Application Insights. If any
blocked keyword or unauthorized table is detected, the query is rejected with
a structured error and the SRE Agent falls back to a safe default query.

This is tested with 16 dedicated unit tests covering edge cases like
case-insensitive matching, substring false positives, and comment-based
evasion attempts.

---

## Q5: Why Cosmos DB instead of a relational database?

Three specific architectural reasons:

**1. Schema flexibility**: Historical DB records have variable-length
`solutions_tried` arrays. Each entry has different fields depending on the
failure reason. In a relational model, this requires a separate table with
JOINs. In Cosmos DB, it's a nested array in the document — one read returns
everything the pipeline needs.

**2. Partition key optimization**: Every lookup starts with a CVE ID.
Cosmos DB's partition key (`/cve_id`) gives O(1) exact lookups without an
index scan. For the RAG replay path, this is the difference between sub-second
and multi-second latency.

**3. Embedding storage**: Each record contains a 1536-dimension embedding
vector (from `text-embedding-3-small`). Cosmos DB stores this as a native
array field in the document — no serialization, no separate vector store.
The cosine similarity computation runs in-memory (numpy) after retrieval,
which is faster and cheaper than a managed vector search service for our
volume (~100s of records, not millions).

**Cost**: Cosmos DB Serverless tier charges only for consumed RUs with zero
minimum. For our demo volume (~10 records, ~50 queries/day), this costs
fractions of a cent — well within the $20 budget.
