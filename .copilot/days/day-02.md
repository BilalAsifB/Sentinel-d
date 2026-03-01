# Day 2 Goals — Dev B
## SRE Agent, Historical DB Clients & Service Bus Consumer

Yesterday's gate passed: webhook → Service Bus confirmed.
Today: build the consumer that picks events up and the SRE Agent that classifies them.

---

## CONTEXT FROM YESTERDAY
- Service Bus queue: `vulnerability-events` is live
- Schema files in `/shared/schemas/` are frozen
- Azure Function is deployed and verified

---

## TASK 1 — Service Bus Consumer Base
Create `/sre-agent/consumer.js`:
- Polls the Service Bus queue using `ServiceBusClient` with `DefaultAzureCredential`
- Implements message lock renewal (lock duration is 5 min — renew at 4 min if processing takes long)
- On success: complete the message
- On failure: abandon the message (returns to queue for retry)
- After 10 failed attempts: message auto-moves to dead-letter (already configured on queue)
- Emits a `telemetry_classification.json` event downstream when done

---

## TASK 2 — KQL Auto-Generation
Create `/sre-agent/kql-generator.js`:

The function signature: `generateKQL(filePath, packageName) → string`

It calls the Azure OpenAI API (or Foundry endpoint — use env var `FOUNDRY_ENDPOINT`)
with a 128-token max output prompt that asks for a KQL query counting calls to the
given file path and package in the last 30 days, using only the `traces` table.

Then create `/sre-agent/kql-validator.js`:

The function signature: `validateKQL(kqlString) → { valid: boolean, reason?: string }`

Rules:
- PERMITTED tables (allowlist): traces, requests, exceptions, dependencies
- BLOCKED operators: externaldata, http_request, invoke, evaluate, plugins
- If the KQL references any non-permitted table: return invalid with reason
- If the KQL contains any blocked operator: return invalid with reason
- If valid: return { valid: true }

Write unit tests for the validator covering:
- Valid KQL passes
- Query targeting `users` table fails
- Query with `externaldata` operator fails
- Prompt injection attempt (CVE description containing malicious KQL) fails

---

## TASK 3 — Application Insights Query Execution
Create `/sre-agent/telemetry-query.js`:

Function: `queryTelemetry(kqlQuery, workspaceId) → { callCount: number, lastCalled: string | null }`

Uses Azure Monitor Query client (`@azure/monitor-query`) with `DefaultAzureCredential`.
Returns structured result — never throws, catches all errors and returns
`{ callCount: 0, lastCalled: null, error: string }` on failure.

---

## TASK 4 — Three-Way Classifier
Create `/sre-agent/classifier.js`:

Function: `classify(telemetryResult, event) → telemetry_classification`

Rules:
- `callCount > 0` → status: ACTIVE
- `callCount === 0` → status: DORMANT (routes to Human Decision Gate next)
- Populates all fields per the `telemetry_classification.json` schema
- blast_radius: HIGH if severity is CRITICAL or HIGH, MEDIUM if MEDIUM, LOW otherwise

---

## TASK 5 — Historical DB Write Client (Cosmos DB)
Create `/historical-db/write-client.js`:

This is the client called by the Safety Governor after a resolution.
Function: `writeResolutionRecord(record) → { id: string }`

Uses `@azure/cosmos` with `DefaultAzureCredential`.
Validates the record against `historical_db_record.json` schema before writing.
On conflict (same id): upsert, don't throw.
Logs the written document ID to App Insights structured log.

Also create `/historical-db/backlog-writer.js`:
Function: `writeDeferred(eventId, cveId, deferralTimestamp, annotation) → void`
Writes to Azure Table Storage `deferred-backlog` table.
Partition key: `deferred`, Row key: `eventId`.

---

## SUCCESS CRITERIA FOR TODAY
- [ ] Service Bus consumer running locally, picking up test messages
- [ ] KQL generator produces syntactically valid KQL for a test CVE
- [ ] KQL validator passes all unit tests (valid + 3 invalid cases)
- [ ] Three-way classifier returns correct status for ACTIVE and DORMANT mock inputs
- [ ] Historical DB write client writes a test record to Cosmos DB emulator
- [ ] Backlog writer writes a test record to local Table Storage emulator
