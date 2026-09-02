#!/usr/bin/env python3
"""Probe 2: adversarial refuter — default REFUTED, E3 not fact, schema, overclaim control."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

ART = REPO / "command-center/research/RES-0058.json"
CATALOG_SCHEMA = REPO / "command-center/schema/research-claim-record.schema.json"
LOCAL_SCHEMA = HERE / "research-claim-record.local.schema.json"


def fail(msg: str) -> int:
    print(f"FAILED:RES-0058-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:RES-0058" not in json.dumps(doc):
        return fail("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")

    reviewer = doc.get("reviewer") or {}
    if reviewer.get("default") != "REFUTED":
        return fail("reviewer default is not REFUTED")
    if reviewer.get("independent") is not True:
        return fail("reviewer not independent")
    if reviewer.get("verdict") != "PASS":
        return fail(f"reviewer verdict {reviewer.get('verdict')}")

    index = E.load_captures()
    overclaim = E.refute_cargo_overclaim(index)
    if overclaim.get("verdict") != "REFUTED":
        return fail(f"cargo overclaim not REFUTED: {overclaim}")
    rec_over = (reviewer.get("overclaim_control") or {}).get("verdict")
    if rec_over != "REFUTED":
        return fail("artifact overclaim_control not REFUTED")

    e3 = [c for c in doc.get("claims") or [] if c.get("evidence_tier") == "E3"]
    if not e3:
        return fail("no E3 control claim")
    for c in e3:
        if c.get("verdict") == "CONFIRMED":
            return fail(f"{c.get('claim_id')} E3 cited as CONFIRMED")
        if c.get("verdict") != "REFUTED":
            return fail(f"{c.get('claim_id')} E3 not REFUTED")

    confirmed = 0
    for c in doc.get("claims") or []:
        if c.get("verdict") != "CONFIRMED":
            continue
        confirmed += 1
        if not c.get("strongest_caveat"):
            return fail(f"{c.get('claim_id')} missing strongest_caveat")
        rails = c.get("source_lineage") or []
        kinds = {r.get("rail") for r in rails}
        if "structured-api" not in kinds or "prose" not in kinds:
            return fail(f"{c.get('claim_id')} CONFIRMED without two rails")
        if len(rails) < 2:
            return fail(f"{c.get('claim_id')} fewer than two rails")

    if not CATALOG_SCHEMA.is_file() or CATALOG_SCHEMA.stat().st_size <= 0:
        return fail("catalog output_schema missing on disk")
    # Catalog shim $ref is https://ast-integrate.invalid/... . jsonschema
    # 4.10.3 on this worktree uses RefResolver and tries the network. The
    # physical class also does not require claims[].source_lineage. Validate
    # a disk-local Draft-07 discriminator that still rejects a stripped rail.
    schema = json.loads(LOCAL_SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft7Validator(schema).validate(doc)
    stripped = copy.deepcopy(doc)
    stripped["claims"][0].pop("source_lineage", None)
    try:
        jsonschema.Draft7Validator(schema).validate(stripped)
        return fail("schema accepted a claim with source_lineage stripped")
    except jsonschema.ValidationError:
        pass

    live_claims = E.build_claims(index)
    live_map = {c["claim_id"]: c for c in live_claims}
    for c in doc.get("claims") or []:
        live = live_map.get(c["claim_id"])
        if not live:
            return fail(f"live claims missing {c['claim_id']}")
        if live["verdict"] != c["verdict"] or live["evidence_tier"] != c["evidence_tier"]:
            return fail(
                f"{c['claim_id']} drift live={live['verdict']}/{live['evidence_tier']} "
                f"art={c['verdict']}/{c['evidence_tier']}"
            )

    print(
        json.dumps(
            {
                "probe": "probe2-refuter",
                "unit_id": "RES-0058",
                "overclaim_refuted": True,
                "e3_refuted": len(e3),
                "confirmed_with_caveat": confirmed,
                "schema_stripped_rejected": True,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print(
        f"overclaim_ok=True e3_refuted={len(e3)} confirmed={confirmed} "
        "schema_stripped_rejected=True"
    )
    print("SUCCESS:RES-0058-probe2 adversarial refuter and schema control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
