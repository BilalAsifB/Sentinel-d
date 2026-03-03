const path = require("path");
const { parseIssueMetadata } = require("./parse-issue");

require("dotenv").config();

// Reuse existing backlog writer from historical-db
const { writeDeferred } = require(path.resolve(
  __dirname,
  "../../historical-db/backlog-writer"
));

/**
 * Handle the sentinel/defer label: write to deferred backlog.
 * Sets defer_until to 30 days from now.
 * @param {string} issueBody - The GitHub Issue body
 * @param {string} [annotation] - Optional human annotation
 * @returns {Promise<{event_id: string, defer_until: string}>}
 */
async function handleDefer(issueBody, annotation) {
  const metadata = parseIssueMetadata(issueBody);

  const deferUntil = new Date();
  deferUntil.setDate(deferUntil.getDate() + 30);
  const deferralTimestamp = deferUntil.toISOString();

  await writeDeferred(
    metadata.event_id,
    metadata.cve_id,
    deferralTimestamp,
    annotation || "Deferred via sentinel/defer label"
  );

  return {
    event_id: metadata.event_id,
    defer_until: deferralTimestamp,
  };
}

module.exports = { handleDefer };
