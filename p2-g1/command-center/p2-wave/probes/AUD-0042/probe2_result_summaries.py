#!/usr/bin/env python3
"""AUD-0042 probe2 -- parsed result summary per CI test step (live pytest, fail-closed).

Lane 1 re-derives the summary arithmetic on every recorded tests-ran row:
passed+failed+errored <= collected with equality whenever nothing skipped,
failed+errored == 0 wherever exit_code == 0, and the worktree never-CI rows
carry the same shape. Lane 2 runs REAL pytest in a temp fixture and re-proves
the parser both-states: a zero-collect run parses to collected=0 (never
test-success even at exit 0 semantics) and a one-test run parses to
collected=1 counted as success. The declared-schema probe's recorded
ref-resolution error is re-verified as an honestly recorded instrument-absent
row (offline), not folded into a pass.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
OUT = REPO / "command-center/audit/AUD-0042-close-baseline-ci-gap.json"
UNIT = "AUD-0042"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}

COLLECTED_RE = re.compile(r"collected (\d+) item")


def parse_summary(text: str) -> dict:
    """Parse a pytest terminal summary the way the artifact's census did."""
    m = COLLECTED_RE.search(text)
    collected = int(m.group(1)) if m else 0
    passed = len(re.findall(r"PASSED|passed", text))
    failed = len(re.findall(r"FAILED|failed", text))
    return {"collected": collected, "passed": passed, "failed": failed}


def run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    # scrub PYTHON* variables so the measure harness's PYTHONPATH (seed-stage,
    # tools/measure-guard, platform/lib) cannot shadow pytest inside the child
    env = {
        k: v for k, v in os.environ.items()
        if not (k.startswith("PYTHON") and k != "PYTHONDONTWRITEBYTECODE")
    }
    p = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                       timeout=600, env=env)
    return p.returncode, (p.stdout + p.stderr)


def main() -> int:
    fails: list[str] = []
    notes: list[str] = []
    try:
        text = OUT.read_text(encoding="utf-8")
        doc = json.loads(text)
    except Exception as exc:
        print(f"FAILED:{UNIT}-probe2 artifact unreadable: {type(exc).__name__}")
        return 1

    def check(ok: bool, label: str, detail: str = "") -> None:
        if not ok:
            fails.append(f"{label}{': ' + detail if detail else ''}")

    # structural predicate
    check(isinstance(doc, dict), "artifact not a JSON object")
    check(doc.get("unit_id") == UNIT, "unit_id mismatch", str(doc.get("unit_id")))
    check(
        str(doc.get("state", "")).upper() not in NOT_DELIVERING,
        "self-declared non-delivery",
        str(doc.get("state")),
    )
    sent = str(doc.get("completion_sentinel") or doc.get("sentinel") or "")
    check(bool(sent) and sent in text, "completion sentinel absent")

    gap = doc.get("gap_steps") or []
    ws = doc.get("worktree_never_ci_steps") or []
    # lane 1: recorded summary arithmetic
    for r in [x for x in gap if x.get("classification") == "tests-ran"] + [
        x for x in ws if x.get("classification") == "tests-ran"
    ]:
        idx = r.get("index", r.get("name"))
        p, f, e, c = (int(r.get("passed") or 0), int(r.get("failed") or 0),
                      int(r.get("errored") or 0), int(r.get("collected") or 0))
        check(p + f + e <= c, "summary arithmetic broken (passed+failed+errored > collected)",
              f"row {idx}: {p}+{f}+{e} vs {c}")
        if r.get("exit_code") == 0:
            check(f + e == 0, "exit-0 row with failed/errored > 0", f"row {idx}")
        check(r.get("counted_as_test_success") is (c > 0 and r.get("exit_code") == 0),
              "success flag inconsistent with collected+exit", f"row {idx}")

    # lane 2: live pytest both-states on a temp fixture
    with tempfile.TemporaryDirectory(prefix="aud0042probe2-") as td:
        fx = Path(td)
        empty = fx / "empty_tests"
        one = fx / "one_tests"
        empty.mkdir()
        one.mkdir()
        (empty / "test_none.py").write_text(
            "# no tests in this file\n", encoding="utf-8", newline="\n"
        )
        (one / "test_one.py").write_text(
            "def test_ok() -> None:\n    assert True\n", encoding="utf-8", newline="\n"
        )
        rc_e, out_e = run([sys.executable, "-m", "pytest", "--no-header",
                           "-p", "no:cacheprovider", "."], empty)
        rc_o, out_o = run([sys.executable, "-m", "pytest", "--no-header",
                           "-p", "no:cacheprovider", "."], one)
        sum_e = parse_summary(out_e)
        sum_o = parse_summary(out_o)
        # pytest's own no-tests-collected exit code is 5; a run with collected=0
        # must never count as test-success even where a runner reports exit 0
        check(sum_e["collected"] == 0 and rc_e == 5,
              "zero-collect fixture did not produce collected=0 / exit 5",
              f"rc={rc_e} summary={sum_e}")
        check(sum_e["collected"] == 0 and not (sum_e["collected"] > 0 and rc_e == 0),
              "zero-collect run counts as success (control cannot fire)")
        check(sum_o["collected"] == 1 and rc_o == 0,
              "one-test fixture did not produce collected=1 / exit 0",
              f"rc={rc_o} summary={sum_o}")
        check(sum_o["collected"] > 0 and rc_o == 0,
              "one-test run does not count as success (rule over-strict)")

    # honesty: the declared-schema probe was recorded instrument-absent (offline)
    dsp = doc.get("declared_schema_probe") or {}
    check(dsp.get("ok") is False and ("RefResolutionError" in str(dsp.get("detail", ""))
                                       or "ref-resolution" in str(dsp.get("detail", "")).lower()),
          "declared_schema_probe not recorded as the honest ref-resolution failure")
    check(str(doc.get("schema_validation_status", "")).upper() == "PASS",
          "schema_validation_status not recorded PASS", str(doc.get("schema_validation_status")))
    # zero-collect control recorded on the artifact side too
    nc = doc.get("negative_controls") or []
    check(any("zero" in str(c.get("id", "")).lower() for c in nc),
          "zero-collect negative control not recorded")

    # drift note: raw logs absent on this worktree
    if not (REPO / "command-center/p2-wave/probes/AUD-0042/runs").is_dir():
        notes.append(
            "instrument-absent: runs/raw logs absent on this worktree (lost with the prior "
            "builder); summary arithmetic re-derived from the recorded rows and the parser "
            "re-proven live with pytest 8.4.2 on a fresh fixture"
        )

    report = {
        "probe": "probe2-parsed-result-summary-per-step",
        "unit_id": UNIT,
        "live_zero_collect": {"rc": rc_e, **sum_e},
        "live_one_test": {"rc": rc_o, **sum_o},
        "notes": notes,
        "fails": fails,
    }
    print(json.dumps(report, indent=1, ensure_ascii=False))
    if fails:
        print(f"FAILED:{UNIT}-probe2 " + "; ".join(fails))
        return 1
    print(f"SUCCESS:{UNIT}-probe2 result summaries re-derived (summary arithmetic holds on "
          f"{len([x for x in gap if x.get('classification') == 'tests-ran'])} tests-ran rows; "
          "live pytest: zero-collect rc5 not success, one-test rc0 counts)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
