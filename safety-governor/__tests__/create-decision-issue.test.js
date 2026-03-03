const { buildIssueBody, buildHistoricalContext } = require("../create-decision-issue");

// Sample test data matching the frozen schemas
const sampleWebhookPayload = {
  event_id: "550e8400-e29b-41d4-a716-446655440000",
  cve_id: "CVE-2024-1234",
  severity: "HIGH",
  affected_package: "org.apache.commons:commons-text",
  current_version: "1.9",
  fix_version_range: ">=1.10.0",
  file_path: "src/main/java/com/example/TextUtils.java",
  line_range: [42, 58],
  repo: "example-org/example-app",
  timestamp: "2024-01-15T10:30:00Z",
};

const sampleTelemetry = {
  event_id: "550e8400-e29b-41d4-a716-446655440000",
  status: "DORMANT",
  call_count_30d: 0,
  last_called: null,
  blast_radius: "LOW",
  kql_query_used: "requests | where name contains 'commons-text'",
  confidence: 0.95,
};

describe("buildHistoricalContext", () => {
  test("returns EXACT_MATCH message with CVE, strategy, and outcome", () => {
    const match = {
      lookup_status: "EXACT_MATCH",
      matched_cve_id: "CVE-2024-1234",
      recommended_strategy: "VERSION_PIN",
      previous_outcome: "SUCCESS",
    };
    const result = buildHistoricalContext(match);
    expect(result).toContain("✅");
    expect(result).toContain("CVE-2024-1234");
    expect(result).toContain("VERSION_PIN");
    expect(result).toContain("SUCCESS");
  });

  test("returns SEMANTIC_MATCH message with confidence", () => {
    const match = {
      lookup_status: "SEMANTIC_MATCH",
      matched_cve_id: "CVE-2023-9999",
      match_confidence: 0.87,
      recommended_strategy: "API_MIGRATION",
      previous_outcome: "SUCCESS",
      replay_eligible: true,
    };
    const result = buildHistoricalContext(match);
    expect(result).toContain("🔍");
    expect(result).toContain("87%");
    expect(result).toContain("Replay eligible: Yes");
  });

  test("returns NO_MATCH message", () => {
    const match = { lookup_status: "NO_MATCH", match_confidence: 0 };
    const result = buildHistoricalContext(match);
    expect(result).toContain("No previous resolution found");
  });

  test("handles null historicalMatch", () => {
    const result = buildHistoricalContext(null);
    expect(result).toContain("No historical data available");
  });
});

describe("buildIssueBody", () => {
  const noMatch = {
    event_id: "550e8400-e29b-41d4-a716-446655440000",
    lookup_status: "NO_MATCH",
    match_confidence: 0,
    replay_eligible: false,
  };

  test("includes sentinel-metadata block with all required fields", () => {
    const body = buildIssueBody(sampleWebhookPayload, sampleTelemetry, noMatch);
    expect(body).toContain("<!-- sentinel-metadata");
    expect(body).toContain("event_id: 550e8400-e29b-41d4-a716-446655440000");
    expect(body).toContain("cve_id: CVE-2024-1234");
    expect(body).toContain("severity: HIGH");
    expect(body).toContain("affected_package: org.apache.commons:commons-text");
    expect(body).toContain("file_path: src/main/java/com/example/TextUtils.java");
    expect(body).toContain("repo: example-org/example-app");
    expect(body).toContain("-->");
  });

  test("includes CVE details table", () => {
    const body = buildIssueBody(sampleWebhookPayload, sampleTelemetry, noMatch);
    expect(body).toContain("| **CVE ID** | `CVE-2024-1234` |");
    expect(body).toContain("| **Severity** | `HIGH` |");
    expect(body).toContain("commons-text");
    expect(body).toContain("1.9");
  });

  test("includes all three label options", () => {
    const body = buildIssueBody(sampleWebhookPayload, sampleTelemetry, noMatch);
    expect(body).toContain("`sentinel/fix-now`");
    expect(body).toContain("`sentinel/defer`");
    expect(body).toContain("`sentinel/wont-fix`");
  });

  test("includes auto-escalation warning", () => {
    const body = buildIssueBody(sampleWebhookPayload, sampleTelemetry, noMatch);
    expect(body).toContain("72 hours");
    expect(body).toContain("auto-escalat");
  });

  test("includes production call count from telemetry", () => {
    const body = buildIssueBody(sampleWebhookPayload, sampleTelemetry, noMatch);
    expect(body).toContain("**0**");
    expect(body).toContain("DORMANT");
  });

  test("renders EXACT_MATCH historical context correctly", () => {
    const exactMatch = {
      event_id: "550e8400-e29b-41d4-a716-446655440000",
      lookup_status: "EXACT_MATCH",
      match_confidence: 1.0,
      matched_cve_id: "CVE-2024-1234",
      recommended_strategy: "VERSION_PIN",
      previous_outcome: "SUCCESS",
      replay_eligible: true,
    };
    const body = buildIssueBody(sampleWebhookPayload, sampleTelemetry, exactMatch);
    expect(body).toContain("✅");
    expect(body).toContain("VERSION_PIN");
  });
});

describe("createDecisionIssue", () => {
  const originalEnv = process.env;

  beforeEach(() => {
    jest.resetModules();
    process.env = { ...originalEnv };
  });

  afterAll(() => {
    process.env = originalEnv;
  });

  test("throws if GITHUB_TOKEN is missing", async () => {
    delete process.env.GITHUB_TOKEN;
    delete process.env.GITHUB_OWNER;
    delete process.env.GITHUB_REPO;
    const { createDecisionIssue } = require("../create-decision-issue");
    await expect(
      createDecisionIssue(sampleTelemetry, { lookup_status: "NO_MATCH" }, sampleWebhookPayload)
    ).rejects.toThrow("GITHUB_TOKEN");
  });

  test("throws if GITHUB_OWNER or GITHUB_REPO is missing", async () => {
    process.env.GITHUB_TOKEN = "test-token";
    delete process.env.GITHUB_OWNER;
    delete process.env.GITHUB_REPO;
    const { createDecisionIssue } = require("../create-decision-issue");
    await expect(
      createDecisionIssue(sampleTelemetry, { lookup_status: "NO_MATCH" }, sampleWebhookPayload)
    ).rejects.toThrow("GITHUB_OWNER");
  });
});
