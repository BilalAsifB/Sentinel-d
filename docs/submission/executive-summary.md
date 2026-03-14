# Executive Summary

**Sentinel-D** is an autonomous DevSecOps pipeline that transforms passive
vulnerability scanning into active, intelligent remediation. When GitHub Advanced
Security detects a vulnerability, Sentinel-D doesn't just create an alert — it
generates a tested, validated patch and opens a pull request, all without human
intervention.

## The Problem

Modern software teams face an overwhelming volume of security vulnerabilities.
GHAS, Snyk, and Dependabot all excel at *finding* vulnerabilities, but the
remediation burden falls entirely on developers. The average critical CVE takes
60+ days to fix. Security teams triage; developers context-switch; patches sit
in queues. Meanwhile, the vulnerability remains exploitable.

## The Solution

Sentinel-D closes the loop from detection to remediation in under 5 minutes:

1. **Intelligent Triage** — An SRE Agent queries Application Insights telemetry
   to classify vulnerabilities as ACTIVE (exploitable code paths are hit),
   DORMANT (code exists but isn't called), or DEFERRED (previously deferred,
   re-evaluated on schedule).

2. **Learning Flywheel** — A Historical Database stores every past resolution.
   When the same CVE appears again (even in a different repo), Sentinel-D
   replays the proven fix via RAG, cutting resolution time from 5 minutes to
   90 seconds — without calling the LLM at all.

3. **Safe Autonomy** — A four-tier Safety Governor ensures that high-confidence
   patches auto-merge, medium-confidence patches require human review, and
   low-confidence issues escalate to security teams. An append-only audit log
   records every decision for compliance.

Built entirely on the Microsoft Azure stack — Foundry for LLM inference,
Cosmos DB for the learning database, Service Bus for event-driven architecture,
Container Apps for ephemeral sandbox validation, and Application Insights for
telemetry-driven classification.
