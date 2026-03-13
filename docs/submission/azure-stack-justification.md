# Azure Stack Justification

Every Azure service in Sentinel-D was chosen for a specific architectural reason.
This document maps each service to its role and explains why it was selected over
alternatives.

## Service Map

| Azure Service | Role in Sentinel-D | Why This Service |
|---------------|-------------------|------------------|
| **Azure Functions** | Webhook receiver | Consumption Plan = zero idle cost. GHAS webhooks are sporadic; pay-per-invocation is ideal. HTTP trigger with AJV schema validation rejects malformed payloads before any processing. |
| **Azure Service Bus** | Event backbone | Dead-letter queues, message lock renewal, and topic/subscription patterns. More reliable than Event Grid for guaranteed delivery. 5-minute lock duration supports long-running SRE Agent classification. |
| **Microsoft Foundry** | LLM inference | Patch generation and KQL auto-generation. Foundry provides enterprise-grade LLM access with built-in content safety, audit logging, and Azure AD integration — no API key management. |
| **Azure Cosmos DB** | Historical Database | Serverless tier for zero minimum cost. Partition key `/cve_id` gives O(1) exact lookups. Document model stores variable-length `solutions_tried` arrays and embedding vectors natively. |
| **Azure Container Apps** | Sandbox validation | Ephemeral, per-validation containers. Dynamic naming prevents cross-contamination. Automatic scale-to-zero between validations. No VM management overhead. |
| **Azure Application Insights** | Telemetry + classification | SRE Agent queries real application telemetry via KQL. Structured logging from all components. Latency tracking across the full pipeline. |
| **Azure Table Storage** | Audit log + deferred backlog | Append-only audit log: cheap, durable, compliance-ready. Deferred backlog: simple key-value storage for items awaiting re-evaluation. |
| **Azure Logic Apps** | Scheduled automation | 72-hour auto-escalation and daily backlog re-scan. Declarative ARM templates, no code to maintain. Timer triggers with HTTP actions for webhook callbacks. |
| **Azure OpenAI** | Embedding generation | `text-embedding-3-small` for 1536-dim vectors. Same Azure AD auth as other services. Consistent embedding space for cosine similarity in Historical DB. |

## Cost Architecture

**Target: Under $20 total for 14-day build period.**

| Service | Tier | Expected Cost |
|---------|------|---------------|
| Azure Functions | Consumption | ~$0.00 (free tier covers demo volume) |
| Service Bus | Basic | ~$0.05/day |
| Cosmos DB | Serverless | ~$0.25/1M RUs (demo volume minimal) |
| Container Apps | Consumption | ~$0.01/validation (scale-to-zero) |
| App Insights | Free tier | $0.00 (under 5GB/month) |
| Table Storage | Standard | ~$0.01/month |
| Logic Apps | Consumption | ~$0.01/execution |
| **Total** | | **< $5 estimated** |

## Security Architecture

- **DefaultAzureCredential** used for all Azure SDK calls — no API keys in code
- **KQL allowlist validator** blocks exfiltration vectors (externaldata, http_request, invoke, evaluate, plugins)
- **Webhook schema validation** rejects malformed payloads before processing
- **Audit log is append-only** — no update/delete operations permitted
- **Container Apps tear down on all paths** including error paths
- **GitHub tokens never appear in logs** — App Insights SDK strips sensitive fields
