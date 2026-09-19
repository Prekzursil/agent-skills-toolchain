#!/usr/bin/env python3
"""AUD-0042 NAMED PROBE 2: zero-collected-count both-states control.

Catalog tests_required:
  control: assert that at least one step reports a NON-ZERO collected count;
  a run where every step collects zero is a harness failure being reported
  as a pass.

Catalog reviewer_requirement: one cross-vendor Codex reviewer who re-runs
ONLY this probe (the second probe).

This is the both-states control the catalog demands: a scratch pytest
invocation that collects ZERO tests but is wrapped the way a careless CI
step can be (`... || true`) so it EXITS 0 anyway (BAD state -- identical
exit code to a real pass, only the collected count tells them apart), next
to a scratch invocation that collects a real, non-zero count and also exits
0 (GOOD state). An exit-code-only detector cannot distinguish these two
states; a collected-count-aware detector can. The probe then independently
re-parses AUD-0042 Probe 1's own JSON output and re-derives
with_nonzero_collected_count from the raw per-step list (not by trusting
Probe 1's precomputed summary field) to confirm the real dataset actually
satisfies the control, not just the synthetic fixture.

Never mutates the live tree; all pytest invocations run against files in a
TemporaryDirectory.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE = Path(__file__).resolve().parent
OUT = PROBE / "probe2-zero-count-control.json"
RAW = PROBE / "probe2-zero-count-control.raw.txt"
PROBE1_JSON = PROBE / "probe1-execute-never-run-steps.json"

EMPTY_TEST_SRC = "def not_a_test_helper():\n    return 1\n"
GOOD_TEST_SRC = "def test_aud0042_control_ok():\n    assert 1 == 1\n"

COLLECTED_RE = re.compile(r"collected (\d+) item")
PASSED_RE = re.compile(r"\b(\d+) passed\b")

lines: list[str] = []


def log(msg: str) -> None:
    lines.append(msg)
    print(msg)


def run_wrapped(cmd: str, cwd: Path) -> dict:
    """Run a shell command exactly as a careless CI step might: `<cmd> || true`
    so a non-zero pytest exit (5 = no tests collected) is silenced to 0,
    mirroring the exact failure mode the catalog's tests_required warns
    about."""
    r = subprocess.run(
        ["bash", "-c", f"{cmd} || true"],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=30,
        encoding="utf-8",
        errors="replace",
    )
    out = (r.stdout or "") + (r.stderr or "")
    passed_m = PASSED_RE.findall(out)
    passed = sum(int(x) for x in passed_m) if passed_m else 0
    collected_m = COLLECTED_RE.findall(out)
    no_tests_ran = "no tests ran" in out.lower()
    collected = (
        passed if passed else (sum(int(x) for x in collected_m) if collected_m else 0)
    )
    return {
        "exit_code": r.returncode,
        "collected_count": collected,
        "no_tests_ran": no_tests_ran,
        "stdout_tail": out[-1000:],
    }


def recheck_probe1_independently() -> dict:
    """Re-derive with_nonzero_collected_count from the RAW per-step list in
    probe1's JSON, rather than trusting probe1's own precomputed summary
    field -- an independent recheck of the same data, as this probe's
    reviewer is expected to perform."""
    if not PROBE1_JSON.is_file():
        return {"ok": False, "reason": "probe1 output missing", "recount": None}
    doc = json.loads(PROBE1_JSON.read_text(encoding="utf-8"))
    steps = doc.get("steps", [])
    recount_nonzero = sum(1 for s in steps if (s.get("collected_count") or 0) > 0)
    recount_zero_pytest = sum(
        1
        for s in steps
        if s.get("is_pytest_step") and (s.get("collected_count") or 0) == 0
    )
    declared = doc.get("with_nonzero_collected_count")
    agree = recount_nonzero == declared
    return {
        "ok": recount_nonzero > 0 and agree,
        "declared_with_nonzero_collected_count": declared,
        "independently_recounted_nonzero": recount_nonzero,
        "independently_recounted_zero_pytest_steps": recount_zero_pytest,
        "agree_with_probe1_summary": agree,
        "total_steps_examined": len(steps),
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="aud-0042-") as td:
        scratch = Path(td)
        (scratch / "empty_test.py").write_text(EMPTY_TEST_SRC, encoding="utf-8")
        (scratch / "good_test.py").write_text(GOOD_TEST_SRC, encoding="utf-8")

        log("AUD-0042 NAMED PROBE 2: zero-collected-count both-states control")
        log("unit=AUD-0042")

        # BAD state: zero tests collected, but the naive `|| true` wrapper
        # used by careless CI steps silences the non-zero pytest exit code.
        bad = run_wrapped(f"{sys.executable} -m pytest empty_test.py -q", scratch)
        log(
            f"BAD_STATE(zero-collected,silenced) exit={bad['exit_code']} "
            f"collected={bad['collected_count']} no_tests_ran={bad['no_tests_ran']}"
        )

        # GOOD state: a real, non-zero collected count, same wrapper.
        good = run_wrapped(f"{sys.executable} -m pytest good_test.py -q", scratch)
        log(
            f"GOOD_STATE(real-pass) exit={good['exit_code']} "
            f"collected={good['collected_count']}"
        )

        # The control fires (distinguishes the states) exactly when both
        # exit codes are identical (0) but the collected counts differ --
        # that is the scenario an exit-code-only detector cannot catch.
        exit_codes_identical = bad["exit_code"] == good["exit_code"] == 0
        collected_counts_differ = (
            bad["collected_count"] == 0 and good["collected_count"] > 0
        )
        both_states = exit_codes_identical and collected_counts_differ
        log(
            f"BOTH_STATES ok={both_states} (identical exit codes, differing collected counts)"
        )

        recheck = recheck_probe1_independently()
        log(
            f"PROBE1_RECHECK ok={recheck['ok']} "
            f"declared={recheck.get('declared_with_nonzero_collected_count')} "
            f"recounted={recheck.get('independently_recounted_nonzero')} "
            f"agree={recheck.get('agree_with_probe1_summary')}"
        )

        control = {
            "id": "AUD0042-C1",
            "kind": "mutation",
            "description": (
                "A scratch pytest run that collects zero tests but is wrapped "
                "in `|| true` exits 0 identically to a real pass; only the "
                "collected count distinguishes the harness-failure-misreported "
                "-as-pass state from the genuine-pass state."
            ),
            "fired_on_bad_state": bad["collected_count"] == 0,
            "silent_on_good_state": good["collected_count"] > 0,
            "ok": both_states,
            "bad_run": bad,
            "good_run": good,
        }

        ok = both_states and bool(recheck.get("ok"))

        result = {
            "ok": ok,
            "unit": "AUD-0042",
            "probe": 2,
            "measured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "both_states": both_states,
            "control": control,
            "probe1_independent_recheck": recheck,
            "live_tree_mutated": False,
            "worktree_mode": "TemporaryDirectory",
        }
        OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

        lines.append(f"both_states={both_states}")
        lines.append(f"control_ok={control['ok']}")
        lines.append(f"probe1_recheck_ok={recheck.get('ok')}")
        lines.append("SUCCESS:AUD-0042-probe2" if ok else "FAILED:AUD-0042-probe2")
        RAW.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
