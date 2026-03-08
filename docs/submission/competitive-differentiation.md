# Competitive Differentiation

## What Exists Today

| Tool | What It Does | What It Doesn't Do |
|------|-------------|-------------------|
| **Dependabot** | Bumps dependency versions | Doesn't validate patches, no custom fix strategies, no telemetry-based triage |
| **Snyk** | Finds vulnerabilities + suggests fixes | Fixes are suggestions, not validated patches. No sandbox testing, no confidence scoring |
| **GitHub Copilot Autofix** | Generates code fixes for CodeQL alerts | Single-file scope, no cross-repo learning, no sandbox validation, no graduated autonomy |
| **SWE-agent** | LLM-driven code agent for GitHub Issues | Generic — not security-specialized. No NER, no historical learning, no safety governor |

## What Sentinel-D Does Differently

### 1. Telemetry-Driven Triage (vs. Static Analysis Only)

Every other tool treats all vulnerabilities equally. Sentinel-D queries
**actual runtime telemetry** via Application Insights KQL:
- Is the vulnerable code path actually called in production?
- How frequently? By which services?
- This prevents wasting cycles on dead code vulnerabilities

### 2. Learning Flywheel (vs. Stateless Processing)

No existing tool remembers past resolutions. Sentinel-D's Historical Database
means:
- Same CVE in a different repo → instant replay (90 seconds vs 5 minutes)
- Failed strategies are never repeated (`solutions_to_avoid`)
- Success patterns propagate across the organization
- Cost per resolution drops with every fix (fewer LLM calls)

### 3. Validated Patches (vs. Suggestions)

Dependabot and Snyk suggest version bumps. Copilot Autofix generates code.
Neither validates the result. Sentinel-D:
- Runs the full test suite in an ephemeral sandbox
- Performs SSIM visual regression testing
- Measures coverage deltas
- Only promotes patches that actually work

### 4. Graduated Autonomy (vs. All-or-Nothing)

Other tools are binary: either fully automated (Dependabot auto-merge) or
fully manual (Snyk tickets). Sentinel-D's four-tier Safety Governor provides
graduated trust:
- HIGH confidence → auto-merge (no human needed)
- MEDIUM → PR with required review
- LOW → escalation to security team
- BLOCKED → archive and alert

Override conditions ensure sensitive changes (auth, crypto, visual regressions)
always get human review regardless of confidence score.

### 5. Anti-Repetition Intelligence

Sentinel-D is the only tool that actively prevents repeating failed strategies:
- Historical DB tracks every attempted solution and its outcome
- Failed strategies become hard constraints in future patch generation
- LLM reasoning that mentions a blocked strategy gets a -0.20 confidence penalty
- This closes the "try the same wrong fix repeatedly" loop that plagues
  LLM-based tools

## The Key Demo Moment

**Path A** (cold start): GHAS alert → validated PR in ~5 minutes
**Path B** (warm start): Same CVE → PR in ~90 seconds, zero LLM calls

The delta between Path A and Path B is the learning flywheel in action.
No existing tool gets faster with experience.
