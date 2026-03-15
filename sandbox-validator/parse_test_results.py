#!/usr/bin/env python3
"""
parse_test_results.py — Container log parser for Sentinel-D sandbox validator.

Parses test runner output from container_output.log and writes a
test_results.json conformant with the fields consumed by validate.js:

    {
      "event_id":        str,
      "tests_passed":    int,   -- count of passing tests, or sentinel -1/-2
      "tests_failed":    int,   -- count of failing tests
      "coverage_before": float, -- always 0.0 here (pre-patch not available in container)
      "coverage_after":  float, -- line/statement coverage pct from test runner, or 0.0
      "container_status": str,
      "exit_code":       int
    }

Sentinel values for tests_passed (mirrors validation_bundle.json schema):
    -1 = infrastructure / container timeout failure
    -2 = patch apply failure (git apply exited non-zero)

Supports:
    Jest  --json output  (--outputFile=test_results.json OR stdout JSON block)
    pytest --json-report output (--json-report-file=test_results.json OR stdout)

Usage:
    python3 parse_test_results.py \\
        --log       container_output.log \\
        --exit-code 0 \\
        --language  javascript \\
        --event-id  <uuid> \\
        --out       test_results.json
"""

import argparse
import json
import os
import re
import sys
from typing import Optional


# ── Jest output helpers ────────────────────────────────────────────────────────

def _parse_jest_json(data: dict) -> Optional[dict]:
    """
    Parse a Jest --json report object.

    Jest JSON shape (relevant fields):
        {
          "numPassedTests": int,
          "numFailedTests": int,
          "coverageMap": { ... }   -- present only with --coverage
        }
    Coverage is in coverageMap but computing a single pct requires aggregation.
    We use the summary line from stdout instead when available (simpler).
    """
    passed = data.get("numPassedTests")
    failed = data.get("numFailedTests")

    if passed is None or failed is None:
        return None

    coverage = _extract_jest_coverage_pct(data)

    return {
        "tests_passed": int(passed),
        "tests_failed": int(failed),
        "coverage_after": coverage,
    }


def _extract_jest_coverage_pct(data: dict) -> float:
    """
    Extract a single coverage percentage from a Jest JSON report.

    Jest puts coverage in data['coverageMap'][<file>]['s'] (statement map) etc.
    The simplest reliable number is the 'All files' Statements pct which Jest
    prints to stdout as:
        All files  |   84.21 |  ...
    We fall back to 0.0 if not present rather than computing from raw maps,
    because the stdout summary line is parsed separately below.
    """
    # Jest embeds a 'summary' key in some versions
    summary = data.get("summary", {})
    if summary:
        stmts = summary.get("statements", {})
        pct = stmts.get("pct")
        if pct is not None:
            return float(pct)
    return 0.0


