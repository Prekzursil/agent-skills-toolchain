#!/usr/bin/env python3
"""Probe 2: both-states control + CI default-invocation enforcement.

Both directions must run: strip a passing record (gate fires) and add a valid
anchor to a failing record (gate clears). The CI form is the gate script with
no extra flags — enforcement is the default, not an opt-in.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import controls  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0073-disposition-evidence-gate.json"
GATE = "command-center/p2-wave/probes/WFA-0073/gate.py"
GOOD = "command-center/p2-wave/probes/WFA-0073/fixtures/ci-good.json"
BAD = "command-center/p2-wave/probes/WFA-0073/fixtures/ci-bad.json"
BANNED_FLAGS = ("--enforce", "--strict", "--relax", "--skip", "--allow", "--no-enforce")


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0073-probe2 {msg}")
    return 1


def run_gate(registry_rel: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    cmd = ["python3", "-B", GATE, registry_rel]
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def main() -> int:
    src = (HERE / "gate.py").read_text(encoding="utf-8")
    for flag in BANNED_FLAGS:
        if flag in src:
            return fail(f"opt-in-or-disarm-flag-present {flag}")
    if "DEFAULT_ENFORCE = True" not in src:
        return fail("DEFAULT_ENFORCE-not-true")

    ctrl = controls.both_states()
    taut = controls.anti_tautology()
    print(json.dumps({"both_states": ctrl, "anti_tautology": taut}, indent=2, sort_keys=True))
    if not ctrl["pass"]:
        return fail("both-states-did-not-discriminate")
    if not taut["pass"]:
        return fail("anti-tautology")
    if not ctrl["silent_on_good"] or not ctrl["fires_on_stripped"] or not ctrl["clears_on_repaired"]:
        return fail("direction-incomplete")

    rc_good, out_good = run_gate(GOOD)
    print(f"ci-good rc={rc_good}")
    for line in out_good.splitlines()[-6:]:
        print(f"  {line}")
    if rc_good != 0:
        return fail(f"ci-good-default-invocation-failed rc={rc_good}")

    rc_bad, out_bad = run_gate(BAD)
    print(f"ci-bad rc={rc_bad}")
    for line in out_bad.splitlines()[-6:]:
        print(f"  {line}")
    if rc_bad == 0:
        return fail("ci-bad-default-invocation-did-not-fire")
    if "FAILED:WFA-0073-gate" not in out_bad:
        return fail("ci-bad-missing-failed-line")

    if not ART.is_file():
        return fail("artifact-missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    art_ctrl = doc.get("both_states") or {}
    if art_ctrl.get("pass") is not True:
        return fail("artifact-both-states-pass")
    if art_ctrl.get("fires_on_stripped") is not True:
        return fail("artifact-strip-direction")
    if art_ctrl.get("clears_on_repaired") is not True:
        return fail("artifact-add-anchor-direction")
    ci = doc.get("ci_invocation") or {}
    if ci.get("opt_in_required_to_enforce") is not False:
        return fail("artifact-claims-opt-in")
    if "gate.py" not in str(ci.get("command") or ""):
        return fail("artifact-ci-command")
    print("SUCCESS:WFA-0073-probe2 both-states + default-invocation enforce")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
