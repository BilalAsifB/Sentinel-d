# Human-in-the-Loop Decision Gate

## Design Rationale

Not every vulnerability requires immediate automated action. When the SRE Agent
classifies a vulnerability as DORMANT — the affected code exists but receives
zero runtime telemetry — automated patching carries risk with no demonstrated
benefit. The Human Decision Gate gives security teams three clear options while
enforcing a 72-hour escalation deadline.

## Three-Way Classification

The SRE Agent's KQL-driven classifier produces one of three outcomes:

| Classification | Criteria | Action |
|---------------|----------|--------|
| **ACTIVE** | App Insights telemetry shows affected code paths are hit | → Full automated pipeline |
| **DORMANT** | Zero telemetry for affected code paths | → Human Decision Gate |
| **DEFERRED** | Previously deferred, re-evaluated by daily Logic App | → Backlog (re-scanned daily) |

## GitHub Issue Template

When a DORMANT vulnerability is detected, Sentinel-D creates a GitHub Issue with:

1. **CVE Data**: ID, severity, affected package and version range
2. **Telemetry Summary**: KQL query used, result showing zero hits
3. **Historical Context**: Past resolutions for similar CVEs (if any)
4. **Three Labelled Options**:
   - `sentinel/fix-now` — Override to ACTIVE, trigger full pipeline
   - `sentinel/defer` — Defer for 30 days, add to backlog
   - `sentinel/wont-fix` — Accept risk, record in Cosmos DB
5. **72-Hour Warning**: Auto-escalation deadline

## Label Handlers

### `sentinel/fix-now`
- Re-queues the vulnerability to Service Bus with status override `ACTIVE`
- Original payload preserved for full pipeline processing
- Issue updated with "Pipeline re-triggered" comment

### `sentinel/defer`
- Writes DEFERRED record to Azure Table Storage
- Sets `defer_until` to 30 days from now
- Daily Logic App re-evaluates deferred items via fresh KQL query
- If telemetry appears → auto-promotes to ACTIVE
- If still dormant → re-pings the issue

### `sentinel/wont-fix`
- Writes `ACCEPTED_RISK` record to Cosmos DB Historical Database
- Records who accepted the risk and when
- Issue closed with acceptance comment
- Audit log entry created (append-only, never deleted)

## Auto-Escalation (72-Hour Logic App)

An Azure Logic App monitors unanswered Decision Gate issues:

1. Fires 72 hours after issue creation
2. Re-runs the SRE Agent's KQL query against fresh telemetry
3. If now ACTIVE → auto-applies `sentinel/fix-now`
4. If still DORMANT → adds "⚠️ 72-hour deadline reached" comment and pings
   the assigned security team

ARM template: `/infrastructure/auto-escalation-logic-app.json`

## Daily Backlog Re-Scan (Logic App)

A second Logic App runs daily to re-evaluate deferred vulnerabilities:

1. Queries Table Storage for items past their `defer_until` date
2. Re-runs KQL classification for each
3. ACTIVE items → re-queued to Service Bus
4. Still DORMANT → deferred again (with updated `defer_until`)
5. Metrics logged to Application Insights

ARM template: `/infrastructure/backlog-rescan-logic-app.json`
