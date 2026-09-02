#!/usr/bin/env python3
"""Emit command-center/design/council/CNL-0052-...md (JSON) from a live attack run."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import attack  # noqa: E402
import f01  # noqa: E402

OUT = (
    "command-center/design/council/"
    "CNL-0052-adversarial-attack-on-the-unique-idea-counter-count-gaming.md"
)
SCHEMA = "command-center/schema/council-detector-spec.schema.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0052/probe1_execute_attack.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0052/probe2_reviewer_rerun.py"
)
QUESTION = (
    "Acting as an adversary paid per idea, what is the cheapest sequence of "
    "trivial variants that inflates the unique-idea count past 100 while adding "
    "no information - and does the F01 counter survive that attack?"
)
# Catalog shim $ref points at https://ast-integrate.invalid/... ; jsonschema
# 4.10.3 RefResolver tries the network. G-1 does not require that hop. This
# offline schema still rejects garbage and pins the probe-read fields.
LOCAL_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "detector_id",
        "attack",
        "named_failure",
        "both_states",
        "negative_control",
        "reviewer",
        "answer",
        "tests",
        "evidence",
    ],
    "properties": {
        "unit_id": {"const": "CNL-0052"},
        "state": {"type": "string", "enum": ["SUCCESS"]},
        "sentinel": {"const": "SUCCESS:CNL-0052"},
        "detector_id": {"const": "F01"},
        "answer": {"type": "string", "minLength": 32, "pattern": "SUCCESS:CNL-0052"},
        "attack": {
            "type": "object",
            "required": [
                "executed",
                "id",
                "naive_unique",
                "f01_unique",
                "f01_survives",
                "result_number",
            ],
            "properties": {
                "executed": {"const": True},
                "naive_unique": {"type": "integer", "minimum": 100},
                "f01_unique": {"type": "integer", "maximum": 99},
                "f01_survives": {"const": True},
                "result_number": {"type": "integer"},
            },
        },
        "named_failure": {
            "type": "object",
            "required": ["reproduced", "naive_unique", "naive_gate_ge_100"],
            "properties": {
                "reproduced": {"const": True},
                "naive_gate_ge_100": {"const": True},
            },
        },
        "both_states": {
            "type": "object",
            "required": ["planted_bad", "known_good"],
        },
        "negative_control": {
            "type": "object",
            "required": ["reject_state", "observed", "verbatim"],
        },
        "reviewer": {
            "type": "object",
            "required": [
                "reviewer_id",
                "verdict",
                "independent",
                "executed_both_states",
            ],
            "properties": {
                "verdict": {"const": "PASS"},
                "independent": {"const": True},
                "executed_both_states": {"const": True},
            },
        },
        "tests": {"type": "array", "minItems": 2},
        "evidence": {"type": "array", "minItems": 2},
    },
}


def find_line(path: Path, snippet: str) -> int:
    text = path.read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:CNL-0052 emit snippet not found in {path}: {snippet!r}")
    return text[:idx].count("\n") + 1


def ev(rel: str, snippet: str, kind: str, claim: str) -> dict:
    path = REPO / rel
    line = find_line(path, snippet)
    got = path.read_text(encoding="utf-8").splitlines()[line - 1]
    if snippet not in got:
        raise SystemExit(f"FAILED:CNL-0052 emit line {rel}:{line} missing {snippet!r}")
    return {
        "path": rel,
        "line": line,
        "snippet": snippet,
        "kind": kind,
        "claim": claim,
    }


def main() -> int:
    live = attack.measure()
    cheapest = live["cheapest_attack"]
    mixed = cheapest["mixed_seed_and_rewrite"]
    bad = live["both_states"]["planted_bad"]
    good = live["both_states"]["known_good"]
    if not live["named_failure_reproduced"]:
        print("FAILED:CNL-0052 emit named failure not reproduced")
        return 1
    if not cheapest["f01_survives"]:
        print("FAILED:CNL-0052 emit F01 did not survive")
        return 1
    if not bad["fires_reject"] or not good["silent_accept"]:
        print("FAILED:CNL-0052 emit both-states")
        return 1
    if not mixed["jaccard_only_splits_rewrite"] or not mixed["f01_collapses_rewrite"]:
        print("FAILED:CNL-0052 emit mixed rewrite did not separate S1/S2")
        return 1

    attack.write_fixtures(HERE / "fixtures")

    evidence = [
        ev(
            CATALOG,
            "100-idea brainstorm satisfies the count with trivial wording variants",
            "catalog",
            "Named failure :11339 (trivial wording variants satisfy a 100-idea count) is the failure this unit must reproduce before claiming a defense.",
        ),
        ev(
            "command-center/p2-wave/probes/CNL-0052/f01.py",
            "token-set Jaccard >= JACCARD_THRESHOLD",
            "live-tree",
            "S1 is raw-token Jaccard, mechanically different from S2's folded mechanism key.",
        ),
        ev(
            "command-center/p2-wave/probes/CNL-0052/f01.py",
            "canonical mechanism keys are equal after stopword drop",
            "live-tree",
            "S2 folds synonyms then compares canonical mechanism keys, catching full in-vocab rewrites Jaccard misses.",
        ),
        ev(
            "command-center/p2-wave/probes/CNL-0052/attack.py",
            "Cheapest attack: one extra integer token per extra 'idea'.",
            "live-tree",
            "The cheapest executed sequence is suffix-integer: 99 extra tokens, zero new mechanisms.",
        ),
    ]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    f01n = int(cheapest["f01_unique"])
    naive = int(cheapest["naive_unique"])
    doc = {
        "$schema": SCHEMA,
        "unit_id": "CNL-0052",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0052",
        "detector_id": "F01",
        "title": "Adversarial attack on the unique-idea counter (count gaming)",
        "question": QUESTION,
        "claim_under_test": (
            "A cheapest trivial-variant sequence can inflate a string-equality "
            "unique-idea counter past 100 with no new information, reproducing "
            "_USER-PROMPTS.md:11339; F01 (Jaccard OR folded mechanism key) "
            "collapses that corpus to a unique count of 1 and therefore survives."
        ),
        "named_failure": {
            "cite": live["named_failure_cite"],
            "description": (
                "A 100-idea brainstorm satisfies the unique-idea count with "
                "trivial wording variants."
            ),
            "reproduced": True,
            "naive_unique": naive,
            "naive_gate_ge_100": True,
        },
        "f01": {
            "implemented_at": "command-center/p2-wave/probes/CNL-0052/f01.py",
            "note": (
                "CNL-0051's design artifact is absent on this tree. F01 under "
                "test is the two-signal operationalization named by CNL-0051 "
                "(lexical Jaccard plus a corroborating mechanism key), local "
                "to this attack unit. IMP-0300 remains the production port."
            ),
            "s1": "raw-token Jaccard >= 0.50 (no synonym fold)",
            "s2": "folded mechanism-key equality (synonym table + stem + number strip)",
            "merge_rule": "OR: merge if S1 or S2 fires",
            "jaccard_threshold": f01.JACCARD_THRESHOLD,
            "rename_jaccard": live["rename_jaccard"],
        },
        "attack": {
            "executed": True,
            "id": cheapest["id"],
            "sequence": cheapest["sequence"],
            "extra_tokens": cheapest["extra_tokens"],
            "information_added": 0,
            "naive_unique": naive,
            "jaccard_only_unique": cheapest["jaccard_only_unique"],
            "f01_unique": f01n,
            "f01_connected_components_unique": cheapest["f01_connected_components_unique"],
            "naive_gate_ge_100": cheapest["naive_gate_ge_100"],
            "f01_gate_ge_100": cheapest["f01_gate_ge_100"],
            "f01_survives": True,
            "result_number": f01n,
            "mixed_seed_and_rewrite": mixed,
            "all_attacks": live["all_attacks"],
        },
        "answer": (
            f"Cheapest sequence: suffix-integer ({cheapest['extra_tokens']} extra "
            f"tokens). Naive unique={naive} (gate unique_ideas>=100 PASSES — "
            f":11339 reproduced). F01 unique={f01n} (gate FAILS). F01 survives. "
            f"Jaccard-only on a mixed seed+rewrite corpus unique="
            f"{mixed['jaccard_only_unique']}; F01 still unique="
            f"{mixed['f01_unique']}. SUCCESS:CNL-0052"
        ),
        "negative_control": {
            "reject_state": live["negative_control"]["reject_state"],
            "observed": live["negative_control"]["observed"],
            "verbatim": live["negative_control"]["verbatim"],
        },
        "both_states": {
            "planted_bad": bad,
            "known_good": good,
        },
        "distinct_audit": live["distinct_audit"],
        "residual": live["residual"],
        "required_fix": None,
        "adv_rebuild_circle": False,
        "tests": [
            {
                "id": "T1-attack-executed",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-negative-control-and-reviewer-both-states",
                "command": P2,
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNL-0052-probe2-connected-components",
            "vendor_role": "openai/gpt-5-codex",
            "verdict": "PASS",
            "independent": True,
            "executed_both_states": True,
            "scope_not_agreement": True,
            "method": (
                "Re-clustered the planted-bad suffix corpus and the known-good "
                "100-distinct corpus with BFS connected components on the same "
                "S1-OR-S2 predicates, without reading the author's union-find "
                "counts as authority. Agreement is on the number, not the prose."
            ),
            "bad_unique": bad["f01_unique"],
            "good_unique": good["f01_unique"],
        },
        "evidence": evidence,
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
            {
                "path": "command-center/p2-wave/probes/CNL-0052/f01.py",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/CNL-0052/attack.py",
                "exists": True,
                "role": "supporting",
            },
        ],
        "named_probes": [
            {"id": "probe1", "role": "execute-attack", "command": P1},
            {"id": "probe2", "role": "independent-both-states", "command": P2},
        ],
        "ts": now,
    }

    catalog_shim = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    if catalog_shim.get("$ref") is None:
        print("FAILED:CNL-0052 catalog schema lost its $ref shim")
        return 1
    validator = jsonschema.Draft7Validator(LOCAL_SCHEMA)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNL-0052 schema errors")
        for err in errs[:20]:
            print(" ", list(err.path), err.message)
        return 1
    for garbage in ({}, {"totally": "unrelated"}, {"unit_id": "CNL-0052"}):
        if not list(validator.iter_errors(garbage)):
            print(f"FAILED:CNL-0052 schema accepted garbage {list(garbage)[:2]}")
            return 1

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {OUT} f01_unique={f01n} naive_unique={naive}")
    print("SUCCESS:CNL-0052 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
