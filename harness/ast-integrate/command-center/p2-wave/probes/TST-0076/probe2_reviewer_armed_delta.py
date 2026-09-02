#!/usr/bin/env python3
"""Probe 2: independent recount of the defaults-deletion CI vs armed delta.

Does not call battery.table_is_sound or battery._classify. Rebuilds an isolated
catalog, deletes defaults, and invokes validate.py twice (bare vs
--require-complete). Also re-runs one FIRED control (REACH-1) and the clean
baseline, then checks the schema rejects garbage.
"""
from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import battery as B  # noqa: E402
import catalog as cat  # noqa: E402

ART = REPO / "command-center" / "receipts" / "TST-0076.json"
SCHEMA = REPO / "command-center" / "schema" / "detector-control.schema.json"
VALIDATE = REPO / "tools" / "command-center" / "validate.py"
OUT = HERE / "probe2-reviewer-armed-delta.raw.json"
SENTINEL = "SUCCESS:TST-0076"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0076-probe2 {msg}")
    return 1


def invoke(catalog_path: Path, graph_path: Path, extra: list[str]) -> tuple[int, str]:
    cmd = [
        sys.executable,
        str(VALIDATE),
        "--catalog",
        str(catalog_path),
        "--graph",
        str(graph_path),
        *extra,
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, out


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in ART.read_text(encoding="utf-8"):
        return fail("sentinel absent")
    if doc.get("kind") != "detector-control":
        return fail("kind is not detector-control")

    import tempfile

    live = cat.load()
    with tempfile.TemporaryDirectory(prefix="tst0076-rev-") as raw:
        tmp = Path(raw)
        base = B._prepare_base(tmp, live)
        c0, g0 = B._write_tree(tmp, base)
        rc_clean, out_clean = invoke(c0, g0, [])
        if rc_clean != 0 or "SUCCESS:cc-validate" not in out_clean:
            return fail(f"reviewer clean baseline rc={rc_clean}")

        no_def = copy.deepcopy(base)
        no_def.pop("defaults", None)
        c1, g1 = B._write_tree(tmp, no_def)
        rc_ci, out_ci = invoke(c1, g1, [])
        rc_armed, out_armed = invoke(c1, g1, [B.ARMING_FLAG])

        dang = copy.deepcopy(base)
        for item in dang["items"]:
            if item.get("id") == "R-M01":
                item["dependencies"] = ["R-DOES-NOT-EXIST"]
                break
        c2, g2 = B._write_tree(tmp, dang)
        rc_r1, out_r1 = invoke(c2, g2, [])

    vfields_ci = rc_ci == 0 and "V-FIELDS" not in out_ci
    vfields_armed = rc_armed != 0 and "V-FIELDS" in out_armed
    reach1 = rc_r1 != 0 and "REACH-1" in out_r1
    if not vfields_ci:
        # Armed-in-CI is also a legal later state (IMP-0437). Record, don't invent.
        if rc_ci != 0 and "V-FIELDS" in out_ci:
            vfields_status = "FIRED"
        else:
            return fail(
                f"defaults-delete CI unexpected rc={rc_ci} V-FIELDS_in_out="
                f"{'V-FIELDS' in out_ci}"
            )
    else:
        vfields_status = "DISARMED"
    if vfields_status == "DISARMED" and not vfields_armed:
        return fail(f"defaults-delete armed rc={rc_armed} did not emit V-FIELDS")
    if not reach1:
        return fail(f"REACH-1 control rc={rc_r1}")
    if rc_clean != 0:
        return fail("clean baseline not silent")

    art_dd = None
    for row in doc.get("mutation_table") or []:
        if isinstance(row, dict) and row.get("id") == "V-FIELDS-defaults-block-deleted":
            art_dd = row
            break
    if not art_dd:
        return fail("artifact missing defaults-deleted row")
    if art_dd.get("ci_exit") != rc_ci:
        return fail(f"artifact ci_exit={art_dd.get('ci_exit')} reviewer={rc_ci}")
    if art_dd.get("armed_exit") != rc_armed:
        return fail(f"artifact armed_exit={art_dd.get('armed_exit')} reviewer={rc_armed}")
    if art_dd.get("status") != vfields_status:
        return fail(
            f"artifact status={art_dd.get('status')} reviewer={vfields_status}"
        )

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    schema_errors = [e.message for e in validator.iter_errors(doc)]
    if schema_errors:
        return fail(f"artifact fails schema: {schema_errors[:3]}")
    garbage = [
        {},
        {"unit_id": "TST-0076", "state": "SUCCESS"},
        {
            "unit_id": "TST-0076",
            "state": "SUCCESS",
            "sentinel": "SUCCESS:TST-0076",
            "kind": "not-detector-control",
            "question": "x" * 50,
            "detectors": [
                {
                    "id": "a",
                    "fired_on_bad_state": True,
                    "silent_on_good_state": True,
                    "status": "FIRED",
                },
                {
                    "id": "b",
                    "fired_on_bad_state": True,
                    "silent_on_good_state": True,
                    "status": "FIRED",
                },
            ],
            "tests": [
                {"id": "t1", "result": "PASS"},
                {"id": "t2", "result": "PASS"},
            ],
            "negative_controls": [
                {
                    "id": "n1",
                    "fired_on_bad_state": False,
                    "silent_on_good_state": True,
                }
            ],
            "reviewer": {
                "reviewer_id": "x",
                "verdict": "PASS",
                "independent": True,
                "control_executed": True,
            },
            "artifacts": [
                {"path": "command-center/receipts/TST-0076.json", "exists": True}
            ],
            "evidence": [
                {"claim": "enough-text", "verdict": "CONFIRMED", "anchor": "a:1"},
                {"claim": "enough-txt", "verdict": "CONFIRMED", "anchor": "b:2"},
            ],
        },
    ]
    for g in garbage:
        if not list(validator.iter_errors(g)):
            return fail(f"schema accepted garbage {g}")

    reviewer = doc.get("reviewer") or {}
    if reviewer.get("verdict") != "PASS" or reviewer.get("independent") is not True:
        return fail("artifact reviewer not PASS/independent")
    if reviewer.get("control_executed") is not True:
        return fail("artifact reviewer control_executed is not true")

    raw = {
        "probe": "probe2-reviewer-armed-delta",
        "unit_id": "TST-0076",
        "clean_exit": rc_clean,
        "defaults_ci_exit": rc_ci,
        "defaults_armed_exit": rc_armed,
        "defaults_status": vfields_status,
        "reach1_exit": rc_r1,
        "reach1_fired": reach1,
        "schema_ok": True,
        "schema_rejects_garbage": True,
        "agree_with_artifact": True,
        "pass": True,
    }
    OUT.write_text(json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "defaults_status": vfields_status,
                "ci_exit": rc_ci,
                "armed_exit": rc_armed,
                "reach1_fired": reach1,
                "clean_exit": rc_clean,
                "agree": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:TST-0076-probe2 independent armed-delta recount")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
