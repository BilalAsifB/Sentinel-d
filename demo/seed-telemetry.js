"use strict";

/**
 * seed-telemetry.js — Seed Application Insights with synthetic telemetry.
 *
 * Creates 48 hours of synthetic request traces showing ~200 POST /api/log
 * calls per day for the ACTIVE demo repo. These appear in the App Insights
 * ``requests`` table, which is what the SRE Agent KQL queries.
 *
 * Usage:
 *   node seed-telemetry.js              (live — writes to App Insights)
 *   node seed-telemetry.js --mock       (dry run — prints what would be sent)
 *   node seed-telemetry.js --verify     (query App Insights to confirm seeding)
 *
 * Env vars:
 *   APPLICATIONINSIGHTS_CONNECTION_STRING — App Insights connection string
 *
 * Notes:
 *   - Uses applicationinsights v3 SDK (flush() returns a Promise, no callback)
 *   - Sends in batches of 50 to avoid overwhelming the ingestion endpoint
 *   - App Insights has 2-5 minute ingestion lag — wait before running Path A
 */

require("dotenv").config({ path: require("path").join(__dirname, "../.env") });

const MOCK_MODE = process.argv.includes("--mock");
const VERIFY_MODE = process.argv.includes("--verify");
const HOURS_TO_SEED = 48;
const REQUESTS_PER_DAY = 200;
const BATCH_SIZE = 50;
const BATCH_DELAY_MS = 500;

function generateSyntheticRequests() {
  const requests = [];
  const now = Date.now();
  const totalRequests = Math.floor((REQUESTS_PER_DAY / 24) * HOURS_TO_SEED);

  for (let i = 0; i < totalRequests; i++) {
    const hoursAgo = Math.random() * HOURS_TO_SEED;
    const timestamp = new Date(now - hoursAgo * 60 * 60 * 1000);
    const duration = Math.floor(Math.random() * 150) + 10; // 10-160ms
    const success = Math.random() > 0.02; // 98% success rate

    requests.push({
      name: "POST /api/log",
      url: "https://sentinel-d-demo-active.azurewebsites.net/api/log",
      duration,
      resultCode: success ? 200 : 500,
      success,
      timestamp,
      properties: {
        "sentinel-d.demo": "true",
        "sentinel-d.repo": "sentinel-d-demo-active",
        environment: "production",
      },
    });
  }

  return requests.sort((a, b) => a.timestamp - b.timestamp);
}

async function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function seedLive(requests) {
  let appInsights;
  try {
    appInsights = require("applicationinsights");
  } catch {
    console.error("❌ applicationinsights package not installed.");
    console.error("   Run: npm install applicationinsights");
    process.exit(1);
  }

  const connectionString = process.env.APPLICATIONINSIGHTS_CONNECTION_STRING;
  if (!connectionString) {
    console.error("❌ APPLICATIONINSIGHTS_CONNECTION_STRING not set.");
    console.error("   Load your .env: export $(grep -v '^#' ../.env | xargs)");
    process.exit(1);
  }

  // Configure SDK — disable auto-collection to avoid noise
  appInsights
    .setup(connectionString)
    .setAutoCollectRequests(false)
    .setAutoCollectPerformance(false)
    .setAutoCollectExceptions(false)
    .setAutoCollectDependencies(false)
    .setAutoCollectConsole(false)
    .setUseDiskRetryCaching(false)
    .start();

  const client = appInsights.defaultClient;

  console.log(`📡 Sending ${requests.length} requests in batches of ${BATCH_SIZE}...`);

  let sent = 0;
  for (let i = 0; i < requests.length; i += BATCH_SIZE) {
    const batch = requests.slice(i, i + BATCH_SIZE);

    for (const req of batch) {
      client.trackRequest({
        name: req.name,
        url: req.url,
        duration: req.duration,
        resultCode: req.resultCode,
        success: req.success,
        time: req.timestamp,
        properties: req.properties,
      });
    }

    // Flush each batch — applicationinsights v3 returns a Promise
    await client.flush();
    sent += batch.length;
    process.stdout.write(`\r   Sent ${sent}/${requests.length}...`);

    // Brief pause between batches to avoid rate limiting
    if (i + BATCH_SIZE < requests.length) {
      await sleep(BATCH_DELAY_MS);
    }
  }

  console.log(`\n✅ All ${requests.length} requests flushed to App Insights.`);
  console.log("⏳ Note: App Insights has 2-5 minute ingestion lag.");
  console.log("   Wait before running Path A to ensure telemetry is queryable.");
}

