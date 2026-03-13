# Microsoft Foundry Integration

## How Foundry Is Used

Sentinel-D uses Microsoft Foundry as its primary LLM inference engine for two
distinct tasks:

### 1. Patch Generation

The Patch Generator sends a structured 4-section prompt to Foundry:

| Section | Content |
|---------|---------|
| **Section 1: Context** | CVE details, affected package, severity, CVSS score |
| **Section 2: Intelligence** | NLP Pipeline output — NER entities, classifier strategy, Stack Overflow solutions |
| **Section 3: Repository** | Target repo language, framework, file structure, existing tests |
| **Section 4: Constraints** | Hard requirements: `solutions_to_avoid` from Historical DB, `CANNOT_PATCH` conditions (auth/crypto touches), test requirements |

The response is parsed into a structured patch object containing:
- `patch_diff` — the actual code change
- `reasoning_chain` — LLM's step-by-step reasoning (included in PR body)
- `fix_strategy` — which strategy the LLM chose
- `touches_auth_crypto` — boolean for Safety Governor override

### 2. KQL Generation

The SRE Agent uses Foundry to generate KQL queries for Application Insights:

- Input: CVE description, affected package, typical code patterns
- Output: KQL query targeting `traces`, `requests`, `exceptions`, `dependencies`
- **Security**: Every generated KQL query passes through an allowlist validator
  before execution — blocked keywords include `externaldata`, `http_request`,
  `invoke`, `evaluate`, and `plugins`

### RAG Replay: When Foundry Is NOT Called

When the Historical Database finds an exact CVE match (same CVE ID, same
language), the RAG Replay path reuses the cached patch without calling Foundry:

```
Historical DB: EXACT_MATCH for CVE-2021-44228
  → Language check: Java ✓
  → git apply --check: clean ✓
  → Skip Foundry entirely
  → Source: RAG_REPLAY (visible in PR body)
  → Time: ~90 seconds (vs ~5 minutes with Foundry)
```

This is verified in App Insights logs — zero Foundry API calls for RAG replays.

## Why Foundry Over Alternatives

| Criterion | Foundry | Direct API (Anthropic/OpenAI) |
|-----------|---------|-------------------------------|
| Azure AD auth | ✅ DefaultAzureCredential | ❌ API key management |
| Content safety | ✅ Built-in filters | ❌ Must implement separately |
| Audit logging | ✅ Azure Monitor integration | ❌ Custom implementation |
| Enterprise compliance | ✅ SOC 2, HIPAA, FedRAMP | ⚠️ Varies by provider |
| Cost tracking | ✅ Azure Cost Management | ❌ Separate billing |
| Network security | ✅ VNet integration | ❌ Public internet |

## Configuration

```
FOUNDRY_ENDPOINT=https://<resource>.services.ai.azure.com/api/inference
FOUNDRY_MODEL=claude-opus-4-6
```

Both values are sourced from environment variables — never hardcoded.
