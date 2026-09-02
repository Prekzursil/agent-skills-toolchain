#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0058-mechanism-vocabulary.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import corpus as C  # noqa: E402
import discriminate as D  # noqa: E402
import mapper as M  # noqa: E402
import namespaces as N  # noqa: E402
import reviewer as R  # noqa: E402
from vocab import (  # noqa: E402
    DISCRIMINATION_FLOOR,
    GAP,
    ID_NAMESPACE,
    VERSION,
    VOCABULARY_ID,
    public_entries,
    vocab_ids,
)

OUT = REPO / "command-center/wfa/WFA-0058-mechanism-vocabulary.json"
REG = REPO / "command-center/wfa/mechanism-registry.json"
SCHEMA_PACK = REPO / "command-center/wfa/schema/wfa-schema-pack.json"
QUESTION = (
    "Implementation target: a canonical, closed vocabulary of mechanism "
    "ids with definitions and discriminating examples, replacing the "
    "free-text candidates[].mechanisms strings, so that mechanism-level "
    "deduplication becomes an exact set operation rather than a judgement call."
)


def main() -> int:
    data = C.load_corpus()
    texts = C.distinct_texts(data)
    mapped = M.map_all(texts)
    leaks = M.closed_ids(mapped)
    multi = M.unique_mapping(mapped)
    if leaks or multi:
        print(f"FAILED:WFA-0058 emit open/multi leaks={leaks} multi={multi}")
        return 1
    blind = D.run_blind()
    if not blind["passed"]:
        print(
            f"FAILED:WFA-0058 emit discrimination "
            f"{blind['correct']}/{blind['n']} < floor"
        )
        return 1
    merge = D.indistinguishable_pair()
    if not merge["merged_before_freeze"]:
        print(f"FAILED:WFA-0058 emit merge control {merge}")
        return 1
    ns = N.audit()
    if not ns["clean"]:
        print(f"FAILED:WFA-0058 emit namespace {ns}")
        return 1
    rev = R.review()
    if rev["verdict"] != "PASS":
        print(f"FAILED:WFA-0058 emit reviewer {rev}")
        return 1
    both = R.mapping_both_states()
    n_mapped = sum(1 for r in mapped if not r["gap"])
    n_gap = sum(1 for r in mapped if r["gap"])
    honesty = (
        data["absent_reason"]
        if not data["live_present"]
        else (
            "Live 08-WORKFLOW-CANDIDATE-REGISTRY.json was loaded; every "
            "distinct candidates[].mechanisms string is in mapping_table."
        )
    )
    answer = (
        f"Closed MX-NNNN vocabulary v{VERSION} with {len(vocab_ids())} "
        f"ids, each carrying a definition and discriminating example. "
        f"Corpus origin={data['origin']} distinct={len(mapped)} "
        f"mapped={n_mapped} {GAP}={n_gap}. Blind two-definition reader "
        f"scored {blind['correct']}/{blind['n']} "
        f"(floor {DISCRIMINATION_FLOOR}). Indistinguishable MX-0004 clone "
        f"was merged before freeze. Id namespace does not collide with "
        f"wf-*, BP-*, or M-NN. {honesty} SUCCESS:WFA-0058"
    )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    table = []
    for src, row in zip(data["rows"], mapped):
        table.append(
            {
                "source_string": row["source"],
                "kind": src["kind"],
                "from": src["source"],
                "vocab_id": row["vocab_id"],
                "rule": row["rule"],
                "gap": row["gap"],
            }
        )
    pack_present = SCHEMA_PACK.is_file()
    doc = {
        "unit_id": "WFA-0058",
        "record_type": "MechanismRecord",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0058",
        "title": (
            "Define the canonical mechanism vocabulary that replaces "
            "free-text mechanism strings"
        ),
        "question": QUESTION,
        "answer": answer,
        "output_schema": (
            "command-center/wfa/schema/wfa-schema-pack.json#/$defs/MechanismRecord"
        ),
        "declared_schema": (
            "command-center/p2-wave/probes/WFA-0058/mechanism-record.schema.json"
        ),
        "schema_pack_present": pack_present,
        "generated_at": now,
        "vocabulary": {
            "vocabulary_id": VOCABULARY_ID,
            "version": VERSION,
            "closed": True,
            "versioned": True,
            "id_namespace": ID_NAMESPACE,
            "gap_token": GAP,
            "mechanisms": public_entries(),
        },
        "mapping_table": table,
        "discrimination": {
            "n": blind["n"],
            "correct": blind["correct"],
            "score": blind["score"],
            "floor": DISCRIMINATION_FLOOR,
            "passed": True,
            "reader": "two-definition overlap+key score; aliases hidden",
            "rows": [
                {
                    "gold": r["gold"],
                    "distractor": r["distractor"],
                    "got": r["got"],
                    "ok": r["ok"],
                }
                for r in blind["rows"]
            ],
        },
        "indistinguishable_pair": merge,
        "namespace_audit": {
            "clean": ns["clean"],
            "pattern_ok": ns["pattern_ok"],
            "collisions": ns["collisions"],
            "planted_M-16_rejected_as_vocab_id": ns[
                "planted_M-16_rejected_as_vocab_id"
            ],
        },
        "both_states": both,
        "live_source": {
            "origin": data["origin"],
            "live_present": data["live_present"],
            "path": data["path"],
            "n_candidates": data["n_candidates"],
            "n_distinct": data["n_distinct"],
            "absent_reason": data["absent_reason"],
        },
        "honesty": honesty,
        "evidence_a": {
            "kind": "mapping-table",
            "detail": (
                "Every distinct free-text mechanism string in the loaded "
                f"corpus maps to exactly one vocabulary id or to {GAP}."
            ),
            "n": len(table),
            "mapped": n_mapped,
            "gaps": n_gap,
            "closed_leaks": [],
            "multi_mapped": {},
        },
        "evidence_b": {
            "kind": "blind-two-definition-discrimination",
            "detail": (
                "A reader given only two mechanism definitions assigned "
                "20 held-out example strings; floor "
                f"{DISCRIMINATION_FLOOR}."
            ),
            "n": blind["n"],
            "score": blind["score"],
            "passed": True,
        },
        "tests": [
            {
                "id": "closed-versioned",
                "result": "PASS",
                "detail": (
                    f"Unmapped strings are {GAP}, not a free-text "
                    f"fallback. Vocabulary version {VERSION} is frozen."
                ),
            },
            {
                "id": "discrimination-floor",
                "result": "PASS",
                "detail": (
                    f"{blind['correct']}/{blind['n']} >= "
                    f"{DISCRIMINATION_FLOOR} before downstream use."
                ),
            },
            {
                "id": "id-namespace",
                "result": "PASS",
                "detail": (
                    "MX-NNNN does not collide with candidate wf-*, "
                    "blueprint BP-*, or option M-NN; planted M-16 rejected."
                ),
            },
        ],
        "reviewer": rev,
        "residual_unknowns": [
            {
                "id": "live-registry-absent"
                if not data["live_present"]
                else "live-gaps",
                "detail": honesty,
            }
        ],
        "downstream_consumers": ["WFA-0059", "WFA-0066", "WFA-0067"],
        "registry_write": str(REG.relative_to(REPO).as_posix()),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    registry = {
        "closed": True,
        "notes": (
            "Canonical closed vocabulary from WFA-0058. Replaces the "
            "WFA-0067 bootstrap 0.1.0 entries by extending them; deleting "
            "this mechanisms block must still turn the registry gate red."
        ),
        "schema_version": 1,
        "version": VERSION,
        "vocabulary_id": VOCABULARY_ID,
        "source_unit": "WFA-0058",
        "mechanisms": public_entries(),
    }
    REG.write_text(
        json.dumps(registry, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT.relative_to(REPO).as_posix()} n_map={len(table)}")
    print(f"wrote {REG.relative_to(REPO).as_posix()} n_mech={len(vocab_ids())}")
    print("SUCCESS:WFA-0058 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
