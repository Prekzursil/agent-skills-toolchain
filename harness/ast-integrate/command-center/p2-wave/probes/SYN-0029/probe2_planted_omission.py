#!/usr/bin/env python3
"""Probe 2: planted omission — delete one requirement from the report.

Independent of probe 1: does not re-run the double-label or vocabulary arms.
A complete report must be unlabelled=0; dropping REQ-FIX-R3 must surface it
as DISAPPEARED. Then recomputes the live unlabelled count from sources.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import closure as C  # noqa: E402
import controls as T  # noqa: E402
import register as R  # noqa: E402
import report as P  # noqa: E402
import schema_local as SL  # noqa: E402

ART = REPO / "command-center/receipts/SYN-0029.json"


def fail(msg: str) -> int:
    print(f"FAILED:SYN-0029-probe2 {msg}")
    return 1


def main() -> int:
    planted = T.test_planted_omission()
    print(
        json.dumps(
            {
                "complete_unlabelled": planted["complete_unlabelled"],
                "planted_unlabelled": planted["planted_unlabelled"],
                "planted_omission_fired": planted["planted_omission_fired"],
                "dropped_label": planted["dropped_label"],
                "file_omit_label": planted["file_omit_label"],
            },
            sort_keys=True,
        )
    )
    if not planted["pass"]:
        return fail("planted omission did not fire")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    raw = json.loads(text)
    if "SUCCESS:SYN-0029" not in text:
        return fail("sentinel-absent")
    if str(raw.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {raw.get('state')}")
    errs = SL.error_list(raw)
    if errs:
        return fail(f"schema {errs[0]}")
    doc = SL.payload(raw)

    size = doc.get("register_size")
    unlabelled = doc.get("unlabelled_count")
    if not isinstance(size, int) or size < 1:
        return fail("register-size-unstated")
    if not isinstance(unlabelled, int):
        return fail("unlabelled_count unstated")
    if unlabelled == 0 and size < 1:
        return fail("zero-unlabelled-with-no-register-size")

    live_reg = R.load_register()
    live_rep = P.load_report()
    recomputed = C.close(
        live_reg["records"],
        live_rep["items"],
        {"path": live_rep["path"], "present": live_rep["present"]},
    )
    if recomputed["register_size"] != size:
        return fail("live register_size drifted")
    if recomputed["unlabelled_count"] != unlabelled:
        return fail("live unlabelled_count drifted")

    disappeared_ids = [
        r["requirement_id"] for r in recomputed["rows"] if r["label"] == C.DISAPPEARED
    ]
    art_disappeared = [
        r["requirement_id"] for r in (doc.get("rows") or []) if r.get("label") == C.DISAPPEARED
    ]
    if disappeared_ids != art_disappeared:
        return fail("live disappeared set drifted")

    recorded = {t.get("id"): t.get("result") for t in (doc.get("tests") or [])}
    if recorded.get("planted_omission") != "PASS":
        return fail("artifact planted_omission not PASS")

    controls = {c.get("id"): c for c in (doc.get("controls") or [])}
    plant = controls.get("planted-omission-REQ-FIX-R3")
    if not plant or plant.get("verdict") != "fired":
        return fail("artifact omission control not fired")

    print(
        f"planted_fired=True complete_unlabelled=0 live_unlabelled={unlabelled} "
        f"register_size={size} disappeared={len(disappeared_ids)}"
    )
    print("SUCCESS:SYN-0029-probe2 planted omission reported unlabelled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
