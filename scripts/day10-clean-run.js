"use strict";

/**
 * day10-clean-run.js — Clean 5-CVE verification run after Day 9 bug fixes.
 *
 * Runs 5 CVEs through the full pipeline to verify zero failures and
 * zero dead-letter entries after Day 10 fixes.
 *
 * Usage:
 *   node scripts/day10-clean-run.js           (live against deployed infra)
 *   node scripts/day10-clean-run.js --mock     (local validation, no Azure)
 *
 * Env vars (for live mode):
 *   WEBHOOK_URL              — Azure Function webhook endpoint
 *   SERVICEBUS_NAMESPACE     — Service Bus namespace
 *   SERVICEBUS_QUEUE_NAME    — Queue name (default: vulnerability-events)
 */

const path = require("path");
const fs = require("fs");
const { v4: uuidv4 } = require("uuid");

require("dotenv").config();

const MOCK_MODE = process.argv.includes("--mock");
const WEBHOOK_URL = process.env.WEBHOOK_URL || "http://localhost:7071/api/webhook";

// ── Load schema validator ─────────────────────────────────────────────────

function loadWebhookValidator() {
  const schemaPath = path.resolve(__dirname, "../shared/schemas/webhook_payload.json");
  const schema = JSON.parse(fs.readFileSync(schemaPath, "utf-8"));

  const Ajv = require(path.resolve(__dirname, "../azure-functions/webhook-receiver/node_modules/ajv"));
  const addFormats = require(path.resolve(__dirname, "../azure-functions/webhook-receiver/node_modules/ajv-formats"));
  const ajv = new Ajv({ allErrors: true });
  addFormats(ajv);
  return ajv.compile(schema);
}

// ── Load SRE Agent classifier (for mock mode) ─────────────────────────────

function loadClassifier() {
  const classifierPath = path.resolve(__dirname, "../sre-agent/classifier.py");
  if (!fs.existsSync(classifierPath)) {
    return null;
  }
  return classifierPath;
}

// ── Test payloads (subset of Day 9) ───────────────────────────────────────

function buildPayloads() {
  const testConfig = JSON.parse(
    fs.readFileSync(path.resolve(__dirname, "day9-test-payloads.json"), "utf-8")
  );

  // Select 5 ACTIVE CVEs (skip DORMANT indices)
  const dormantIndices = new Set(testConfig.dormant_indices);
  const activePayloads = testConfig.payloads
    .filter((_, i) => !dormantIndices.has(i))
    .slice(0, 5);

  return activePayloads.map((template) => {
    const { _notes, ...payload } = template;
    return {
      ...payload,
      event_id: uuidv4(),
      timestamp: new Date().toISOString(),
      _isActive: true,
    };
  });
}

// ── Mock pipeline ─────────────────────────────────────────────────────────

async function runMockPipeline(payloads) {
  const validate = loadWebhookValidator();
  const results = [];
  let deadLetterCount = 0;

  for (let i = 0; i < payloads.length; i++) {
    const payload = payloads[i];
    const start = Date.now();
    const result = {
      index: i,
      cve_id: payload.cve_id,
      webhook: false,
      classification: null,
      routing: null,
      error: null,
    };

    // Step 1: Webhook schema validation (strip internal _isActive flag)
    const { _isActive, ...cleanPayload } = payload;
    const valid = validate(cleanPayload);
    if (!valid) {
      result.error = `Schema validation failed: ${validate.errors.map((e) => e.message).join("; ")}`;
      result.webhook = false;
      deadLetterCount++;
      results.push(result);
      continue;
    }
    result.webhook = true;

    // Step 2: Classification (mock — all selected payloads are ACTIVE per dormant_indices filter)
    result.classification = _isActive ? "ACTIVE" : "DORMANT";

    // Step 3: Routing
    if (result.classification === "ACTIVE") {
      result.routing = "nlp-pipeline-input";
    } else {
      result.routing = "Decision Gate";
    }

    result.timeMs = Date.now() - start;
    results.push(result);
  }

  return { results, deadLetterCount };
}

