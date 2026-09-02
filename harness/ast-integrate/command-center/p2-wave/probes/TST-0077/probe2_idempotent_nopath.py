#!/usr/bin/env python3
"""Probe 2: idempotency, no-path reported not skipped, wrong-inverse control."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from scenario import run_scenario  # noqa: E402

ART = REPO / "command-center" / "receipts" / "TST-0077.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0077-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:TST-0077" not in json.dumps(doc):
        return fail("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")

    live = run_scenario()
    t2 = live["tests"]["test_migration_is_idempotent"]
    t3 = live["tests"]["test_a_layout_with_no_migration_is_reported_not_skipped"]
    if not t2["pass"]:
        print(json.dumps(t2, indent=2, default=str)[:3000])
        return fail("idempotency")
    if not t3["pass"]:
        print(json.dumps(t3, indent=2, default=str)[:3000])
        return fail("no-path-not-reported")
    if not t3.get("skip_mutant_would_hide_unknown"):
        return fail("skip-mutant-did-not-fire")
    if not (live.get("negative_control_wrong_inverse") or {}).get("pass"):
        return fail("wrong-inverse-did-not-fail-roundtrip")
    if not (live.get("round_trip") or {}).get("pass"):
        return fail("good-inverse-roundtrip")

    rec_t3 = (doc.get("tests") or {}).get(
        "test_a_layout_with_no_migration_is_reported_not_skipped"
    ) or {}
    if rec_t3.get("pass") is not True:
        return fail("artifact t3 pass is not true")
    rec_no = doc.get("answer") or {}
    if rec_no.get("which_have_no_migration_path") != live["answer"]["which_have_no_migration_path"]:
        return fail("artifact no-path census drifted from live")

    print(
        json.dumps(
            {
                "probe": "probe2-idempotent-nopath",
                "pass": True,
                "idempotent": t2["pass"],
                "nopath": t3,
                "wrong_inverse_fired": True,
            },
            sort_keys=True,
        )
    )
    print(
        f"idempotent={t2['pass']} nopath_reported={t3['unknown_reported_not_skipped']} "
        f"hybrid={t3['hybrid_reported_ambiguous']} skip_mutant={t3['skip_mutant_would_hide_unknown']}"
    )
    print("SUCCESS:TST-0077-probe2 idempotent and no-path-reported-not-skipped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
