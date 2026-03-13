# Architecture Overview

## Pipeline Flow

```
GHAS Alert
  → Azure Function (webhook receiver + AJV schema validation)
  → Service Bus (vulnerability-events queue)
  → SRE Agent (KQL generation → App Insights query → ACTIVE/DORMANT/DEFERRED)
      ├─ DORMANT → Human Decision Gate (GitHub Issue + label handlers)
      ├─ DEFERRED → Table Storage backlog (re-evaluated by Logic App daily)
      └─ ACTIVE  → Historical DB Lookup (Cosmos DB exact + cosine similarity)
                      ├─ EXACT_MATCH/SEMANTIC_MATCH → RAG Replay (skip Foundry)
                      └─ NO_MATCH → NLP Pipeline (spaCy NER + DistilBERT)
                                      → Patch Generator (Foundry, 4-section prompt)
                                      → Sandbox Validator (Container App + SSIM)
                                      → Safety Governor (composite score → tier)
                                      → PR / Issue / Archive
                                      → Historical DB Write (Cosmos DB record)
```

## Component Map

| Component | Language | Location | Azure Service |
|-----------|----------|----------|---------------|
| Webhook Receiver | Node.js | `/azure-functions/webhook-receiver/` | Azure Functions |
| SRE Agent | Python | `/sre-agent/` | Service Bus consumer |
| NLP Pipeline | Python | `/nlp-pipeline/` | Azure ML (optional) |
| Historical DB | Node.js + Python | `/historical-db/` + `/nlp-pipeline/historical_db/` | Cosmos DB |
| Patch Generator | Python | `/agents/patch_generator/` | Microsoft Foundry |
| Sandbox Validator | Node.js + Python | `/sandbox-validator/` | Container Apps |
| Safety Governor | Node.js | `/safety-governor/` | Table Storage (audit) |
| Human Decision Gate | Node.js | `/safety-governor/` | GitHub Issues |
| Auto-Escalation | ARM template | `/infrastructure/` | Logic Apps |
| Backlog Re-scan | ARM template | `/infrastructure/` | Logic Apps |

## Architecture Diagram

See `/docs/architecture-v3.png` for the visual diagram.

## Key Design Decisions

### Event-Driven Architecture
Azure Service Bus decouples the webhook receiver from downstream processing.
Dead-letter queues catch failures after 3 retries, and a dead-letter handler
creates GitHub Issues for human investigation.

### Historical Learning Database
Cosmos DB with partition key `/cve_id` enables O(1) exact lookups. In-memory
cosine similarity (numpy, threshold 0.88) finds semantically similar past
resolutions when exact matches don't exist. This "learning flywheel" means
Sentinel-D gets faster and more accurate with every resolved vulnerability.

### Ephemeral Sandboxes
Each patch validation runs in a fresh Azure Container App instance with a
unique name. The container tears down on ALL code paths (success, failure,
error) via `if: always()` in the workflow. SSIM visual regression testing
catches UI regressions that unit tests miss.

### Four-Tier Safety Governor
Confidence scores map to graduated autonomy:
- HIGH (≥0.85): Auto-merge — no human needed
- MEDIUM (≥0.70): PR with review required
- LOW (≥0.55): GitHub Issue escalation + PagerDuty
- BLOCKED (<0.55): Archive + security team alert

Override conditions (visual regression, auth/crypto changes, infrastructure
failures) can only *downgrade* a tier, never upgrade.
