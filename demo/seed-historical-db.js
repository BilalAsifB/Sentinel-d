"use strict";

/**
 * seed-historical-db.js — Seed the Log4Shell record for RAG replay demo.
 *
 * Seeds the exact record specified in the Sentinel-D v3.0 spec so that
 * Demo Path B (RAG replay) can demonstrate the learning flywheel:
 *   - Same CVE triggers → Historical DB finds EXACT_MATCH
 *   - RAG replay reuses previous patch → skips Foundry entirely
 *   - PR generated in <90 seconds vs ~5 minutes cold start
 *
 * Usage:
 *   node seed-historical-db.js              (live — writes to Cosmos DB)
 *   node seed-historical-db.js --mock       (validate only, no write)
 *   node seed-historical-db.js --cleanup    (delete seeded record)
 *
 * Env vars (for live mode):
 *   COSMOS_DB_ENDPOINT    — Cosmos DB account endpoint URL
 *   COSMOS_DB_DATABASE    — Database name (default: "sentinel")
 *   COSMOS_DB_CONTAINER   — Container name (default: "historical_records")
 */

const path = require("path");
const fs = require("fs");

require("dotenv").config();

const MOCK_MODE = process.argv.includes("--mock");
const CLEANUP_MODE = process.argv.includes("--cleanup");

// 1536-dim zero vector placeholder (text-embedding-3-small produces 1536-dim)
const PLACEHOLDER_EMBEDDING = new Array(1536).fill(0);

function buildSeedRecord() {
  return {
    id: "demo-seed-log4shell",
    cve_id: "CVE-2021-44228",
    affected_package: "log4j-core",
    affected_version_range: "<2.15.0",
    cve_description_embedding: PLACEHOLDER_EMBEDDING,
    fix_strategy_used: "API_MIGRATION",
    patch_diff:
      "--- a/pom.xml\n+++ b/pom.xml\n@@ -12 +12 @@\n-<version>2.14.0</version>\n+<version>2.15.0</version>",
    patch_outcome: "SUCCESS",
    solutions_tried: [
      {
        strategy: "VERSION_PIN",
        outcome: "FAILED",
        failure_reason: "Test suite failures in auth module",
      },
    ],
    repo: "org/previous-service",
    language: "Java",
    framework: "Spring Boot",
    resolved_at: new Date(Date.now() - 60 * 24 * 60 * 60 * 1000).toISOString(),
    resolved_by: "sentinel-d/safety-governor@3.0.0",
    human_override: false,
    pipeline_version: "3.0.0",
  };
}

function validateRecord(record) {
  const schemaPath = path.resolve(__dirname, "../shared/schemas/historical_db_record.json");
  const schema = JSON.parse(fs.readFileSync(schemaPath, "utf-8"));

  let Ajv, addFormats;
  try {
    Ajv = require(path.resolve(__dirname, "../historical-db/node_modules/ajv"));
    addFormats = require(path.resolve(__dirname, "../historical-db/node_modules/ajv-formats"));
  } catch {
    // Fallback: basic field presence check
    const required = ["id", "cve_id", "affected_package", "patch_outcome", "pipeline_version"];
    const missing = required.filter((f) => !(f in record));
    return { valid: missing.length === 0, errors: missing.map((f) => `Missing required field: ${f}`) };
  }

  const ajv = new Ajv({ allErrors: true });
  addFormats(ajv);
  const validate = ajv.compile(schema);
  const valid = validate(record);

  return {
    valid,
    errors: valid ? [] : validate.errors.map((e) => `${e.instancePath || "/"}: ${e.message}`),
  };
}

async function main() {
  console.log("═══════════════════════════════════════════════════════");
  console.log("  Sentinel-D — Demo Historical DB Seeder (Log4Shell)");
  console.log(`  Mode: ${CLEANUP_MODE ? "CLEANUP" : MOCK_MODE ? "MOCK (validate only)" : "LIVE"}`);
  console.log("═══════════════════════════════════════════════════════\n");

  const record = buildSeedRecord();

  console.log("📋 Validating record against schema...");
  const { valid, errors } = validateRecord(record);

  if (!valid) {
    console.error("❌ Schema validation failed:");
    errors.forEach((e) => console.error(`  - ${e}`));
    process.exit(1);
  }
  console.log("  ✅ Record passes schema validation\n");

  if (MOCK_MODE) {
    console.log("🔍 Record preview:\n");
    console.log(`  CVE:       ${record.cve_id}`);
    console.log(`  Package:   ${record.affected_package}`);
    console.log(`  Strategy:  ${record.fix_strategy_used}`);
    console.log(`  Outcome:   ${record.patch_outcome}`);
    console.log(`  Tried:     ${record.solutions_tried.length} previous attempt(s)`);
    console.log(`  Language:  ${record.language} / ${record.framework}`);
    console.log(`  Resolved:  ${record.resolved_at}`);
    console.log("\n✅ Validation complete. Run without --mock to write to Cosmos DB.");
    return;
  }

  if (CLEANUP_MODE) {
    const { deleteRecord } = require("../historical-db/cosmos-client");
    try {
      await deleteRecord(record.id, record.cve_id);
      console.log(`🗑️  Deleted ${record.id}`);
    } catch (err) {
      if (err.code === 404) {
        console.log(`⚠️  ${record.id} not found (already deleted)`);
      } else {
        throw err;
      }
    }
    return;
  }

  const { writeRecord } = require("../historical-db/cosmos-client");
  console.log("📝 Writing Log4Shell seed record to Cosmos DB...");
  const result = await writeRecord(record);
  console.log(`  ✅ Seeded ${record.cve_id} (id: ${result.id})`);
  console.log("\n✅ Demo Path B (RAG replay) is now ready.");
  console.log("   Triggering the same CVE should produce EXACT_MATCH and skip Foundry.");
}

main()
  .then(() => process.exit(0))
  .catch((err) => {
    console.error("❌ Seeder failed:", err.message);
    process.exit(1);
  });