async function verifySeeding() {
  const { DefaultAzureCredential } = require("@azure/identity");
  const { LogsQueryClient } = require("@azure/monitor-query");

  const resourceId = process.env.APP_INSIGHTS_RESOURCE_ID;
  if (!resourceId) {
    console.error("❌ APP_INSIGHTS_RESOURCE_ID not set in .env");
    process.exit(1);
  }

  const client = new LogsQueryClient(new DefaultAzureCredential());

  console.log("🔍 Querying App Insights to verify seeded telemetry...");

  try {
    const result = await client.queryResource(
      resourceId,
      `requests
| where timestamp > ago(3d)
| where name == "POST /api/log"
| summarize call_count=count(), last_called=max(timestamp)`,
      { duration: "P3D" }
    );

    if (result.tables && result.tables[0].rows.length > 0) {
      const row = result.tables[0].rows[0];
      console.log(`✅ Telemetry verified:`);
      console.log(`   call_count: ${row[0]}`);
      console.log(`   last_called: ${row[1]}`);
      if (row[0] > 0) {
        console.log("✅ SRE Agent will classify this CVE as ACTIVE");
      } else {
        console.log("⚠️  call_count is 0 — seeding may not have completed yet");
        console.log("   Wait 5 minutes and run --verify again");
      }
    } else {
      console.log("⚠️  No rows returned — seeding not yet visible in App Insights");
      console.log("   Wait 5 minutes and run --verify again");
    }
  } catch (err) {
    console.error("❌ Verification query failed:", err.message);
  }
}

async function main() {
  console.log("═══════════════════════════════════════════════════════");
  console.log("  Sentinel-D — Telemetry Seeder");
  console.log(`  Mode: ${VERIFY_MODE ? "VERIFY" : MOCK_MODE ? "MOCK (dry run)" : "LIVE"}`);
  if (!VERIFY_MODE) {
    console.log(`  Requests: ~${REQUESTS_PER_DAY * 2} over ${HOURS_TO_SEED} hours`);
  }
  console.log("═══════════════════════════════════════════════════════\n");

  if (VERIFY_MODE) {
    await verifySeeding();
    return;
  }

  const requests = generateSyntheticRequests();

  console.log(`📊 Generated ${requests.length} synthetic request records`);
  console.log(`   Earliest: ${requests[0].timestamp.toISOString()}`);
  console.log(`   Latest:   ${requests[requests.length - 1].timestamp.toISOString()}`);
  console.log(`   Success:  ${requests.filter((r) => r.success).length}`);
  console.log(`   Failures: ${requests.filter((r) => !r.success).length}\n`);

  if (MOCK_MODE) {
    console.log("🔍 Sample requests (first 5):\n");
    for (const req of requests.slice(0, 5)) {
      console.log(
        `  ${req.timestamp.toISOString()} — ${req.name} → ${req.resultCode} (${req.duration}ms)`
      );
    }
    console.log("\n✅ Mock complete. Run without --mock to send to App Insights.");
    console.log("   After seeding, run --verify to confirm data is queryable.");
    return;
  }

  await seedLive(requests);
}

main()
  .then(() => process.exit(0))
  .catch((err) => {
    console.error("❌ Seeder failed:", err.message);
    process.exit(1);
  });