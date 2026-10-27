#!/usr/bin/env python3
"""I2 -- the both-states red-proof for the wf-timeout CI integration.

A gate that has never gone red is indistinguishable from a no-op.  This script
mirrors the minimum tree ``ci/tests/test_wf_timeout_ci_wiring.py`` reads into a
temp directory (the test derives its repo root from ``__file__.parents[2]``, so a
mirror is enough), then runs the SAME test file against three states:

    S0 WIRED     -- quality.yml verbatim                      -> expect PASS
    S1 UNWIRED   -- the setup-node + wf-timeout step removed   -> expect FAIL
    S2 WEAKENED  -- --cov-fail-under=100 downgraded to 80      -> expect FAIL

S0 is the control on the control: without it, a mirror that is broken for some
unrelated reason would report red in every state and prove nothing.

The live working tree is never mutated.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEST_REL = "ci/tests/test_wf_timeout_ci_wiring.py"

MIRROR_FILES = [
    TEST_REL,
    "ci/tests/conftest.py",
    "ci/tests/dual_write_fixtures.py",
    ".github/workflows/quality.yml",
    ".github/workflows/skill-dual-write.yml",
    "tools/wf-timeout/wf_gate.py",
    "tools/wf-timeout/h6_extract.py",
    "tools/wf-timeout/h6_harness.mjs",
    "tools/wf-timeout/test_h6_timeout.py",
    "skills/workflow-authoring/templates/h6-timeout-heartbeat.md",
]

# The exact block this lane added, reconstructed from the live file by anchors so
# the excision is the real "step was never added" state, not an approximation.
BLOCK_START = "      # tools/wf-timeout -- design item H6"
BLOCK_END = "      # ================================ VENDORED TOOL TREES"


def mirror(dest: Path) -> None:
    for rel in MIRROR_FILES:
        src = ROOT / rel
        if not src.is_file():
            raise SystemExit(f"FAILED:redproof mirror source missing: {rel}")
        out = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, out)


def excise_step(text: str) -> str:
    start = text.index(BLOCK_START)
    end = text.index(BLOCK_END)
    if not start < end:
        raise SystemExit("FAILED:redproof anchors out of order")
    return text[:start] + text[end:]


def run(dest: Path) -> tuple[int, str]:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            TEST_REL,
            "-q",
            "--no-header",
            "-p",
            "no:cacheprovider",
        ],
        cwd=dest,
        capture_output=True,
        text=True,
    )
    tail = [ln for ln in proc.stdout.splitlines() if ln.strip()][-1:]
    return proc.returncode, (tail[0] if tail else "<no output>")


def state(name: str, mutate, want_pass: bool) -> bool:
    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp)
        mirror(dest)
        wf = dest / ".github" / "workflows" / "quality.yml"
        wf.write_text(mutate(wf.read_text(encoding="utf-8")), encoding="utf-8")
        rc, tail = run(dest)
        passed = rc == 0
        ok = passed == want_pass
        verdict = "PASS" if passed else "FAIL"
        want = "PASS" if want_pass else "FAIL"
        print(f"  {name:<10} rc={rc} -> {verdict:<4} (want {want}) [{tail}]")
        return ok


def main() -> int:
    print("I2 both-states red-proof for the wf-timeout CI wiring")
    results = [
        state("S0 WIRED", lambda t: t, want_pass=True),
        state("S1 UNWIRED", excise_step, want_pass=False),
        state(
            "S2 WEAKENED",
            lambda t: t.replace(
                "--cov-report=term-missing --cov-fail-under=100\n"
                "          python wf_gate.py --self-test",
                "--cov-report=term-missing --cov-fail-under=80\n"
                "          python wf_gate.py --self-test",
            ),
            want_pass=False,
        ),
    ]
    if all(results):
        print("SUCCESS:redproof control fires -- green when wired, red when not")
        return 0
    print("FAILED:redproof a state did not behave as required; the check is not a gate")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
