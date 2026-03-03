const path = require("path");
const { parseIssueMetadata } = require("./parse-issue");

require("dotenv").config();

// Reuse existing Cosmos DB write client from historical-db
const { writeResolutionRecord } = require(path.resolve(
  __dirname,
  "../../historical-db/write-client"
));

/**
 * Handle the sentinel/wont-fix label: write ACCEPTED_RISK to Cosmos DB.
 * Critical Rule #7: This prevents future re-alerting on this CVE+file combination.
 * @param {string} issueBody - The GitHub Issue body
 * @param {string} decidedBy - GitHub username of the person who applied the label
 * @param {string} issueUrl - URL of the GitHub Issue
 * @returns {Promise<{event_id: string, record_id: string}>}
 */
async function handleWontFix(issueBody, decidedBy, issueUrl) {
  const metadata = parseIssueMetadata(issueBody);

  const record = {
    id: `accepted-risk-${metadata.event_id}`,
    cve_id: metadata.cve_id,
    affected_package: metadata.affected_package || "unknown",
    affected_version_range: metadata.current_version || "unknown",
    cve_description_embedding: [],
    fix_strategy_used: "ACCEPTED_RISK",
    patch_diff: "",
    patch_outcome: "ACCEPTED_RISK",
    failure_reason: null,
    solutions_tried: [],
    repo: metadata.repo,
    language: "unknown",
    framework: "unknown",
    resolved_at: new Date().toISOString(),
    resolved_by: decidedBy || "unknown",
    human_override: true,
    pipeline_version: "1.0.0",
  };

  const { id } = await writeResolutionRecord(record);

  return {
    event_id: metadata.event_id,
    record_id: id,
  };
}

module.exports = { handleWontFix };
