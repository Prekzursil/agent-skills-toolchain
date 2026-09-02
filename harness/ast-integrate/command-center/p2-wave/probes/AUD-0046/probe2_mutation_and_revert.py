#!/usr/bin/env python3
"""Probe 2: independent mutation + revert recount.

Does not trust probe 1's table. Re-runs every planted mutation and the revert
arm, then checks the artifact. This is the mechanical stand-in for the catalog's
cross-vendor reviewer who re-runs ONLY the second probe.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import sweep as S  # noqa: E402

ART = REPO / "command-center" / "audit" / "AUD-0046-gate-detector-control-sweep.json"
SCHEMA = REPO / "command-center" / "schema" / "audit-detector-control.schema.json"
OUT = HERE / "probe2-mutation-and-revert.raw.json"
SENTINEL = "SUCCESS:AUD-0046"


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0046-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in text:
        return fail("sentinel absent")
    if doc.get("kind") != "detector-control":
        return fail("kind is not detector-control")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft7Validator(schema).validate(doc)

    report = S.run_report()
    if not report["revert_ok"]:
        return fail("revert did not restore green")
    fired = [m for m in report["measured"] if m["status"] == "FIRED"]
    if len(fired) < 2:
        return fail(f"too few FIRED: {len(fired)}")
    for row in fired:
        if row.get("bad_exit") == 0:
            return fail(f"{row['id']} mutation stayed green")
        if row.get("reverted_exit") != 0:
            return fail(f"{row['id']} revert did not return to 0")
        if row.get("good_exit") != 0:
            return fail(f"{row['id']} good state not 0")

    vfields = next(m for m in report["measured"] if m["id"] == "cc-validate-V-FIELDS")
    if vfields["status"] != "DISARMED":
        return fail(f"V-FIELDS status={vfields['status']} want DISARMED")
    if vfields.get("bad_exit") != 0:
        return fail("V-FIELDS under CI argv was not silent")
    if not vfields.get("armed_exit"):
        return fail("V-FIELDS did not fire with --require-complete")

    always = next(m for m in report["measured"] if m["id"] == "always-zero-ignores-tree")
    if always["status"] != "SILENT-IN-BOTH" or always.get("bad_exit") != 0:
        return fail("negative control did not stay silent on the planted defect")

    art_rows = {
        r.get("id"): r
        for r in (doc.get("detectors") or [])
        if isinstance(r, dict)
    }
    for row in report["measured"]:
        art = art_rows.get(row["id"]) or {}
        if art.get("status") != row["status"]:
            return fail(
                f"{row['id']} artifact status={art.get('status')} live={row['status']}"
            )
        if art.get("bad_exit") != row.get("bad_exit"):
            return fail(f"{row['id']} bad_exit mismatch")
        if art.get("reverted_exit") != row.get("reverted_exit"):
            return fail(f"{row['id']} reverted_exit mismatch")

    tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    for tid in (
        "test_unmodified_scratch_exits_zero",
        "test_planted_mutation_exits_nonzero_then_revert_zero",
    ):
        if (tests.get(tid) or {}).get("result") != "PASS":
            return fail(f"artifact test {tid} is not PASS")

    raw = {
        "probe": "probe2-mutation-and-revert",
        "unit_id": "AUD-0046",
        "agree": True,
        "n_fired": len(fired),
        "vfields_status": vfields["status"],
        "vfields_ci_exit": vfields.get("bad_exit"),
        "vfields_armed_exit": vfields.get("armed_exit"),
        "negative_control_bad_exit": always.get("bad_exit"),
        "revert_ok": True,
        "pass": True,
    }
    OUT.write_text(json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "agree": True,
                "fired": len(fired),
                "vfields": vfields["status"],
                "ci_exit": vfields.get("bad_exit"),
                "armed_exit": vfields.get("armed_exit"),
                "revert_ok": True,
            }
        )
    )
    print("SUCCESS:AUD-0046-probe2 independent mutation+revert recount")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
