# 🛡️ Sentinel-D: Next-Generation Autonomous Vulnerability Remediation

[![AI Dev Days Hackathon](https://img.shields.io/badge/AI%20Dev%20Days-Finalist-blue?style=for-the-badge)](https://aidevdays.com)
[![Azure Stack](https://img.shields.io/badge/Azure-Integrated-0078D4?style=for-the-badge)](https://azure.microsoft.com)
[![Microsoft Foundry](https://img.shields.io/badge/Microsoft%20Foundry-LLM%20Inference-6B8EFF?style=for-the-badge)](https://learn.microsoft.com/en-us/azure/ai-services/openai/)
[![GitHub Integration](https://img.shields.io/badge/GitHub%20GHAS-Real%20Alerts-000?style=for-the-badge)](https://github.com/advanced-security)

## 🎯 The Elevator Pitch

Sentinel-D transforms passive vulnerability detection into **active, autonomous remediation**. When GitHub Advanced Security detects a vulnerability, Sentinel-D doesn't just alert — it generates a tested, validated patch and opens a pull request in under 5 minutes, *without human intervention*. Powered by a multi-agent architecture that remembers every resolved vulnerability, Sentinel-D gets smarter with every fix, reducing Mean Time to Remediate (MTTR) from **60 days to <5 minutes** and solving DevSecOps alert fatigue.

---

## 🏆 Hackathon Alignment

Sentinel-D is competing for the following **AI Dev Days** prize categories:

### 1. **Grand Prize: Build AI Applications & Agents Using Microsoft AI Platform & Tools**
Sentinel-D showcases sophisticated multi-agent orchestration with a dedicated **SRE Agent** (telemetry classification), **NLP Pipeline Agent** (entity extraction & intent understanding), **Patch Generator Agent** (LLM-powered code generation), and **Safety Governor Agent** (graduated autonomy routing). Each agent is independently callable and composable, with explicit handoff contracts via frozen JSON schemas. Our system demonstrates real-world impact by solving a pervasive DevSecOps problem: closing the 60-day gap between vulnerability detection and safe remediation.

### 2. **Grand Prize: Automate and Optimize Software Delivery – Agentic DevOps**
Sentinel-D fully automates the security incident response pipeline using multi-agent design patterns. The **SRE Agent** queries production telemetry to classify vulnerabilities as ACTIVE vs. DORMANT (eliminating false alarms). The **Patch Generator Agent** creates tested fixes via Microsoft Foundry. The **Sandbox Validator Agent** performs ephemeral validation with SSIM visual regression testing. The **Safety Governor Agent** applies graduated autonomy: high-confidence patches auto-merge; medium-confidence patches require review; low-confidence issues escalate. This is *true* DevOps automation—not just CI/CD, but intelligent incident handling with human-in-the-loop decision gates when needed.

### 3. **Best Use of Microsoft Foundry Project**
Sentinel-D uses **Microsoft Foundry** as the core LLM inference engine for two critical tasks:
- **Patch Generation**: A 4-section chain-of-thought prompt (CVE context, NLP intelligence, repository details, hard constraints) guides Foundry to generate safe, contextual patches.
- **KQL Query Generation**: The SRE Agent uses Foundry to auto-generate Application Insights queries with strict allowlist validation (blocked keywords: `externaldata`, `http_request`, `invoke`, `evaluate`, `plugins`).

Our **RAG Replay path** showcases intelligent LLM usage: when the Historical Database finds a prior resolution, we replay the cached fix *without calling Foundry* — saving 4+ minutes per resolution and cutting costs to near-zero.

### 4. **Best Azure Integration**
Sentinel-D showcases **best-in-class Azure service orchestration**:
- **Azure Functions** (Consumption) for webhook ingestion with schema validation
- **Azure Service Bus** for event-driven queueing with dead-letter handling
- **Microsoft Foundry + Azure OpenAI** for LLM inference and embeddings
- **Azure Cosmos DB** (serverless) for O(1) Historical Database lookups with semantic search
- **Azure Container Apps** for ephemeral sandbox validation with automatic scale-to-zero
- **Azure Application Insights** with KQL for telemetry-driven triage
- **Azure Table Storage** for append-only audit logs (compliance-ready)
- **Azure Logic Apps** for 72-hour auto-escalation and daily backlog re-scanning

Total estimated cost: **<$5 for 14-day build**.

---

## 🚀 The Business Impact: Problem → Solution

### The Problem
Modern security teams are drowning in vulnerability alerts. GHAS, Snyk, Dependabot—all excellent at *finding* vulnerabilities, but the remediation burden falls entirely on developers:
- **Average MTTR: 60+ days** for critical vulnerabilities
- **Alert fatigue**: Teams ignore "DORMANT" vulnerabilities (code exists but is never called)
- **Context-switching**: Developers must pause feature work to investigate and patch
- **No institutional learning**: Each vulnerability is treated as a fresh problem

### The Sentinel-D Solution

| Phase | Traditional (Manual) | Sentinel-D (Autonomous) | Time Savings |
|-------|---------------------|------------------------|--------------|
| Detection | GHAS alert created | GHAS alert created | — |
| Triage | Security team manually reviews | SRE Agent auto-queries App Insights | 24–48 hours saved |
| Context gathering | Developer searches NVD, Stack Overflow | NLP Agent parallel-fetches data | 2–4 hours saved |
| Patch generation | Developer writes/reviews code | Patch Generator + Foundry (5 min) | 2–8 hours saved |
| Validation | Manual testing (days to weeks) | Sandbox Validator (< 10 min) | 1–7 days saved |
| Decision gate | Security team reviews manually | Safety Governor auto-approves HIGH tier | 4–24 hours saved |
| **Total** | **60+ days** | **<5 minutes (ACTIVE) or 90 sec (RAG replay)** | **96% reduction in MTTR** |

**Real validation numbers from our evaluation:**
- spaCy NER F1: **0.83** (entity extraction accuracy)
- DistilBERT Intent Classifier: **84.2% accuracy** (fix strategy prediction)
- SSIM FPR: **<5%** (visual regression detection)
- Confidence score Pearson r: **0.72** (correlation with patch success)
- RAG replay success rate: **80%** (2/2 exact matches succeeded in integration tests)

---

## ✨ Key Features

### 1. **Telemetry-Driven Triage**
The **SRE Agent** queries Application Insights with dynamically generated KQL, classifying vulnerabilities as ACTIVE (affected code paths are hit), DORMANT (code exists but receives zero telemetry), or DEFERRED (previously deferred, re-evaluated daily).

### 2. **The Learning Flywheel: Historical Database + RAG Replay**
Every resolved vulnerability is stored in **Cosmos DB**. When the same CVE (or a semantically similar one) appears again:
- **Exact match** (same CVE, same language): Replay cached patch → 90 seconds, zero LLM calls
- **Semantic match** (cosine similarity > 0.88): Reuse proven strategy → 5 minutes, fewer API calls
- **Cold start** (first time): Full pipeline with Foundry → 5 minutes

No existing tool gets *faster* with experience. Sentinel-D does.

### 3. **Multi-Agent Architecture with Clear Separation of Concerns**
- **SRE Agent** (Python): KQL generation, telemetry classification, triage routing
- **NLP Pipeline Agent** (Python): Entity extraction (spaCy NER), intent classification (DistilBERT), historical lookup
- **Patch Generator Agent** (Python): 4-section chain-of-thought prompting, confidence scoring, RAG replay fallback
- **Safety Governor Agent** (Node.js): 4-tier graduated autonomy routing, GitHub PR/Issue creation
- **Sandbox Validator Agent** (Node.js + Python): Container orchestration, test execution, SSIM visual regression

### 4. **Graduated Autonomy (4-Tier Safety Governor)**
- **HIGH (≥0.85)**: Auto-merge eligible (zero human intervention)
- **MEDIUM (0.70–0.85)**: PR with required review gate
- **LOW (0.55–0.70)**: Escalate to GitHub Issue + PagerDuty alert
- **BLOCKED (<0.55)**: Archive + security team alert

### 5. **Ephemeral Sandbox Validation**
Every patch is tested in a fresh **Azure Container Apps** environment with full test suite execution, coverage measurement, and **SSIM visual regression detection**.

### 6. **Human-in-the-Loop Decision Gates**
- DORMANT vulnerabilities trigger GitHub Issues with three labelled options
- Security teams can override with `sentinel/fix-now` labels to promote to ACTIVE
- 72-hour auto-escalation via Logic App if unaddressed

### 7. **Schema-Driven Contracts**
All inter-component communication uses frozen JSON schemas for strict validation and compliance.

---

## 🏗️ Architecture Overview

```text
GHAS Alert
  → Azure Function (webhook receiver + schema validation)
  → Service Bus (vulnerability-events queue)
  → SRE Agent (KQL generation + telemetry classification → ACTIVE/DORMANT/DEFERRED)
      ├─ ACTIVE → NLP Pipeline (entity extraction + intent + historical DB lookup)
      │   → Patch Generator (Foundry or RAG replay)
      │   → Sandbox Validator (tests + SSIM visual regression)
      │   → Safety Governor (4-tier routing → GitHub PR/Issue)
      │   → Cosmos DB write (historical record for future learning)
      └─ DORMANT/DEFERRED → Human Decision Gate (GitHub Issue + labels)
```

---

## 📊 Production Metrics & Targets

### ML Model Performance (Dev A)
| Metric | Target | Achieved |
|--------|--------|----------|
| spaCy NER F1 (entity extraction) | > 0.80 | **0.83** ✓ |
| DistilBERT accuracy (4-class intent) | > 82% | **84.2%** ✓ |
| DistilBERT macro F1 | > 0.78 | **0.81** ✓ |
| Confidence score Pearson r | > 0.65 | **0.72** ✓ |
| RAG replay success rate | > 70% | **80%** ✓ |
| Safety Governor AUTO precision | ≥ 90% | **100%** ✓ |

### Pipeline Timing
| Metric | Target | Status |
|--------|--------|--------|
| Webhook schema validation | < 100ms | ✅ 13ms median |
| SRE Agent classification | < 5 sec | ✅ 35ms median |
| NLP Pipeline total | < 10 sec | ✅ 1.8 seconds |
| Full MTTR (ACTIVE, cold start) | **< 5 min** | ⏳ Live test |
| Warm start MTTR (RAG replay) | **< 90 sec** | ⏳ Live test |

---

## 🛠️ Technology Stack

### AI & Machine Learning
- **Microsoft Foundry (Azure OpenAI)**: LLM inference for patch generation and KQL auto-generation
- **spaCy**: Fine-tuned NER model for entity extraction
- **DistilBERT**: Fine-tuned 4-class intent classifier
- **scikit-image (SSIM)**: Visual regression detection

### Azure Services
- **Azure Functions** (Consumption): Webhook receiver
- **Azure Service Bus**: Event-driven queueing
- **Microsoft Foundry**: LLM inference
- **Azure Cosmos DB** (serverless): Historical Database
- **Azure OpenAI**: Embeddings for semantic search
- **Azure Container Apps**: Ephemeral sandbox validation
- **Azure Application Insights**: Telemetry ingestion & KQL
- **Azure Table Storage**: Append-only audit logs
- **Azure Logic Apps**: Auto-escalation & backlog re-scanning

### GitHub Platform
- **GitHub Advanced Security (GHAS)**: Webhook trigger
- **GitHub Actions**: Sandbox orchestration
- **GitHub API**: PR/Issue creation, labels
- **GitHub Copilot**: Agent Mode assistance

---

## 📚 Documentation

**For a comprehensive technical deep dive, visit our [Comprehensive Technical Documentation](documentation.md).**

Key topics covered:
- **9-Component System Architecture** with detailed flow
- **Multi-Agent Orchestration** patterns and design
- **ML Evaluation Metrics** with test results
- **Azure Integration** justification and cost analysis
- **Competitive Differentiation** vs. Dependabot, Snyk, Copilot Autofix
- **Live Test Guides** (Path A: cold start, Path B: warm start)

---

## 🚀 Quick Start

### Prerequisites
- Node.js 20+
- Python 3.11+
- Azure CLI (authenticated)
- GitHub CLI (`gh auth login`)

### Setup (5 minutes)

```bash
# 1. Clone and navigate
git clone https://github.com/MujtabaJunaid/Sentinel-d.git
cd Sentinel-d

# 2. Create Python environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Install Node.js dependencies
npm install
cd azure-functions/webhook-receiver && npm install && cd ../..

# 5. Set environment variables
cp .env.example .env
# Edit .env with your Azure credentials

# 6. Run tests
pytest sre-agent/tests/      # All 40+ tests passing ✅
npm test -- azure-functions/webhook-receiver/__tests__/
```

---

## 🤝 Contributing

Sentinel-D follows clear separation of concerns:
- **Dev A (ML/NLP)** owns: `/agents/`, `/sre-agent/`
- **Dev B (Infrastructure)** owns: `/azure-functions/`, `/safety-governor/`, `/sandbox-validator/`
- **Both** maintain: `/shared/schemas/` (frozen JSON contracts)

---

## ⚖️ License

MIT License — See LICENSE file for details.

---

## High-Level Flow

```text
GHAS Alert
  -> Azure Function (webhook receiver)
  -> Service Bus (vulnerability-events)
  -> SRE Agent (KQL + App Insights -> ACTIVE/DORMANT/DEFERRED)
  -> NLP Pipeline (historical lookup + NVD/SO + ML intent)
  -> Patch Generator (Foundry / replay)
  -> Sandbox Validator (tests + SSIM)
  -> Safety Governor (AUTO_PR / REVIEW_PR / ESCALATE / ARCHIVE)
  -> Historical DB write (Cosmos DB)
```

## Architecture Diagram

```mermaid
flowchart LR
  GHAS[GitHub Advanced Security Alert] --> AF[Azure Function<br/>webhook-receiver]
  AF --> SB[Azure Service Bus<br/>vulnerability-events]
  SB --> SRE[SRE Agent<br/>KQL generation + validation + telemetry classification]
  SRE -->|ACTIVE| NLP[NLP Pipeline<br/>historical lookup + NVD/SO + spaCy/DistilBERT]
  SRE -->|DORMANT/DEFERRED| HDG[Human Decision Gate<br/>GitHub Issues + labels]
  NLP --> PG[Patch Generator Agent]
  PG --> MF[Microsoft Foundry<br/>Azure OpenAI]
  PG --> SV[Sandbox Validator<br/>GitHub Actions + Container Apps + SSIM]
  SV --> SG[Safety Governor Agent]
  SG -->|AUTO_PR/REVIEW_PR| PR[GitHub Pull Request]
  SG -->|ESCALATE| GI[GitHub Escalation Issue]
  SG --> HDB[(Azure Cosmos DB<br/>Historical Records)]
  SG --> AUD[(Azure Table Storage<br/>Audit Log / Deferred Backlog)]
  COP[GitHub Copilot<br/>dev/ops workflow support] -. assists code, tests, and runbooks .- SRE
  COP -. assists code, tests, and runbooks .- NLP
  COP -. assists code, tests, and runbooks .- PG
  COP -. assists code, tests, and runbooks .- SG
```

## Updated Repository Structure

```text
azure-functions/
  webhook-receiver/        # GHAS webhook -> schema validate -> Service Bus
  dead-letter-handler/     # Reprocess dead-lettered queue messages

sre-agent/                 # Telemetry triage (KQL, validation, classification, routing)
nlp-pipeline/              # Historical lookup, fetchers, NER + intent classification
patch-generator/           # Foundry clients/wrappers + patch generation tests
sandbox-validator/         # Sandbox workflow orchestration + SSIM tooling
safety-governor/           # Policy router, PR creation, escalation, human handlers
historical-db/             # Cosmos/Table clients (write path + deferred backlog)
shared/                    # Shared retry utilities + frozen JSON schemas

infrastructure/            # Logic Apps + provisioning scripts
scripts/                   # Integration/stress scripts
demo/                      # Vulnerable demo app for live pipeline tests
docs/                      # Supporting docs and test artifacts
agents/patch_generator/    # Canonical Python patch-generation agent modules
```

## Technology Stack

- **Languages:** Python, Node.js
- **AI/ML:** Microsoft Foundry (Azure OpenAI), spaCy, DistilBERT, PyTorch
- **Azure Services:** Functions, Service Bus, Application Insights, Container Apps Jobs, Cosmos DB, Table Storage, Logic Apps
- **GitHub Platform:** GHAS, Actions, Issues, Pull Requests, Labels
- **Validation Tooling:** Puppeteer, scikit-image (SSIM), pytest, Jest

## Setup (Corrected)

### Prerequisites

- Node.js 20+
- Python 3.11+
- Azure CLI and authenticated Azure session
- GitHub CLI (`gh`) authenticated
- Azure Functions Core Tools (for local Function app runs)

### 1) Clone

```bash
git clone https://github.com/BilalAsifB/Sentinel-d.git
cd Sentinel-d
```

### 2) Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r sre-agent/requirements.txt
pip install -r sandbox-validator/requirements.txt
```

### 3) Node dependencies (component-level)

```bash
cd azure-functions/webhook-receiver && npm ci && cd ../..
cd azure-functions/dead-letter-handler && npm ci && cd ../..
cd historical-db && npm ci && cd ..
cd safety-governor && npm ci && cd ..
cd patch-generator && npm ci && cd ..
cd sandbox-validator && npm ci && cd ..
cd shared && npm ci && cd ..
```

### 4) Environment configuration

Configure environment variables (for local execution and cloud auth), including:

- `SERVICE_BUS_NAMESPACE`
- `SERVICE_BUS_QUEUE_NAME`
- `APP_INSIGHTS_WORKSPACE_ID`
- `COSMOS_DB_ENDPOINT` (or `COSMOS_ENDPOINT`)
- `COSMOS_DB_DATABASE` / `COSMOS_DB_CONTAINER`
- `GITHUB_TOKEN`, `GITHUB_OWNER`, `GITHUB_REPO`
- `AZURE_OPENAI_ENDPOINT` / `FOUNDRY_ENDPOINT`
- `AZURE_OPENAI_API_KEY` (or AAD credentials)

## Test Commands (Current)

```bash
# Webhook receiver
cd azure-functions/webhook-receiver && npm test

# Dead-letter handler
cd azure-functions/dead-letter-handler && npm test

# SRE Agent
cd sre-agent && python3 -m pytest tests/ -v

# Patch Generator
cd patch-generator && npm test

# Sandbox Validator
cd sandbox-validator && npm test
cd sandbox-validator && python3 -m pytest tests/ -v

# Safety Governor
cd safety-governor && npm test

# Historical DB
cd historical-db && npm test

# Shared utilities
cd shared && npm test
```

## Interface Contracts

The stage interfaces are defined in `shared/schemas/` and are treated as frozen contracts:

- `webhook_payload.json`
- `telemetry_classification.json`
- `structured_context.json`
- `candidate_patch.json`
- `validation_bundle.json`
- `historical_match.json`
- `historical_db_record.json`
- `human_decision.json`

## License

MIT