def _parse_jest_from_log(log: str) -> Optional[dict]:
    """
    Extract a Jest JSON block from raw container stdout.

    Jest writes a single top-level JSON object to stdout when --json is passed.
    It may be preceded/followed by other output lines. We find the JSON object
    by locating the first '{' after a line that looks like it starts Jest JSON
    output, then extracting the balanced object.
    """
    # Jest JSON always starts with {"numFailedTestSuites":
    marker = '"numFailedTestSuites"'
    idx = log.find(marker)
    if idx == -1:
        return None

    # Walk back to the opening brace
    start = log.rfind("{", 0, idx)
    if start == -1:
        return None

    # Extract balanced JSON object
    depth = 0
    for i, ch in enumerate(log[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    data = json.loads(log[start : i + 1])
                    return _parse_jest_json(data)
                except json.JSONDecodeError:
                    return None
    return None


def _parse_jest_summary_line(log: str) -> Optional[dict]:
    """
    Fallback: parse Jest human-readable summary lines.

    Jest prints (to stderr/stdout):
        Tests:       5 passed, 5 total
        Tests:       2 failed, 3 passed, 5 total
    and optionally:
        All files  |   84.21 | ...   (coverage table)
    """
    passed = 0
    failed = 0
    found = False

    # Match: "Tests:  X failed, Y passed, Z total"  or  "Tests:  Y passed, Z total"
    pattern = re.compile(
        r"Tests:\s+"
        r"(?:(\d+)\s+failed,\s*)?"   # optional failed count
        r"(?:(\d+)\s+passed)?"        # optional passed count
    )
    for line in log.splitlines():
        m = pattern.search(line)
        if m:
            failed = int(m.group(1) or 0)
            passed = int(m.group(2) or 0)
            found = True
            break

    if not found:
        return None

    # Coverage: "All files  |   84.21 | ..."
    coverage = 0.0
    cov_pattern = re.compile(r"All files\s+\|\s+([\d.]+)")
    m = cov_pattern.search(log)
    if m:
        try:
            coverage = float(m.group(1))
        except ValueError:
            coverage = 0.0

    return {
        "tests_passed": passed,
        "tests_failed": failed,
        "coverage_after": coverage,
    }


# ── pytest output helpers ──────────────────────────────────────────────────────

def _parse_pytest_json(data: dict) -> Optional[dict]:
    """
    Parse a pytest-json-report output object.

    pytest-json-report shape (relevant fields):
        {
          "summary": {
            "passed":  int,
            "failed":  int,
            "total":   int
          },
          "collectors": [...],
          "tests": [...]
        }
    Coverage is NOT included in pytest-json-report by default; it requires
    pytest-cov with --cov --cov-report=json. We read it from coverage.json
    if present, otherwise 0.0.
    """
    summary = data.get("summary", {})
    passed = summary.get("passed", 0)
    failed = summary.get("failed", 0)

    if "passed" not in summary and "failed" not in summary:
        return None

    coverage = _read_pytest_coverage()

    return {
        "tests_passed": int(passed),
        "tests_failed": int(failed),
        "coverage_after": coverage,
    }


def _read_pytest_coverage() -> float:
    """
    Read statement coverage % from coverage.json if pytest-cov wrote it.
    Falls back to 0.0 if the file is absent or malformed.

    coverage.json shape:
        { "totals": { "percent_covered": 84.21, ... } }
    """
    for candidate in ["coverage.json", "/tmp/coverage.json"]:
        if os.path.exists(candidate):
            try:
                with open(candidate) as f:
                    data = json.load(f)
                pct = data.get("totals", {}).get("percent_covered")
                if pct is not None:
                    return float(pct)
            except (json.JSONDecodeError, KeyError):
                pass
    return 0.0


def _parse_pytest_from_log(log: str) -> Optional[dict]:
    """
    Extract a pytest-json-report JSON block from raw container stdout.

    pytest-json-report writes a JSON object to the report file, but when
    captured via container logs the full JSON may appear inline.
    We look for the {"summary": marker.
    """
    marker = '"summary"'
    idx = log.find(marker)
    if idx == -1:
        return None

    start = log.rfind("{", 0, idx)
    if start == -1:
        return None

    depth = 0
    for i, ch in enumerate(log[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    data = json.loads(log[start : i + 1])
                    result = _parse_pytest_json(data)
                    if result:
                        return result
                except json.JSONDecodeError:
                    return None
    return None


def _parse_pytest_summary_line(log: str) -> Optional[dict]:
    """
    Fallback: parse pytest human-readable short test summary.

    pytest -q prints:
        5 passed in 1.23s
        2 failed, 3 passed in 1.23s
        1 error in 0.45s
    """
    pattern = re.compile(
        r"(?:(\d+)\s+failed[,\s])?"     # optional failed
        r"(?:(\d+)\s+passed)?"           # optional passed
        r"(?:.*?)in\s+[\d.]+s"           # "in X.Xs" anchor
    )
    for line in reversed(log.splitlines()):  # last summary line wins
        m = pattern.search(line)
        if m and (m.group(1) or m.group(2)):
            failed = int(m.group(1) or 0)
            passed = int(m.group(2) or 0)
            return {
                "tests_passed": passed,
                "tests_failed": failed,
                "coverage_after": _read_pytest_coverage(),
            }
    return None


# ── Patch apply failure detection ─────────────────────────────────────────────

def _is_patch_apply_failure(log: str, exit_code: int) -> bool:
    """
    Detect whether the container failed because git apply rejected the patch.

    git apply exit codes:
        0  = success
        1  = patch did not apply (conflicts)
        128 = fatal git error

    We also check for the literal error strings git emits.
    """
    if exit_code not in (1, 128):
        return False

    patch_fail_markers = [
        "error: patch failed",
        "error: .* patch does not apply",
        "patch does not apply",
        "No such file or directory",  # patch targets a file that doesn't exist
    ]
    for marker in patch_fail_markers:
        if re.search(marker, log, re.IGNORECASE):
            return True
    return False


def _is_infrastructure_failure(log: str, exit_code: int) -> bool:
    """
    Detect container-level infrastructure failures unrelated to test outcomes.

    Covers: OOM kills, missing dependencies, import errors before tests run,
    container timeout (exit code 124 from the `timeout` wrapper).
    """
    if exit_code == 124:  # timeout(1) exit code
        return True

    infra_markers = [
        "Cannot find module",           # Node.js missing dependency
        "ModuleNotFoundError",          # Python missing dependency
        "ImportError",                  # Python bad import
        "Segmentation fault",
        "Killed",                       # OOM kill
        "Error: spawn .* ENOENT",       # missing binary
        "npm ERR!",                     # npm install failure
        "pip.*ERROR",                   # pip install failure
    ]
    for marker in infra_markers:
        if re.search(marker, log, re.IGNORECASE):
            return True
    return False


# ── Main ───────────────────────────────────────────────────────────────────────

def parse(
    log_path: str,
    exit_code: int,
    language: str,
    event_id: str,
    out_path: str,
) -> dict:
    """
    Parse container_output.log and write test_results.json.

    Returns the parsed result dict (also written to out_path).
    """
    log = ""
    if os.path.exists(log_path):
        with open(log_path, encoding="utf-8", errors="replace") as f:
            log = f.read()

    result = None

    # ── Infrastructure failure: patch apply ───────────────────────────────────
    if _is_patch_apply_failure(log, exit_code):
        result = {
            "event_id": event_id,
            "tests_passed": -2,
            "tests_failed": 0,
            "coverage_before": 0.0,
            "coverage_after": 0.0,
            "container_status": "patch_apply_failure",
            "exit_code": exit_code,
        }

    # ── Infrastructure failure: container / timeout ───────────────────────────
    elif _is_infrastructure_failure(log, exit_code):
        result = {
            "event_id": event_id,
            "tests_passed": -1,
            "tests_failed": 0,
            "coverage_before": 0.0,
            "coverage_after": 0.0,
            "container_status": "infrastructure_failure",
            "exit_code": exit_code,
        }

    # ── Jest (JavaScript) ─────────────────────────────────────────────────────
    elif language == "javascript":
        # Priority 1: Jest --json embedded in log
        parsed = _parse_jest_from_log(log)
        # Priority 2: Jest human-readable summary lines
        if not parsed:
            parsed = _parse_jest_summary_line(log)
        # Priority 3: pre-written test_results.json in working directory
        if not parsed and os.path.exists("test_results.json"):
            try:
                with open("test_results.json") as f:
                    data = json.load(f)
                parsed = _parse_jest_json(data)
            except (json.JSONDecodeError, KeyError):
                pass

        if parsed:
            result = {
                "event_id": event_id,
                "tests_passed": parsed["tests_passed"],
                "tests_failed": parsed["tests_failed"],
                "coverage_before": 0.0,
                "coverage_after": parsed.get("coverage_after", 0.0),
                "container_status": "Succeeded" if exit_code == 0 else "Failed",
                "exit_code": exit_code,
            }

    # ── pytest (Python) ───────────────────────────────────────────────────────
    elif language == "python":
        # Priority 1: pytest-json-report embedded in log
        parsed = _parse_pytest_from_log(log)
        # Priority 2: pytest-json-report file written to disk
        if not parsed:
            for candidate in ["test_results.json", "/tmp/test_results.json"]:
                if os.path.exists(candidate):
                    try:
                        with open(candidate) as f:
                            data = json.load(f)
                        parsed = _parse_pytest_json(data)
                        if parsed:
                            break
                    except (json.JSONDecodeError, KeyError):
                        pass
        # Priority 3: pytest human-readable summary line
        if not parsed:
            parsed = _parse_pytest_summary_line(log)

        if parsed:
            result = {
                "event_id": event_id,
                "tests_passed": parsed["tests_passed"],
                "tests_failed": parsed["tests_failed"],
                "coverage_before": 0.0,
                "coverage_after": parsed.get("coverage_after", 0.0),
                "container_status": "Succeeded" if exit_code == 0 else "Failed",
                "exit_code": exit_code,
            }

    # ── Fallback: could not parse, treat as infrastructure failure ────────────
    if result is None:
        result = {
            "event_id": event_id,
            "tests_passed": -1,
            "tests_failed": 0,
            "coverage_before": 0.0,
            "coverage_after": 0.0,
            "container_status": "parse_failure",
            "exit_code": exit_code,
        }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    return result


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Parse container test output into test_results.json")
    ap.add_argument("--log",        required=True,  help="Path to container_output.log")
    ap.add_argument("--exit-code",  required=True,  type=int, help="Container exit code")
    ap.add_argument("--language",   required=True,  choices=["javascript", "python"])
    ap.add_argument("--event-id",   required=True,  help="Sentinel-D event UUID")
    ap.add_argument("--out",        default="test_results.json", help="Output path")
    args = ap.parse_args()

    result = parse(
        log_path=args.log,
        exit_code=args.exit_code,
        language=args.language,
        event_id=args.event_id,
        out_path=args.out,
    )

    print(json.dumps(result, indent=2), file=sys.stdout)
    sys.exit(0 if result["tests_passed"] >= 0 else 1)