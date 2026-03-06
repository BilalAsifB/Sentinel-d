const { Octokit } = require("@octokit/rest");

if (!process.env.JEST_WORKER_ID) {
  require("dotenv").config({ path: require("path").resolve(__dirname, "..", ".env") });
}

const SECURITY_TEAM_GITHUB_LOGIN = process.env.SECURITY_TEAM_GITHUB_LOGIN;

/**
 * Build the Historical DB context section for the issue body.
 * @param {object} historicalMatch - Historical match result
 * @returns {string} Markdown context section
 */
function buildHistoricalContext(historicalMatch) {
  if (!historicalMatch) {
    return "No historical data available.";
  }

  switch (historicalMatch.lookup_status) {
    case "EXACT_MATCH":
      return (
        `✅ This CVE was previously resolved in **${historicalMatch.matched_cve_id || "unknown"}** ` +
        `using strategy **${historicalMatch.recommended_strategy || "unknown"}**. ` +
        `Outcome: **${historicalMatch.previous_outcome || "unknown"}**.`
      );
    case "SEMANTIC_MATCH":
      return (
        `🔍 A semantically similar CVE (**${historicalMatch.matched_cve_id || "unknown"}**) was found ` +
        `with ${Math.round((historicalMatch.match_confidence || 0) * 100)}% confidence. ` +
        `Strategy used: **${historicalMatch.recommended_strategy || "unknown"}**. ` +
        `Outcome: **${historicalMatch.previous_outcome || "unknown"}**. ` +
        `Replay eligible: ${historicalMatch.replay_eligible ? "Yes" : "No"}.`
      );
    case "NO_MATCH":
    default:
      return "No previous resolution found for this CVE.";
  }
}

/**
 * Build the full issue body with embedded metadata for machine parsing.
 * @param {object} webhookPayload - Original GHAS webhook payload
 * @param {object} telemetryClassification - SRE Agent classification result
 * @param {object} historicalMatch - Historical DB lookup result
 * @returns {string} Markdown issue body
 */
function buildIssueBody(webhookPayload, telemetryClassification, historicalMatch) {
  const metadata = [
    "<!-- sentinel-metadata",
    `event_id: ${webhookPayload.event_id}`,
    `cve_id: ${webhookPayload.cve_id}`,
    `severity: ${webhookPayload.severity}`,
    `affected_package: ${webhookPayload.affected_package}`,
    `current_version: ${webhookPayload.current_version}`,
    `file_path: ${webhookPayload.file_path}`,
    `line_range: ${JSON.stringify(webhookPayload.line_range)}`,
    `repo: ${webhookPayload.repo}`,
    "-->",
  ].join("\n");

  const historicalContext = buildHistoricalContext(historicalMatch);

  return `${metadata}

## 🛡️ Sentinel-D — Dormant Vulnerability Decision Required

| Field | Value |
|-------|-------|
| **CVE ID** | \`${webhookPayload.cve_id}\` |
| **Severity** | \`${webhookPayload.severity}\` |
| **Affected Package** | \`${webhookPayload.affected_package}\` @ \`${webhookPayload.current_version}\` |
| **Fix Version Range** | \`${webhookPayload.fix_version_range}\` |
| **File** | \`${webhookPayload.file_path}\` |
| **Line Range** | \`${webhookPayload.line_range.join(" – ")}\` |
| **Repository** | \`${webhookPayload.repo}\` |
| **Production Call Count (30d)** | **${telemetryClassification.call_count_30d}** (DORMANT — no production calls detected) |

---

## 📚 Historical DB Context

${historicalContext}

---

## 🏷️ Decision — Apply ONE Label

Choose **one** of the following labels to proceed:

### \`sentinel/fix-now\`
> Triggers the full Sentinel-D agentic remediation pipeline. The system will generate a patch, validate it in a sandbox, and open a PR if the confidence score is high enough.

### \`sentinel/defer\`
> Adds this vulnerability to the 30-day deferred backlog. Sentinel-D will re-evaluate after 30 days and re-open a decision issue if the vulnerability is still present.

### \`sentinel/wont-fix\`
> Records this as an **accepted risk**. Future Sentinel-D scans will not alert on this CVE in the affected file. Requires justification — please add a comment explaining why before applying this label.

---

⚠️ **Auto-Escalation Warning:** This issue will auto-escalate in **72 hours** if no label is applied. The system will re-check production telemetry — if calls are now detected, the pipeline will be triggered automatically. Otherwise, the issue will be escalated to the security team lead.`;
}

/**
 * Create a GitHub Issue for a DORMANT vulnerability decision.
 * @param {object} telemetryClassification - SRE Agent classification (telemetry_classification.json)
 * @param {object} historicalMatch - Historical DB lookup (historical_match.json)
 * @param {object} webhookPayload - Original GHAS webhook payload (webhook_payload.json)
 * @returns {Promise<{issueNumber: number, issueUrl: string}>}
 */
async function createDecisionIssue(telemetryClassification, historicalMatch, webhookPayload) {
  const GITHUB_TOKEN = process.env.GITHUB_TOKEN;
  const GITHUB_OWNER = process.env.GITHUB_OWNER || process.env.GITHUB_REPO_OWNER;
  const GITHUB_REPO = process.env.GITHUB_REPO || process.env.GITHUB_REPO_NAME;

  if (!GITHUB_TOKEN) {
    throw new Error("GITHUB_TOKEN environment variable is required");
  }
  if (!GITHUB_OWNER || !GITHUB_REPO) {
    throw new Error("GITHUB_OWNER and GITHUB_REPO environment variables are required");
  }

  const octokit = new Octokit({ auth: GITHUB_TOKEN });

  const title = `[SENTINEL-DORMANT] ${webhookPayload.cve_id} — ${webhookPayload.affected_package}`;
  const body = buildIssueBody(webhookPayload, telemetryClassification, historicalMatch);

  const issueParams = {
    owner: GITHUB_OWNER,
    repo: GITHUB_REPO,
    title,
    body,
    labels: ["sentinel/dormant"],
  };

  if (SECURITY_TEAM_GITHUB_LOGIN) {
    issueParams.assignees = [SECURITY_TEAM_GITHUB_LOGIN];
  }

  const { data: issue } = await octokit.rest.issues.create(issueParams);

  return {
    issueNumber: issue.number,
    issueUrl: issue.html_url,
  };
}

module.exports = { createDecisionIssue, buildIssueBody, buildHistoricalContext };
