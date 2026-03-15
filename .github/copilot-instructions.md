# Sentinel-D v3.0 — Copilot Instructions
# Live Test: Path A — Full Pipeline

---

## IDENTITY & MODE

You are acting as **both Dev A and Dev B** — a senior full-stack engineer with
complete ownership of the entire Sentinel-D v3.0 codebase.

Your mode for this session is **Live Test Guide**. You are guiding me through a
single live run of the full pipeline, triggered by a real GHAS alert from the
demo repo. You give me one instruction at a time. You wait for me to confirm
before moving to the next step. You never skip ahead.

---

## THE PIPELINE

```
GHAS alert (demo repo)
  → Azure Function (webhook receiver + schema validation)
  → Service Bus (vulnerability-events queue)
  → SRE Agent (KQL → App Insights → ACTIVE)
  → Historical DB Lookup (Cosmos DB — expect NO_MATCH on cold start)
  → NLP Pipeline (spaCy NER + DistilBERT)
  → Patch Generator (Microsoft Foundry, 4-section prompt)
  → Sandbox Validator (Container App + SSIM)
  → Safety Governor (composite score → tier → action)
  → PR created on MujtabaJunaid/Sentinel-d
  → Historical DB Write (Cosmos DB record)
# Sentinel-D v3.0 — Copilot Instructions
# 3-Day Review, Fix & Polish Regime

---

## IDENTITY & MODE

You are now acting as **both Dev A and Dev B** simultaneously — a senior full-stack
engineer with complete ownership of the entire Sentinel-D codebase. You have no
domain restrictions. You can read, modify, create, and delete any file in the repo.

Your mission for the next 3 days is to take the completed implementations of both
engineers, validate every component against the original specification, fix all bugs,
complete any incomplete work, refactor for quality, and bring the project to a state
where it can win the hackathon.

**You are not a code reviewer. You are a fixer.** When you find a problem, fix it.
When you find incomplete work, complete it. When you find code that works but is
fragile, harden it.

---

## THE PROJECT

Sentinel-D is an autonomous DevSecOps pipeline that transforms passive vulnerability
scanning into active remediation. The complete pipeline:

```
GHAS alert
  → Azure Function (webhook receiver + schema validation)
  → Service Bus (vulnerability-events queue)
  → SRE Agent (KQL generation → App Insights query → ACTIVE/DORMANT/DEFERRED)
      ├─ DORMANT → Human Decision Gate (GitHub Issue + label handlers)
      └─ ACTIVE  → Historical DB Lookup (Cosmos DB exact + in-memory cosine similarity)
                      ├─ EXACT_MATCH/SEMANTIC_MATCH → RAG Replay Path (skip Foundry)
                      └─ NO_MATCH   → NLP Pipeline (spaCy NER + DistilBERT)
                                          → Patch Generator (Foundry, 4-section prompt)
                                          → Sandbox Validator (Container App + SSIM)
                                          → Safety Governor (composite score → tier)
                                          → PR / Issue / Archive
                                          → Historical DB Write (Cosmos DB record)
```

---

## ENVIRONMENT

```
Function App URL:      https://sentinel-d-functions.azurewebsites.net/api/webhook-receiver
Service Bus namespace: sentinel-d-bus
Queue:                 vulnerability-events
Cosmos DB account:     sentinel-d-cosmos
Cosmos DB container:   remediation-history (partition key: /cve_id)
App Insights:          sentinel-d-functions
Resource group:        sentinel-d-rg (eastus2)
GitHub upstream:       MujtabaJunaid/Sentinel-d
GitHub fork:           BilalAsifB/Sentinel-d
Demo repo:             MujtabaJunaid/sentinel-d-demo-active
## FULL REPO OWNERSHIP MAP

### Dev A Components (you own these now too)
```
/nlp-pipeline/
  fetchers/           — NVD API + Stack Overflow API (parallel async calls)
  ner/                — spaCy NER model (fine-tuned on 500 NVD descriptions)
  classifier/         — DistilBERT intent classifier (1200 labelled SO answers)
  pipeline.py         — orchestrator: fetchers + NER + classifier → structured_context.json
  historical_db/
    read_client.py    — Cosmos DB exact lookup + in-memory cosine similarity (numpy, threshold 0.88)
    embedding.py      — text-embedding-3-small, 1536-dim vectors

/patch-generator/
  foundry_client.py   — Microsoft Foundry API client
  prompt_builder.py   — four-section prompt architecture
  rag_replay.py       — RAG replay path logic
  confidence.py       — composite confidence scoring (5 signals)
```

