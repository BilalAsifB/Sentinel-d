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
#    ⚠️  Run at least 10 minutes before Path A — App Insights has ingestion lag
npm run seed-telemetry          # or: node seed-telemetry.js --mock

# 3. Seed Historical DB with Log4Shell record for RAG replay
npm run seed-historical-db      # or: node seed-historical-db.js --mock

# 4. Start the demo app (optional — for local testing)
npm start
```

## Pre-Demo Checklist

Before running any demo path, verify:

```bash
# Validate seed record without writing
node seed-historical-db.js --mock

# Validate telemetry without writing
node seed-telemetry.js --mock

# Confirm seed record is in Cosmos DB
node -e "
const { CosmosClient } = require('@azure/cosmos');
const { DefaultAzureCredential } = require('@azure/identity');
const client = new CosmosClient({ endpoint: process.env.COSMOS_ENDPOINT, aadCredentials: new DefaultAzureCredential() });
client.database('sentinel-d-db').container('remediation-history')
  .item('demo-seed-log4shell', 'CVE-2021-44228').read()
  .then(r => console.log('✅ Seed record present:', r.resource.id))
  .catch(() => console.error('❌ Seed record missing — run seed-historical-db.js'));
"
```

## Reset Between Demo Runs

To reset Path A back to cold-start state (removes the record written by the live pipeline):

```bash
# Delete the live pipeline record (keeps the seed record intact)
node -e "
const { CosmosClient } = require('@azure/cosmos');
const { DefaultAzureCredential } = require('@azure/identity');
const client = new CosmosClient({ endpoint: process.env.COSMOS_ENDPOINT, aadCredentials: new DefaultAzureCredential() });
client.database('sentinel-d-db').container('remediation-history')
  .items.query({ query: \"SELECT c.id, c.cve_id FROM c WHERE c.cve_id = 'CVE-2021-44228' AND c.id != 'demo-seed-log4shell'\" })
  .fetchAll()
  .then(async ({ resources }) => {
    for (const r of resources) {
      await client.database('sentinel-d-db').container('remediation-history').item(r.id, r.cve_id).delete();
      console.log('🗑️  Deleted', r.id);
    }
    if (!resources.length) console.log('ℹ️  No live pipeline records found — already clean');
  });
"
```

To clean up the seed record entirely (e.g. after demo):

```bash
node seed-historical-db.js --cleanup
```

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | App Insights for telemetry seeding | *(required)* |
| `COSMOS_ENDPOINT` | Cosmos DB account endpoint URL | *(required)* |
| `COSMOS_DB_NAME` | Database name | `sentinel-d-db` |
| `COSMOS_CONTAINER_NAME` | Container name | `remediation-history` |
| `JWT_SECRET` | Demo app JWT secret | `demo-secret-do-not-use` |