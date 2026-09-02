"""Run extracted commands verbatim in a clean environment and diff outputs."""
from __future__ import annotations

import difflib
import os
import re
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

CRED_RE = re.compile(
    r"API[_-]?KEY|AUTHORIZATION\s*:|Bearer\s+\$|OPENAI|ANTHROPIC|"
    r"AWS_SECRET|--password|--token\b|\bgh\s+auth\b|\bdocker\s+login\b",
    re.I,
)
DANGER_RE = re.compile(
    r"\bgit\s+(add|commit|push|stash|checkout|rebase|reset|clone)\b|"
    r"\bnpm\s+(install|ci)\b|"
    r"\bpip3?\s+install\b|"
    r"seed\.py\b.*--force|"
    r"render\.py(?!\s+--check)|"
    r"close\.py\s+(?!--list\b)(?!--help\b)|"
    r"\brm\s+-rf\b|"
    r"unit_manifest\.py\s+.*--write|"
    r"finish-everything-close|p2-cloud-ok-deliver|"
    r"git-crypt\s+unlock|"
    r"claude\s+(plugin|mcp)\s+",
    re.I,
)


def normalize_output(text: str) -> str:
    lines = [ln.rstrip() for ln in (text or "").replace("\r\n", "\n").split("\n")]
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def output_diff(documented: str, actual: str) -> str:
    a = normalize_output(documented).splitlines(keepends=True)
    b = normalize_output(actual).splitlines(keepends=True)
    if a and not a[-1].endswith("\n"):
        a[-1] = a[-1] + "\n"
    if b and not b[-1].endswith("\n"):
        b[-1] = b[-1] + "\n"
    return "".join(
        difflib.unified_diff(a, b, fromfile="documented", tofile="actual", n=3)
    )


NET_RE = re.compile(
    r"\buvx\b|"
    r"\bnpm\s+test\b|"
    r"claude\s+mcp\s+get\b",
    re.I,
)


def classify_block(invocation: str) -> str | None:
    if CRED_RE.search(invocation or ""):
        return "blocked-external:credentials"
    if DANGER_RE.search(invocation or ""):
        return "blocked-external:destructive-or-forbidden"
    if NET_RE.search(invocation or ""):
        return "blocked-external:network-or-package-fetch"
    return None


def argv0_exists(invocation: str, repo: Path) -> tuple[bool, str]:
    try:
        args = shlex.split(invocation)
    except ValueError as exc:
        return False, f"unparseable:{exc}"
    if not args:
        return False, "empty-invocation"
    first = args[0]
    if os.path.isabs(first):
        return os.path.isfile(first) or os.path.isdir(first), first
    if "/" in first or first.startswith("."):
        cand = repo / first
        return cand.exists(), str(cand)
    found = shutil.which(first)
    return found is not None, found or first


def _clean_env(home: Path, tmp: Path) -> dict[str, str]:
    path = os.pathsep.join(
        p
        for p in ("/usr/bin", "/bin", "/usr/local/bin")
        if p
    )
    env = {
        "PATH": path,
        "HOME": str(home),
        "TMPDIR": str(tmp),
        "TEMP": str(tmp),
        "TMP": str(tmp),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
    }
    return env