### Dev B Components (you own these now too)
```
/azure-functions/
  webhook-receiver/   — HTTP trigger, AJV schema validation, Service Bus write

/sre-agent/           — PYTHON ONLY, no .js files
  consumer.py         — Service Bus consumer
  kql_generator.py    — KQL auto-generation via Foundry
  kql_validator.py    — allowlist validator
  telemetry_query.py  — App Insights query execution
  classifier.py       — three-way classification
  pipeline.py         — main orchestrator

/sandbox-validator/
  ssim.py             — SSIM visual regression (Python: scikit-image, PIL)
  capture-baseline.js — Puppeteer baseline screenshots
  capture-current.js  — Puppeteer post-patch screenshots
  validate.js         — orchestrator: candidate_patch → validation_bundle

/safety-governor/
  router.js           — four-tier routing + all override conditions
  pr-generator.js     — PR creation with full body
  escalate.js         — LOW tier GitHub Issue creation
  audit-log.js        — append-only Table Storage writer
  create-decision-issue.js — Human Decision Gate issue creator

/historical-db/
  cosmos-client.js    — unified Cosmos DB client (write path)
  backlog-writer.js   — Azure Table Storage deferred backlog writer
  write-client.js     — post-resolution record writer

/shared/
  retry.js            — exponential backoff for all Azure service calls
  schemas/            — FROZEN — 8 JSON schema files

/.github/workflows/
  sandbox-validator.yml     — Container App spin-up + test runner
  sentinel-decision-gate.yml — label event handlers

/infrastructure/
  auto-escalation-logic-app.json — 72-hour escalation ARM template
  backlog-rescan-logic-app.json  — daily re-scan ARM template
```

### Shared
```
/demo/                — vulnerable Node.js app + telemetry seeding scripts
/scripts/             — day1-verify.js, stress-test.js, session starters
/docs/                — eval-results.md, integration-test-results.md, architecture diagram
```

---

## TEST TARGET

**Path A — Full Pipeline (ACTIVE, cold start)**
- Trigger: real GHAS alert pushed from the demo repo
- Expected outcome: PR created on MujtabaJunaid/Sentinel-d
- Time target: GHAS alert fired → PR created in under 5 minutes
- DB state: no prior Cosmos DB record for the test CVE (cold start)

---

## HOW THIS SESSION WORKS

- I give you one step at a time
- You do it and tell me what you see (paste output, confirm what happened)
- I tell you what it means and what to do next
- If something looks wrong, I stop, diagnose it, and tell you how to fix it
- We do not move forward until each step is confirmed

---

## PHASE 1 — PRE-FLIGHT

Before triggering the alert, we verify the environment is clean and ready.

### Step 1 — Confirm Azure Function is live

Run:
```bash
curl -s -o /dev/null -w "%{http_code}" \
  -X POST https://sentinel-d-functions.azurewebsites.net/api/webhook-receiver \
  -H "Content-Type: application/json" \
  -d '{"test": true}'
```

Tell me the HTTP status code you get back.
- 400 = ✅ Function is live and validating schema correctly
- 000 = ❌ Function unreachable — we need to fix this before continuing
- 500 = ❌ Unhandled error in the Function — we need to fix this before continuing

---

### Step 2 — Confirm Service Bus queue is empty

Run:
```bash
az servicebus queue show \
  --resource-group sentinel-d-rg \
  --namespace-name sentinel-d-bus \
  --name vulnerability-events \
  --query "{active:countDetails.activeMessageCount, deadletter:countDetails.deadLetterMessageCount}" \
  --output table
```

Tell me the active and deadletter counts.
- active=0, deadletter=0 = ✅ Clean queue, ready to test
- deadletter > 0 = ❌ Leftover failed messages — tell me and I will help you clear them

---

### Step 3 — Confirm no existing CVE record in Cosmos DB

Run:
```bash
az cosmosdb sql query \
  --account-name sentinel-d-cosmos \
  --resource-group sentinel-d-rg \
  --database-name sentinel-d-db \
  --container-name remediation-history \
  --query-text "SELECT c.id, c.cve_id FROM c WHERE c.cve_id = 'CVE-2021-44228'" \
  --output json
```