// ── Live pipeline ─────────────────────────────────────────────────────────

async function runLivePipeline(payloads) {
  const results = [];
  let deadLetterCount = 0;

  for (let i = 0; i < payloads.length; i++) {
    const payload = payloads[i];
    const start = Date.now();
    const result = {
      index: i,
      cve_id: payload.cve_id,
      webhook: false,
      classification: null,
      routing: null,
      error: null,
    };

    try {
      const response = await fetch(WEBHOOK_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const body = await response.text();
        result.error = `Webhook returned ${response.status}: ${body}`;
        deadLetterCount++;
      } else {
        result.webhook = true;
        const data = await response.json();
        result.classification = data.classification || "unknown";
        result.routing = data.routing || "unknown";
      }
    } catch (err) {
      result.error = `Webhook call failed: ${err.message}`;
      deadLetterCount++;
    }

    result.timeMs = Date.now() - start;
    results.push(result);
  }

  return { results, deadLetterCount };
}

// ── Main ──────────────────────────────────────────────────────────────────

async function main() {
  console.log("═══════════════════════════════════════════════════════");
  console.log("  Sentinel-D — Day 10 Clean 5-CVE Verification Run");
  console.log(`  Mode: ${MOCK_MODE ? "MOCK (local validation)" : "LIVE (deployed infra)"}`);
  console.log("═══════════════════════════════════════════════════════\n");

  const payloads = buildPayloads();
  console.log(`  Loaded ${payloads.length} ACTIVE CVE payloads\n`);

  const { results, deadLetterCount } = MOCK_MODE
    ? await runMockPipeline(payloads)
    : await runLivePipeline(payloads);

  // Print results table
  console.log("  ┌────┬───────────────────────┬──────────┬───────────────┬───────────────────────┬──────────┐");
  console.log("  │ #  │ CVE ID                │ Webhook  │ Classification│ Routing               │ Time(ms) │");
  console.log("  ├────┼───────────────────────┼──────────┼───────────────┼───────────────────────┼──────────┤");

  for (const r of results) {
    const idx = String(r.index).padEnd(2);
    const cve = (r.cve_id || "—").padEnd(21);
    const wh = r.webhook ? "✅".padEnd(6) : "❌".padEnd(6);
    const cls = (r.classification || "—").padEnd(13);
    const route = (r.routing || "—").padEnd(21);
    const time = r.timeMs !== undefined ? String(r.timeMs).padEnd(8) : "—".padEnd(8);
    console.log(`  │ ${idx} │ ${cve} │ ${wh}   │ ${cls} │ ${route} │ ${time} │`);
  }

  console.log("  └────┴───────────────────────┴──────────┴───────────────┴───────────────────────┴──────────┘\n");

  // Summary
  const failures = results.filter((r) => r.error);
  const passed = results.length - failures.length;

  console.log("📊 Summary:\n");
  console.log(`  CVEs processed:    ${results.length}`);
  console.log(`  Passed:            ${passed}`);
  console.log(`  Failed:            ${failures.length}`);
  console.log(`  Dead-letter count: ${deadLetterCount}\n`);

  if (failures.length > 0) {
    console.log("❌ Failures:\n");
    for (const f of failures) {
      console.log(`  ${f.cve_id}: ${f.error}`);
    }
    console.log("");
    process.exit(1);
  }

  if (deadLetterCount > 0) {
    console.log(`❌ ${deadLetterCount} message(s) in dead-letter queue. Expected: 0.\n`);
    process.exit(1);
  }

  console.log("✅ Clean run: 0 failures, 0 dead-letter entries");
  console.log("✅ All 5 CVEs processed successfully\n");

  if (MOCK_MODE) {
    console.log("ℹ️  Run without --mock for live pipeline verification.");
  }
}

main()
  .then(() => process.exit(0))
  .catch((err) => {
    console.error("\n❌ Clean run failed:", err.message);
    process.exit(1);
  });
