#!/usr/bin/env python3
"""Probe 1: both-states control on the live checker and fusion attempts."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from jsonschema import Draft202012Validator  # noqa: E402

import checker as C  # noqa: E402
import fusion as F  # noqa: E402
from world import load_world  # noqa: E402

UNIT = "WFA-0107"
OUT = "command-center/wfa/WFA-0107-fusion-precondition-checker.json"
SCHEMA_FILE = "command-center/wfa/schema/wfa-schema-pack.json"
LOCAL_SCHEMA = (
    "command-center/p2-wave/probes/WFA-0107/regression-fixture.schema.json"
)
SENTINEL = "SUCCESS:WFA-0107"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    art_path = REPO / OUT
    if not art_path.is_file() or art_path.stat().st_size <= 0:
        return fail("artifact missing")
    text = art_path.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if not (REPO / SCHEMA_FILE).is_file():
        return fail("catalog schema pack missing")
    schema = json.loads((REPO / LOCAL_SCHEMA).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    loc_v = Draft202012Validator(schema)
    loc_errs = list(loc_v.iter_errors(doc))
    if loc_errs:
        return fail(f"local schema {loc_errs[0].message}")
    if not list(loc_v.iter_errors({"totally": "unrelated"})):
        return fail("local schema accepts garbage")

    world = load_world()
    live = C.cartesian(world)
    art_rows = {
        (r["left"], r["right"], r["operator"]): r for r in doc["verdicts"]
    }
    live_rows = {(r["left"], r["right"], r["operator"]): r for r in live}
    if set(art_rows) != set(live_rows):
        return fail("cartesian key mismatch vs artifact")
    for key, row in live_rows.items():
        other = art_rows[key]
        if row["verdict"] != other["verdict"]:
            return fail(f"verdict drift {key} live={row['verdict']} art={other['verdict']}")
        if row["verdict"] == "ILLEGAL":
            if not row["blocking_edge"] or "|" not in row["reason"]:
                return fail(f"generic reason {key} {row['reason']!r}")
            if row["blocking_edge"] not in row["reason"]:
                return fail(f"reason omits blocking_edge {key}")

    counts = C.legality_counts(live)
    if counts["LEGAL"] < 1 or counts["ILLEGAL"] < 1:
        return fail("both-states empty")
    if counts != doc["legality_counts"]:
        return fail("legality_counts drift")

    bps = F.load_blueprints()
    legal_ok = 0
    for row in live:
        if row["verdict"] != "LEGAL":
            continue
        fwd = F.attempt(row["left"], row["right"], row["operator"], bps)
        rev = F.attempt(row["right"], row["left"], row["operator"], bps)
        if not fwd["ok"] or not rev["ok"]:
            return fail(
                f"LEGAL did not succeed both directions {row} fwd={fwd['defects']} rev={rev['defects']}"
            )
        legal_ok += 1

    illegal_fail = 0
    for row in live:
        if row["verdict"] != "ILLEGAL":
            continue
        att = F.attempt(row["left"], row["right"], row["operator"], bps)
        if att["ok"]:
            return fail(f"ILLEGAL attempt succeeded (over-refusal?) {row}")
        illegal_fail += 1

    lic = C.check("wf-review-a", "wf-review-prop", "union", world)
    if lic["verdict"] != "ILLEGAL":
        return fail("licence pair not ILLEGAL")
    if not world.has_compat("wf-review-a", "wf-review-prop"):
        return fail("licence pair missing structural compat")
    if "licence" not in (lic["blocking_edge"] or ""):
        return fail(f"licence reason not a licence edge {lic}")
    if "incompatible" in lic["reason"].lower() and "licence-incompatible edge" not in lic["reason"]:
        return fail("generic incompatibility wording")
    if F.attempt("wf-review-a", "wf-review-prop", "union", bps)["ok"]:
        return fail("licence-illegal fusion attempt succeeded")

    copyleft = C.check("wf-review-a", "wf-review-gpl", "union", world)
    if copyleft["verdict"] != "LEGAL":
        return fail("copyleft+permissive over-refused")
    if not F.attempt("wf-review-a", "wf-review-gpl", "union", bps)["ok"]:
        return fail("copyleft+permissive attempt failed")

    print(
        json.dumps(
            {
                "ok": True,
                "probe": "probe1-both-states",
                "unit_id": UNIT,
                "cells": counts["cells"],
                "LEGAL": counts["LEGAL"],
                "ILLEGAL": counts["ILLEGAL"],
                "legal_attempts_both_directions": legal_ok,
                "illegal_attempts_failed": illegal_fail,
                "licence_blocks_despite_compat": True,
            },
            sort_keys=True,
        )
    )
    print(
        f"SUCCESS:{UNIT}-probe1 both-states LEGAL={counts['LEGAL']} "
        f"ILLEGAL={counts['ILLEGAL']} licence-edge-named"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