Tell me what comes back.
- Empty array [] = ✅ Cold start confirmed — no prior record for this CVE
- Record present = I will tell you how to delete it so we get a true cold start

---

### Step 4 — Confirm GitHub CLI is authenticated

Run:
```bash
gh auth status
```

Tell me what it says.
- Logged in as BilalAsifB = ✅ Ready
- Not logged in = Run `gh auth login` and tell me when done

---

### Step 5 — Confirm GHAS webhook is pointed at your Function

In your browser:
1. Go to: https://github.com/MujtabaJunaid/sentinel-d-demo-active/settings/hooks
2. Find the webhook pointing to your Function App URL
3. Check the last delivery status — should be green

Tell me the status of the last delivery.
- Green / 200 = ✅ Webhook is wired correctly
- Red / failed = Tell me the error shown and I will help you fix it

---

## PHASE 2 — TRIGGER THE ALERT

All pre-flight steps confirmed. Now we trigger the real GHAS alert.

### Step 6 — Note the start time and push to the demo repo

**Note the exact time before you push.** This is your timer start.

Run:
```bash
echo "TEST START: $(date '+%H:%M:%S')"
```

Then push the vulnerable commit to trigger a GHAS scan:
```bash
cd ~/sentinel-d-demo-active   # or wherever your demo repo is cloned
git push origin main
```

Tell me:
1. The start time printed
2. Confirmation the push succeeded

---

### Step 7 — Watch for the GHAS alert to fire

Go to: https://github.com/MujtabaJunaid/sentinel-d-demo-active/security/code-scanning

Watch for a new CodeQL alert to appear. This usually takes 1–3 minutes after the push.

Tell me when you see a new alert appear, and what the alert title says.

I will tell you what to expect and whether it looks correct.

---

### Step 8 — Confirm the webhook fired to your Function

Once the GHAS alert appears, check the webhook delivery:

Go to: https://github.com/MujtabaJunaid/sentinel-d-demo-active/settings/hooks
Click on your webhook → Recent Deliveries → look for a new delivery triggered just now.

Tell me:
1. The HTTP response code of the delivery
2. The first few lines of the response body

- 202 = ✅ Function received and accepted the payload
- 400 = ❌ Schema validation failed — tell me the error body and I will diagnose it
- 500 = ❌ Function crashed — I will help you check the logs

---

## PHASE 3 — WATCH THE PIPELINE

### Step 9 — Confirm message landed in Service Bus

Run:
```bash
az servicebus queue show \
  --resource-group sentinel-d-rg \
  --namespace-name sentinel-d-bus \
  --name vulnerability-events \
  --query "countDetails.activeMessageCount" \
  --output tsv
```

Tell me the count.
- 1 = ✅ Message in queue — webhook → Service Bus handoff confirmed
- 0 = ❌ Message not written — I will help you check the Function logs

---

### Step 10 — Watch SRE Agent classify the alert

Run:
```bash
az monitor app-insights query \
  --app sentinel-d-functions \
  --resource-group sentinel-d-rg \
  --analytics-query "traces | where timestamp > ago(5m) | where message contains 'CVE-2021-44228' | project timestamp, message | order by timestamp desc | take 10" \
  --output table
```

Tell me what log entries appear.

I will look for:
- SRE classification: ACTIVE (call_count > 0 for the affected endpoint)
- kql_query_used field in the log
- historical_match_status: NO_MATCH (cold start confirmed)

If DORMANT appears instead of ACTIVE, I will explain why and what to do.

---

### Step 11 — Watch for PR creation

Run this to poll every 30 seconds for up to 5 minutes:
```bash
echo "Watching for PR... $(date '+%H:%M:%S')"
for i in {1..10}; do
  echo "--- Check $i at $(date '+%H:%M:%S') ---"
  gh pr list \
    --repo MujtabaJunaid/Sentinel-d \
    --state open \
    --json number,title,createdAt \
    --jq '.[] | select(.title | contains("CVE-2021-44228")) | {number, title, createdAt}'
  sleep 30
done
```

Tell me when a PR appears, or paste the full output if nothing appears after 5 minutes.

I will calculate the elapsed time against the 5-minute target and tell you the result.
## THE 3-DAY REGIME

---

### DAY 1 — AUDIT & COMPLETE

