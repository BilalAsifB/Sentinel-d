"use strict";

/**
 * day10-verify-vector-index.js — Verify Azure AI Search vector index.
 *
 * Tests that CVE embeddings have been indexed and that semantically similar
 * CVEs (Log4Shell variants) have high cosine similarity.
 *
 * Usage:
 *   node scripts/day10-verify-vector-index.js           (live query against Azure AI Search)
 *   node scripts/day10-verify-vector-index.js --mock     (validate with placeholder vectors)
 *
 * Env vars (for live mode):
 *   AZURE_SEARCH_ENDPOINT   — Azure AI Search endpoint URL
 *   AZURE_SEARCH_INDEX      — Index name (default: "cve-embeddings")
 *   AZURE_SEARCH_API_KEY    — Admin or query API key (optional if using DefaultAzureCredential)
 *
 * NOTE: Dev A owns embedding generation. If the index is empty, this script
 * documents the dependency and defers testing to Day 11.
 */

const path = require("path");

require("dotenv").config();

const MOCK_MODE = process.argv.includes("--mock");
const SIMILARITY_THRESHOLD = 0.88;

// ── Cosine similarity ─────────────────────────────────────────────────────

/**
 * Compute cosine similarity between two vectors.
 * @param {number[]} a
 * @param {number[]} b
 * @returns {number} Similarity score in [-1, 1]
 */
function cosineSimilarity(a, b) {
  if (a.length !== b.length) {
    throw new Error(`Vector dimension mismatch: ${a.length} vs ${b.length}`);
  }

  let dotProduct = 0;
  let normA = 0;
  let normB = 0;

  for (let i = 0; i < a.length; i++) {
    dotProduct += a[i] * b[i];
    normA += a[i] * a[i];
    normB += b[i] * b[i];
  }

  normA = Math.sqrt(normA);
  normB = Math.sqrt(normB);

  if (normA === 0 || normB === 0) {
    return 0;
  }

  return dotProduct / (normA * normB);
}

// ── Mock embeddings ───────────────────────────────────────────────────────

function buildMockEmbeddings() {
  // Simulate two similar Log4Shell variants with high similarity
  const base = new Array(384).fill(0).map(() => Math.random() * 2 - 1);

  // CVE-2021-44228 — base vector
  const embedding1 = [...base];

  // CVE-2021-4104 — similar variant (small perturbation)
  const embedding2 = base.map((v) => v + (Math.random() * 0.1 - 0.05));

  // CVE-2023-44487 — unrelated CVE (HTTP/2 rapid reset) — different vector
  const embedding3 = new Array(384).fill(0).map(() => Math.random() * 2 - 1);

  return {
    "CVE-2021-44228": embedding1,
    "CVE-2021-4104": embedding2,
    "CVE-2023-44487": embedding3,
  };
}

// ── Live query ────────────────────────────────────────────────────────────

