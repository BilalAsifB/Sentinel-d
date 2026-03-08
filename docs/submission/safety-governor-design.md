# Safety Governor Design

## Overview

The Safety Governor is the final decision point in the Sentinel-D pipeline.
It takes a validated patch with a composite confidence score and routes it
to one of four tiers — from fully autonomous auto-merge to human escalation.

## Four-Tier Routing

| Tier | Score Range | Action | Human Involvement |
|------|------------|--------|-------------------|
| **HIGH** | S ≥ 0.85 | `AUTO_PR` — auto-merge eligible | None |
| **MEDIUM** | 0.70 ≤ S < 0.85 | `REVIEW_PR` — PR with review required | Review before merge |
| **LOW** | 0.55 ≤ S < 0.70 | `GITHUB_ISSUE_ESCALATE` + PagerDuty | Security team triage |
| **BLOCKED** | S < 0.55 | `ARCHIVE` + security team alert | Full manual investigation |

## Override Conditions

Six conditions can **downgrade** a tier (never upgrade). They fire regardless
of the confidence score:

| Condition | Forced Minimum Tier | Rationale |
|-----------|-------------------|-----------|
| `visual_regression === true` | MEDIUM | UI changes need human eyes |
| `fix_strategy === 'FULL_REFACTOR'` | MEDIUM | Refactors are too complex for auto-merge |
| `touches_auth_crypto === true` | LOW | Security-sensitive changes must be reviewed |
| `candidatePatch.status === 'CANNOT_PATCH'` | BLOCKED | No valid patch exists |
| `tests_failed === -1` (infrastructure failure) | BLOCKED | Sandbox couldn't run — unknown state |
| `tests_failed === -2` (patch apply failure) | BLOCKED | Patch doesn't apply cleanly |

## Composite Confidence Score

The score combines 5 weighted signals:

```
score = (log_prob × 0.40) + (constraint_adherence × 0.35) + (nlp_alignment × 0.25)
      + rag_bonus        // +0.05 if source === RAG_REPLAY
      - avoidance_penalty // -0.20 if reasoning mentions solutions_to_avoid
```

## PR Body Contents

Every generated PR includes:

- **CVE ID, severity, affected package** — from the original alert
- **Confidence tier + composite score** — displayed to 2 decimal places
- **Source** — `FOUNDRY` or `RAG_REPLAY`
- **Sandbox results** — tests passed, coverage delta, visual regression status
- **Link to sandbox test log** — full test output
- **Link to LLM reasoning chain** — step-by-step explanation
- **Warning banner** — displayed for MEDIUM tier PRs

## Actions Per Tier

### HIGH (AUTO_PR)
1. Create PR via GitHub API with full body
2. Write SUCCESS record to Historical DB
3. Append audit log entry (Table Storage)
4. Log to Application Insights

### MEDIUM (REVIEW_PR)
1. Create PR with ⚠️ warning banner
2. Write PARTIAL record to Historical DB
3. Append audit log entry
4. Request review from CODEOWNERS

### LOW (GITHUB_ISSUE_ESCALATE)
1. Create GitHub Issue with full context
2. Write FAILED record to Historical DB
3. Append audit log entry
4. Trigger PagerDuty alert

### BLOCKED (ARCHIVE)
1. Archive the validation bundle
2. Write FAILED record to Historical DB
3. Append audit log entry
4. Alert security team channel

## Audit Trail

Every Safety Governor decision is recorded in Azure Table Storage as an
append-only audit log entry. Records are **never updated or deleted**.

Each entry contains:
- Timestamp, CVE ID, repository
- Confidence score and tier
- Override conditions that fired
- Action taken
- Source (FOUNDRY or RAG_REPLAY)
- Pipeline version
