"use strict";

/**
 * day9-seed-historical-db.js — Seed Historical DB for Day 9 integration test.
 *
 * Seeds 2 CVE records into Cosmos DB so the pipeline can demonstrate
 * EXACT_MATCH → RAG replay during the 10-CVE integration test.
 *
 * Usage:
 *   node scripts/day9-seed-historical-db.js           (live write to Cosmos DB)
 *   node scripts/day9-seed-historical-db.js --mock     (validate only, no write)
 *   node scripts/day9-seed-historical-db.js --cleanup   (delete seeded records)
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

// Placeholder 384-dimension zero vector (Dev A owns real embedding generation)
const PLACEHOLDER_EMBEDDING = new Array(384).fill(0);

/**
 * Build the two seed records conforming to historical_db_record.json schema.
 * @returns {object[]}
 */
function buildSeedRecords() {
  return [
    {
      id: "day9-seed-log4shell",
      cve_id: "CVE-2021-44228",
      affected_package: "org.apache.logging.log4j:log4j-core",
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
          failure_reason:
            "Test suite failures in auth module — incompatible with 2.15 auth API",
        },
      ],
      repo: "org/previous-service",
      language: "Java",
      framework: "Spring Boot",
      resolved_at: new Date(
        Date.now() - 60 * 24 * 60 * 60 * 1000
      ).toISOString(),
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
      patch_diff:
        '--- a/pom.xml\n+++ b/pom.xml\n@@ -18 +18 @@\n-<jackson.version>2.9.10.3</jackson.version>\n+<jackson.version>2.9.10.4</jackson.version>',
      patch_outcome: "SUCCESS",
      solutions_tried: [],
      repo: "org/data-service",
      language: "Java",
      framework: "Spring Boot",
      resolved_at: new Date(
        Date.now() - 90 * 24 * 60 * 60 * 1000
      ).toISOString(),
      resolved_by: "sentinel-d/safety-governor@3.0.0",
      human_override: false,
      pipeline_version: "3.0.0",
    },
  ];
}

/**
 * Validate records against the historical_db_record.json schema.
 * Reuses ajv from the historical-db module.
 * @param {object[]} records
 * @returns {{ valid: boolean, errors: string[] }}
 */
function validateRecords(records) {
  const schemaPath = path.resolve(
    __dirname,
    "../shared/schemas/historical_db_record.json"
  );
  const schema = JSON.parse(fs.readFileSync(schemaPath, "utf-8"));

  const Ajv = require(path.resolve(__dirname, "../historical-db/node_modules/ajv"));
  const addFormats = require(path.resolve(__dirname, "../historical-db/node_modules/ajv-formats"));
  const ajv = new Ajv({ allErrors: true });
  addFormats(ajv);
  const validate = ajv.compile(schema);

  const errors = [];
  for (const record of records) {
    const valid = validate(record);
    if (!valid) {
      const fieldErrors = validate.errors.map(
        (e) => `${record.id}: ${e.instancePath || "/"}: ${e.message}`
      );
      errors.push(...fieldErrors);
    }
  }

  return { valid: errors.length === 0, errors };
}

async function seedRecords(records) {
  const { writeRecord } = require("../historical-db/cosmos-client");

  for (const record of records) {
    try {
      const result = await writeRecord(record);
      console.log(`  ✅ Seeded ${record.cve_id} (id: ${result.id})`);
    } catch (err) {
      console.error(`  ❌ Failed to seed ${record.cve_id}: ${err.message}`);
      throw err;
    }
  }
}

async function cleanupRecords(records) {
  const { deleteRecord } = require("../historical-db/cosmos-client");

  for (const record of records) {
    try {
      await deleteRecord(record.id, record.cve_id);
      console.log(`  🗑️  Deleted ${record.cve_id} (id: ${record.id})`);
    } catch (err) {
      if (err.code === 404) {
        console.log(`  ⚠️  ${record.cve_id} not found (already deleted)`);
      } else {
        console.error(
          `  ❌ Failed to delete ${record.cve_id}: ${err.message}`
        );
      }
    }
  }
}

async function main() {
  console.log("═══════════════════════════════════════════════════════");
  console.log("  Sentinel-D — Day 9 Historical DB Seeder");
  console.log(
    `  Mode: ${CLEANUP_MODE ? "CLEANUP" : MOCK_MODE ? "MOCK (validate only)" : "LIVE"}`
  );
  console.log("═══════════════════════════════════════════════════════\n");

  const records = buildSeedRecords();

  // Always validate first
  console.log("📋 Validating records against schema...");
  const { valid, errors } = validateRecords(records);

  if (!valid) {
    console.error("❌ Schema validation failed:");
    for (const err of errors) {
      console.error(`  - ${err}`);
    }
    process.exit(1);
  }

  console.log(`  ✅ ${records.length} records pass schema validation\n`);

  if (MOCK_MODE) {
    console.log("🔍 Mock mode — printing records (no Cosmos DB write):\n");
    for (const record of records) {
      console.log(`  📄 ${record.cve_id} (${record.id})`);
      console.log(`     Strategy: ${record.fix_strategy_used}`);
      console.log(`     Outcome:  ${record.patch_outcome}`);
      console.log(
        `     Tried:    ${record.solutions_tried.length} previous attempt(s)`
      );
    }
    console.log("\n✅ Validation complete. Run without --mock to write to Cosmos DB.");
    return;
  }

  if (CLEANUP_MODE) {
    console.log("🗑️  Cleaning up seeded records...");
    await cleanupRecords(records);
    console.log("\n✅ Cleanup complete.");
    return;
  }

  // Live mode: write to Cosmos DB
  console.log("📝 Writing records to Cosmos DB...");
  await seedRecords(records);
  console.log("\n✅ Seeding complete. Both CVEs are now in the Historical DB.");
  console.log(
    "   The pipeline should return EXACT_MATCH for these CVEs during the integration test."
  );
}

main()
  .then(() => process.exit(0))
  .catch((err) => {
    console.error("\n❌ Seeder failed:", err.message);
    process.exit(1);
  });
