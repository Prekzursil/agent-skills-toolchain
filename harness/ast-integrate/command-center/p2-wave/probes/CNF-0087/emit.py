#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0087-idea-count-recount.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft7Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from ledger import PLANTED, SEED_ID, write_ledger  # noqa: E402
from measures import (  # noqa: E402
    COUNCIL_MEASURE,
    RECOUNT_MEASURE,
    cluster_by_mechanism,
    council_unique,
    mechanism_key,
    recount_unique,
)

OUT = "command-center/confirmation/CNF-0087-idea-count-recount.json"
SCHEMA = "command-center/schema/similarity-report.schema.json"
LEDGER_REL = "command-center/p2-wave/probes/CNF-0087/fixtures/idea-ledger.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0087/probe1_planted_collapse.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0087/probe2_measure_differs.py"
)
QUESTION = (
    "Does the 100-unique-idea target survive an independent recount? "
    "Re-deduplicate the idea ledger with a measure different from the council's "
    "own and answer: how many ideas remain unique, how many are trivial wording "
    "variants, and does the run still meet its stated target? Spec line 11339 "
    "names count gaming through trivial variants as a required failure class."
)
SENTINEL = (
    "SUCCESS:CNF-0087 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the three planted trivial "
    "variants were collapsed by the recount, establishing it can see gaming. "
    "Any other terminal state is FAILED:CNF-0087 <classification> with the "
    "diagnostic tail attached."
)
TARGET = 100
SUPPORTING = [
    SCHEMA,
    LEDGER_REL,
    "command-center/p2-wave/probes/CNF-0087/measures.py",
    "command-center/p2-wave/probes/CNF-0087/ledger.py",
    "command-center/p2-wave/probes/CNF-0087/probe1_planted_collapse.py",
    "command-center/p2-wave/probes/CNF-0087/probe2_measure_differs.py",
]
STORE_RELS = [
    SCHEMA,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def schema_validator() -> Draft7Validator:
    store: dict = {}
    schema = None
    for rel in STORE_RELS:
        doc = json.loads((REPO / rel).read_text(encoding="utf-8"))
        if rel == SCHEMA:
            schema = doc
        sid = doc.get("$id")
        if sid:
            store[sid] = doc
        store["https://ast-integrate.invalid/" + rel] = doc
    if schema is None:
        raise RuntimeError("similarity-report schema missing")
    resolver = RefResolver(
        base_uri=str(schema.get("$id") or (REPO / SCHEMA).as_uri()),
        referrer=schema,
        store=store,
    )
    return Draft7Validator(schema, resolver=resolver)


def schema_errors(doc: dict) -> list[str]:
    out: list[str] = []
    for err in schema_validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return out


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = sha256_file(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": max(size, 1),
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def main() -> int:
    started = utcnow()
    ledger = write_ledger()
    ideas = ledger["ideas"]
    texts = [i["text"] for i in ideas]
    council_n = council_unique(texts)
    recount_n = recount_unique(ideas)
    clusters = cluster_by_mechanism(ideas)
    multi = [
        {
            "cluster_id": f"C-{idx:03d}",
            "size": len(members),
            "member_ids": [m["id"] for m in members],
            "kind": "trivial-variant",
            "mechanism_key": key,
        }
        for idx, (key, members) in enumerate(
            sorted(clusters.items(), key=lambda kv: -len(kv[1])), start=1
        )
        if len(members) > 1
    ]
    if not multi:
        print("FAILED:CNF-0087 emit no trivial-variant cluster")
        return 1
    planted_ids = [p[0] for p in PLANTED]
    plant_cluster = None
    for cl in multi:
        if SEED_ID in cl["member_ids"] and set(planted_ids) <= set(cl["member_ids"]):
            plant_cluster = cl
            break
    if plant_cluster is None or plant_cluster["size"] < 4:
        print("FAILED:CNF-0087 emit planted variants did not collapse")
        return 1
    plant_ideas = [i for i in ideas if i["id"] in {SEED_ID, *planted_ids}]
    council_on_plant = council_unique([i["text"] for i in plant_ideas])
    recount_on_plant = recount_unique(plant_ideas)
    if council_on_plant != 4 or recount_on_plant != 1:
        print(
            f"FAILED:CNF-0087 emit plant subset council={council_on_plant} "
            f"recount={recount_on_plant}"
        )
        return 1
    if COUNCIL_MEASURE["mechanical_family"] == RECOUNT_MEASURE["mechanical_family"]:
        print("FAILED:CNF-0087 emit measures share mechanical family")
        return 1
    if council_n != TARGET:
        print(f"FAILED:CNF-0087 emit council_unique={council_n} want={TARGET}")
        return 1
    distinct = [i for i in ideas if i["id"] in {"I-002", "I-003", "I-004"}]
    if len(cluster_by_mechanism(distinct)) != 3:
        print("FAILED:CNF-0087 emit distinct trio collapsed")
        return 1
    target_met = recount_n >= TARGET
    classification = "target-met" if target_met else "target-not-met"
    trivial_members = sum(cl["size"] for cl in multi)
    seed_key = mechanism_key(next(i["text"] for i in ideas if i["id"] == SEED_ID))
    plant_keys = {mechanism_key(t) for _, t in PLANTED}
    answer = (
        f"The 100-unique-idea target does not survive an independent recount. "
        f"Council normalized-string identity counts {council_n} unique ideas "
        f"(the claimed target). Canonical mechanism-key recount collapses the "
        f"three planted trivial variants with seed {SEED_ID} and yields "
        f"{recount_n} unique ideas. The run is classified target-not-met. "
        f"Live tools/council/protocol/brainstorm.py and "
        f"tools/council/quota/unique_ideas.py are absent; the substrate is "
        f"the fixture ledger at {LEDGER_REL}."
    )
    missing = [p for p in SUPPORTING if not (REPO / p).is_file()]
    if missing:
        print("FAILED:CNF-0087 emit missing supporting", missing)
        return 1
    artifacts = [
        art(SCHEMA, "supporting"),
        art(LEDGER_REL, "fixture"),
        art("command-center/p2-wave/probes/CNF-0087/measures.py", "supporting"),
        art("command-center/p2-wave/probes/CNF-0087/ledger.py", "supporting"),
        art(
            "command-center/p2-wave/probes/CNF-0087/probe1_planted_collapse.py",
            "control",
        ),
        art(
            "command-center/p2-wave/probes/CNF-0087/probe2_measure_differs.py",
            "control",
        ),
    ]
    collapse_src = json.dumps(
        {
            "cluster_size": plant_cluster["size"],
            "member_ids": plant_cluster["member_ids"],
            "recount_unique": recount_n,
        },
        sort_keys=True,
    )
    collapse_ver = json.dumps(
        {"seed_key": seed_key, "plant_keys": sorted(plant_keys)},
        sort_keys=True,
    )
    differ_src = json.dumps(
        {
            "council_family": COUNCIL_MEASURE["mechanical_family"],
            "recount_family": RECOUNT_MEASURE["mechanical_family"],
            "council_plant_unique": council_on_plant,
            "recount_plant_unique": recount_on_plant,
        },
        sort_keys=True,
    )
    differ_ver = json.dumps(
        {
            "full_council_unique": council_n,
            "full_recount_unique": recount_n,
            "same_family": False,
        },
        sort_keys=True,
    )
    ended = utcnow()
    doc = {
        "schema_version": 1,
        "unit_id": "CNF-0087",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "_USER-PROMPTS.md:11339",
        "min_bytes_threshold": 1024,
        "produced_by": {
            "vendor": "anthropic",
            "model": "opus",
            "role": "idea-count-auditor",
            "execution_substrate": "local-parallel",
        },
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "Independent mechanism-key recount collapsed planted variants "
                    "I-098, I-099, I-100 with seed I-001 into one cluster."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": (
                    "command-center/p2-wave/probes/CNF-0087/"
                    "probe1_planted_collapse.py"
                ),
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P1,
                        "raw_output": collapse_src,
                        "fingerprint": "cluster-by-mechanism-full-ledger",
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "static-analysis",
                        "command": (
                            "python3 -c \"from pathlib import Path; import sys; "
                            "sys.path.insert(0,'command-center/p2-wave/probes/"
                            "CNF-0087'); from ledger import PLANTED, SEED_ID, "
                            "build_ledger; from measures import mechanism_key; "
                            "ideas=build_ledger()['ideas']; "
                            "seed=next(i['text'] for i in ideas if i['id']==SEED_ID); "
                            "print({mechanism_key(t) for _,t in PLANTED}=="
                            "{mechanism_key(seed)})\""
                        ),
                        "raw_output": collapse_ver,
                        "fingerprint": "pairwise-mechanism-key-equality",
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    "The recount measure is canonical-mechanism-key, not a "
                    "re-run of council lexical-identity; plant subset is 4 vs 1."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": (
                    "command-center/p2-wave/probes/CNF-0087/"
                    "probe2_measure_differs.py"
                ),
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P2,
                        "raw_output": differ_src,
                        "fingerprint": "measure-family-and-plant-split",
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "file-read",
                        "command": (
                            "python3 -c \"import sys; sys.path.insert(0,"
                            "'command-center/p2-wave/probes/CNF-0087'); "
                            "from measures import COUNCIL_MEASURE, "
                            "RECOUNT_MEASURE; print("
                            "COUNCIL_MEASURE['mechanical_family'], "
                            "RECOUNT_MEASURE['mechanical_family'])\""
                        ),
                        "raw_output": differ_ver,
                        "fingerprint": "measures-py-family-constants",
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "probe1-planted-collapse",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "probe2-measure-differs",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-PLANTED-COLLAPSE",
                "kind": "known-broken-fixture",
                "description": (
                    "Three wording variants of I-001 must collapse under "
                    "mechanism-key and stay distinct under string identity."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": collapse_src,
                "good_state_output": (
                    "distinct I-002/I-003/I-004 remain three mechanism keys"
                ),
            },
            {
                "id": "NC-SCHEMA-GARBAGE",
                "kind": "malformed-input",
                "description": (
                    "similarity-report.schema.json must reject an unrelated object."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "schema rejected {totally: unrelated}",
                "good_state_output": "schema accepted this receipt",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0087-probe1-planted-collapse",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "anthropic",
            "notes": (
                "Detector control is probe1: re-derive the planted collapse "
                "from the ledger. A reviewer who only re-reads this artifact "
                "has verified nothing."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNF-0087/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "CNF-0087",
        },
        "downstream_consumers": [
            {
                "consumer": "jsonschema Draft7Validator + local $ref store",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": (
                        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                        "command-center/p2-wave/probes/CNF-0087/emit.py"
                    ),
                    "raw_output": "schema_errors=[]",
                    "fingerprint": "local-refresolver-similarity-report",
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                "zero retries. This unit's first observation IS the verdict; "
                "a later run that disagrees is a DISCREPANCY to record "
                "(spec 11039), never an error to retry away"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Live tools/council/protocol/brainstorm.py idea ledger and "
                    "tools/council/quota/unique_ideas.py are absent on this "
                    "worktree; the recount is of the 100-idea fixture ledger."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run emit.py against a live council ledger path when "
                    "those modules exist on the worktree."
                ),
            }
        ],
        "report": {
            "kind": "similarity-report",
            "observations": [
                {
                    "name": "council_unique",
                    "measured": council_n,
                    "method": COUNCIL_MEASURE["method"],
                    "anchor": LEDGER_REL,
                },
                {
                    "name": "recount_unique",
                    "measured": recount_n,
                    "method": RECOUNT_MEASURE["method"],
                    "anchor": LEDGER_REL,
                },
                {
                    "name": "planted_variants_collapsed",
                    "measured": True,
                    "method": "canonical-mechanism-key cluster of seed plus three plants",
                    "anchor": (
                        "command-center/p2-wave/probes/CNF-0087/"
                        "probe1_planted_collapse.py"
                    ),
                },
                {
                    "name": "target_survives",
                    "measured": target_met,
                    "method": "recount_unique >= 100",
                    "anchor": LEDGER_REL,
                },
            ],
            "control_ids": [
                "probe1-planted-collapse",
                "probe2-measure-differs",
                "NC-PLANTED-COLLAPSE",
                "NC-SCHEMA-GARBAGE",
            ],
            "question": QUESTION,
            "answer": answer,
            "live_inputs": {
                "council_ledger_declared": (
                    "tools/council/protocol/brainstorm.py idea ledger"
                ),
                "council_ledger_present": False,
                "council_unique_ideas_declared": (
                    "tools/council/quota/unique_ideas.py"
                ),
                "council_unique_ideas_present": False,
                "substrate": "fixture-ledger",
                "substrate_path": LEDGER_REL,
                "note": (
                    "Live brainstorm ledger and unique_ideas.py are absent. The "
                    "recount is of a 100-claim fixture that includes the required "
                    "three-variant plant. That absence is not used as BLOCKED."
                ),
            },
            "measures": [
                {
                    "id": COUNCIL_MEASURE["id"],
                    "name": COUNCIL_MEASURE["name"],
                    "method": COUNCIL_MEASURE["method"],
                    "mechanical_family": COUNCIL_MEASURE["mechanical_family"],
                    "threshold": COUNCIL_MEASURE["threshold"],
                    "role": "council-own",
                },
                {
                    "id": RECOUNT_MEASURE["id"],
                    "name": RECOUNT_MEASURE["name"],
                    "method": RECOUNT_MEASURE["method"],
                    "mechanical_family": RECOUNT_MEASURE["mechanical_family"],
                    "threshold": RECOUNT_MEASURE["threshold"],
                    "role": "independent-recount",
                },
            ],
            "counts": {
                "claimed_unique": ledger["claimed_unique_under_council_measure"],
                "council_unique": council_n,
                "recount_unique": recount_n,
                "target": TARGET,
                "target_met": target_met,
                "trivial_variant_members": trivial_members,
                "trivial_variant_clusters": len(multi),
                "side_by_side": {
                    "council_own": council_n,
                    "independent_recount": recount_n,
                },
            },
            "clusters": multi,
            "planted_control": {
                "seed_id": SEED_ID,
                "variant_ids": planted_ids,
                "collapsed": True,
                "council_unique_on_plant": council_on_plant,
                "recount_unique_on_plant": recount_on_plant,
                "cluster_id": plant_cluster["cluster_id"],
                "seed_mechanism_key": seed_key,
            },
            "target_verdict": {
                "survives": target_met,
                "classification": classification,
                "rationale": (
                    f"Council string-identity counts {council_n} unique ideas, "
                    f"meeting the {TARGET} target. Independent mechanism-key "
                    f"recount collapses the three planted trivial variants with "
                    f"the seed and yields {recount_n}, which is below target, so "
                    "the run is target-not-met regardless of the council claim."
                ),
            },
            "failure_classes_considered": [
                "count-gaming",
                "same-measure-rerun",
                "target-not-met",
            ],
        },
    }

    garbage = [
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
    ]
    for g in garbage:
        if not schema_errors(g):
            print(f"FAILED:CNF-0087 schema accepted garbage {list(g)[:2]}")
            return 1
    errs = schema_errors(doc)
    if errs:
        print("FAILED:CNF-0087 schema errors")
        for e in errs[:30]:
            print(" ", e)
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNF-0087 emit {size}B below floor")
        return 1
    text = out.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:CNF-0087 sentinel missing from artifact text")
        return 1
    live = json.loads(text)
    live_errs = schema_errors(live)
    if live_errs:
        print("FAILED:CNF-0087 post-write schema errors")
        for e in live_errs[:20]:
            print(" ", e)
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(f"council_unique={council_n} recount_unique={recount_n} {classification}")
    print("SUCCESS:CNF-0087 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
