"use strict";

/**
 * seed-telemetry.js — Seed Application Insights with synthetic telemetry.
 *
 * Creates 48 hours of synthetic traces showing ~200 POST /api/log calls
 * per day for the ACTIVE demo repo, and zero telemetry for DORMANT.
 *
 * Usage:
 *   node seed-telemetry.js              (live — writes to App Insights)
 *   node seed-telemetry.js --mock       (dry run — prints what would be sent)
 *
 * Env vars:
 *   APPINSIGHTS_CONNECTION_STRING — App Insights connection string
 */

const MOCK_MODE = process.argv.includes("--mock");
const HOURS_TO_SEED = 48;
const REQUESTS_PER_DAY = 200;

function generateSyntheticTraces() {
  const traces = [];
  const now = Date.now();
  const totalRequests = Math.floor((REQUESTS_PER_DAY / 24) * HOURS_TO_SEED);

  for (let i = 0; i < totalRequests; i++) {
    const hoursAgo = Math.random() * HOURS_TO_SEED;
    const timestamp = new Date(now - hoursAgo * 60 * 60 * 1000);
    const duration = Math.floor(Math.random() * 150) + 10; // 10-160ms
    const success = Math.random() > 0.02; // 98% success rate

    traces.push({
      name: "POST /api/log",
      url: "https://sentinel-d-demo-active.azurewebsites.net/api/log",
      duration,
      resultCode: success ? 200 : 500,
      success,
      timestamp: timestamp.toISOString(),
      properties: {
        "sentinel-d.demo": "true",
        "sentinel-d.repo": "sentinel-d-demo-active",
        environment: "production",
      },
    });
  }

  return traces.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
}

async function seedLive(traces) {
  let appInsights;
  try {
    appInsights = require("applicationinsights");
  } catch {
    console.error("❌ applicationinsights package not installed.");
    console.error("   Run: npm install applicationinsights");
    process.exit(1);
  }

  const connectionString = process.env.APPINSIGHTS_CONNECTION_STRING;
  if (!connectionString) {
    console.error("❌ APPINSIGHTS_CONNECTION_STRING not set.");
    process.exit(1);
  }

  appInsights.setup(connectionString).setAutoCollectRequests(false).start();
  const client = appInsights.defaultClient;

  console.log(`📡 Sending ${traces.length} traces to App Insights...`);

  for (const trace of traces) {
    client.trackRequest({
      name: trace.name,
      url: trace.url,
      duration: trace.duration,
      resultCode: trace.resultCode,
      success: trace.success,
      time: new Date(trace.timestamp),
      properties: trace.properties,
    });
  }

  await new Promise((resolve) => client.flush({ callback: resolve }));
  console.log("✅ All traces flushed to App Insights.");
}

async function main() {
  console.log("═══════════════════════════════════════════════════════");
  console.log("  Sentinel-D — Telemetry Seeder");
  console.log(`  Mode: ${MOCK_MODE ? "MOCK (dry run)" : "LIVE"}`);
  console.log(`  Traces: ~${REQUESTS_PER_DAY * 2} over ${HOURS_TO_SEED} hours`);
  console.log("═══════════════════════════════════════════════════════\n");

  const traces = generateSyntheticTraces();

  console.log(`📊 Generated ${traces.length} synthetic request traces`);
  console.log(`   Earliest: ${traces[0].timestamp}`);
  console.log(`   Latest:   ${traces[traces.length - 1].timestamp}`);
  console.log(`   Success:  ${traces.filter((t) => t.success).length}`);
  console.log(`   Failures: ${traces.filter((t) => !t.success).length}\n`);

  if (MOCK_MODE) {
    console.log("🔍 Sample traces (first 5):\n");
    for (const trace of traces.slice(0, 5)) {
      console.log(`  ${trace.timestamp} — ${trace.name} → ${trace.resultCode} (${trace.duration}ms)`);
    }
    console.log("\n✅ Mock complete. Run without --mock to send to App Insights.");
    return;
  }

  await seedLive(traces);
}

main()
  .then(() => process.exit(0))
  .catch((err) => {
    console.error("❌ Seeder failed:", err.message);
    process.exit(1);
  });
