const { TableClient } = require("@azure/data-tables");
const { DefaultAzureCredential } = require("@azure/identity");
const { withRetry } = require("../shared/retry");
const telemetry = require("../shared/telemetry");

require("dotenv").config();

const logger = {
  info: (data) => process.env.NODE_ENV !== "test" && telemetry.logInfo(data.message || "info", data),
  error: (data) => telemetry.logError(data.message || "error", data),
};

const TABLE_NAME = "deferredbacklog";

// Singleton TableClient — lazy initialized
let _tableClient = null;

/**
 * Get (or create) the singleton TableClient for the deferred backlog.
 * @returns {import("@azure/data-tables").TableClient}
 */
function getTableClient() {
  if (!_tableClient) {
    const TABLE_STORAGE_CONN = process.env.TABLE_STORAGE_CONN_STRING;
    const TABLE_STORAGE_ACCOUNT = process.env.TABLE_STORAGE_ACCOUNT || process.env.STORAGE_ACCOUNT_NAME;

    if (TABLE_STORAGE_CONN) {
      _tableClient = TableClient.fromConnectionString(TABLE_STORAGE_CONN, TABLE_NAME);
    } else if (TABLE_STORAGE_ACCOUNT) {
      const credential = new DefaultAzureCredential();
      _tableClient = new TableClient(
        `https://${TABLE_STORAGE_ACCOUNT}.table.core.windows.net`,
        TABLE_NAME,
        credential
      );
    } else {
      throw new Error("Missing TABLE_STORAGE_CONN_STRING or TABLE_STORAGE_ACCOUNT");
    }
  }
  return _tableClient;
}

/**
 * Write a deferred event to Azure Table Storage for later re-scan.
 * Partition key: "deferred", Row key: eventId.
 * @param {string} eventId - The event ID from the webhook payload
 * @param {string} cveId - The CVE identifier
 * @param {string} deferUntil - ISO 8601 timestamp when deferral expires
 * @param {string} annotation - Human annotation for the deferral
 * @param {object} [originalPayload] - Original webhook payload for re-queuing
 */
async function writeDeferred(eventId, cveId, deferUntil, annotation, originalPayload) {
  const tableClient = getTableClient();

  const entity = {
    partitionKey: "deferred",
    rowKey: eventId,
    cveId,
    defer_until: deferUntil,
    deferralTimestamp: deferUntil,
    original_payload: originalPayload ? JSON.stringify(originalPayload) : "",
    annotation,
    deferred_at: new Date().toISOString(),
    createdAt: new Date().toISOString(),
  };

  await withRetry(
    () => tableClient.upsertEntity(entity, "Replace"),
    { label: "table-upsert-deferred" }
  );

  logger.info({
    message: "Deferred backlog entry written",
    eventId,
    cveId,
  });
}

module.exports = { writeDeferred, getTableClient, _resetForTest: () => { _tableClient = null; } };
