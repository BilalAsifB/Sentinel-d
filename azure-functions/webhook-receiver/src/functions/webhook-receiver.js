const { app } = require("@azure/functions");
const { ServiceBusClient } = require("@azure/service-bus");
const { DefaultAzureCredential } = require("@azure/identity");
const Ajv = require("ajv");
const addFormats = require("ajv-formats");
const path = require("path");
const fs = require("fs");

// Load webhook payload schema
// When deployed, __dirname is the functions directory; resolve relative to repo root
const schemaPath = path.resolve(
  __dirname,
  "../../../../shared/schemas/webhook_payload.json"
);
const webhookSchema = JSON.parse(fs.readFileSync(schemaPath, "utf-8"));

// Set up AJV validator
const ajv = new Ajv({ allErrors: true });
addFormats(ajv);
const validate = ajv.compile(webhookSchema);

// Service Bus config from environment
const SB_NAMESPACE = process.env.SERVICE_BUS_NAMESPACE;
const SB_QUEUE = process.env.SERVICE_BUS_QUEUE_NAME || "vulnerability-events";

/**
 * Send validated payload to Azure Service Bus queue.
 * Uses DefaultAzureCredential — no connection strings.
 */
async function sendToServiceBus(payload) {
  const credential = new DefaultAzureCredential();
  const client = new ServiceBusClient(
    `${SB_NAMESPACE}.servicebus.windows.net`,
    credential
  );
  const sender = client.createSender(SB_QUEUE);

  try {
    await sender.sendMessages({ body: payload });
  } finally {
    await sender.close();
    await client.close();
  }
}

async function handler(request, context) {
  // Validate Content-Type
  const contentType = request.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) {
    return {
      status: 400,
      jsonBody: {
        error: "Invalid Content-Type",
        detail: "Content-Type must be application/json",
      },
    };
  }

  // Parse body
  let payload;
  try {
    payload = await request.json();
  } catch {
    return {
      status: 400,
      jsonBody: {
        error: "Invalid JSON",
        detail: "Request body is not valid JSON",
      },
    };
  }

  // Validate against schema
  const valid = validate(payload);
  if (!valid) {
    context.log("Schema validation failed:", validate.errors);
    return {
      status: 400,
      jsonBody: {
        error: "Schema validation failed",
        detail: validate.errors.map((e) => ({
          path: e.instancePath || "/",
          message: e.message,
          params: e.params,
        })),
      },
    };
  }

  // Send to Service Bus
  try {
    await sendToServiceBus(payload);
    context.log(`Message sent to Service Bus: event_id=${payload.event_id}`);
    return {
      status: 202,
      jsonBody: {
        status: "accepted",
        event_id: payload.event_id,
      },
    };
  } catch (err) {
    context.error("Service Bus send failed:", err.message);
    return {
      status: 400,
      jsonBody: {
        error: "Message delivery failed",
        detail: err.message,
      },
    };
  }
}

app.http("webhook-receiver", {
  methods: ["POST"],
  authLevel: "function",
  handler,
});

// Export for testing
module.exports = { validate, sendToServiceBus, handler };
