#!/usr/bin/env python3
"""CI Silent-Pass Lint — deterministic linter for GitHub Actions workflows.

Scans .github/workflows/*.{yml,yaml} for patterns that make a gate report
GREEN while masking real findings. Exits non-zero when any HIGH-severity
shape is found so the tool is directly gate-able in pre-PR hooks.

Usage:
    python lint_workflows.py [repo-path]   (default: current directory)
    python lint_workflows.py --help

Shape catalogue (11 silent-pass shapes):
    S01  continue-on-error: true on a gate/analysis step             HIGH
    S02  || true / || exit 0 swallowing a command exit code          HIGH
    S03  issue/quality policy mode: audit (reports but never fails)  HIGH
    S04  token-less / no-token uploads that silently no-op           HIGH
    S05  set +e without re-check; "; true"; pipe ignores failure      HIGH
    S06  gate keyed to stale/pinned SHA instead of HEAD              MEDIUM*
    S07  if: always() on a "success-summary" step                    LOW†
    S08  soft thresholds: --exit-zero, --no-error, severity filters  HIGH
    S09  required-check name mismatch (job never produces the check)  INFO‡
    S10  artifact upload without a corresponding fail-on-findings gate MEDIUM
    S11  fail-fast:false + missing aggregate gate                     MEDIUM

    * S06: YAML alone cannot prove a SHA is stale; linter detects pinned-SHA
           patterns on quality-gate steps (not security-pinning on uses: lines,
           which is a recommended practice). Route final confirmation to the
           MCP cross-check in gate_findings_at_head.md.
    † S07: if:always() is legitimate for artifact/log uploads; linter restricts
           it to steps that post a green-status summary comment or set outputs
           claiming success regardless of upstream job status.
    ‡ S09: required-check name must be validated against branch-protection
           rulesets via API; linter inventories job names only and emits INFO.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import NamedTuple

# ---------------------------------------------------------------------------
# Optional structural analysis via PyYAML (used for S10, S11 only)
# ---------------------------------------------------------------------------
try:
    import yaml as _yaml  # type: ignore

    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

SEVERITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "INFO": 3}


class Finding(NamedTuple):
    file: str
    line: int
    shape: str
    severity: str
    snippet: str
    message: str


# ---------------------------------------------------------------------------
# Per-shape regex patterns (line-local scan)
# ---------------------------------------------------------------------------

# S01 — continue-on-error: true
# Matches the YAML key anywhere on a line, tolerates spacing variants.
_RE_S01 = re.compile(r"\bcontinue-on-error\s*:\s*true\b", re.IGNORECASE)

# S02 — || true  /  || exit 0
_RE_S02 = re.compile(r"\|\|\s*(true|exit\s+0)\b")

# S03 — mode: audit  (issue/quality policy)
_RE_S03 = re.compile(r"\bmode\s*:\s*['\"]?audit['\"]?", re.IGNORECASE)

# S04a — uploads with no token / empty token
# Catches: codecov/codecov-action token:, fail_ci_if_error: false
_RE_S04_NO_TOKEN = re.compile(
    r"(token\s*:\s*$"  # token: <nothing>
    r"|token\s*:\s*['\"]['\"]"  # token: ''  or  token: ""
    r"|fail_ci_if_error\s*:\s*false"
    r")",
    re.IGNORECASE,
)
# S04b — upload step but no token line near it (structural; handled in yaml block below)

# S05 — set +e without recheck; "; true"; pipe masks failure
_RE_S05 = re.compile(
    r"("
    r"set\s+\+e"  # set +e (disables exit-on-error)
    r"|;\s*true\b"  # ; true (swallows previous exit code)
    r"|\|\s*true\b"  # | true (piped to true, masks exit)
    r")",
)

# S06 — pinned SHA in a *run:* step (not uses: — that's security best-practice)
# Only flag when a SHA appears as an explicit --ref or similar argument value.
_RE_S06 = re.compile(
    r"(?:--ref|--sha|--commit)[=\s]+['\"]?[0-9a-f]{40}['\"]?",
    re.IGNORECASE,
)

# S07 — if: always() on a step whose name contains "success", "green", "pass",
#        "summary" (narrow to avoid false-positives on artifact-upload steps)
_RE_S07_IF = re.compile(r"\bif\s*:\s*always\(\)", re.IGNORECASE)
_RE_S07_NAME = re.compile(
    r"\bname\s*:\s*['\"]?[^'\"\n]*(success|green|pass|summary)[^'\"\n]*['\"]?",
    re.IGNORECASE,
)

# S08 — soft threshold flags
_RE_S08 = re.compile(
    r"("
    r"--exit-zero"
    r"|--no-error\b"
    r"|--error-on-unmatched-pattern\s+false"  # semgrep variant
    r"|--max-count=0"  # grep-as-gate silencer
    r"|error_on_failure\s*:\s*false"
    r"|--warning-as-error\s+false"
    r"|severity\s*:\s*['\"]?(none|off|disabled)['\"]?"
    r"|-W\s+ignore"  # python -W ignore
    r"|--fail-under\s+0\b"  # coverage --fail-under 0
    r")",
    re.IGNORECASE,
)

# S09 — inventory job names (emitted as INFO so downstream can compare to
#        branch-protection required contexts; no false-positive HIGH firing)
_RE_S09_JOB = re.compile(r"^(\s{0,4})(\S[\w\-]+)\s*:", re.MULTILINE)

# S10 / S11 — structural; handled in the yaml section below.


# ---------------------------------------------------------------------------
# Line-by-line scanner (provides file:line + snippet for all shapes)
# ---------------------------------------------------------------------------


def _scan_lines(path: Path, lines: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    fname = str(path)

    # Track a sliding window for S07 (name: line precedes if: line)
    recent_name: str | None = None
    recent_name_lineno: int = 0

    for lineno, raw in enumerate(lines, start=1):
        line = raw.rstrip("\n")
        stripped = line.strip()

        # Skip pure comments
        if stripped.startswith("#"):
            continue

        # S01 — continue-on-error: true
        if _RE_S01.search(line):
            findings.append(
                Finding(
                    file=fname,
                    line=lineno,
                    shape="S01",
                    severity="HIGH",
                    snippet=stripped,
                    message="continue-on-error: true on a gate/analysis step masks step failures",
                )
            )

        # S02 — || true / || exit 0
        m = _RE_S02.search(line)
        if m:
            findings.append(
                Finding(
                    file=fname,
                    line=lineno,
                    shape="S02",
                    severity="HIGH",
                    snippet=stripped,
                    message=f"Exit-code swallow via '|| {m.group(1)}' — command failures silently ignored",
                )
            )

        # S03 — mode: audit
        if _RE_S03.search(line):
            findings.append(
                Finding(
                    file=fname,
                    line=lineno,
                    shape="S03",
                    severity="HIGH",
                    snippet=stripped,
                    message="Policy mode: audit — issues are reported but the step never fails",
                )
            )

        # S04a — token-less / fail_ci_if_error:false
        if _RE_S04_NO_TOKEN.search(line):
            findings.append(
                Finding(
                    file=fname,
                    line=lineno,
                    shape="S04",
                    severity="HIGH",
                    snippet=stripped,
                    message="Upload with empty/missing token or fail_ci_if_error:false — silently no-ops when unauthenticated",
                )
            )

        # S05 — set +e / ; true / | true
        # Skip lines already caught by S02 (|| true / || exit 0) to avoid
        # double-reporting: || true satisfies both patterns but S02 is more specific.
        already_s02 = bool(_RE_S02.search(line))
        m5 = _RE_S05.search(line)
        if m5 and not already_s02:
            findings.append(
                Finding(
                    file=fname,
                    line=lineno,
                    shape="S05",
                    severity="HIGH",
                    snippet=stripped,
                    message=f"Exit-code suppression via '{m5.group(1).strip()}' — upstream failures masked",
                )
            )

        # S06 — pinned SHA in a run step argument (not uses: lines)
        if "--ref" in line or "--sha" in line or "--commit" in line:
            if _RE_S06.search(line):
                findings.append(
                    Finding(
                        file=fname,
                        line=lineno,
                        shape="S06",
                        severity="MEDIUM",
                        snippet=stripped,
                        message="Hardcoded SHA passed as --ref/--sha/--commit argument; gate may analyze a stale commit rather than HEAD",
                    )
                )

        # S07 — if: always() near a "success/pass/green/summary" step name
        if _RE_S07_NAME.search(line):
            recent_name = stripped
            recent_name_lineno = lineno

        if _RE_S07_IF.search(line):
            # Flag only if a matching step name was seen in the last 5 lines
            if recent_name and (lineno - recent_name_lineno) <= 5:
                findings.append(
                    Finding(
                        file=fname,
                        line=lineno,
                        shape="S07",
                        severity="LOW",
                        snippet=stripped,
                        message=(
                            f"if: always() on step '{recent_name}' — "
                            "success-summary step runs regardless of upstream failures"
                        ),
                    )
                )

        # S08 — soft thresholds
        if _RE_S08.search(line):
            findings.append(
                Finding(
                    file=fname,
                    line=lineno,
                    shape="S08",
                    severity="HIGH",
                    snippet=stripped,
                    message="Soft threshold flag detected — tool exit code suppressed, findings never fail the gate",
                )
            )

    return findings


# ---------------------------------------------------------------------------
# Structural scanner via PyYAML (S10, S11; best-effort when available)
# ---------------------------------------------------------------------------


def _scan_structural(path: Path, content: str) -> list[Finding]:
    """Parse workflow YAML to detect cross-step / cross-job shapes."""
    if not _YAML_AVAILABLE:
        return []

    try:
        doc = _yaml.safe_load(content)
    except _yaml.YAMLError:
        return []

    if not isinstance(doc, dict):
        return []

    findings: list[Finding] = []
    fname = str(path)
    jobs: dict = doc.get("jobs", {}) or {}

    # S11 — fail-fast: false on a matrix without an aggregate gate job
    for job_name, job in jobs.items():
        if not isinstance(job, dict):
            continue
        strategy = job.get("strategy", {}) or {}
        if isinstance(strategy, dict) and strategy.get("fail-fast") is False:
            matrix = strategy.get("matrix")
            if matrix:
                # Look for any job that declares a "needs:" containing this job
                has_aggregate = any(
                    job_name
                    in (
                        (other.get("needs", []) or [])
                        if isinstance(other.get("needs", []), list)
                        else [other.get("needs")]
                    )
                    for other_name, other in jobs.items()
                    if isinstance(other, dict) and other_name != job_name
                )
                if not has_aggregate:
                    findings.append(
                        Finding(
                            file=fname,
                            line=0,
                            shape="S11",
                            severity="MEDIUM",
                            snippet=f"jobs.{job_name}.strategy.fail-fast: false",
                            message=(
                                f"Job '{job_name}' uses fail-fast:false with a matrix but no aggregate "
                                "gate job depends on it — one failing leg won't block the overall workflow"
                            ),
                        )
                    )

    # S10 — upload step without downstream fail-on-findings gate
    # Heuristic: any step whose uses: contains "upload" or "publish" with no
    # sibling step that checks / asserts findings afterwards in the same job.
    UPLOAD_PATTERN = re.compile(
        r"(upload|publish|report|coverage|codecov|codacy-coverage)",
        re.IGNORECASE,
    )
    GATE_PATTERN = re.compile(
        r"(fail.on.findings|error.on.findings|--fail|exit.code|gate|zero|assert)",
        re.IGNORECASE,
    )
    for job_name, job in jobs.items():
        if not isinstance(job, dict):
            continue
        steps = job.get("steps", []) or []
        upload_step_indices: list[int] = []
        gate_step_indices: list[int] = []
        for idx, step in enumerate(steps):
            if not isinstance(step, dict):
                continue
            uses = step.get("uses", "") or ""
            run = step.get("run", "") or ""
            name = step.get("name", "") or ""
            combined = f"{uses} {run} {name}"
            if UPLOAD_PATTERN.search(combined):
                upload_step_indices.append(idx)
            if GATE_PATTERN.search(combined):
                gate_step_indices.append(idx)

        for uidx in upload_step_indices:
            # Check if any gate step follows this upload step
            has_gate_after = any(gidx > uidx for gidx in gate_step_indices)
            if not has_gate_after:
                step_name = steps[uidx].get(
                    "name", steps[uidx].get("uses", f"step[{uidx}]")
                )
                findings.append(
                    Finding(
                        file=fname,
                        line=0,
                        shape="S10",
                        severity="MEDIUM",
                        snippet=f"jobs.{job_name}.steps[{uidx}] ({step_name})",
                        message=(
                            f"Upload/publish step '{step_name}' in job '{job_name}' has no "
                            "fail-on-findings gate after it — findings are uploaded but never block"
                        ),
                    )
                )

    return findings


# ---------------------------------------------------------------------------
# Main scanner
# ---------------------------------------------------------------------------


def scan_repo(repo_path: Path) -> list[Finding]:
    workflow_dir = repo_path / ".github" / "workflows"
    if not workflow_dir.is_dir():
        print(
            f"[ci-silent-pass-lint] No .github/workflows/ found under {repo_path}",
            file=sys.stderr,
        )
        return []

    patterns = list(workflow_dir.glob("*.yml")) + list(workflow_dir.glob("*.yaml"))
    if not patterns:
        print(
            f"[ci-silent-pass-lint] No workflow files found in {workflow_dir}",
            file=sys.stderr,
        )
        return []

    all_findings: list[Finding] = []
    for wf_path in sorted(patterns):
        try:
            content = wf_path.read_text(encoding="utf-8")
        except OSError as exc:
            print(
                f"[ci-silent-pass-lint] Cannot read {wf_path}: {exc}", file=sys.stderr
            )
            continue
        lines = content.splitlines(keepends=True)
        all_findings.extend(_scan_lines(wf_path, lines))
        all_findings.extend(_scan_structural(wf_path, content))

    # Sort: by severity, then file, then line
    all_findings.sort(
        key=lambda f: (SEVERITY_ORDER.get(f.severity, 99), f.file, f.line)
    )
    return all_findings


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

SEVERITY_LABEL = {
    "HIGH": "[HIGH  ]",
    "MEDIUM": "[MEDIUM]",
    "LOW": "[LOW   ]",
    "INFO": "[INFO  ]",
}


def report(findings: list[Finding]) -> None:
    if not findings:
        print("[ci-silent-pass-lint] No silent-pass shapes detected. EXIT 0.")
        return

    counts: dict[str, int] = {}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1

    print(
        f"[ci-silent-pass-lint] {len(findings)} finding(s) across "
        f"{len({f.file for f in findings})} file(s):\n"
    )

    for f in findings:
        loc = f"{f.file}:{f.line}" if f.line else f"{f.file}"
        print(f"  {SEVERITY_LABEL[f.severity]} {f.shape}  {loc}")
        print(f"    snippet : {f.snippet}")
        print(f"    message : {f.message}")
        print()

    print(
        "Summary:",
        " | ".join(
            f"{sev}={counts.get(sev, 0)}" for sev in ("HIGH", "MEDIUM", "LOW", "INFO")
        ),
    )

    if counts.get("HIGH", 0) > 0:
        print(
            f"\n[ci-silent-pass-lint] {counts['HIGH']} HIGH-severity shape(s) detected "
            "— gate FAILED. Fix before PR creation."
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Detect CI/gate workflows that report GREEN while masking findings.",
    )
    parser.add_argument(
        "repo_path",
        nargs="?",
        default=".",
        help="Path to the repository root (default: current directory)",
    )
    args = parser.parse_args(argv)

    repo_path = Path(args.repo_path).resolve()
    if not repo_path.is_dir():
        print(
            f"[ci-silent-pass-lint] ERROR: {repo_path} is not a directory.",
            file=sys.stderr,
        )
        return 2

    findings = scan_repo(repo_path)
    report(findings)

    high_count = sum(1 for f in findings if f.severity == "HIGH")
    return 1 if high_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