def run_one(
    invocation: str,
    repo: Path,
    timeout: int = 45,
) -> dict[str, Any]:
    blocked = classify_block(invocation)
    exists, resolved = argv0_exists(invocation, repo)
    row: dict[str, Any] = {
        "invocation": invocation,
        "argv0_resolved": resolved,
        "argv0_exists": exists,
        "blocked_reason": blocked,
        "actual_output": "",
        "actual_exit": None,
        "timed_out": False,
        "fresh_home_empty_at_start": True,
        "diff": "",
        "outcome": "",
        "classification": "",
    }
    if blocked:
        row["outcome"] = "BLOCKED"
        row["classification"] = blocked
        return row
    if not exists:
        row["outcome"] = "COMMAND-MISSING"
        row["classification"] = "documentation-defect"
        return row
    try:
        args = shlex.split(invocation)
    except ValueError as exc:
        row["outcome"] = "COMMAND-MISSING"
        row["classification"] = f"documentation-defect:unparseable:{exc}"
        return row
    with tempfile.TemporaryDirectory(prefix="cnf0037-home-") as home_s:
        with tempfile.TemporaryDirectory(prefix="cnf0037-tmp-") as tmp_s:
            home = Path(home_s)
            listing = list(home.iterdir())
            row["fresh_home_empty_at_start"] = listing == []
            env = _clean_env(home, Path(tmp_s))
            try:
                proc = subprocess.run(
                    args,
                    cwd=str(repo),
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
            except subprocess.TimeoutExpired as exc:
                out = ((exc.stdout or "") + (exc.stderr or "")).strip()
                row["actual_output"] = out
                row["timed_out"] = True
                row["outcome"] = "TIMEOUT"
                row["classification"] = "blocked-external"
                return row
            text = ((proc.stdout or "") + (proc.stderr or ""))
            row["actual_output"] = text
            row["actual_exit"] = int(proc.returncode)
    return row


def verdict_for(extracted: dict[str, Any], ran: dict[str, Any]) -> dict[str, Any]:
    documented = extracted.get("documented_output") or ""
    documented_exit = extracted.get("documented_exit")
    merged = dict(extracted)
    merged.update(ran)
    diff = output_diff(documented, ran.get("actual_output") or "")
    merged["diff"] = diff
    merged["diff_algorithm"] = "difflib.unified_diff"
    if ran.get("outcome") in {"BLOCKED", "COMMAND-MISSING", "TIMEOUT"}:
        return merged
    actual_exit = ran.get("actual_exit")
    out_norm = normalize_output(ran.get("actual_output") or "")
    doc_norm = normalize_output(documented)
    exit_mismatch = (
        documented_exit is not None
        and actual_exit is not None
        and int(actual_exit) != int(documented_exit)
    )
    output_mismatch = bool(doc_norm) and doc_norm != out_norm
    if output_mismatch or (bool(doc_norm) and diff):
        merged["outcome"] = "DIFF"
        merged["classification"] = "documentation-defect"
        return merged
    if exit_mismatch:
        merged["outcome"] = "FAILED"
        merged["classification"] = "documentation-defect"
        return merged
    if actual_exit not in (0, None) and documented_exit is None and not doc_norm:
        merged["outcome"] = "FAILED"
        merged["classification"] = "documentation-defect"
        return merged
    merged["outcome"] = "MATCH"
    merged["classification"] = "conforming"
    return merged


def execute_all(
    extracted: list[dict[str, Any]],
    repo: Path,
    timeout: int = 45,
) -> list[dict[str, Any]]:
    out = []
    for rec in extracted:
        ran = run_one(rec["invocation"], repo, timeout=timeout)
        out.append(verdict_for(rec, ran))
    return out


def check_verdict(outcome: str) -> str:
    if outcome == "MATCH":
        return "PASS"
    if outcome == "BLOCKED":
        return "BLOCKED"
    return "FAIL"


def counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    tally = {
        "extracted": len(rows),
        "recorded": len(rows),
        "silently_omitted": 0,
        "match": 0,
        "command_missing": 0,
        "failed": 0,
        "output_differs": 0,
        "blocked": 0,
        "timeout": 0,
    }
    for r in rows:
        o = r.get("outcome")
        if o == "MATCH":
            tally["match"] += 1
        elif o == "COMMAND-MISSING":
            tally["command_missing"] += 1
        elif o == "FAILED":
            tally["failed"] += 1
        elif o == "DIFF":
            tally["output_differs"] += 1
        elif o == "BLOCKED":
            tally["blocked"] += 1
        elif o == "TIMEOUT":
            tally["timeout"] += 1
    tally["do_not_exist_or_fail_or_differ"] = (
        tally["command_missing"] + tally["failed"] + tally["output_differs"]
    )
    return tally