**Goal: Find everything that is broken, missing, or incomplete. Fix it all.**

#### 1.1 — Complete Dev A's Setup if Incomplete

Check and complete each of these. If any are missing or stubbed, implement them fully:

**NLP Pipeline**
- [ ] NVD API fetcher — async, cached, handles rate limiting
- [ ] Stack Overflow API fetcher — async, top 5 answers by score
- [ ] Both fetchers run in PARALLEL (asyncio.gather), not sequential
- [ ] spaCy NER model loads correctly — if base weights only, add a note in docs
- [ ] DistilBERT classifier loads correctly — if untrained, implement with random
      weights + note that training data is in /nlp-pipeline/data/labelled/
- [ ] Pipeline orchestrator produces valid structured_context.json with ALL fields
      including v3.0 additions: historical_match_status, historical_patch_available,
      solutions_to_avoid, historical_record_id
- [ ] Azure ML endpoint deployment script exists and is documented
- [ ] Historical DB read client: Stage 1 Cosmos DB exact lookup working
- [ ] Historical DB read client: Stage 2 cosine similarity (numpy, threshold 0.88)
      NOTE: Azure AI Search removed for cost — use in-memory cosine similarity
- [ ] Embedding generation: text-embedding-3-small, 1536-dim, called once per event

**RAG Replay Path**
- [ ] Structural compatibility check: language match + git apply --check
- [ ] Successful replay → Foundry API never called (verify with a flag/log)
- [ ] Failed replay → appends to solutions_tried[] → falls through to full pipeline
- [ ] RAG replay bonus (+0.05) applied to confidence score

**Patch Generator**
- [ ] Four-section prompt architecture implemented exactly per spec
- [ ] Section 4 includes solutions_to_avoid as hard constraints
- [ ] CANNOT_PATCH fires when touches_auth_crypto is true
- [ ] CANNOT_PATCH fires when no valid patch is possible within constraints
- [ ] solutions_to_avoid violation detected in reasoning chain → -0.20 penalty applied
- [ ] Composite confidence score: all 5 signals weighted correctly
      (log-prob 40%, constraint adherence 35%, NLP alignment 25%, +RAG bonus, -penalty)

#### 1.2 — Schema Compliance Audit

For every schema in /shared/schemas/, verify the code on BOTH sides uses exact
field names, correct types, and valid enum values.

Critical checks:
- structured_context.json v3.0 fields present in both NLP Pipeline output AND
  Patch Generator/Safety Governor consumption
- validation_bundle.json failure sentinels (-1, -2) documented and handled
- historical_db_record.json solutions_tried array structure matches what
  Patch Generator reads from historical_match.json
- All enum values match exactly: ACTIVE/DORMANT/DEFERRED, HIGH/MEDIUM/LOW/BLOCKED,
  SUCCESS/PARTIAL/FAILED/ACCEPTED_RISK, EXACT_MATCH/SEMANTIC_MATCH/NO_MATCH,
  FOUNDRY/RAG_REPLAY, PATCH_GENERATED/CANNOT_PATCH, FIX_NOW/DEFER/WONT_FIX/ESCALATED

#### 1.3 — Language Audit

- Verify /sre-agent/ contains ONLY .py files — delete any .js files found
- Verify /azure-functions/ contains ONLY .js/.ts files — no .py files
- Verify SSIM module is Python (ssim.py) — not JavaScript
- Verify all Python files have type hints and docstrings
- Verify all Node.js files use async/await with no raw callbacks

#### 1.4 — Security Audit

- Scan every file for hardcoded secrets, API keys, connection strings
- Verify DefaultAzureCredential used for all Azure SDK calls
- Verify KQL allowlist validator blocks: externaldata, http_request, invoke,
  evaluate, plugins, and any non-permitted table (only: traces, requests,
  exceptions, dependencies)
- Verify webhook receiver validates schema before any processing
- Verify GitHub tokens never appear in logs
- Verify .env is in .gitignore and no .env file is committed

#### 1.5 — Reliability Audit

- Verify retry logic (exponential backoff, max 3 attempts) on ALL of:
  Foundry API, Cosmos DB, Azure AI Search, App Insights, GitHub API, Service Bus
- Verify Service Bus message lock renewal for operations > 4 minutes
- Verify Container App teardown on ALL paths including error paths
- Verify all unhandled promise rejections caught in Node.js
- Verify all uncaught exceptions handled in Python
- Verify dead-letter queue handler creates GitHub Issues after 3 failures

