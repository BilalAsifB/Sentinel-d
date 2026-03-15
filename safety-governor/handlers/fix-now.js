"use strict";

/**
 * fix-now.js — Handler for sentinel/fix-now label on dormant decision issues.
 *
 * Reads the original webhook_payload from the GitHub Issue body metadata
 * block, then re-queues a message to the Service Bus vulnerability-events
 * queue with status_override=ACTIVE and the full original payload embedded.
 *
 * The SRE Agent consumer detects status_override=ACTIVE and skips the
 * telemetry query, forcing ACTIVE classification so the full remediation
 * pipeline runs immediately.
 *
 * Message format written to Service Bus:
 * {
 *   event_id: string,          — new UUID for this pipeline run
 *   cve_id: string,
 *   status_override: "ACTIVE",
 *   source: "human-decision-gate",
 *   decision: "FIX_NOW",
 *   original_payload: {        — full original webhook_payload fields
 *     event_id, cve_id, severity, affected_package, current_version,
 *     fix_version_range, file_path, line_range, repo, timestamp
 *   }
 * }
 *
 * Env vars:
 *   SERVICE_BUS_NAMESPACE  — Service Bus namespace (without .servicebus.windows.net)
 *   SERVICE_BUS_QUEUE_NAME — Queue name (default: vulnerability-events)
 */

const { ServiceBusClient } = require("@azure/service-bus");
const { DefaultAzureCredential } = require("@azure/identity");
const { randomUUID } = require("crypto");

const SB_NAMESPACE = process.env.SERVICE_BUS_NAMESPACE || process.env.SERVICEBUS_NAMESPACE || "";
const SB_QUEUE = process.env.SERVICE_BUS_QUEUE_NAME || process.env.SERVICEBUS_QUEUE_NAME || "vulnerability-events";

/**
 * Parse the sentinel metadata block from a GitHub Issue body.
 *
 * The decision issue template embeds the original webhook payload as an
 * HTML comment at the top of the issue body:
 *
 *   <!-- sentinel-metadata
 *   event_id: <uuid>
 *   cve_id: CVE-XXXX-XXXXX
 *   severity: CRITICAL
 *   affected_package: log4j-core
 *   current_version: 2.14.0
 *   fix_version_range: >=2.15.0
 *   file_path: src/main/java/Logger.java
 *   line_range: [142,168]
 *   repo: org/repo
 *   -->
 *
 * @param {string} issueBody - The full GitHub Issue body text.
 * @returns {object} Parsed metadata fields.
 * @throws {Error} If the metadata block is missing or malformed.
 */
function parseIssueMetadata(issueBody) {
  const metaMatch = issueBody.match(
    /<!--\s*sentinel-metadata\s*([\s\S]*?)-->/
  );

  if (!metaMatch) {
    throw new Error(
      "Issue body does not contain a sentinel-metadata block. " +
      "Cannot extract original payload for re-queuing."
    );
  }

  const metaBlock = metaMatch[1].trim();
  const fields = {};

  for (const line of metaBlock.split("\n")) {
    const colonIdx = line.indexOf(":");
    if (colonIdx === -1) continue;

    const key = line.slice(0, colonIdx).trim();
    const value = line.slice(colonIdx + 1).trim();

    if (!key) continue;

    // Parse line_range array: "[142,168]" → [142, 168]
    if (key === "line_range") {
      try {
        fields[key] = JSON.parse(value);
      } catch {
        fields[key] = [0, 0];
      }
    } else {
      fields[key] = value;
    }
  }

  // Validate required fields
  const required = [
    "cve_id",
    "severity",
    "affected_package",
    "current_version",
    "fix_version_range",
    "file_path",
    "repo",
  ];

  const missing = required.filter((f) => !fields[f]);
  if (missing.length > 0) {
    throw new Error(
      `Metadata block missing required fields: ${missing.join(", ")}`
    );
  }

  return fields;
}

/**
 * Handle the sentinel/fix-now label event.
 *
 * Parses the original webhook payload from the issue body, then re-queues
 * it to Service Bus with status_override=ACTIVE so the SRE Agent processes
 * it as an active vulnerability without re-running the telemetry query.
 *
 * @param {string} issueBody - The full GitHub Issue body text.
 * @returns {Promise<object>} Result with event_id and queue details.
 * @throws {Error} If metadata parsing or Service Bus write fails.
 */
async function handleFixNow(issueBody) {
  if (!SB_NAMESPACE) {
    throw new Error(
      "SERVICE_BUS_NAMESPACE environment variable is not set. " +
      "Cannot re-queue fix-now message."
    );
  }

  // Extract the original webhook payload from the issue metadata block
  const originalFields = parseIssueMetadata(issueBody);

  // Build the re-queue message with full original payload embedded
  const newEventId = randomUUID();
  const message = {
    event_id: newEventId,
    cve_id: originalFields.cve_id,
    status_override: "ACTIVE",
    source: "human-decision-gate",
    decision: "FIX_NOW",
    original_payload: {
      event_id: originalFields.event_id || newEventId,
      cve_id: originalFields.cve_id,
      severity: originalFields.severity,
      affected_package: originalFields.affected_package,
      current_version: originalFields.current_version,
      fix_version_range: originalFields.fix_version_range,
      file_path: originalFields.file_path,
      line_range: originalFields.line_range || [0, 0],
      repo: originalFields.repo,
      timestamp: new Date().toISOString(),
    },
  };

  // Write to Service Bus
  const credential = new DefaultAzureCredential();
  const client = new ServiceBusClient(
    `${SB_NAMESPACE}.servicebus.windows.net`,
    credential
  );

  try {
    const sender = client.createSender(SB_QUEUE);
    try {
      await sender.sendMessages({
        body: JSON.stringify(message),
        applicationProperties: {
          source: "human-decision-gate",
          event_id: newEventId,
          status_override: "ACTIVE",
          decision: "FIX_NOW",
        },
        contentType: "application/json",
      });

      console.log(
        JSON.stringify({
          level: "info",
          message: "fix-now re-queued to Service Bus",
          event_id: newEventId,
          original_cve_id: originalFields.cve_id,
          queue: SB_QUEUE,
        })
      );

      return {
        event_id: newEventId,
        queue: SB_QUEUE,
        original_cve_id: originalFields.cve_id,
      };
    } finally {
      await sender.close();
    }
  } finally {
    await client.close();
  }
}

module.exports = { handleFixNow, parseIssueMetadata };