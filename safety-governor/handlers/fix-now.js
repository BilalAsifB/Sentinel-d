const { ServiceBusClient } = require("@azure/service-bus");
const { DefaultAzureCredential } = require("@azure/identity");
const { parseIssueMetadata } = require("./parse-issue");

require("dotenv").config();

const SB_NAMESPACE = process.env.SERVICE_BUS_NAMESPACE;
const SB_QUEUE = process.env.SERVICE_BUS_QUEUE_NAME || "vulnerability-events";

/**
 * Handle the sentinel/fix-now label: re-queue the event as ACTIVE.
 * Sends the original event payload to Service Bus with status override.
 * @param {string} issueBody - The GitHub Issue body
 * @returns {Promise<{event_id: string}>}
 */
async function handleFixNow(issueBody) {
  const metadata = parseIssueMetadata(issueBody);

  if (!SB_NAMESPACE) {
    throw new Error("SERVICE_BUS_NAMESPACE environment variable is required");
  }

  const namespace = SB_NAMESPACE.includes('.servicebus.windows.net')
    ? SB_NAMESPACE
    : `${SB_NAMESPACE}.servicebus.windows.net`;
  const credential = new DefaultAzureCredential();
  const client = new ServiceBusClient(
    namespace,
    credential
  );
  const sender = client.createSender(SB_QUEUE);

  try {
    await sender.sendMessages({
      body: {
        event_id: metadata.event_id,
        cve_id: metadata.cve_id,
        status_override: "ACTIVE",
        source: "human-decision-gate",
        decision: "FIX_NOW",
      },
      applicationProperties: {
        source: "sentinel-decision-gate",
        decision: "FIX_NOW",
      },
    });
  } finally {
    await sender.close();
    await client.close();
  }

  return { event_id: metadata.event_id };
}

module.exports = { handleFixNow };
