#!/usr/bin/env python3
"""Probe 2: two-project isolation; a hardcoded other-project command is dead.

Independent of probe 1: reads each project's gate script and thresholds file
from disk, re-runs the resolver, and transplants alpha's command into beta's
cwd. Does not reuse probe 1's gated/absent assertions as the pass criterion.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import resolver as R  # noqa: E402
import scenario as S  # noqa: E402

ART = REPO / "command-center/receipts/TST-0338.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0338-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:TST-0338" not in json.dumps(doc):
        return fail("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")

    alpha_gate = S.ALPHA / "gate_alpha.py"
    beta_gate = S.BETA / "gate_beta.py"
    alpha_thr = S.ALPHA / ".coverage-thresholds.json"
    beta_thr = S.BETA / ".coverage-thresholds.json"
    if not alpha_gate.is_file() or not beta_gate.is_file():
        return fail("gate scripts missing")
    if S.MARKER_ALPHA not in alpha_gate.read_text(encoding="utf-8"):
        return fail("alpha gate script lost its marker")
    if S.MARKER_BETA not in beta_gate.read_text(encoding="utf-8"):
        return fail("beta gate script lost its marker")
    if S.MARKER_ALPHA in beta_gate.read_text(encoding="utf-8"):
        return fail("beta gate script contains alpha marker")
    a_cmd = json.loads(alpha_thr.read_text(encoding="utf-8"))["enforcement"]["command"]
    b_cmd = json.loads(beta_thr.read_text(encoding="utf-8"))["enforcement"]["command"]
    if a_cmd == b_cmd:
        return fail("fixture commands are identical; control cannot discriminate")

    live = S.fixture_rows()
    isol = S.dead_command_control(live)
    if not isol["commands_differ"]:
        return fail("resolver returned the same command for both projects")
    if live["alpha"].get("declared_command") != a_cmd:
        return fail("resolver did not read alpha's file")
    if live["beta"].get("declared_command") != b_cmd:
        return fail("resolver did not read beta's file")
    if not isol["alpha_marker_in_alpha"] or not isol["beta_marker_in_beta"]:
        return fail("markers missing from the project that owns them")
    if not isol["alpha_marker_not_in_beta"] or not isol["beta_marker_not_in_alpha"]:
        return fail("marker leaked across projects")
    if not isol["transplant_alpha_command_into_beta"]["dead"]:
        return fail("alpha command still succeeded in beta cwd (not dead)")
    if isol["alpha_exit_code"] == isol["beta_exit_code"]:
        return fail("exit codes did not discriminate the two projects")
    if R.DEFAULT_ENFORCEMENT_COMMAND is not None:
        return fail("resolver carries a hardcoded default command")

    rec = (doc.get("tests") or {}).get("wrong_project_control") or {}
    if rec.get("pass") is not True:
        return fail("artifact wrong-project test not pass")
    if rec.get("alpha_command") != a_cmd or rec.get("beta_command") != b_cmd:
        return fail("artifact commands != on-disk files")
    if rec.get("transplant_dead") is not True:
        return fail("artifact did not record transplant dead")

    rec_iso = (doc.get("fixture_proof") or {}).get("isolation") or {}
    if rec_iso.get("alpha_command") != live["alpha"].get("declared_command"):
        return fail("artifact isolation alpha_command != live")
    if rec_iso.get("beta_command") != live["beta"].get("declared_command"):
        return fail("artifact isolation beta_command != live")

    src = doc.get("source_probe") or {}
    ver = doc.get("verifier_probe") or {}
    if not src or not ver:
        return fail("empty source_probe or verifier_probe")
    if json.dumps(src, sort_keys=True) == json.dumps(ver, sort_keys=True):
        return fail("source_probe identical to verifier_probe")

    out = {
        "probe": "probe2-wrong-project",
        "unit_id": "TST-0338",
        "commands_differ": True,
        "transplant_dead": True,
        "alpha_command": a_cmd,
        "beta_command": b_cmd,
        "alpha_exit": isol["alpha_exit_code"],
        "beta_exit": isol["beta_exit_code"],
        "default_command": R.DEFAULT_ENFORCEMENT_COMMAND,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"commands_differ={isol['commands_differ']} "
        f"transplant_dead={isol['transplant_alpha_command_into_beta']['dead']}"
    )
    print("SUCCESS:TST-0338-probe2 two-project isolation and dead-command control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