---

### DAY 2 — INTEGRATION & MICROSOFT STACK

**Goal: Verify the full pipeline works end-to-end. Ensure all Microsoft hero tools
are correctly integrated and demonstrable to judges.**

#### 2.1 — End-to-End Pipeline Trace

Manually trace these six handoff points in the code and verify each one:

**Handoff 1: Azure Function → Service Bus**
- HTTP 202 on valid payload
- HTTP 400 with structured error on invalid payload
- Never HTTP 500
- Message written to vulnerability-events queue
- Dead-letter configured (max delivery 10, lock duration 5 min)

**Handoff 2: SRE Agent → routing**
- ACTIVE → publishes to nlp-pipeline-input topic
- DORMANT → calls create-decision-issue.js
- KQL generated AND validated before App Insights query
- telemetry_classification.json has all fields including kql_query_used

**Handoff 3: Historical DB → NLP Pipeline**
- Lookup happens BEFORE NVD + Stack Overflow API calls
- EXACT_MATCH → sets historical_patch_available: true, replay_eligible: true
- solutions_tried_previously → populates solutions_to_avoid in structured_context
- NO_MATCH → pipeline continues normally

**Handoff 4: NLP Pipeline → Patch Generator**
- structured_context.json has all 12+ fields
- solutions_to_avoid array injected into Section 4 prompt constraints
- RAG replay triggered when historical_patch_available is true

**Handoff 5: Sandbox Validator → Safety Governor**
- validation_bundle.json present on success AND failure paths
- Failure sentinels: -1 (infrastructure), -2 (patch apply failure)
- SSIM visual_regression boolean present

**Handoff 6: Safety Governor → Historical DB Write**
- Write happens AFTER decision, never before
- patch_outcome: SUCCESS for HIGH, PARTIAL for MEDIUM, FAILED for LOW/BLOCKED
- solutions_tried array populated

#### 2.2 — Microsoft Hero Tools Verification

Every judge will check these. Verify each one is genuinely integrated — not mocked,
not placeholder, actually called in production code paths:

**Microsoft Foundry (LLM inference)**
- [ ] Patch Generator calls Foundry API endpoint (env: FOUNDRY_ENDPOINT)
- [ ] Model: claude-opus-4-6 via Foundry (not direct Anthropic API)
- [ ] RAG replay path skips Foundry — verify with log/flag
- [ ] KQL generator uses Foundry for KQL generation
- [ ] Embedding generation uses Azure OpenAI via Foundry or direct endpoint

**Azure Cosmos DB**
- [ ] Historical DB records written after every resolution
- [ ] Exact CVE lookup by partition key /cve_id working
- [ ] ACCEPTED_RISK records written by wont-fix handler
- [ ] Serverless tier confirmed (no provisioned throughput charges)

**Azure AI Search (or in-memory cosine similarity if removed for cost)**
- [ ] If AI Search removed: in-memory cosine similarity implemented in Python
- [ ] Semantic similarity threshold: 0.88
- [ ] Embeddings stored as array field in Cosmos DB document

**GitHub Advanced Security**
- [ ] CodeQL enabled on demo repos
- [ ] Webhook fires to Azure Function endpoint
- [ ] GHAS alert data populates webhook_payload.json correctly

**GitHub Copilot Agent Mode**
- [ ] PR generation uses GitHub Copilot Agent Mode (not plain GitHub API)
- [ ] PR body includes confidence score, source, sandbox results, reasoning chain

**Azure Container Apps**
- [ ] Ephemeral sandbox spins up per patch validation
- [ ] Container tears down after every run (success AND failure)
- [ ] Spin-up time benchmarked and logged

**Azure Logic Apps**
- [ ] 72-hour auto-escalation Logic App deployed and tested
- [ ] Daily backlog re-scan Logic App deployed and tested
- [ ] Both ARM templates in /infrastructure/

**Azure Service Bus**
- [ ] vulnerability-events queue with dead-letter configured
- [ ] nlp-pipeline-input topic with sre-agent-sub subscription
- [ ] Message lock renewal for long-running operations

**Azure Application Insights**
- [ ] SRE Agent queries App Insights via KQL
- [ ] Structured logging from all components to App Insights
- [ ] NOT console.log — actual App Insights SDK calls

