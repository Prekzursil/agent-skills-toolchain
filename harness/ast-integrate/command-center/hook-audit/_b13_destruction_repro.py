"""Prove, by EXECUTION, that a failing probe run no longer destroys committed evidence.

WHAT THIS MEASURED BEFORE THE FIX (round 5, recorded here because the code that produced it
is gone). Forcing `_r4_githygiene_range.py` down its INCONCLUSIVE branch with `GIT_HYGIENE=off`
overwrote `R4-GITHYGIENE-RANGE.json` with a partial dict: SIX top-level keys disappeared
(`samples_ms`, `range_ms`, `range_pct_of_declared_90s_check_budget`,
`range_pct_of_enforced_35s_event_budget`, `h4_recorded_run_ms`, `understatement_factor_vs_h4`)
and `check_citations.py` went from 0 unbacked to 18. The evidence was restored byte-exact.

WHAT IT ASSERTS NOW. The same forced failure must leave the committed file BYTE-IDENTICAL and
put its partial output in the `.INCONCLUSIVE.json` sibling instead.

This file was rewritten rather than left as the one-shot it started as. As a one-shot it would
have begun failing its own D2 control the moment the fix landed -- "the committed file now
reads INCONCLUSIVE" is only true of the broken code -- which is the self-erasing-control shape
this round repointed C1 away from. A regression that goes red when the tree gets BETTER is
worse than no regression.

CONTROLS -- all must hold or no verdict is published:
  D1 baseline clean   -- `unbacked` is 0 before the run; otherwise "unchanged" means nothing.
  D2 fail path taken  -- the probe exits non-zero AND the INCONCLUSIVE sibling exists carrying
     verdict=INCONCLUSIVE. Without this the success branch ran and nothing was demonstrated.
     This is the control that fired on the first version of this probe and forced the rewrite.
  D3 committed file untouched -- sha256 identical across the run. THE CLAIM.
  D4 axis unmoved     -- `unbacked` still 0 afterwards.
  D5 nothing else moved -- the gate's exit code is identical before and after.

D1/D4 assert on `unbacked`, not on the gate's exit code. The first version asserted rc == 0 and
failed its own controls while the destruction it was measuring worked perfectly: the gate was
red for an unrelated reason -- BUILD-R5.md, this round's own in-progress artifact, had zero
citations and tripped the per-document floor. Binding a control to a coarser signal than the
claim makes it fail on other people's work. D5 keeps the coarse signal as a leave-no-trace check.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _evidence_io import inconclusive_path  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
EVIDENCE = HERE / "R4-GITHYGIENE-RANGE.json"
PROBE = HERE / "_r4_githygiene_range.py"
GATE = HERE / "check_citations.py"
OUT = HERE / "B13-DESTRUCTION-REPRO.json"

UNBACKED_RE = re.compile(r"(\d+)\s+citations checked,\s+(\d+)\s+unbacked")

# Measured against blob 1294fa1aaef5202a0d355bacb23c780b6ab9aade (the pre-fix probe).
HISTORICAL_PREFIX_DAMAGE = {
    "n_top_level_keys_lost": 6,
    "gate_unbacked_before": 0,
    "gate_unbacked_after_destruction": 18,
    "keys_lost": [
        "h4_recorded_run_ms",
        "range_ms",
        "range_pct_of_declared_90s_check_budget",
        "range_pct_of_enforced_35s_event_budget",
        "samples_ms",
        "understatement_factor_vs_h4",
    ],
    "measured_against_blob": "1294fa1aaef5202a0d355bacb23c780b6ab9aade",
}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def run_gate() -> dict:
    p = subprocess.run(
        [sys.executable, str(GATE)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(REPO),
    )
    m = UNBACKED_RE.search((p.stdout or "") + (p.stderr or ""))
    return {
        "rc": p.returncode,
        "checked": int(m.group(1)) if m else None,
        "unbacked": int(m.group(2)) if m else None,
    }


def main() -> int:
    out: dict = {
        "probe": "_b13_destruction_repro.py",
        "historical_prefix_damage": HISTORICAL_PREFIX_DAMAGE,
    }
    if not EVIDENCE.is_file() or not PROBE.is_file():
        print("FAILED:b13-repro subject files absent")
        return 2

    sibling = inconclusive_path(EVIDENCE)
    sibling.unlink(missing_ok=True)

    before_sha = sha(EVIDENCE)
    gate_before = run_gate()
    out["gate_before"] = gate_before
    d1 = gate_before["unbacked"] == 0

    env = dict(os.environ)
    env["GIT_HYGIENE"] = "off"  # forces BOTH arms to early-return -> no discrimination
    p = subprocess.run(
        [sys.executable, str(PROBE)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(REPO),
        env=env,
        timeout=300,
    )
    out["probe_rc"] = p.returncode

    sibling_verdict = None
    if sibling.is_file():
        try:
            sibling_verdict = json.loads(sibling.read_text(encoding="utf-8")).get(
                "verdict"
            )
        except (OSError, json.JSONDecodeError):
            sibling_verdict = "<unreadable>"
    out["inconclusive_sibling"] = sibling.name if sibling.is_file() else None
    out["inconclusive_sibling_verdict"] = sibling_verdict
    d2 = p.returncode != 0 and sibling_verdict == "INCONCLUSIVE"

    after_sha = sha(EVIDENCE)
    out["evidence_sha_before"] = before_sha
    out["evidence_sha_after"] = after_sha
    d3 = after_sha == before_sha
    out["committed_evidence_untouched"] = d3

    gate_after = run_gate()
    out["gate_after"] = gate_after
    d4 = gate_after["unbacked"] == 0
    d5 = gate_after["rc"] == gate_before["rc"]

    out["controls"] = {
        "D1_baseline_unbacked_zero": d1,
        "D2_fail_path_actually_taken": d2,
        "D3_committed_evidence_untouched": d3,
        "D4_unbacked_unmoved": d4,
        "D5_gate_rc_unchanged": d5,
    }
    ok = d1 and d2 and d3 and d4 and d5
    out["controls_all_pass"] = ok
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))
    if not ok:
        print(
            "FAILED:b13-repro controls did not hold -- no preservation claim may be cited"
        )
        return 2
    print(
        "SUCCESS:b13-repro forced failure left committed evidence byte-identical; "
        f"partial output went to {sibling.name}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
