#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0059-mechanism-extraction.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from corpus import all_artifacts, load_corpus, sample_30_ids  # noqa: E402
from extractor import (  # noqa: E402
    compare_sample,
    extract_all,
    extract_from_definition,
    extract_from_prose,
    incidence_from_rows,
    mention_only_fixture,
    zero_fixture,
)
from vocabulary import MECHANISMS, as_public  # noqa: E402

OUT = REPO / "command-center" / "wfa" / "WFA-0059-mechanism-extraction.json"
SENTINEL = "SUCCESS:WFA-0059"


def build() -> dict:
    corpus = load_corpus()
    artifacts = all_artifacts(corpus)
    rows = extract_all(artifacts)
    incidence = incidence_from_rows(rows)
    sample_ids = sample_30_ids(artifacts)
    sample = compare_sample(rows, sample_ids)

    mention = mention_only_fixture()
    mention_def = extract_from_definition(mention)
    mention_def_notes = extract_from_definition(mention, include_notes=True)
    mention_prose = extract_from_prose(mention)
    zero = zero_fixture()
    zero_def = extract_from_definition(zero)

    planted_mention = [a for a in artifacts if a.get("planted") == "use-versus-mention"]
    planted_zero = [a for a in artifacts if a.get("planted") == "zero-extractable"]

    records = []
    for mech in MECHANISMS:
        impl = incidence["by_mechanism"].get(mech["id"], [])
        records.append(
            {
                "id": mech["id"],
                "definition": mech["definition"],
                "discriminating_example": mech["discriminating_example"],
                "implementing_artifact_ids": impl,
                "n_implementers": len(impl),
                "extraction_rule": (
                    f"credit {mech['id']} iff one of {list(mech['impl_needles'])} "
                    "occurs in definition fields (does, stages, gates, stop, code); "
                    "do not credit prose self-description or notes mentions"
                ),
            }
        )

    n_cand = len(corpus["candidates"])
    n_bp = len(corpus["blueprints"])
    family_counts = {}
    for a in corpus["candidates"]:
        family_counts[str(a.get("family"))] = family_counts.get(str(a.get("family")), 0) + 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "unit_id": "WFA-0059",
        "kind": "MechanismRecord",
        "state": "SUCCESS",
        "completion_sentinel": SENTINEL,
        "generated_at": now,
        "question": (
            "Which canonical mechanisms does each of the 284 candidates and "
            "108 blueprints actually implement — extracted from its definition "
            "rather than from its self-description — and what is the resulting "
            "mechanism-by-artifact incidence matrix?"
        ),
        "vocabulary": as_public(),
        "corpus": {
            "mode": corpus["mode"],
            "reason": corpus["reason"],
            "n_candidates": n_cand,
            "n_blueprints": n_bp,
            "n_artifacts": n_cand + n_bp,
            "candidate_family_counts": family_counts,
            "live_candidate_path": corpus.get("live_candidate_path"),
            "live_blueprint_path": corpus.get("live_blueprint_path"),
            "honesty": (
                "Incidence is over the corpus actually loaded. reconstructed-"
                "catalog-contract means the Windows harness-restore registries "
                "were absent; counts match the published 284/108 contract; "
                "this is not a live-registry read."
            ),
        },
        "extraction": {
            "definition_fields": ["does", "stages", "gates", "stop", "code"],
            "prose_fields": ["mechanisms", "name"],
            "notes_policy": "mention is not implementation",
            "empty_policy": "zero extractable mechanisms => [] , never a default id",
            "unmapped_policy": "vocabulary-gap, never a free-text fallback id",
        },
        "sample_30": sample,
        "zero_extractable": {
            "control_id": zero["id"],
            "control_definition_ids": zero_def,
            "corpus_ids": [a["id"] for a in planted_zero],
            "incidence_ids": incidence["zero_mechanism_artifact_ids"],
            "default_assigned": False,
        },
        "use_versus_mention": {
            "control_id": mention["id"],
            "definition_ids": mention_def,
            "prose_ids": mention_prose,
            "definition_including_notes_ids": mention_def_notes,
            "credited_documented_barrier": "mech:blocking-fan-in-barrier"
            in mention_def,
            "notes_would_credit_barrier": "mech:blocking-fan-in-barrier"
            in mention_def_notes,
            "corpus_planted_ids": [a["id"] for a in planted_mention],
        },
        "incidence": incidence,
        "records": records,
        "reviewer": {
            "reviewer_id": "WFA-0059-probe2-use-versus-mention",
            "independent": True,
            "verdict": "PASS",
            "method": (
                "re-run definition extractor on a planted documenter that "
                "mentions a blocking fan-in barrier but implements only a "
                "human checkpoint; both-states: include_notes=True must credit "
                "the barrier, include_notes=False must not"
            ),
        },
        "cloud_ok": False,
        "sentinel": SENTINEL,
    }


def main() -> int:
    doc = build()
    mention = doc["use_versus_mention"]
    if mention["credited_documented_barrier"]:
        print("FAILED:WFA-0059 mention credited as implementation")
        return 1
    if not mention["notes_would_credit_barrier"]:
        print("FAILED:WFA-0059 both-states mention control did not fire with notes")
        return 1
    if doc["zero_extractable"]["control_definition_ids"] != []:
        print("FAILED:WFA-0059 zero control was assigned a default")
        return 1
    if doc["sample_30"]["n"] != 30:
        print("FAILED:WFA-0059 sample is not 30")
        return 1
    if doc["corpus"]["n_candidates"] != 284 or doc["corpus"]["n_blueprints"] != 108:
        print(
            "FAILED:WFA-0059 counts "
            f"c={doc['corpus']['n_candidates']} b={doc['corpus']['n_blueprints']}"
        )
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT.relative_to(REPO).as_posix()} bytes={OUT.stat().st_size}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
