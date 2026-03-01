# Day 1 Goals — Dev B
## Environment, Schema Freeze & Azure Foundation

Today's objective: get the Azure backbone running end-to-end so a mock GHAS webhook
fires and a message lands in Service Bus. Everything else this sprint depends on this.

---

## TASK 1 — Azure Environment Provisioning
Provision all Azure resources in this order (dependencies matter):

1. Resource group: `sentinel-d-rg` in `eastus2`
2. Azure Service Bus namespace (Standard tier) + queue named `vulnerability-events`
   - Enable dead-letter on message expiration AND on max delivery count (10)
   - Set lock duration: 5 minutes (gives downstream agents time to process)
3. Azure Function App (Consumption Plan, Node.js 20, eastus2)
4. Azure Cosmos DB account (Core API, serverless) — container: `remediation-history`
   - Partition key: `/cve_id`
   - Enable analytical store: no (keep it simple for now)
5. Azure AI Search (Basic tier) — we configure the index schema on Day 2
6. Azure Table Storage account — two tables: `deferred-backlog` and `audit-log`
7. Azure Application Insights workspace (for the SRE Agent to query later)

Generate ARM templates or `az cli` commands for each of these so the setup is
reproducible and both engineers can spin up identical environments.

---

## TASK 2 — Schema File Creation
Create `/shared/schemas/` directory with these 8 JSON schema files.
These are the team contract — once created today, treat them as frozen.

Create each as a JSON Schema draft-07 file with `$schema`, `title`, `required`,
and `properties` fields. Base the field names and types on these definitions:

**webhook_payload.json**
Fields: event_id (string, uuid), cve_id (string), severity (enum: CRITICAL/HIGH/MEDIUM/LOW),
affected_package (string), current_version (string), fix_version_range (string),
file_path (string), line_range (array of 2 integers), repo (string), timestamp (string, date-time)

**telemetry_classification.json**
Fields: event_id, status (enum: ACTIVE/DORMANT/DEFERRED), call_count_30d (integer),
last_called (string, date-time, nullable), blast_radius (enum: HIGH/MEDIUM/LOW/UNKNOWN),
kql_query_used (string), confidence (number 0-1)

**historical_match.json**
Fields: event_id, lookup_status (enum: EXACT_MATCH/SEMANTIC_MATCH/NO_MATCH),
match_confidence (number 0-1), matched_cve_id (string, nullable),
matched_record_id (string, nullable), recommended_strategy (string, nullable),
historical_patch_diff (string, nullable), previous_outcome (string, nullable),
solutions_tried_previously (array of objects with strategy/outcome/failure_reason),
replay_eligible (boolean), replay_ineligible_reason (string, nullable)

**human_decision.json**
Fields: event_id, decision (enum: FIX_NOW/DEFER/WONT_FIX/ESCALATED),
decided_by (string), decided_at (string, date-time), annotation (string, nullable),
defer_until (string, date-time, nullable), github_issue_url (string),
auto_escalated (boolean)

**structured_context.json** — DEV A OWNS THIS, just create the schema file stub with all fields
Fields: event_id, fix_strategy (string), breaking_changes (array), community_intent_class (string),
intent_confidence (number 0-1), nvd_context (object), migration_steps (array of strings),
historical_match_status (string), historical_patch_available (boolean),
solutions_to_avoid (array of objects), historical_record_id (string, nullable),
pipeline_version (string)

**candidate_patch.json** — DEV A OWNS THIS, create schema stub
Fields: event_id, status (enum: PATCH_GENERATED/CANNOT_PATCH), source (enum: FOUNDRY/RAG_REPLAY),
diff (string, nullable), files_modified (array of strings), lines_changed (integer),
touches_auth_crypto (boolean), llm_confidence (number 0-1),
reasoning_chain (string, nullable), model_id (string), cannot_patch_reason (string, nullable)

**validation_bundle.json** — I OWN THIS
Fields: event_id, tests_passed (integer), tests_failed (integer),
coverage_before (number), coverage_after (number), visual_diff_pct (number 0-1),
visual_regression (boolean), container_id (string), test_log_url (string),
screenshot_diff_url (string, nullable)

**historical_db_record.json** — used for Cosmos DB document validation
Fields: id (string), cve_id, affected_package, affected_version_range,
cve_description_embedding (array of numbers), fix_strategy_used, patch_diff,
patch_outcome (enum: SUCCESS/PARTIAL/FAILED/ACCEPTED_RISK), failure_reason (nullable),
solutions_tried (array), repo, language, framework, resolved_at, resolved_by,
human_override (boolean), pipeline_version

---

## TASK 3 — Azure Function Webhook Receiver
Create `/azure-functions/webhook-receiver/` with:

- `index.js` (or `function.js` for v4 model): HTTP trigger that receives POST requests
- Validates Content-Type is application/json
- Validates the payload against `webhook_payload.json` schema using `ajv`
- If valid: writes message to Service Bus queue, returns HTTP 202
- If invalid: returns HTTP 400 with validation error details
- Never returns 500 — catch all errors and return structured error responses
- Use `DefaultAzureCredential` for Service Bus authentication (not connection strings)

Also create:
- `function.json` or equivalent config
- `package.json` with dependencies: `@azure/functions`, `@azure/service-bus`,
  `@azure/identity`, `ajv`
- A mock test in `__tests__/webhook-receiver.test.js` using Jest that sends a valid
  and an invalid payload and asserts correct responses

---

## TASK 4 — End-of-Day Verification
The day gate: a mock GHAS webhook payload hits the Azure Function and a message
appears in the Service Bus queue.

Write a test script `scripts/day1-verify.js` that:
1. POSTs a valid `webhook_payload.json` example to the Function endpoint
2. Reads the next message from the Service Bus queue
3. Asserts the message body matches the sent payload
4. Prints PASS or FAIL with details

---

## SUCCESS CRITERIA FOR TODAY
- [ ] All 8 schema files created in `/shared/schemas/` and committed
- [ ] Azure resources provisioned (verify with `az resource list -g sentinel-d-rg`)
- [ ] Azure Function deployed and responding to POST requests
- [ ] Valid payload → message in Service Bus queue (confirmed by day1-verify.js)
- [ ] Invalid payload → HTTP 400 with error details
- [ ] Dead-letter queue configured and visible in Azure portal

---

## HOW TO USE PLAN MODE TODAY
Before starting Task 3 (the Function code), press Shift+Tab to enter Plan mode.
Tell Copilot: "Plan the implementation of Task 3 from my Day 1 goals."
Review the plan, adjust if needed, then approve it before Copilot writes any code.
This is especially important for the schema validation logic — get the AJV setup right.
