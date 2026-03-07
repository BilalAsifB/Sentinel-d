"use strict";

/**
 * day10-verify-historical-db.js — Verify Historical DB records after Day 9 integration test.
 *
 * Queries Cosmos DB for all remediation records and validates:
 *   - At least 10 records exist (2 seeded + 8 from integration run)
 *   - Every record has required fields: cve_id, patch_outcome, solutions_tried, pipeline_version
 *   - pipeline_version === "3.0.0" for all records
 *   - patch_outcome is one of: SUCCESS, PARTIAL, FAILED, ACCEPTED_RISK
 *   - solutions_tried is an array
 *
 * Usage:
 *   node scripts/day10-verify-historical-db.js           (live query against Cosmos DB)
 *   node scripts/day10-verify-historical-db.js --mock     (validate seeded records locally)
 *
 * Env vars (for live mode):
 *   COSMOS_ENDPOINT or COSMOS_DB_ENDPOINT  — Cosmos DB account endpoint URL
 *   COSMOS_DB_NAME or COSMOS_DB_DATABASE   — Database name (default: "sentinel")
 *   COSMOS_CONTAINER_NAME or COSMOS_DB_CONTAINER — Container name (default: "historical_records")
 */

const path = require("path");
const fs = require("fs");

require("dotenv").config();

const MOCK_MODE = process.argv.includes("--mock");
const VALID_OUTCOMES = new Set(["SUCCESS", "PARTIAL", "FAILED", "ACCEPTED_RISK"]);
const EXPECTED_PIPELINE_VERSION = "3.0.0";
const MIN_RECORDS = 10;

// ── Schema loader ─────────────────────────────────────────────────────────

function loadValidator() {
  const schemaPath = path.resolve(__dirname, "../shared/schemas/historical_db_record.json");
  const schema = JSON.parse(fs.readFileSync(schemaPath, "utf-8"));

  const Ajv = require(path.resolve(__dirname, "../historical-db/node_modules/ajv"));
  const addFormats = require(path.resolve(__dirname, "../historical-db/node_modules/ajv-formats"));
  const ajv = new Ajv({ allErrors: true });
  addFormats(ajv);
  return ajv.compile(schema);
}

// ── Mock records ──────────────────────────────────────────────────────────

function buildMockRecords() {
  const PLACEHOLDER_EMBEDDING = new Array(384).fill(0);
  const now = new Date().toISOString();

  const seeded = [
    {
      id: "day9-seed-log4shell",
      cve_id: "CVE-2021-44228",
      affected_package: "org.apache.logging.log4j:log4j-core",
      affected_version_range: "<2.15.0",
      cve_description_embedding: PLACEHOLDER_EMBEDDING,
      fix_strategy_used: "API_MIGRATION",
      patch_diff: "--- a/pom.xml\n+++ b/pom.xml\n@@ -12 +12 @@\n-<version>2.14.0</version>\n+<version>2.15.0</version>",
      patch_outcome: "SUCCESS",
      solutions_tried: [
        { strategy: "VERSION_PIN", outcome: "FAILED", failure_reason: "Test suite failures in auth module" },
      ],
      repo: "org/previous-service",
      language: "Java",
      framework: "Spring Boot",
      resolved_at: new Date(Date.now() - 60 * 24 * 60 * 60 * 1000).toISOString(),
      resolved_by: "sentinel-d/safety-governor@3.0.0",
      human_override: false,
      pipeline_version: "3.0.0",
    },
    {
      id: "day9-seed-jackson",
      cve_id: "CVE-2020-9547",
      affected_package: "com.fasterxml.jackson.core:jackson-databind",
      affected_version_range: "<2.9.10.4",
      cve_description_embedding: PLACEHOLDER_EMBEDDING,
      fix_strategy_used: "VERSION_PIN",
      patch_diff: "--- a/pom.xml\n+++ b/pom.xml\n@@ -18 +18 @@\n-<jackson.version>2.9.10.3</jackson.version>\n+<jackson.version>2.9.10.4</jackson.version>",
      patch_outcome: "SUCCESS",
      solutions_tried: [],
      repo: "org/data-service",
      language: "Java",
      framework: "Spring Boot",
      resolved_at: new Date(Date.now() - 90 * 24 * 60 * 60 * 1000).toISOString(),
      resolved_by: "sentinel-d/safety-governor@3.0.0",
      human_override: false,
      pipeline_version: "3.0.0",
    },
  ];

  const testPayloadsPath = path.resolve(__dirname, "day9-test-payloads.json");
  const testConfig = JSON.parse(fs.readFileSync(testPayloadsPath, "utf-8"));
  const dormantIndices = new Set(testConfig.dormant_indices);

  const pipeline = testConfig.payloads
    .filter((_, i) => !dormantIndices.has(i))
    .map((p, i) => ({
      id: `day9-pipeline-${p.cve_id || `cve-${i}`}`,
      cve_id: p.cve_id,
      affected_package: p.affected_package || `pkg-${i}`,
      affected_version_range: p.affected_version_range || "<1.0.0",
      cve_description_embedding: PLACEHOLDER_EMBEDDING,
      fix_strategy_used: "VERSION_PIN",
      patch_diff: `--- a/package.json\n+++ b/package.json\n@@ -1 +1 @@\n-"old"\n+"new"`,
      patch_outcome: "SUCCESS",
      solutions_tried: [],
      repo: p.repo || "org/test-repo",
      language: p.language || "JavaScript",
      framework: p.framework || "Express",
      resolved_at: now,
      resolved_by: "sentinel-d/safety-governor@3.0.0",
      human_override: false,
      pipeline_version: "3.0.0",
    }));

  return [...seeded, ...pipeline];
}

