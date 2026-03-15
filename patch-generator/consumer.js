"use strict";

/**
 * consumer.js — Patch Generator Service Bus Consumer
 *
 * Subscribes to patch-generator-input / patch-generator-sub.
 * For each message:
 *   - If historical_patch_available=true AND replay_eligible=true
 *     → spawn rag_replay_runner.py (git apply --check, build candidate_patch)
 *     → on success: publish RAG_REPLAY candidate_patch to sandbox-input
 *     → on failure: fall through to Foundry
 *   - Otherwise → call generatePatch() from foundry-client.js
 *
 * Env vars (from .env):
 *   SERVICEBUS_NAMESPACE      — e.g. sentinel-d-bus
 *   PATCH_GENERATOR_TOPIC     — input topic  (default: patch-generator-input)
 *   SANDBOX_TOPIC             — output topic (default: sandbox-input)
 *   AZURE_CLIENT_ID / AZURE_CLIENT_SECRET / AZURE_TENANT_ID — for DefaultAzureCredential
 */

require("dotenv").config({ path: require("path").join(__dirname, "../.env") });

const { ServiceBusClient } = require("@azure/service-bus");
const { DefaultAzureCredential } = require("@azure/identity");
const { spawn } = require("child_process");
const path = require("path");

const { generatePatch } = require("./foundry-client");
const telemetry = require("../shared/telemetry");

// ── Config ───────────────────────────────────────────────────────────────────

const SB_NAMESPACE = process.env.SERVICEBUS_NAMESPACE;
const INPUT_TOPIC = process.env.PATCH_GENERATOR_TOPIC || "patch-generator-input";
const INPUT_SUBSCRIPTION = "patch-generator-sub";
const OUTPUT_TOPIC = process.env.SANDBOX_TOPIC || "sandbox-input";
const LOCK_RENEWAL_MS = 4 * 60 * 1000; // 4 min (lock TTL = 5 min)

if (!SB_NAMESPACE) {
  console.error("[FATAL] SERVICEBUS_NAMESPACE is not set");
  process.exit(1);
}

// ── RAG Replay via Python child process ──────────────────────────────────────

/**
 * Invoke rag_replay_runner.py with the structured_context JSON.
 * Returns parsed candidate_patch on success, null on failure.
 *
 * @param {object} structuredContext
 * @returns {Promise<object|null>}
 */
function runRagReplay(structuredContext) {
  return new Promise((resolve) => {
    const runnerPath = path.join(__dirname, "rag_replay_runner.py");
    const input = JSON.stringify(structuredContext);

    const child = spawn("python3", [runnerPath], {
      cwd: path.join(__dirname, ".."),
      env: process.env,
    });

    let stdout = "";
    let stderr = "";

    child.stdin.write(input);
    child.stdin.end();

    child.stdout.on("data", (d) => (stdout += d));
    child.stderr.on("data", (d) => (stderr += d));

    child.on("close", (code) => {
      if (stderr.trim()) {
        console.error(`[RAG_REPLAY] stderr: ${stderr.trim()}`);
      }
      if (code !== 0) {
        console.warn(`[RAG_REPLAY] Runner exited ${code} — falling through to Foundry`);
        return resolve(null);
      }
      try {
        const result = JSON.parse(stdout.trim());
        if (result && result.status === "PATCH_GENERATED") {
          console.log(`[RAG_REPLAY] Success for event ${result.event_id}`);
          return resolve(result);
        }
        console.warn(`[RAG_REPLAY] Runner returned status=${result.status} — falling through`);
        resolve(null);
      } catch (e) {
        console.error(`[RAG_REPLAY] Failed to parse runner output: ${e.message}`);
        resolve(null);
      }
    });

    child.on("error", (err) => {
      console.error(`[RAG_REPLAY] Spawn error: ${err.message}`);
      resolve(null);
    });
  });
}

// ── Message processing ───────────────────────────────────────────────────────

/**
 * Parse raw Service Bus message body (azure/service-bus v7 compatible).
 * @param {object} message
 * @returns {object}
 */
function parseMessageBody(message) {
  // azure/service-bus JS v7 exposes body as already-parsed for JSON content-type
  // but falls back to Buffer for AMQP data sections
  let raw = message.body;
  if (Buffer.isBuffer(raw)) raw = raw.toString("utf8");
  if (typeof raw === "string") return JSON.parse(raw);
  if (typeof raw === "object" && raw !== null) return raw;
  throw new Error(`Unexpected body type: ${typeof raw}`);
}

/**
 * Process one message end-to-end.
 * @param {object} message
 * @param {ServiceBusClient} sbClient
 * @returns {Promise<object>} candidate_patch
 */
