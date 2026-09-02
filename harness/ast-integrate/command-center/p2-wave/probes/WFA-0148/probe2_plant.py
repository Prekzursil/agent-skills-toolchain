#!/usr/bin/env python3
"""Probe 2: six forcing plants must be emitted; mutant proves discrimination."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import classifier as C  # noqa: E402
import plants as P  # noqa: E402
import reviewer as V  # noqa: E402
import schema_check as S  # noqa: E402

OUT = (
    "command-center/foundry/"
    "WFA-0148-classifier-expressiveness-audit-six-vocabulary-value.json"
)
SCHEMA = "command-center/schema/foundry-artifact.schema.json"
GARBAGE = (
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {},
)


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0148-probe2 {msg}")
    return 1


def main() -> int:
    rows = P.run_plants()
    spots = P.blind_spots(rows)
    mutant = P.run_plants(skip_values={"REJECT"})
    mutant_reject = next(r for r in mutant if r["value"] == "REJECT")
    review = V.replay_plants()
    for row in rows:
        print(
            f"plant {row['value']} emitted={row['emitted']} "
            f"reachable={row['reachable']} rule={row['rule_id']}"
        )
        rec = P.plant_for(row["value"])
        if "classification" in rec:
            return fail("plant pre-set classification")
        if rec["id"] != row["candidate_id"]:
            return fail("plant id drift")
    print(f"blind_spot_values={spots}")
    print(
        f"mutant_skip=REJECT emitted={mutant_reject['emitted']} "
        f"reachable={mutant_reject['reachable']}"
    )
    if spots:
        return fail(f"classifier cannot emit {spots}")
    if mutant_reject["reachable"] or mutant_reject["emitted"] == "REJECT":
        return fail("mutant still emits REJECT; plant test does not discriminate")
    if len(rows) != 6:
        return fail(f"expected 6 plants, got {len(rows)}")
    if {r["value"] for r in rows} != set(C.UNUSED_DECLARED):
        return fail("plant values != unused vocabulary")
    if not all(r["reachable"] for r in review):
        return fail("reviewer plant replay missed a value")
    adopt = C.classify(
        {
            "id": "neg-adopt",
            "does": "plain compatible workflow",
            "license": "MIT",
            "runtime": "ast-integrate",
            "control_plane": "ast-integrate",
        }
    )
    print(f"negative_control_adopt={adopt['classification']}")
    if adopt["classification"] != "ADOPT-AS-IS":
        return fail("negative control did not emit ADOPT-AS-IS")
    art = REPO / OUT
    if not art.is_file() or art.stat().st_size <= 0:
        return fail("artifact missing")
    text = art.read_text(encoding="utf-8")
    if "SUCCESS:WFA-0148" not in text:
        return fail("sentinel-absent")
    parsed = json.loads(text)
    if str(parsed.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared:{parsed.get('state')}")
    pay = S.payload_of(parsed)
    recorded = pay.get("plants") or parsed.get("plants") or []
    if len(recorded) != 6:
        return fail("artifact plants != 6")
    by_value = {r["value"]: r for r in recorded if isinstance(r, dict)}
    for live in rows:
        rec_row = by_value.get(live["value"]) or {}
        if rec_row.get("emitted") != live["emitted"]:
            return fail("artifact plant emitted mismatch")
        if rec_row.get("reachable") is not True:
            return fail("artifact plant not reachable")
    if pay.get("blind_spot_values") != []:
        return fail("artifact claims a blind spot")
    try:
        S.assert_rejects_garbage()
        errs = S.error_list(parsed)
    except Exception as exc:
        return fail(f"schema:{type(exc).__name__}:{exc}")
    if errs:
        print("FAILED:WFA-0148-probe2 schema errors")
        for line in errs[:8]:
            print(" ", line)
        return 1
    print("schema_valid=True schema_rejects_garbage=True")
    print("SUCCESS:WFA-0148-probe2 six-plants mutant-control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
