# Day 3 Goals — Dev B
## Human Decision Gate (GitHub Issue + Label Handlers)
## Plus: 200-answer Stack Overflow labelling (joint task with Dev A)

Split the day: morning is labelling, afternoon is the Decision Gate build.

---

## MORNING — Stack Overflow Labelling (joint with Dev A)
Label 200 Stack Overflow answers for the intent classifier training set.
Focus on Java/Maven ecosystem answers (Dev A takes npm and PyPI).

Labels to apply in Label Studio:
- VERSION_PIN — answer recommends pinning to a specific non-vulnerable version
- API_MIGRATION — answer requires refactoring call sites to use a new API
- MONKEY_PATCH — answer applies a runtime workaround without changing the dependency
- FULL_REFACTOR — answer recommends replacing the dependency entirely

After labelling, export your 200 labels as JSON and commit to `/nlp-pipeline/data/labelled/devb-maven-200.json`.

At EOD, Dev A computes Cohen's Kappa on 100 overlapping samples.
Target: κ > 0.80. If below, hold alignment session before Day 4.

---

## AFTERNOON — Human Decision Gate

### TASK 1 — GitHub Issue Template
Create `.github/ISSUE_TEMPLATE/sentinel-dormant-decision.md`:

The template must include:
- CVE ID, severity, affected package + version (populated dynamically by the creator script)
- Affected file and line range
- Production call count (30 days) — always 0 for DORMANT events
- Historical DB context section (populated if a match exists)
- Three labelled options with exact label names:
  - `sentinel/fix-now` → triggers full pipeline
  - `sentinel/defer` → adds to 30-day backlog
  - `sentinel/wont-fix` → accepted risk, requires justification annotation
- Auto-escalation warning: "This issue auto-escalates in 72 hours if no label is applied."

### TASK 2 — Issue Creator Script
Create `/safety-governor/create-decision-issue.js`:

Function: `createDecisionIssue(telemetryClassification, historicalMatch) → { issueNumber, issueUrl }`

Uses GitHub REST API (`@octokit/rest`) with `GITHUB_TOKEN` env var.
Populates the issue template with real CVE data.
Populates the Historical DB context section:
- If `historicalMatch.lookup_status === 'EXACT_MATCH'`: show "✅ This CVE was resolved in [repo] on [date] using [strategy]. Outcome: SUCCESS."
- If `historicalMatch.lookup_status === 'NO_MATCH'`: show "No previous resolution found for this CVE."
Assigns the issue to the security team alias (env var: `SECURITY_TEAM_GITHUB_LOGIN`).
Adds label `sentinel/dormant` on creation.

### TASK 3 — Label Event GitHub Actions Handlers
Create `.github/workflows/sentinel-decision-gate.yml`:

Trigger: `issue_comment` and `issues` events, filtered to label additions.

Three jobs, each triggering on a different label:

**Job: handle-fix-now** (label: `sentinel/fix-now`)
- Reads the issue body to extract `event_id`
- Posts message to Service Bus queue with original event payload + `status: ACTIVE` override
- Comments on the issue: "✅ Sentinel-D pipeline triggered. Full agentic remediation in progress."
- Closes the issue

**Job: handle-defer** (label: `sentinel/defer`)
- Reads issue body to extract `event_id` and `cve_id`
- Calls `/historical-db/backlog-writer.js` to write DEFERRED record
- Sets `defer_until` = 30 days from now
- Comments on the issue: "📋 Added to deferred backlog. Will re-evaluate on [date]."
- Closes the issue

**Job: handle-wont-fix** (label: `sentinel/wont-fix`)
- Reads issue body to extract `event_id`, `cve_id`, `file_path`
- Calls Historical DB write client to create ACCEPTED_RISK record in Cosmos DB
  (This prevents future pipeline runs from re-alerting on this CVE+file combination)
- Comments on the issue: "🔒 Recorded as accepted risk. Future Sentinel-D scans will not alert on this CVE in this file."
- Closes the issue

### TASK 4 — 72-Hour Auto-Escalation Logic App
Define the Logic App in `/infrastructure/auto-escalation-logic-app.json` (ARM template):

Trigger: Recurrence — check every hour
Condition: Find GitHub Issues with label `sentinel/dormant` that are older than 72 hours and still open
Action sequence:
1. Re-run KQL telemetry query for the CVE in the issue body
2. If call_count > 0 (now ACTIVE): post to Service Bus with ACTIVE override, close issue, comment "⚡ Auto-promoted: production calls detected."
3. If still DORMANT: re-assign issue to `SECURITY_TEAM_LEAD_GITHUB_LOGIN`, add comment "⚠️ 72-hour escalation: no decision made. Escalated to security team lead."

---

## SUCCESS CRITERIA FOR TODAY
- [ ] 200 labelled Stack Overflow answers committed (Maven ecosystem)
- [ ] GitHub Issue template renders correctly with all required sections
- [ ] Issue creator script creates a well-formed issue against a test repo
- [ ] All three label handlers trigger correctly with mock label events
- [ ] wont-fix handler writes ACCEPTED_RISK to Cosmos DB emulator
- [ ] Logic App ARM template validates (`az deployment group validate`)
