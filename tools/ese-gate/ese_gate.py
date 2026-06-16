#!/usr/bin/env python3
"""
Ensemble Semantic Entropy (ESE) Escalation Gate
================================================
Measures cross-model disagreement among council candidates by clustering them
on execution-equivalence, computing normalised Shannon entropy over cluster
sizes, and emitting a routing decision:

  escalate=false  →  models agree  →  accept cheaply
  escalate=true   →  models disagree  →  deep-review lane

Requires only the Python standard library.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_THRESHOLD: float = 0.5
DEFAULT_TIMEOUT: int = 120  # seconds per candidate run
BROKEN_SIGNATURE: str = "__BROKEN__"


# ---------------------------------------------------------------------------
# Patch application
# ---------------------------------------------------------------------------

def _apply_patch_unified(workdir: str, patch_text: str) -> bool:
    """
    Try to apply a unified diff patch to *workdir* using the `patch` command
    (preferred on Unix) or `git apply` (fallback).  Returns True on success.
    """
    # Write patch to a temp file inside the workdir so paths resolve correctly.
    patch_file = os.path.join(workdir, "__candidate.patch")
    try:
        with open(patch_file, "w", encoding="utf-8", errors="replace") as fh:
            fh.write(patch_text)

        # Attempt 1: `patch -p1`
        result = subprocess.run(
            ["patch", "-p1", "--input", patch_file],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return True

        # Attempt 2: `git apply`
        result2 = subprocess.run(
            ["git", "apply", "--whitespace=nowarn", patch_file],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result2.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False
    finally:
        try:
            os.remove(patch_file)
        except OSError:
            pass


def _apply_files_map(workdir: str, files: dict[str, str]) -> bool:
    """Write a files-map (path→content) into *workdir*.  Always succeeds unless
    an I/O error occurs."""
    try:
        for rel_path, content in files.items():
            abs_path = os.path.join(workdir, rel_path)
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            with open(abs_path, "w", encoding="utf-8", errors="replace") as fh:
                fh.write(content)
        return True
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Behaviour signature
# ---------------------------------------------------------------------------

def _parse_pytest_outcomes(output: str) -> list[str] | None:
    """
    Extract a sorted list of '<nodeid>::<PASSED|FAILED|ERROR>' strings from
    pytest -v or -q output.  Returns None if the format is not recognisable.
    """
    # pytest -v lines look like:
    #   tests/test_foo.py::test_bar PASSED
    #   tests/test_foo.py::test_baz FAILED
    pattern = re.compile(
        r"^([\w/\\.\-]+::[\w\[\]\-]+)\s+(PASSED|FAILED|ERROR)\s*$",
        re.MULTILINE,
    )
    matches = pattern.findall(output)
    if not matches:
        return None
    return sorted(f"{nid}:{outcome}" for nid, outcome in matches)


_NOISE_PATTERNS: tuple[re.Pattern[str], ...] = (
    # pytest rootdir / header lines that embed the (temp-unique) working path
    re.compile(r"^rootdir\s*:", re.IGNORECASE),
    re.compile(r"^cachedir\s*:", re.IGNORECASE),
    re.compile(r"^platform\s+\w+"),
    re.compile(r"^plugins\s*:"),
    re.compile(r"^collecting\s+\.\.\."),
    # pytest timing suffix:  "3 passed in 0.29s"  /  "= 3 passed in 0.29s ="
    re.compile(r"\bin\s+\d+[\.,]\d+s\b"),
    # Lines that look like absolute paths (contain :\ or start with /)
    re.compile(r"(?:[A-Za-z]:[/\\]|^/)"),
)


def _strip_noise(text: str) -> str:
    """Remove lines / fragments that vary across identical runs (paths, timings)."""
    cleaned: list[str] = []
    for line in text.splitlines():
        stripped = line.rstrip()
        if not stripped:
            continue
        # Drop lines that match any noise pattern.
        if any(p.search(stripped) for p in _NOISE_PATTERNS):
            continue
        cleaned.append(stripped)
    return "\n".join(cleaned)


def _behaviour_signature(exit_code: int, stdout: str) -> str:
    """
    Derive a stable behaviour signature from (exit_code, stdout).

    Strategy (in order of precision):
      1. If pytest -v output is recognisable (individual PASSED/FAILED lines) →
         hash sorted pass/fail list (ignores timing noise and ordering).
      2. Otherwise → hash noise-stripped stdout so that identical test runs
         produce the same hash regardless of temp-path or timing differences.
    """
    outcomes = _parse_pytest_outcomes(stdout)
    if outcomes:
        raw = f"exit={exit_code}|outcomes={','.join(outcomes)}"
    else:
        normalised = _strip_noise(stdout)
        raw = f"exit={exit_code}|stdout={normalised}"

    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Per-candidate execution
# ---------------------------------------------------------------------------

def _run_candidate(
    candidate: dict[str, Any],
    workdir: str,
    test_cmd: str,
    timeout: int,
) -> str:
    """
    Copy *workdir* to a temp directory, apply the candidate's changes, run
    *test_cmd*, and return the behaviour signature.

    Returns BROKEN_SIGNATURE if anything goes wrong.
    """
    with tempfile.TemporaryDirectory(prefix="ese_candidate_") as tmp:
        # Copy the pristine workdir into the temp location.
        sandbox = os.path.join(tmp, "workdir")
        try:
            shutil.copytree(workdir, sandbox)
        except OSError:
            return BROKEN_SIGNATURE

        # Apply changes.
        applied = False
        if "patch" in candidate:
            applied = _apply_patch_unified(sandbox, candidate["patch"])
        elif "files" in candidate:
            applied = _apply_files_map(sandbox, candidate["files"])
        else:
            # No changes specified — run baseline as-is.
            applied = True

        if not applied:
            return BROKEN_SIGNATURE

        # Run the test command.
        try:
            proc = subprocess.run(
                test_cmd,
                shell=True,
                cwd=sandbox,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
            return _behaviour_signature(proc.returncode, proc.stdout + proc.stderr)
        except subprocess.TimeoutExpired:
            return BROKEN_SIGNATURE
        except OSError:
            return BROKEN_SIGNATURE


# ---------------------------------------------------------------------------
# Clustering & entropy
# ---------------------------------------------------------------------------

def _cluster_candidates(
    candidates: list[dict[str, Any]],
    signatures: list[str],
) -> dict[str, list[str]]:
    """
    Group candidate models by their behaviour signature.
    Returns {signature: [model_label, ...]} mapping.
    """
    clusters: dict[str, list[str]] = {}
    for candidate, sig in zip(candidates, signatures):
        label = candidate.get("model", "unknown")
        clusters.setdefault(sig, []).append(label)
    return clusters


def _normalised_entropy(clusters: dict[str, list[str]], n: int) -> float:
    """
    Compute Shannon entropy over cluster-size distribution, normalised by
    log(N) so the result is always in [0, 1].

      H = -Σ p_i * log(p_i) / log(N)

    Edge cases:
      * N == 1  →  0.0  (only one candidate, trivially agree)
      * all in one cluster  →  0.0
      * all in distinct clusters  →  1.0
    """
    if n <= 1:
        return 0.0
    total = sum(len(v) for v in clusters.values())
    if total == 0:
        return 0.0
    raw_h = 0.0
    for members in clusters.values():
        p = len(members) / total
        if p > 0:
            raw_h -= p * math.log(p)
    return raw_h / math.log(n)


# ---------------------------------------------------------------------------
# Verdict assembly
# ---------------------------------------------------------------------------

def _build_verdict(
    candidates: list[dict[str, Any]],
    clusters: dict[str, list[str]],
    entropy: float,
    threshold: float,
    require_majority: bool,
) -> dict[str, Any]:
    """
    Assemble the final JSON verdict dict.
    """
    n = len(candidates)

    # Identify plurality cluster (largest, excluding broken if possible).
    non_broken = {sig: m for sig, m in clusters.items() if sig != BROKEN_SIGNATURE}
    broken_models = clusters.get(BROKEN_SIGNATURE, [])

    plurality_sig: str | None = None
    plurality_models: list[str] = []
    plurality_share: float = 0.0

    if non_broken:
        plurality_sig = max(non_broken, key=lambda s: len(non_broken[s]))
        plurality_models = non_broken[plurality_sig]
        plurality_share = len(plurality_models) / n
    elif broken_models:
        # All candidates broken — escalate regardless.
        plurality_sig = BROKEN_SIGNATURE
        plurality_models = broken_models
        plurality_share = 1.0

    # Escalation logic.
    escalate = entropy >= threshold
    if require_majority and plurality_share < 0.5:
        escalate = True

    # Pick a representative winner from plurality cluster (first candidate
    # whose model label appears in plurality_models, preserving manifest order).
    recommended_winner: dict[str, Any] | None = None
    if plurality_sig and plurality_sig != BROKEN_SIGNATURE:
        for c in candidates:
            if c.get("model", "unknown") in plurality_models:
                recommended_winner = {k: v for k, v in c.items() if k != "patch" and k != "files"}
                recommended_winner["model"] = c.get("model", "unknown")
                break

    # Clusters serialised with short sig keys.
    clusters_out = {sig: sorted(models) for sig, models in clusters.items()}

    # Human summary.
    if escalate:
        summary = (
            f"ESCALATE: entropy={entropy:.3f} (threshold={threshold}), "
            f"plurality={plurality_share:.0%} of {n} candidates"
        )
    else:
        summary = (
            f"ACCEPT: entropy={entropy:.3f} (threshold={threshold}), "
            f"plurality cluster ({', '.join(sorted(plurality_models))}) "
            f"covers {plurality_share:.0%} of {n} candidates"
        )

    return {
        "escalate": escalate,
        "entropy": round(entropy, 6),
        "threshold": threshold,
        "n_candidates": n,
        "clusters": clusters_out,
        "plurality_models": sorted(plurality_models),
        "plurality_share": round(plurality_share, 4),
        "recommended_winner": recommended_winner,
        "broken_models": sorted(broken_models),
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run(manifest: dict[str, Any], threshold: float, timeout: int, require_majority: bool) -> dict[str, Any]:
    """
    Core logic — separated from CLI so tests can call it directly.
    """
    candidates: list[dict[str, Any]] = manifest.get("candidates", [])
    test_cmd: str = manifest.get("test_cmd", "")
    workdir: str = manifest.get("workdir", ".")

    if not candidates:
        return {
            "escalate": True,
            "error": "No candidates in manifest",
            "summary": "ESCALATE: no candidates provided",
        }

    if not test_cmd:
        return {
            "escalate": True,
            "error": "No test_cmd in manifest",
            "summary": "ESCALATE: no test_cmd provided",
        }

    # Resolve workdir relative to cwd if not absolute.
    if not os.path.isabs(workdir):
        workdir = os.path.abspath(workdir)

    if not os.path.isdir(workdir):
        return {
            "escalate": True,
            "error": f"workdir does not exist: {workdir}",
            "summary": "ESCALATE: workdir not found",
        }

    # Execute each candidate in isolation.
    signatures: list[str] = []
    for i, candidate in enumerate(candidates):
        sig = _run_candidate(candidate, workdir, test_cmd, timeout)
        signatures.append(sig)

    # Cluster and compute entropy.
    clusters = _cluster_candidates(candidates, signatures)
    n = len(candidates)
    entropy = _normalised_entropy(clusters, n)

    return _build_verdict(candidates, clusters, entropy, threshold, require_majority)


def main(argv: list[str] | None = None) -> int:
    """
    CLI entry point.  Returns exit code (0 = success, 1 = tool error).
    Fail-safe: any unhandled exception emits escalate=true and exits 0
    (safe lane) so the caller is never silently unprotected.
    """
    try:
        parser = argparse.ArgumentParser(
            prog="ese_gate",
            description="Ensemble Semantic Entropy escalation gate for multi-model code councils.",
        )
        parser.add_argument(
            "--manifest",
            metavar="FILE",
            help="Path to the JSON manifest (omit to read from stdin).",
        )
        parser.add_argument(
            "--threshold",
            type=float,
            default=DEFAULT_THRESHOLD,
            help=f"Normalised entropy threshold for escalation (default: {DEFAULT_THRESHOLD}).",
        )
        parser.add_argument(
            "--timeout",
            type=int,
            default=DEFAULT_TIMEOUT,
            help=f"Per-candidate test-run timeout in seconds (default: {DEFAULT_TIMEOUT}).",
        )
        parser.add_argument(
            "--no-require-majority",
            dest="require_majority",
            action="store_false",
            default=True,
            help="Disable automatic escalation when plurality < 50%% (not recommended).",
        )
        parser.add_argument(
            "--pretty",
            action="store_true",
            help="Pretty-print the JSON output.",
        )
        args = parser.parse_args(argv)

        # Load manifest.
        if args.manifest:
            with open(args.manifest, "r", encoding="utf-8") as fh:
                manifest = json.load(fh)
        else:
            manifest = json.load(sys.stdin)

        verdict = run(
            manifest=manifest,
            threshold=args.threshold,
            timeout=args.timeout,
            require_majority=args.require_majority,
        )

        indent = 2 if args.pretty else None
        print(json.dumps(verdict, indent=indent))
        return 0

    except Exception:  # pylint: disable=broad-except
        # FAIL-SAFE: never let a tool crash silently accept a bad patch.
        error_info = traceback.format_exc()
        safe_verdict = {
            "escalate": True,
            "error": "ese_gate internal error — defaulting to escalate",
            "detail": error_info,
            "summary": "ESCALATE: tool error; safe default applied",
        }
        print(json.dumps(safe_verdict, indent=2))
        return 0  # Exit 0 so shell scripts that check exit code still get the JSON.


if __name__ == "__main__":
    sys.exit(main())
