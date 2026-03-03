---
name: Sentinel-D Dormant Decision
about: Human decision required for a DORMANT vulnerability detected by Sentinel-D
title: "[SENTINEL-DORMANT] {{ CVE_ID }} — {{ AFFECTED_PACKAGE }}"
labels: ["sentinel/dormant"]
assignees: ""
---

<!-- sentinel-metadata
event_id: PLACEHOLDER
cve_id: PLACEHOLDER
severity: PLACEHOLDER
affected_package: PLACEHOLDER
current_version: PLACEHOLDER
file_path: PLACEHOLDER
line_range: PLACEHOLDER
repo: PLACEHOLDER
-->

## 🛡️ Sentinel-D — Dormant Vulnerability Decision Required

| Field | Value |
|-------|-------|
| **CVE ID** | `{{ CVE_ID }}` |
| **Severity** | `{{ SEVERITY }}` |
| **Affected Package** | `{{ AFFECTED_PACKAGE }}` @ `{{ CURRENT_VERSION }}` |
| **Fix Version Range** | `{{ FIX_VERSION_RANGE }}` |
| **File** | `{{ FILE_PATH }}` |
| **Line Range** | `{{ LINE_RANGE }}` |
| **Repository** | `{{ REPO }}` |
| **Production Call Count (30d)** | **0** (DORMANT — no production calls detected) |

---

## 📚 Historical DB Context

{{ HISTORICAL_CONTEXT }}

---

## 🏷️ Decision — Apply ONE Label

Choose **one** of the following labels to proceed:

### `sentinel/fix-now`
> Triggers the full Sentinel-D agentic remediation pipeline. The system will generate a patch, validate it in a sandbox, and open a PR if the confidence score is high enough.

### `sentinel/defer`
> Adds this vulnerability to the 30-day deferred backlog. Sentinel-D will re-evaluate after 30 days and re-open a decision issue if the vulnerability is still present.

### `sentinel/wont-fix`
> Records this as an **accepted risk**. Future Sentinel-D scans will not alert on this CVE in the affected file. Requires justification — please add a comment explaining why before applying this label.

---

⚠️ **Auto-Escalation Warning:** This issue will auto-escalate in **72 hours** if no label is applied. The system will re-check production telemetry — if calls are now detected, the pipeline will be triggered automatically. Otherwise, the issue will be escalated to the security team lead.