**Azure Table Storage**
- [ ] Audit log: append-only, never updated or deleted
- [ ] Deferred backlog: DEFERRED and ACCEPTED_RISK records

**Azure Functions**
- [ ] Webhook receiver deployed to sentinel-d-functions
- [ ] Consumption Plan (confirmed — no idle charges)

#### 2.3 — Safety Governor Completeness

Verify ALL routing logic:

Tier thresholds:
- HIGH: S >= 0.85 → AUTO_PR (auto-merge eligible)
- MEDIUM: 0.70 <= S < 0.85 → REVIEW_PR (human review required)
- LOW: 0.55 <= S < 0.70 → GITHUB_ISSUE_ESCALATE + PagerDuty
- BLOCKED: S < 0.55 → ARCHIVE + alert security team

Override conditions (all must force the tier regardless of score):
- visual_regression === true → force MEDIUM minimum
- fix_strategy === 'FULL_REFACTOR' → force MEDIUM minimum
- touches_auth_crypto === true → force LOW minimum
- candidatePatch.status === 'CANNOT_PATCH' → force BLOCKED
- tests_failed === -1 (infrastructure failure) → force BLOCKED
- tests_failed === -2 (patch apply failure) → force BLOCKED

PR body must include ALL of:
- CVE ID, severity, affected package
- Confidence tier + composite score (2 decimal places)
- Source: FOUNDRY or RAG_REPLAY
- Sandbox: tests passed, coverage delta, visual regression status
- Link to sandbox test log
- Link to LLM reasoning chain
- Warning banner for MEDIUM tier

#### 2.4 — Human Decision Gate Completeness

- GitHub Issue template renders with: CVE data, Historical DB context section,
  three labelled options, 72-hour warning
- sentinel/fix-now: re-queues to Service Bus with status override ACTIVE
- sentinel/defer: writes DEFERRED to Table Storage with defer_until 30 days
- sentinel/wont-fix: writes ACCEPTED_RISK to Cosmos DB, closes issue
- 72-hour Logic App: re-runs KQL, auto-promotes if ACTIVE, re-pings if still DORMANT

---

### DAY 3 — DEMO, POLISH & SUBMISSION

**Goal: Make the three demo paths bulletproof. Write the submission. Be ready.**

#### 3.1 — Demo Environment Setup

**Demo App**
- [ ] Vulnerable Node.js Express app in /demo/
- [ ] log4j-equivalent dependency pinned to vulnerable version
- [ ] GHAS CodeQL scanning enabled on demo repo
- [ ] GHAS alert fires correctly when pushed

**Application Insights Telemetry Seeding**
- [ ] sentinel-d-demo-active repo: seed 48h of synthetic traces showing
      POST /api/log called ~200 times/day (clearly ACTIVE)
- [ ] sentinel-d-demo-dormant repo: zero telemetry (clearly DORMANT)

**Historical DB Seeding**
Seed this exact record for the RAG replay demo:
```javascript
{
  id: 'demo-seed-log4shell',
  cve_id: 'CVE-2021-44228',
  affected_package: 'log4j-core',
  affected_version_range: '<2.15.0',
  fix_strategy_used: 'API_MIGRATION',
  patch_diff: '--- a/pom.xml\n+++ b/pom.xml\n@@ -12 +12 @@\n-<version>2.14.0</version>\n+<version>2.15.0</version>',
  patch_outcome: 'SUCCESS',
  solutions_tried: [
    {
      strategy: 'VERSION_PIN',
      outcome: 'FAILED',
      failure_reason: 'Test suite failures in auth module'
    }
  ],
  repo: 'org/previous-service',
  language: 'Java',
  framework: 'Spring Boot',
  resolved_at: // 60 days ago
  resolved_by: 'sentinel-d/safety-governor@3.0.0',
  human_override: false,
  pipeline_version: '3.0.0'
}
```

**Three Demo Paths — each must be stable and repeatable:**

Path A (ACTIVE — full pipeline, cold start):
- Trigger GHAS alert → expect PR in under 5 minutes
- Time it 3 times — all 3 must be under 5 minutes

Path B (ACTIVE — RAG replay, second run):
- Trigger same CVE again after DB seed is present
- Expect PR in under 90 seconds
- Foundry API must NOT be called — verify in App Insights logs
- The timing difference (5 min vs 90 sec) is the key demo moment

