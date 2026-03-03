const { parseIssueMetadata } = require("../handlers/parse-issue");

// Sample issue body matching the format produced by create-decision-issue.js
const sampleIssueBody = `<!-- sentinel-metadata
event_id: 550e8400-e29b-41d4-a716-446655440000
cve_id: CVE-2024-1234
severity: HIGH
affected_package: org.apache.commons:commons-text
current_version: 1.9
file_path: src/main/java/com/example/TextUtils.java
line_range: [42, 58]
repo: example-org/example-app
-->

## 🛡️ Sentinel-D — Dormant Vulnerability Decision Required

| Field | Value |
|-------|-------|
| **CVE ID** | \`CVE-2024-1234\` |`;

describe("parseIssueMetadata", () => {
  test("extracts all metadata fields", () => {
    const metadata = parseIssueMetadata(sampleIssueBody);
    expect(metadata.event_id).toBe("550e8400-e29b-41d4-a716-446655440000");
    expect(metadata.cve_id).toBe("CVE-2024-1234");
    expect(metadata.severity).toBe("HIGH");
    expect(metadata.affected_package).toBe("org.apache.commons:commons-text");
    expect(metadata.current_version).toBe("1.9");
    expect(metadata.file_path).toBe("src/main/java/com/example/TextUtils.java");
    expect(metadata.repo).toBe("example-org/example-app");
  });

  test("parses line_range as JSON array", () => {
    const metadata = parseIssueMetadata(sampleIssueBody);
    expect(metadata.line_range).toEqual([42, 58]);
  });

  test("throws on missing sentinel-metadata block", () => {
    expect(() => parseIssueMetadata("No metadata here")).toThrow(
      "No sentinel-metadata block found"
    );
  });

  test("throws on missing required fields", () => {
    const incomplete = `<!-- sentinel-metadata
cve_id: CVE-2024-1234
-->`;
    expect(() => parseIssueMetadata(incomplete)).toThrow(
      "Missing required metadata field: event_id"
    );
  });
});

// Mock the Azure SDK clients for handler tests
const mockSendMessages = jest.fn().mockResolvedValue(undefined);
const mockSenderClose = jest.fn().mockResolvedValue(undefined);
const mockClientClose = jest.fn().mockResolvedValue(undefined);

jest.mock("@azure/service-bus", () => ({
  ServiceBusClient: jest.fn().mockImplementation(() => ({
    createSender: jest.fn().mockReturnValue({
      sendMessages: mockSendMessages,
      close: mockSenderClose,
    }),
    close: mockClientClose,
  })),
}));

jest.mock("@azure/identity", () => ({
  DefaultAzureCredential: jest.fn(),
}));

// Mock the historical-db modules directly by relative path
const mockWriteDeferred = jest.fn().mockResolvedValue(undefined);
const mockWriteResolutionRecord = jest.fn().mockResolvedValue({
  id: "accepted-risk-550e8400",
});

jest.mock("../../historical-db/backlog-writer", () => ({
  writeDeferred: mockWriteDeferred,
}));
jest.mock("../../historical-db/write-client", () => ({
  writeResolutionRecord: mockWriteResolutionRecord,
}));

describe("handleFixNow", () => {
  beforeEach(() => {
    process.env.SERVICE_BUS_NAMESPACE = "test-sb-namespace";
    process.env.SERVICE_BUS_QUEUE_NAME = "test-queue";
    mockSendMessages.mockClear();
  });

  test("sends Service Bus message with ACTIVE override", async () => {
    const { handleFixNow } = require("../handlers/fix-now");
    const result = await handleFixNow(sampleIssueBody);
    expect(result.event_id).toBe("550e8400-e29b-41d4-a716-446655440000");
    expect(mockSendMessages).toHaveBeenCalledWith(
      expect.objectContaining({
        body: expect.objectContaining({
          event_id: "550e8400-e29b-41d4-a716-446655440000",
          status_override: "ACTIVE",
          decision: "FIX_NOW",
        }),
      })
    );
  });

  test("throws if SERVICE_BUS_NAMESPACE is missing", async () => {
    delete process.env.SERVICE_BUS_NAMESPACE;
    jest.resetModules();
    jest.mock("@azure/service-bus", () => ({
      ServiceBusClient: jest.fn(),
    }));
    jest.mock("@azure/identity", () => ({
      DefaultAzureCredential: jest.fn(),
    }));
    const { handleFixNow } = require("../handlers/fix-now");
    await expect(handleFixNow(sampleIssueBody)).rejects.toThrow(
      "SERVICE_BUS_NAMESPACE"
    );
  });
});

describe("handleDefer", () => {
  beforeEach(() => {
    mockWriteDeferred.mockClear();
  });

  test("writes deferred record and returns defer_until date", async () => {
    const { handleDefer } = require("../handlers/defer");
    const result = await handleDefer(sampleIssueBody);
    expect(result.event_id).toBe("550e8400-e29b-41d4-a716-446655440000");
    expect(result.defer_until).toBeDefined();

    // defer_until should be ~30 days from now
    const deferDate = new Date(result.defer_until);
    const now = new Date();
    const daysDiff = (deferDate - now) / (1000 * 60 * 60 * 24);
    expect(daysDiff).toBeGreaterThan(29);
    expect(daysDiff).toBeLessThan(31);

    expect(mockWriteDeferred).toHaveBeenCalledWith(
      "550e8400-e29b-41d4-a716-446655440000",
      "CVE-2024-1234",
      expect.any(String),
      "Deferred via sentinel/defer label"
    );
  });
});

describe("handleWontFix", () => {
  beforeEach(() => {
    mockWriteResolutionRecord.mockClear();
  });

  test("writes ACCEPTED_RISK record to Cosmos DB", async () => {
    const { handleWontFix } = require("../handlers/wont-fix");
    const result = await handleWontFix(
      sampleIssueBody,
      "security-reviewer",
      "https://github.com/example-org/example-app/issues/42"
    );
    expect(result.event_id).toBe("550e8400-e29b-41d4-a716-446655440000");
    expect(result.record_id).toBe("accepted-risk-550e8400");

    expect(mockWriteResolutionRecord).toHaveBeenCalledWith(
      expect.objectContaining({
        cve_id: "CVE-2024-1234",
        patch_outcome: "ACCEPTED_RISK",
        fix_strategy_used: "ACCEPTED_RISK",
        human_override: true,
        resolved_by: "security-reviewer",
        repo: "example-org/example-app",
      })
    );
  });
});