// ── Verification logic ────────────────────────────────────────────────────

function verifyRecords(records) {
  const checks = {
    total: records.length,
    passed: 0,
    failed: 0,
    errors: [],
  };

  // Check minimum count
  if (records.length < MIN_RECORDS) {
    checks.errors.push(`Expected >= ${MIN_RECORDS} records, found ${records.length}`);
    checks.failed++;
  } else {
    checks.passed++;
  }

  const validate = loadValidator();

  for (const record of records) {
    const label = `${record.id || "unknown"} (${record.cve_id || "no-cve"})`;

    // Schema validation
    const valid = validate(record);
    if (!valid) {
      const fieldErrors = validate.errors.map(
        (e) => `  ${e.instancePath || "/"}: ${e.message}`
      );
      checks.errors.push(`${label}: schema validation failed:\n${fieldErrors.join("\n")}`);
      checks.failed++;
      continue;
    }

    // Required field checks (beyond schema)
    const fieldErrors = [];

    if (!record.cve_id) {
      fieldErrors.push("missing cve_id");
    }

    if (!VALID_OUTCOMES.has(record.patch_outcome)) {
      fieldErrors.push(`invalid patch_outcome: "${record.patch_outcome}" (expected one of: ${[...VALID_OUTCOMES].join(", ")})`);
    }

    if (!Array.isArray(record.solutions_tried)) {
      fieldErrors.push(`solutions_tried is not an array: ${typeof record.solutions_tried}`);
    }

    if (record.pipeline_version !== EXPECTED_PIPELINE_VERSION) {
      fieldErrors.push(`pipeline_version: "${record.pipeline_version}" (expected "${EXPECTED_PIPELINE_VERSION}")`);
    }

    if (fieldErrors.length > 0) {
      checks.errors.push(`${label}: ${fieldErrors.join("; ")}`);
      checks.failed++;
    } else {
      checks.passed++;
    }
  }

  return checks;
}

// ── Live query ────────────────────────────────────────────────────────────

async function queryAllRecords() {
  const { CosmosClient } = require("@azure/cosmos");
  const { DefaultAzureCredential } = require("@azure/identity");

  const endpoint = process.env.COSMOS_ENDPOINT || process.env.COSMOS_DB_ENDPOINT;
  const databaseName = process.env.COSMOS_DB_NAME || process.env.COSMOS_DB_DATABASE || "sentinel";
  const containerName = process.env.COSMOS_CONTAINER_NAME || process.env.COSMOS_DB_CONTAINER || "historical_records";

  if (!endpoint) {
    throw new Error("Missing COSMOS_ENDPOINT or COSMOS_DB_ENDPOINT environment variable");
  }

  const credential = new DefaultAzureCredential();
  const client = new CosmosClient({ endpoint, aadCredentials: credential });
  const container = client.database(databaseName).container(containerName);

  const { resources } = await container.items
    .query("SELECT * FROM c ORDER BY c.resolved_at DESC")
    .fetchAll();

  return resources;
}

// ── Main ──────────────────────────────────────────────────────────────────

async function main() {
  console.log("═══════════════════════════════════════════════════════");
  console.log("  Sentinel-D — Day 10 Historical DB Verification");
  console.log(`  Mode: ${MOCK_MODE ? "MOCK (local validation)" : "LIVE (Cosmos DB query)"}`);
  console.log("═══════════════════════════════════════════════════════\n");

  let records;

  if (MOCK_MODE) {
    console.log("📋 Building mock records (2 seeded + pipeline results)...\n");
    records = buildMockRecords();
  } else {
    console.log("📋 Querying all records from Cosmos DB...\n");
    records = await queryAllRecords();
  }

  console.log(`  Found ${records.length} record(s)\n`);

  // Print summary table
  console.log("  ┌───────────────────────┬────────────────┬──────────────┬─────────────────┐");
  console.log("  │ CVE ID                │ Outcome        │ Tried        │ Pipeline Ver    │");
  console.log("  ├───────────────────────┼────────────────┼──────────────┼─────────────────┤");

  for (const r of records) {
    const cve = (r.cve_id || "—").padEnd(21);
    const outcome = (r.patch_outcome || "—").padEnd(14);
    const tried = String(Array.isArray(r.solutions_tried) ? r.solutions_tried.length : "?").padEnd(12);
    const ver = (r.pipeline_version || "—").padEnd(15);
    console.log(`  │ ${cve} │ ${outcome} │ ${tried} │ ${ver} │`);
  }

  console.log("  └───────────────────────┴────────────────┴──────────────┴─────────────────┘\n");

  // Run verification
  console.log("🔍 Running verification checks...\n");
  const checks = verifyRecords(records);

  if (checks.errors.length > 0) {
    console.log("❌ Verification errors:\n");
    for (const err of checks.errors) {
      console.log(`  ❌ ${err}`);
    }
    console.log(`\n  Summary: ${checks.passed} passed, ${checks.failed} failed\n`);
    process.exit(1);
  }

  console.log(`  ✅ All ${checks.passed} checks passed`);
  console.log(`  ✅ ${records.length} records verified with correct fields`);
  console.log(`  ✅ All pipeline_version === "${EXPECTED_PIPELINE_VERSION}"`);
  console.log(`  ✅ All patch_outcome values are valid`);
  console.log(`  ✅ All solutions_tried are arrays\n`);

  if (MOCK_MODE) {
    console.log("ℹ️  Run without --mock to verify against live Cosmos DB.");
  }
}

main()
  .then(() => process.exit(0))
  .catch((err) => {
    console.error("\n❌ Verification failed:", err.message);
    process.exit(1);
  });
