"""Run the CI steps that CAN run on this box, as a substitute for the dead runner.

NOT equivalent to CI and does not claim to be. Excluded by construction:
  * anything needing `pip install` into the runner env (coverage suites in subprojects),
  * anything Linux-only (opengrep/gitleaks tarballs, /usr/local/bin, venv bin/python),
  * anything needing docker services (routing-benchmark's ollama),
  * anything that pushes/opens PRs (autofix-models, codex-runner, dependabot).

What is left is the set of pure-stdlib gates the small workflows run, plus the repo-wide
ruff pair from quality.yml. Those are exactly the ones that guard the lanes' recent commits.

Each step prints SUCCESS:<id> / FAILED:<id> (AGENTS.md section 4) so the log is diffable.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent

# (workflow, step-id, argv). Ordered cheapest-first so a fast break shows early.
STEPS: list[tuple[str, str, list[str]]] = [
    # RUFF FORMAT IS DELEGATED, NOT REIMPLEMENTED. The first version of this script ran
    # `ruff format --check .` directly and reported 50 red files. That number was an
    # artifact twice over: it walked the WORKING TREE (313 untracked lane-scratch files
    # CI never sees) and it read the working-tree BYTES, while this repo has
    # core.autocrlf=true so a tracked file sits CRLF on disk when its blob is LF -- and
    # ruff has been measured deciding differently on the two forms for the same commit.
    # `_b9_format_tracked.py` already gets both right: it derives every tracked *.py
    # (rather than walking a hardcoded list, the hole that let bac65640 ship unformatted)
    # and materialises them from `git cat-file -p` with the committed ruff.toml alongside.
    # Reimplementing it here would have been a second, worse source of truth.
    (
        "quality",
        "ruff-format-blobs",
        [sys.executable, "command-center/hook-audit/_b9_format_tracked.py"],
    ),
    # Same scope trap as format, one level subtler. Ruff honours .gitignore, so `ruff check .`
    # skips ignored files -- but this tree carries 300+ untracked-and-NOT-ignored lane probes
    # that a CI checkout never has, and they contributed all 4 violations the raw step reported.
    # `_ci_lint_tracked.py` intersects with `git ls-files` and passes --force-exclude, without
    # which explicitly-named paths bypass ruff.toml's extend-exclude and the deliberate
    # p2-wave control fixtures read as 90 real violations.
    ("quality", "ruff-check-tracked", [sys.executable, "_ci_lint_tracked.py"]),
    (
        "interpreter-floor",
        "ifloor-selftest",
        [sys.executable, "command-center/ci/interpreter_floor_gate.py", "--self-test"],
    ),
    (
        "interpreter-floor",
        "ifloor-wiring",
        [
            sys.executable,
            "command-center/ci/interpreter_floor_gate.py",
            "--verify-wiring",
        ],
    ),
    (
        "interpreter-floor",
        "ifloor-report",
        [sys.executable, "command-center/ci/interpreter_floor_gate.py", "--report"],
    ),
    (
        "mcp-audit",
        "mcp-selftest",
        [sys.executable, "command-center/mcp-audit/ci_gate.py", "--self-test"],
    ),
    ("mcp-audit", "mcp-gate", [sys.executable, "command-center/mcp-audit/ci_gate.py"]),
    (
        "rule-audit",
        "rule-selftest",
        [sys.executable, "docs/rule-audit/ci_gate.py", "--self-test"],
    ),
    ("rule-audit", "rule-gate", [sys.executable, "docs/rule-audit/ci_gate.py"]),
    (
        "hook-audit",
        "cite-selftest",
        [sys.executable, "command-center/hook-audit/check_citations.py", "--self-test"],
    ),
    (
        "hook-audit",
        "cite-gate-test",
        [sys.executable, "command-center/hook-audit/test_citation_gate.py"],
    ),
    (
        "hook-audit",
        "cite-gate",
        [sys.executable, "command-center/hook-audit/check_citations.py"],
    ),
    (
        "hook-audit",
        "predeploy-tests",
        [
            sys.executable,
            "-m",
            "pytest",
            "command-center/hook-audit/test_hook_predeploy_gate.py",
            "-q",
        ],
    ),
    (
        "hook-audit",
        "failpath-tests",
        [
            sys.executable,
            "-m",
            "pytest",
            "command-center/hook-audit/test_failpath_evidence.py",
            "-q",
        ],
    ),
    (
        "p2next",
        "rail-selftest",
        [sys.executable, "command-center/p2-next/rail_count_gate.py", "--self-test"],
    ),
    (
        "p2next",
        "rail-gate",
        [sys.executable, "command-center/p2-next/rail_count_gate.py"],
    ),
    (
        "p2next",
        "vendor-sat",
        [
            sys.executable,
            "command-center/p2-next/vendor_satisfiability.py",
            "--basis",
            "committed",
        ],
    ),
    (
        "p2next",
        "split-review",
        [
            sys.executable,
            "command-center/p2-next/split_review_gate.py",
            "--basis",
            "committed",
        ],
    ),
    (
        "p2next",
        "k4-selftest",
        [sys.executable, "command-center/p2-next/_k4_tree_survey.py", "--self-test"],
    ),
    (
        "p2next",
        "k4-check",
        [sys.executable, "command-center/p2-next/_k4_tree_survey.py", "--check"],
    ),
    (
        "no-runtime-junk",
        "pubcmd-selftest",
        [
            sys.executable,
            "command-center/slop-report/check_published_commands.py",
            "--self-test",
        ],
    ),
    (
        "no-runtime-junk",
        "pubcmd-gate",
        [sys.executable, "command-center/slop-report/check_published_commands.py"],
    ),
    (
        "no-runtime-junk",
        "r6-transcript",
        [sys.executable, "command-center/slop-report/_r6_transcript.py", "--committed"],
    ),
    (
        "skill-dual-write",
        "cs-wiring",
        [sys.executable, "-m", "pytest", "ci/tests/test_cs_wiring.py", "-q"],
    ),
    (
        "skill-dual-write",
        "ssot-wiring",
        [sys.executable, "-m", "pytest", "ci/tests/test_ssot_wiring.py", "-q"],
    ),
    (
        "skill-dual-write",
        "desc-ratchet",
        [sys.executable, "ci/check_skill_description_ratchet.py"],
    ),
    (
        "skill-dual-write",
        "render-traps",
        [sys.executable, "ci/check_skill_render_traps.py"],
    ),
    (
        "skill-dual-write",
        "skill-index",
        [sys.executable, "ci/gen_skill_index.py", "--check", "--fail-on-drift"],
    ),
    (
        "skill-dual-write",
        "skills-manifest",
        [sys.executable, "ci/gen_skills_manifest.py", "--check"],
    ),
]


def main() -> int:
    results: list[tuple[str, str, str, float, str]] = []
    for wf, sid, argv in STEPS:
        t0 = time.monotonic()
        try:
            p = subprocess.run(
                argv, cwd=REPO, capture_output=True, text=True, timeout=420
            )
            rc, tail = p.returncode, (p.stdout + p.stderr).strip().splitlines()
        except subprocess.TimeoutExpired:
            rc, tail = 124, ["TIMEOUT after 420s"]
        except FileNotFoundError as exc:
            rc, tail = 127, [f"not found: {exc}"]
        dt = time.monotonic() - t0
        last = tail[-1][:150] if tail else ""
        # KEEP THE DIAGNOSTIC. The first version of this script stored only `tail[-1]`,
        # so when `failpath-tests` went red the entire record was "1 failed, 10 passed"
        # -- no test name, no assertion, no traceback. The failure did not reproduce
        # minutes later and could not be diagnosed, because the evidence was discarded
        # at the moment it existed. A gate that reports a failure it cannot explain
        # sends you hunting hypotheses instead of reading the answer.
        if rc:
            diag = REPO / f"_ci_fail_{sid}.log"
            diag.write_text("\n".join(tail[-200:]), encoding="utf-8")
            print(
                f"       diagnostic -> {diag.name} ({len(tail)} lines captured)",
                flush=True,
            )
        results.append(
            (wf, sid, "SUCCESS" if rc == 0 else "FAILED", dt, last if rc else "")
        )
        print(
            f"{'SUCCESS' if rc == 0 else 'FAILED':7} :{sid:<20} {dt:6.1f}s  [{wf}]"
            f"{'  rc=' + str(rc) + '  ' + last if rc else ''}",
            flush=True,
        )

    bad = [r for r in results if r[2] == "FAILED"]
    print("\n" + "=" * 72)
    print(
        f"ran {len(results)} CI steps locally: {len(results) - len(bad)} pass, {len(bad)} fail"
    )
    for wf, sid, _, _, last in bad:
        print(f"  FAILED :{sid}  [{wf}]  {last}")
    print(
        "SUCCESS:ci-local-substitute"
        if not bad
        else f"FAILED:ci-local-substitute {len(bad)} step(s)"
    )
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
