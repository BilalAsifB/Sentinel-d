# Day 4 Goals — Dev B
## Container App GitHub Action + DB Write Path + Auto-Escalation Deploy

---

## CONTEXT
- SRE Agent classifies events (Day 2 ✓)
- Decision Gate creates issues and handles labels (Day 3 ✓)
- Today: build the ephemeral sandbox environment and wire the DB write path

---

## TASK 1 — Container App GitHub Action Skeleton
Create `.github/workflows/sandbox-validator.yml`:

Trigger: `workflow_dispatch` with inputs: `event_id`, `patch_diff_b64` (base64-encoded diff), `repo`, `language`

Steps:
1. Checkout the target repo at HEAD
2. Apply the patch diff (`echo $patch_diff_b64 | base64 -d | git apply`)
3. Create Azure Container App job (`az containerapp job create`) with:
   - Image: node:20-alpine (for JS repos) or python:3.11-slim (for Python)
   - Environment variables: event_id, test_command (from repo's package.json or pytest config)
   - Scale: 0→1 on trigger, max execution time: 15 minutes
4. Run the test suite inside the container
5. Capture exit code and test output as JSON
6. Tear down the Container App job (`az containerapp job delete`)
7. Write test results to `test_results.json`
8. Trigger the next workflow step (SSIM screenshot capture)

Benchmark the spin-up + teardown time and log it. Target: < 5 minutes total.
If it exceeds 8 minutes, add pre-warm logic.

---

## TASK 2 — Puppeteer Baseline Screenshot Capture
Create `/sandbox-validator/capture-baseline.js`:

Captures screenshots of three test routes before any patch is applied.
Routes (configurable via env vars, defaults for the demo app):
- `/` (home page)
- `/api/status` (API health endpoint, rendered as JSON)  
- `/dashboard` (main UI route)

For each route:
- Launch Puppeteer headless, navigate to URL
- Wait for network idle
- Capture full-page screenshot at 1280×720
- Save to `/sandbox-validator/baselines/[route-slug]-baseline.png`
- Commit baselines to Git LFS

These baselines are the "before" state. The SSIM module compares post-patch screenshots against them.

---

## TASK 3 — Historical DB Write Path Wiring
Create `/historical-db/cosmos-client.js`:

This is the unified Cosmos DB client used by both the write path (Safety Governor)
and eventually by Dev A's read path (they will implement their own read client).

Export two functions:
- `writeRecord(record)` — upsert a remediation record
- `getRecord(cveId)` — exact lookup by cve_id (used for testing the write path today)

Use `@azure/cosmos` with `DefaultAzureCredential`.
Connection info from env vars: `COSMOS_ENDPOINT`, `COSMOS_DB_NAME`, `COSMOS_CONTAINER_NAME`.

Write an integration test `__tests__/cosmos-write.test.js` that:
1. Writes a mock SUCCESS record for CVE-2021-44228
2. Reads it back using `getRecord`
3. Asserts all fields match
4. Cleans up the test record

---

## TASK 4 — Deploy the 72-Hour Auto-Escalation Logic App
Deploy the ARM template from Day 3 to Azure:

```bash
az deployment group create \
  --resource-group sentinel-d-rg \
  --template-file infrastructure/auto-escalation-logic-app.json \
  --parameters securityTeamLogin=$SECURITY_TEAM_GITHUB_LOGIN \
               securityTeamLeadLogin=$SECURITY_TEAM_LEAD_GITHUB_LOGIN
```

Test it by:
1. Creating a test GitHub Issue with label `sentinel/dormant` and a timestamp 73 hours ago
2. Manually triggering the Logic App run
3. Verifying the re-assignment and escalation comment appear on the issue

---

## SUCCESS CRITERIA FOR TODAY
- [ ] Container App GitHub Action completes a full spin-up → echo test → teardown cycle
- [ ] Spin-up + teardown time benchmarked and logged
- [ ] Three baseline screenshots captured and committed to Git LFS
- [ ] Cosmos DB write + read integration test passes against real Azure
- [ ] Logic App deployed and escalation test passes