async function processMessage(message, sbClient) {
  const body = parseMessageBody(message);

  const eventId = body.event_id;
  const structuredContext = body.structured_context;
  const webhookPayload = body.webhook_payload || {};

  if (!eventId || !structuredContext) {
    throw new Error(
      `Malformed message ${message.messageId}: missing event_id or structured_context`
    );
  }

  console.log(
    `[PATCH_GEN] Processing event=${eventId} ` +
    `historical_match=${structuredContext.historical_match_status} ` +
    `patch_available=${structuredContext.historical_patch_available}`
  );

  let candidatePatch = null;

  // ── Path A: RAG Replay ────────────────────────────────────────────────────
  const replayEligible =
    structuredContext.historical_patch_available === true &&
    structuredContext.replay_eligible === true &&
    structuredContext.historical_patch_diff;

  if (replayEligible) {
    console.log(`[PATCH_GEN] Attempting RAG replay for event=${eventId}`);
    candidatePatch = await runRagReplay(structuredContext);

    if (candidatePatch) {
      telemetry.trackEvent("PatchGeneration", {
        event_id: eventId,
        path: "RAG_REPLAY",
        status: candidatePatch.status,
      });
    } else {
      console.warn(`[PATCH_GEN] RAG replay failed for ${eventId} — falling through to Foundry`);
    }
  }

  // ── Path B: Foundry (new generation or replay fallback) ───────────────────
  if (!candidatePatch) {
    console.log(`[PATCH_GEN] Calling Foundry for event=${eventId}`);
    candidatePatch = await generatePatch(structuredContext);

    telemetry.trackEvent("PatchGeneration", {
      event_id: eventId,
      path: "FOUNDRY",
      status: candidatePatch.status,
      llm_confidence: candidatePatch.llm_confidence,
    });
  }

  // ── Publish to sandbox-input ──────────────────────────────────────────────
  const outboundBody = {
    event_id: eventId,
    candidate_patch: candidatePatch,
    structured_context: structuredContext,
    webhook_payload: webhookPayload,
  };

  const sender = sbClient.createSender(OUTPUT_TOPIC);
  try {
    const sbMsg = {
      body: JSON.stringify(outboundBody),
      contentType: "application/json",
      applicationProperties: {
        source: "patch-generator",
        event_id: eventId,
        patch_status: candidatePatch.status,
        patch_source: candidatePatch.source,
        llm_confidence: candidatePatch.llm_confidence,
      },
    };
    await sender.sendMessages(sbMsg);
    console.log(
      `[PATCH_GEN] Published candidate_patch for event=${eventId} ` +
      `status=${candidatePatch.status} source=${candidatePatch.source} ` +
      `confidence=${candidatePatch.llm_confidence} → topic=${OUTPUT_TOPIC}`
    );
  } finally {
    await sender.close();
  }

  return candidatePatch;
}

// ── Main consumer loop ───────────────────────────────────────────────────────

async function startConsumer() {
  const credential = new DefaultAzureCredential();
  const sbClient = new ServiceBusClient(
    `${SB_NAMESPACE}.servicebus.windows.net`,
    credential
  );

  const receiver = sbClient.createReceiver(INPUT_TOPIC, INPUT_SUBSCRIPTION, {
    receiveMode: "peekLock",
  });

  console.log(
    `[PATCH_GEN] Consumer started — topic=${INPUT_TOPIC} sub=${INPUT_SUBSCRIPTION} → ${OUTPUT_TOPIC}`
  );

  let stopping = false;
  const stopHandler = () => {
    console.log("[PATCH_GEN] Shutdown signal received...");
    stopping = true;
  };
  process.on("SIGINT", stopHandler);
  process.on("SIGTERM", stopHandler);

  while (!stopping) {
    let messages;
    try {
      messages = await receiver.receiveMessages(1, { maxWaitTimeInMs: 5000 });
    } catch (err) {
      if (stopping) break;
      console.error(`[PATCH_GEN] receiveMessages error: ${err.message}`);
      await new Promise((r) => setTimeout(r, 2000));
      continue;
    }

    for (const message of messages) {
      // Start lock renewal
      const renewalInterval = setInterval(async () => {
        try {
          await receiver.renewMessageLock(message);
        } catch (e) {
          console.error(`[PATCH_GEN] Lock renewal failed: ${e.message}`);
        }
      }, LOCK_RENEWAL_MS);

      try {
        await processMessage(message, sbClient);
        await receiver.completeMessage(message);
      } catch (err) {
        console.error(
          `[PATCH_GEN] Processing failed for message ${message.messageId}: ${err.message}`,
          err
        );
        await receiver.abandonMessage(message);
      } finally {
        clearInterval(renewalInterval);
      }
    }
  }

  console.log("[PATCH_GEN] Shutting down...");
  await receiver.close();
  await sbClient.close();
}

// ── Entry point ──────────────────────────────────────────────────────────────
startConsumer().catch((err) => {
  console.error("[PATCH_GEN] Fatal startup error:", err);
  process.exit(1);
});