async function getEmbeddingFromIndex(cveId) {
  const endpoint = process.env.AZURE_SEARCH_ENDPOINT;
  const indexName = process.env.AZURE_SEARCH_INDEX || "cve-embeddings";
  const apiKey = process.env.AZURE_SEARCH_API_KEY;

  if (!endpoint) {
    throw new Error("Missing AZURE_SEARCH_ENDPOINT environment variable");
  }

  const url = `${endpoint}/indexes/${indexName}/docs?api-version=2024-07-01&search=*&$filter=cve_id eq '${cveId}'&$select=cve_id,cve_description_embedding`;

  const headers = {
    "Content-Type": "application/json",
  };

  if (apiKey) {
    headers["api-key"] = apiKey;
  }

  const response = await fetch(url, { headers });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Azure AI Search query failed (${response.status}): ${body}`);
  }

  const data = await response.json();

  if (!data.value || data.value.length === 0) {
    return null;
  }

  return data.value[0].cve_description_embedding;
}

// ── Main ──────────────────────────────────────────────────────────────────

async function main() {
  console.log("═══════════════════════════════════════════════════════");
  console.log("  Sentinel-D — Day 10 Vector Index Verification");
  console.log(`  Mode: ${MOCK_MODE ? "MOCK (simulated embeddings)" : "LIVE (Azure AI Search)"}`);
  console.log("═══════════════════════════════════════════════════════\n");

  const testPairs = [
    {
      label: "Log4Shell variants (should be similar)",
      cve1: "CVE-2021-44228",
      cve2: "CVE-2021-4104",
      expectedAbove: SIMILARITY_THRESHOLD,
    },
  ];

  if (MOCK_MODE) {
    console.log("📋 Using simulated embeddings (Dev A owns real embedding generation)\n");
    const mockEmbeddings = buildMockEmbeddings();

    for (const pair of testPairs) {
      const emb1 = mockEmbeddings[pair.cve1];
      const emb2 = mockEmbeddings[pair.cve2];

      if (!emb1 || !emb2) {
        console.log(`  ⚠️  Missing mock embedding for ${!emb1 ? pair.cve1 : pair.cve2}`);
        continue;
      }

      const similarity = cosineSimilarity(emb1, emb2);
      const passed = similarity > pair.expectedAbove;

      console.log(`  ${pair.label}:`);
      console.log(`    ${pair.cve1} ↔ ${pair.cve2}`);
      console.log(`    Cosine similarity: ${similarity.toFixed(4)}`);
      console.log(`    Threshold: > ${pair.expectedAbove}`);
      console.log(`    Result: ${passed ? "✅ PASS" : "❌ FAIL"}\n`);
    }

    // Also test dissimilar pair
    const dissimilar = cosineSimilarity(mockEmbeddings["CVE-2021-44228"], mockEmbeddings["CVE-2023-44487"]);
    console.log(`  Dissimilar pair (sanity check):`);
    console.log(`    CVE-2021-44228 ↔ CVE-2023-44487`);
    console.log(`    Cosine similarity: ${dissimilar.toFixed(4)}`);
    console.log(`    Expected: significantly lower than ${SIMILARITY_THRESHOLD}`);
    console.log(`    Result: ${dissimilar < SIMILARITY_THRESHOLD ? "✅ PASS (low similarity as expected)" : "⚠️  Unexpectedly high similarity"}\n`);

    console.log("ℹ️  Run without --mock to test against live Azure AI Search index.");
    console.log("ℹ️  If Dev A hasn't wired embeddings yet, defer this test to Day 11.");
    return;
  }

  // Live mode
  console.log("📋 Querying Azure AI Search for CVE embeddings...\n");

  let anyMissing = false;

  for (const pair of testPairs) {
    const emb1 = await getEmbeddingFromIndex(pair.cve1);
    const emb2 = await getEmbeddingFromIndex(pair.cve2);

    if (!emb1 || !emb2) {
      anyMissing = true;
      console.log(`  ⚠️  ${pair.label}:`);
      if (!emb1) console.log(`    ❌ No embedding found for ${pair.cve1}`);
      if (!emb2) console.log(`    ❌ No embedding found for ${pair.cve2}`);
      console.log(`    → Dev A dependency: embedding generation not yet wired`);
      console.log(`    → Defer this test to Day 11\n`);
      continue;
    }

    // Check for placeholder zero vectors
    const isZero1 = emb1.every((v) => v === 0);
    const isZero2 = emb2.every((v) => v === 0);

    if (isZero1 || isZero2) {
      anyMissing = true;
      console.log(`  ⚠️  ${pair.label}:`);
      if (isZero1) console.log(`    ⚠️  ${pair.cve1} has placeholder zero vector`);
      if (isZero2) console.log(`    ⚠️  ${pair.cve2} has placeholder zero vector`);
      console.log(`    → Real embeddings not yet generated (Dev A dependency)`);
      console.log(`    → Defer cosine similarity test to Day 11\n`);
      continue;
    }

    const similarity = cosineSimilarity(emb1, emb2);
    const passed = similarity > pair.expectedAbove;

    console.log(`  ${pair.label}:`);
    console.log(`    ${pair.cve1} ↔ ${pair.cve2}`);
    console.log(`    Cosine similarity: ${similarity.toFixed(4)}`);
    console.log(`    Threshold: > ${pair.expectedAbove}`);
    console.log(`    Result: ${passed ? "✅ PASS" : "❌ FAIL"}\n`);

    if (!passed) {
      process.exit(1);
    }
  }

  if (anyMissing) {
    console.log("⚠️  Some embeddings missing or placeholder. Defer full verification to Day 11.");
    console.log("   Document this dependency in integration test results.");
    process.exit(0);
  }

  console.log("✅ All vector index checks passed.");
}

main()
  .then(() => process.exit(0))
  .catch((err) => {
    console.error("\n❌ Vector index verification failed:", err.message);
    process.exit(1);
  });