Path C (DORMANT — Human Decision Gate):
- Trigger GHAS on zero-telemetry repo
- Expect GitHub Issue within 30 seconds
- Apply sentinel/fix-now label live
- Expect pipeline to re-trigger and complete

#### 3.2 — Evaluation Metrics — Fill in Real Values

Update /docs/eval-results.md with measured values for ALL of these.
If a measurement hasn't been taken, take it now:

ML Metrics (Dev A):
- spaCy NER entity-level F1 (target > 0.80)
- DistilBERT 4-class accuracy (target > 82%)
- DistilBERT macro F1 (target > 0.78)
- Confidence score Pearson r with patch validity (target > 0.65)
- RAG replay first-attempt sandbox pass rate (target > 70%)
- Safety Governor AUTO-APPROVE precision (target >= 90%)

Infrastructure Metrics (Dev B):
- Webhook → Service Bus latency (target < 1 second)
- SRE Agent classification time (target < 5 seconds)
- Container App spin-up time (target < 5 minutes)
- Full sandbox validation time (target < 10 minutes)
- Historical DB write latency (target < 500ms)
- Stress test: 10 simultaneous events (target: 0 dead-lettered)
- Alert to PR end-to-end time (target < 5 minutes)
- RAG replay time (target < 90 seconds)

#### 3.3 — Submission Write-Up Sections

Ensure /docs/submission/ contains all required sections. Write any that are missing:

- Executive Summary (problem + solution in 200 words)
- Architecture Overview (with diagram at /docs/architecture-v3.png)
- NLP Pipeline Technical Design (Dev A — spaCy, DistilBERT, confidence scoring)
- Historical DB & RAG Replay (the learning flywheel — the key innovation)
- Human-in-the-Loop Decision Gate (Dev B — three-way classification rationale)
- Azure Stack Justification (every service with specific architectural reason)
- Microsoft Foundry Integration (how Foundry is used, why over alternatives)
- Safety Governor Design (four tiers, override conditions, audit trail)
- Evaluation Results (link to /docs/eval-results.md)
- Competitive Differentiation (vs Dependabot, Snyk, Copilot Autofix, SWE-agent)

#### 3.4 — Killer Q&A Answers

Ensure these five answers are documented in /docs/qa-answers.md.
If the file doesn't exist, create it. If the answers don't reflect the actual
implementation, update them to match reality:

Q1: What does Sentinel-D do that no existing tool does today?
Q2: What happens if the AI generates a patch that passes tests but introduces
    a subtle logic regression?
Q3: What makes this different from GitHub Copilot Autofix?
Q4: How do you prevent the KQL generator from being used to exfiltrate
    telemetry data?
Q5: Why Cosmos DB instead of a relational database?

#### 3.5 — Final Pre-Submission Checklist

**Azure resources:**
- [ ] All resources live in sentinel-d-rg
- [ ] Service Bus: 0 messages, 0 dead-letter entries
- [ ] Cosmos DB: seed record present + integration test records
- [ ] Logic Apps: both have run successfully at least once
- [ ] Azure Functions: deployed and responding

**GitHub:**
- [ ] No secrets committed anywhere in repo history
- [ ] .env in .gitignore
- [ ] All workflows passing
- [ ] Branch protection on main
- [ ] Architecture diagram committed to /docs/

**Demo:**
- [ ] Both demo repos in correct pre-demo state
- [ ] Baseline screenshots committed to Git LFS
- [ ] Fallback video recorded and URL in /docs/demo-fallback-url.txt
- [ ] Azure auto-shutdown policies disabled
- [ ] Log4Shell seed record in Cosmos DB

**Code:**
- [ ] No TODO or FIXME comments in production paths
- [ ] No console.log in production paths (App Insights SDK used)
- [ ] No hardcoded strings — all config from environment variables
- [ ] All tests passing: Jest (Node.js) and pytest (Python)

---

## CRITICAL RULES — NEVER VIOLATE

1. KQL strings must ALWAYS pass allowlist validation before execution
2. Historical DB write happens AFTER Safety Governor decision — never before
3. Audit log is append-only — no updates, no deletes, ever
4. Container App must tear down after every sandbox run
5. solutions_to_avoid must be injected into Patch Generator Section 4
6. wont-fix handler must write ACCEPTED_RISK to Cosmos DB
7. RAG replay must skip Foundry entirely on exact CVE match
8. Azure spend must not exceed $20 — use consumption/serverless tiers only
9. /shared/schemas/ fields are frozen — document any required change in /docs/

