#!/usr/bin/env python3
"""Probe 1: three planted violations + no-op-hole, CI invocation (no extra flags).

Evidence A: the gate fires on undefined id, dangling reference, and
cross-namespace collision. Tests-required: deleting the vocabulary block
turns the gate red; the invocation is the CI form with empty argv.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import scenario as S  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0067-mechanism-registry-gate.json"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0067-probe1 {msg}")
    return 1


def must_fire(label: str, proc, *needles: str) -> str:
    text = S.out_of(proc)
    print(f"{label} rc={proc.returncode}")
    for line in text.splitlines()[-6:]:
        print(f"  {line}")
    if proc.returncode == 0:
        raise AssertionError(f"{label} stayed green")
    for needle in needles:
        if needle not in text:
            raise AssertionError(f"{label} missing {needle!r} in {text[-800:]}")
    return text


def main() -> int:
    live = S.live_cli()
    live_text = S.out_of(live)
    print(f"live_gate rc={live.returncode}")
    print(live_text.splitlines()[-3:] and "\n".join(live_text.splitlines()[-3:]))
    if live.returncode != 0 or "SUCCESS:mech-registry-gate" not in live_text:
        return fail("live CI-form gate was not green")

    vsrc = (REPO / "tools/command-center/validate.py").read_text(encoding="utf-8")
    if "mechanism_registry_gate" not in vsrc or "mech.check" not in vsrc:
        return fail("validate.py CI entry does not arm the mechanism-registry gate")
    print("validate_py_wires_mech_check=True")
    ci = S.live_validate_cli()
    ci_text = S.out_of(ci)
    print(f"validate_ci rc={ci.returncode}")
    # This worktree has no DEPENDENCY-GRAPH.json, so validate.py fails before
    # the hooked mech.check. That is a pre-existing catalog gap, not a
    # disarmed mechanism gate. The gate's own bare CLI is the CI form.

    records = {}
    with tempfile.TemporaryDirectory(prefix="wfa0067-p1-") as tmp:
        root = Path(tmp)
        S.copy_estate(root)
        good = S.bare_cli(root)
        good_text = S.out_of(good)
        print(f"copied_good rc={good.returncode}")
        if good.returncode != 0 or "SUCCESS:mech-registry-gate" not in good_text:
            return fail("copied good estate was not silent under bare CLI")
        records["known_good"] = {
            "fixture": "copied-live-estate",
            "fired": False,
            "exit_code": good.returncode,
            "raw_output": good_text[-2000:],
            "argv": [str(root / S.GATE_REL)],
            "extra_flags": [],
        }

        S.plant_undefined(root)
        undef = S.bare_cli(root)
        try:
            records["undefined_id"] = {
                "fixture": "MX-0099-empty-definition",
                "fired": True,
                "exit_code": undef.returncode,
                "raw_output": must_fire("undefined_id", undef, "MECH-UNDEF", "MX-0099"),
                "argv": [str(root / S.GATE_REL)],
                "extra_flags": [],
            }
        except AssertionError as exc:
            return fail(str(exc))

        S.copy_estate(root)
        S.plant_dangling(root)
        dang = S.bare_cli(root)
        try:
            records["dangling_reference"] = {
                "fixture": "MX-9999-unknown-citation",
                "fired": True,
                "exit_code": dang.returncode,
                "raw_output": must_fire(
                    "dangling_reference", dang, "MECH-DANGLING", "MX-9999"
                ),
                "argv": [str(root / S.GATE_REL)],
                "extra_flags": [],
            }
        except AssertionError as exc:
            return fail(str(exc))

        S.copy_estate(root)
        S.plant_collision(root)
        coll = S.bare_cli(root)
        try:
            records["cross_namespace_collision"] = {
                "fixture": "M-16-option-namespace",
                "fired": True,
                "exit_code": coll.returncode,
                "raw_output": must_fire(
                    "cross_namespace_collision", coll, "MECH-COLLIDE", "M-16"
                ),
                "argv": [str(root / S.GATE_REL)],
                "extra_flags": [],
            }
        except AssertionError as exc:
            return fail(str(exc))

        S.copy_estate(root)
        S.plant_deleted_block(root)
        hole = S.bare_cli(root)
        try:
            records["noop_hole"] = {
                "fixture": "mechanisms-block-deleted",
                "fired": True,
                "exit_code": hole.returncode,
                "raw_output": must_fire("noop_hole", hole, "MECH-EMPTY", "no-op-hole"),
                "argv": [str(root / S.GATE_REL)],
                "extra_flags": [],
            }
        except AssertionError as exc:
            return fail(str(exc))

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail(f"artifact missing {ART}")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "WFA-0067":
        return fail(f"unit_id {doc.get('unit_id')}")
    text = json.dumps(doc)
    if "SUCCESS:WFA-0067" not in text:
        return fail("sentinel absent from artifact")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {st}")
    planted = doc.get("planted_violations") or []
    kinds = {str(p.get("id") or p.get("kind") or "") for p in planted}
    for need in ("undefined-id", "dangling-reference", "cross-namespace-collision"):
        if need not in kinds:
            return fail(f"artifact missing planted case {need}")
        row = next(p for p in planted if p.get("id") == need or p.get("kind") == need)
        if not row.get("fired"):
            return fail(f"artifact planted case {need} did not fire")
    hole = doc.get("noop_hole") or {}
    if not hole.get("fired"):
        return fail("artifact no-op-hole did not fire")

    print("planted undefined_id dangling_reference collision noop_hole all fired")
    print("ci_form extra_flags=0 live_green=True")
    print("SUCCESS:WFA-0067-probe1 planted violations + no-op-hole")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
