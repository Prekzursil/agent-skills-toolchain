#!/usr/bin/env python3
"""Probe 1: instantiate the preset, nearest-sibling differential, schema."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import OUT_REL, REPO, SCHEMA_REL, load_records, materialize_preset  # noqa: E402
from instantiate import differential, fingerprint, instantiate  # noqa: E402
from schema_util import PRESET_SCHEMA_REL, validate_envelope, validate_preset  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0105-probe1 {msg}")
    return 1


def main() -> int:
    rec = load_records()
    base = rec["base_councilspec"]
    this = materialize_preset(rec["preset_cnl0105"])
    sibling = materialize_preset(rec["sibling_gated_critique"])
    task = rec["task"]

    profile = instantiate(this, base, task)
    sib_profile = instantiate(sibling, base, task)
    required = ("roster", "protocol_schedule", "voting_method", "stopping_expression")
    for key in required:
        if not profile.get(key):
            return fail(f"profile missing {key}")
    if profile["voting_method"] == sib_profile["voting_method"] and profile[
        "protocol_schedule"
    ] == sib_profile["protocol_schedule"]:
        return fail("instantiation collapsed onto sibling")

    diff = differential(fingerprint(profile), fingerprint(sib_profile))
    if not diff["measurable"]:
        return fail(f"differential not measurable {diff}")
    if sibling["id"] != "CNL-0104.gated-critique-board":
        return fail(f"nearest sibling not named {sibling['id']}")

    this_errs, this_msgs = validate_preset(this)
    sib_errs, sib_msgs = validate_preset(sibling)
    inv_errs, _inv_msgs = validate_preset(rec["invalid_preset"])
    if this_errs != 0:
        return fail(f"this preset schema errors {this_errs} {this_msgs[:4]}")
    if sib_errs != 0:
        return fail(f"sibling schema errors {sib_errs} {sib_msgs[:4]}")
    if inv_errs <= 0:
        return fail("invalid record produced 0 errors (vacuous validator)")

    out = REPO / OUT_REL
    if not out.is_file():
        return fail(f"artifact absent {OUT_REL}")
    doc = json.loads(out.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:CNL-0105" not in json.dumps(doc):
        return fail("sentinel absent")
    inst = doc.get("instantiation") or {}
    live_profile = inst.get("profile") or {}
    if live_profile.get("voting_method") != profile["voting_method"]:
        return fail("artifact voting_method drifted from fixture re-derivation")
    if live_profile.get("protocol_schedule") != profile["protocol_schedule"]:
        return fail("artifact protocol_schedule drifted from fixture re-derivation")
    if (doc.get("differential") or {}).get("distance") != diff["distance"]:
        return fail("artifact differential distance drifted")
    env_errs, env_msgs = validate_envelope(doc)
    if env_errs != 0:
        return fail(f"artifact envelope errors {env_errs} {env_msgs[:6]}")
    art_preset_errs, art_preset_msgs = validate_preset(doc.get("preset") or {})
    if art_preset_errs != 0:
        return fail(f"artifact preset schema errors {art_preset_errs} {art_preset_msgs[:4]}")
    named = ((doc.get("sibling_map") or {}).get("nearest_sibling") or {}).get("id")
    if named != sibling["id"]:
        return fail(f"artifact nearest sibling {named}")

    print(
        json.dumps(
            {
                "roster": [r["seat"] for r in profile["roster"]],
                "protocol_schedule": profile["protocol_schedule"],
                "voting_method": profile["voting_method"],
                "stopping_expression": profile["stopping_expression"],
                "nearest_sibling": sibling["id"],
                "distance": diff["distance"],
                "differing_axes": diff["differing_axes"],
                "affected_error_count": this_errs + sib_errs,
                "invalid_error_count": inv_errs,
                "schema": SCHEMA_REL,
                "working_preset_schema": PRESET_SCHEMA_REL,
            },
            sort_keys=True,
        )
    )
    print(
        f"instantiate ok sibling={sibling['id']} distance={diff['distance']} "
        f"schema 0/{inv_errs}"
    )
    print("SUCCESS:CNL-0105-probe1 instantiate schema sibling-differential")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