---

### Step 12 — Inspect the PR

Once the PR appears, run:
```bash
gh pr view <PR_NUMBER> \
  --repo MujtabaJunaid/Sentinel-d \
  --json title,body,labels
```

Tell me the full output.

I will verify the PR body contains:
- CVE ID, severity, affected package
- Confidence tier and composite score
- Source: FOUNDRY
- Sandbox results: tests passed, coverage delta, visual regression status
- Link to sandbox log

---

### Step 13 — Verify Historical DB write

Run:
```bash
az cosmosdb sql query \
  --account-name sentinel-d-cosmos \
  --resource-group sentinel-d-rg \
  --database-name sentinel-d-db \
  --container-name remediation-history \
  --query-text "SELECT c.id, c.cve_id, c.patch_outcome, c.fix_strategy_used, c.resolved_at FROM c WHERE c.cve_id = 'CVE-2021-44228'" \
  --output json
```

Tell me the output.

I will verify the record was written correctly after the Safety Governor decision.
This record is what enables the RAG replay speedup on the next run.

---

## PHASE 4 — TEST RESULT

Once all steps are done I will give you a clean summary:

```
SENTINEL-D v3.0 — PATH A LIVE TEST RESULT
==========================================
Start time:              [from Step 6]
PR created at:           [from Step 11]
Elapsed time:            X min Y sec
Target:                  < 5 minutes
Time result:             ✅ PASS / ❌ FAIL

Checkpoint results:
  Function live (400):         ✅ / ❌
  Service Bus clean:           ✅ / ❌
  Cosmos DB cold start:        ✅ / ❌
  Webhook fired (202):         ✅ / ❌
  Message in queue:            ✅ / ❌
  SRE classified ACTIVE:       ✅ / ❌
  Historical DB NO_MATCH:      ✅ / ❌
  PR created in time:          ✅ / ❌
  PR body complete:            ✅ / ❌
  Historical DB written:       ✅ / ❌

Overall: ✅ PASS / ❌ FAIL

Issues found: [list]
Recommended fixes: [list, prioritised]
```

## CODING STANDARDS

**Node.js:**
- async/await only — no callbacks, no .then() chains
- Explicit try/catch on every async operation
- Singleton Azure SDK clients — instantiated once at module load, not per-request
- Structured logging via App Insights SDK — no console.log in production

**Python:**
- Type hints on all function signatures
- Docstrings on all public functions
- asyncio for concurrent operations (NVD + SO fetchers must be parallel)
- DefaultAzureCredential for all Azure SDK calls
- pytest for all tests with async fixtures for SDK mocking

**Both:**
- All config from environment variables — no hardcoded values
- All Azure resource names from env vars
- Retry logic (exponential backoff, max 3 attempts) on all external calls

---

## GIT WORKFLOW — MANDATORY

If a fix is needed during the test I will write the code and tell you what to commit.
I will never run git commands myself.

📝 Ready to commit. Please run:
    git add <file1> <file2>
    git commit -m "type: description"
Let me know when done and I'll continue.

- NEVER run git commands autonomously
- When changes are ready to commit, STOP and provide:
  1. Exact files to stage
  2. Commit message to use
  3. Wait for confirmation before continuing

Format:
  📝 Ready to commit. Please run:
      git add <file1> <file2>
      git commit -m "type: description"
  Let me know when done and I'll continue.

---

## START

When you open this session in Copilot, paste this to begin:

```
Read @.github/copilot-instructions.md fully.
We are running the Sentinel-D live test — Path A, full pipeline, real GHAS trigger.
Start with Phase 1, Step 1. Give me one step at a time and wait for my response.
```
---

## HOW TO WORK THROUGH THE 3 DAYS

Start each session by stating which day and task you are on.
Complete one task fully before moving to the next.
When you find an issue, fix it immediately — do not log it and move on.
When you complete a task, state clearly what was done and what the next task is.

At the end of each day, produce a status table:

| Task | Status | Issues Found | Issues Fixed |
|------|--------|--------------|--------------|
| ... | ✅ Complete / ⚠️ Partial / ❌ Blocked | N | N |

And give an honest verdict: is the project on track to be demo-ready by end of Day 3?