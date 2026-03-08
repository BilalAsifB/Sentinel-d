# Sentinel-D Demo Environment

## Overview

This directory contains a deliberately vulnerable Node.js Express app and
seeding scripts for demonstrating the Sentinel-D autonomous remediation pipeline.

**⚠️ DO NOT deploy this app to production.** It uses pinned vulnerable
dependencies to trigger GHAS alerts.

## Vulnerable Dependencies

| Package | Pinned Version | CVE | Severity |
|---------|---------------|-----|----------|
| log4js | 4.0.0 | CVE-2022-29167 | High |
| lodash | 4.17.20 | CVE-2021-23337 | High |
| jsonwebtoken | 8.5.0 | CVE-2022-23529 | Medium |

## Demo Paths

### Path A — Full Pipeline (Cold Start, <5 min)
1. Push code with vulnerable dependencies to demo repo
2. GHAS CodeQL scan triggers alert → webhook → Azure Function
3. SRE Agent classifies as ACTIVE (telemetry shows POST /api/log ~200×/day)
4. NLP Pipeline → Patch Generator → Sandbox → Safety Governor → PR
5. **Expected:** PR created in under 5 minutes

### Path B — RAG Replay (Second Run, <90 sec)
1. Ensure Log4Shell seed record is in Historical DB (`npm run seed-historical-db`)
2. Trigger same CVE again
3. Historical DB finds EXACT_MATCH → RAG replay reuses previous patch
4. Foundry API is **never called** (verify in App Insights)
5. **Expected:** PR created in under 90 seconds
6. **Key moment:** Timing difference (5 min vs 90 sec) demonstrates the learning flywheel

### Path C — Human Decision Gate (Dormant, <30 sec)
1. Trigger GHAS on zero-telemetry demo repo (sentinel-d-demo-dormant)
2. SRE Agent classifies as DORMANT (no App Insights traces)
3. GitHub Issue created with CVE data, 3 label options, 72-hour warning
4. Apply `sentinel/fix-now` label live during demo
5. Pipeline re-triggers and completes

## Setup

```bash
# 1. Install demo app dependencies
cd demo && npm install

# 2. Seed Application Insights with 48h of synthetic telemetry
npm run seed-telemetry          # or: node seed-telemetry.js --mock

# 3. Seed Historical DB with Log4Shell record for RAG replay
npm run seed-historical-db      # or: node seed-historical-db.js --mock

# 4. Start the demo app (optional — for local testing)
npm start
```

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `APPINSIGHTS_CONNECTION_STRING` | App Insights for telemetry seeding |
| `COSMOS_DB_ENDPOINT` | Cosmos DB for Historical DB seeding |
| `COSMOS_DB_DATABASE` | Database name (default: `sentinel`) |
| `COSMOS_DB_CONTAINER` | Container name (default: `historical_records`) |
| `JWT_SECRET` | Demo app JWT secret (default: `demo-secret-do-not-use`) |
