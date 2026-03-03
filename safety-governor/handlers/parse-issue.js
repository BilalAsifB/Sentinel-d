/**
 * Parse sentinel metadata from a GitHub Issue body.
 * Extracts fields from the <!-- sentinel-metadata --> HTML comment block.
 * @param {string} issueBody - The raw issue body markdown
 * @returns {object} Parsed metadata fields
 */
function parseIssueMetadata(issueBody) {
  const metadataMatch = issueBody.match(
    /<!--\s*sentinel-metadata\s*\n([\s\S]*?)-->/
  );

  if (!metadataMatch) {
    throw new Error("No sentinel-metadata block found in issue body");
  }

  const rawBlock = metadataMatch[1];
  const fields = {};

  for (const line of rawBlock.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed) continue;

    const colonIndex = trimmed.indexOf(":");
    if (colonIndex === -1) continue;

    const key = trimmed.slice(0, colonIndex).trim();
    let value = trimmed.slice(colonIndex + 1).trim();

    // Parse JSON arrays (e.g., line_range)
    if (value.startsWith("[")) {
      try {
        value = JSON.parse(value);
      } catch {
        // keep as string if parse fails
      }
    }

    fields[key] = value;
  }

  const required = ["event_id", "cve_id", "file_path", "repo"];
  for (const field of required) {
    if (!fields[field]) {
      throw new Error(`Missing required metadata field: ${field}`);
    }
  }

  return fields;
}

module.exports = { parseIssueMetadata };
