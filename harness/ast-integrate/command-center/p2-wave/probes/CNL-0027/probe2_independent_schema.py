#!/usr/bin/env python3
"""Probe 2: independent id-set recount + jsonschema enum + garbage control.

Does NOT call triad.check. Minted options = set(selects) minus set of
proposal option_ids. A per-round JSON Schema enum over filed ids is a
second mechanism. Disagreement with the artifact blocks the unit.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import fixtures as F  # noqa: E402

ART = (
    REPO
    / "command-center/design/council/"
    / "CNL-0027-proposer-critic-and-synthesiser-triad-mandates.md"
)
SCHEMA = REPO / "command-center/schema/council-design-note.schema.json"


def filed_options(rnd: dict) -> set[str]:
    return {str(p["option_id"]) for p in rnd["proposals"]}


def filed_objections(rnd: dict) -> set[str]:
    return {str(c["objection_id"]) for c in rnd["critiques"]}


def top_level_cited(rnd: dict) -> tuple[set[str], set[str], bool]:
    syn = rnd.get("synthesis") or {}
    opts: set[str] = set()
    objs: set[str] = set()
    for key in ("selects", "selects_from"):
        for item in syn.get(key) or []:
            opts.add(str(item))
    for row in syn.get("ranked_options") or []:
        if isinstance(row, dict) and row.get("option_id"):
            opts.add(str(row["option_id"]))
    for key in ("addresses", "unresolved"):
        for item in syn.get(key) or []:
            objs.add(str(item))
    mint_key = bool(syn.get("new_proposal") or syn.get("new_option"))
    obj_key = bool(syn.get("new_objection") or syn.get("new_critique"))
    return opts, objs, mint_key or obj_key


def enum_schema(filed_opt: list[str], filed_obj: list[str]) -> dict:
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "required": ["proposals", "critiques", "synthesis"],
        "properties": {
            "synthesis": {
                "type": "object",
                "not": {
                    "anyOf": [
                        {"required": ["new_proposal"]},
                        {"required": ["new_option"]},
                        {"required": ["new_objection"]},
                        {"required": ["new_critique"]},
                    ]
                },
                "properties": {
                    "selects": {
                        "type": "array",
                        "items": {"type": "string", "enum": filed_opt},
                    },
                    "addresses": {
                        "type": "array",
                        "items": {"type": "string", "enum": filed_obj},
                    },
                    "unresolved": {
                        "type": "array",
                        "items": {"type": "string", "enum": filed_obj},
                    },
                },
            }
        },
    }


def independent_row(rnd: dict) -> dict:
    fopt = filed_options(rnd)
    fobj = filed_objections(rnd)
    cited_opt, cited_obj, mint_key = top_level_cited(rnd)
    minted_opt = cited_opt - fopt
    minted_obj = cited_obj - fobj
    schema = enum_schema(sorted(fopt), sorted(fobj))
    schema_errors = list(jsonschema.Draft7Validator(schema).iter_errors(rnd))
    fires = bool(minted_opt or minted_obj or mint_key or schema_errors)
    filed = fopt | fobj
    cited_in = (cited_opt | cited_obj) & filed
    coverage = (len(cited_in) / float(len(filed))) if filed else 0.0
    return {
        "fires": fires,
        "coverage": coverage,
        "joint": 0.0 if fires else 1.0,
        "minted_opt": sorted(minted_opt),
        "minted_obj": sorted(minted_obj),
        "schema_error_count": len(schema_errors),
        "mint_key": mint_key,
    }


def main() -> int:
    bags = {
        "known_good": F.known_good(),
        "planted_new_proposal": F.planted_new_proposal(),
        "planted_new_objection": F.planted_new_objection(),
        "mention_only": F.mention_only(),
        "coverage_plus_mint": F.coverage_plus_mint(),
        "critic_proposes": F.critic_proposes(),
    }
    live = {name: independent_row(doc) for name, doc in bags.items()}
    for name, row in live.items():
        print(
            f"recount {name}: fires={row['fires']} coverage={row['coverage']:.12f} "
            f"joint={row['joint']:.12f} minted_opt={row['minted_opt']} "
            f"schema_errors={row['schema_error_count']}"
        )

    if live["known_good"]["fires"] or live["mention_only"]["fires"]:
        print("FAILED:CNL-0027-probe2 known-good or mention-only FIRED")
        return 1
    if not live["planted_new_proposal"]["fires"]:
        print("FAILED:CNL-0027-probe2 planted new-proposal did not FIRE")
        return 1
    if "P-SYNTH" not in live["planted_new_proposal"]["minted_opt"]:
        print("FAILED:CNL-0027-probe2 P-SYNTH missing from set-difference")
        return 1
    if live["planted_new_proposal"]["schema_error_count"] < 1:
        print("FAILED:CNL-0027-probe2 jsonschema enum did not reject P-SYNTH")
        return 1
    if not live["planted_new_objection"]["fires"]:
        print("FAILED:CNL-0027-probe2 planted new-objection did not FIRE")
        return 1
    if live["coverage_plus_mint"]["coverage"] != live["known_good"]["coverage"]:
        print("FAILED:CNL-0027-probe2 coverage mechanisms disagree")
        return 1
    if abs(live["coverage_plus_mint"]["coverage"] - 1.0) > 1e-12:
        print("FAILED:CNL-0027-probe2 coverage-plus-mint not 1.0")
        return 1
    if not live["coverage_plus_mint"]["fires"]:
        print("FAILED:CNL-0027-probe2 coverage-plus-mint did not FIRE")
        return 1
    if live["known_good"]["schema_error_count"] != 0:
        print("FAILED:CNL-0027-probe2 known-good failed enum schema")
        return 1

    # critic_proposes: synthesis is closed-world, so this recount (synthesis
    # selects only) is SILENT. That is the independence: probe1 catches the
    # critic mint; this probe's synthesis-enum does not. Record it.
    if live["critic_proposes"]["fires"]:
        print("FAILED:CNL-0027-probe2 critic_proposes should be silent on synthesis enum")
        return 1
    print(
        "COUNTEREXAMPLE instance: planted_new_proposal synthesis.selects "
        "contains P-SYNTH, which is not in proposal.option_id set "
        f"{sorted(filed_options(bags['planted_new_proposal']))}. "
        "Prompt role labels do not prevent the mint; the closed-world enum does."
    )

    if not ART.is_file():
        print("FAILED:CNL-0027-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:CNL-0027" not in ART.read_text(encoding="utf-8"):
        print("FAILED:CNL-0027-probe2 sentinel absent")
        return 1
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNL-0027-probe2 self-declared {st}")
        return 1
    scores = doc.get("fixture_scores") or {}
    for name in ("known_good", "planted_new_proposal", "coverage_plus_mint"):
        rec = scores.get(name) or {}
        if bool(rec.get("fires")) != bool(live[name]["fires"]):
            print(f"FAILED:CNL-0027-probe2 disagreement {name}.fires")
            return 1
        if abs(float(rec.get("coverage", -1)) - float(live[name]["coverage"])) > 1e-12:
            print(f"FAILED:CNL-0027-probe2 disagreement {name}.coverage")
            return 1

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft7Validator.check_schema(schema)
    jsonschema.Draft7Validator(schema).validate(doc)
    rejected = 0
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"unit_id": "CNL-0027", "state": "SUCCESS"},
    ):
        try:
            jsonschema.Draft7Validator(schema).validate(garbage)
        except jsonschema.ValidationError:
            rejected += 1
            continue
        print(f"FAILED:CNL-0027-probe2 schema accepted garbage {garbage}")
        return 1
    if rejected != 3:
        print(f"FAILED:CNL-0027-probe2 garbage rejected {rejected}/3")
        return 1

    print(
        "coverage-only: coverage_plus_mint.coverage == known_good.coverage == 1.0; "
        "joint mint=0 vs good=1 (coverage does not catch a second proposer)"
    )
    print("schema garbage rejected 3/3")
    print("SUCCESS:CNL-0027-probe2 independent recount schema-control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
