#!/usr/bin/env python3
"""Emit the CNL-0054 design note (JSON at the catalog .md path)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import fixtures as F  # noqa: E402
import measure as M  # noqa: E402

OUT_REL = (
    "command-center/design/council/"
    "CNL-0054-category-taxonomy-coverage-and-diversity-as-one-measuremen.md"
)
CATALOG_SCHEMA = "command-center/schema/council-design-note.schema.json"
LOCAL_SCHEMA = "command-center/p2-wave/probes/CNL-0054/artifact.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0054/probe1_cluster_vs_spread.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0054/probe2_independent_recount.py"
)
QUESTION = (
    "What taxonomy do category targets range over, how is coverage computed "
    "against it, and does a high coverage score distinguish genuine spread "
    "from many ideas clustered in one popular category?"
)


def find_line(path: Path, needle: str) -> int:
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return i
    raise SystemExit(f"FAILED:CNL-0054 emit anchor missing in {path}: {needle}")


def compact(row: dict) -> dict:
    out = {
        "n": row["n"],
        "valid": row["valid"],
        "coverage": row["coverage"],
        "joint": row["joint"],
        "fires": row["fires"],
        "reason": row["reason"],
        "threshold": row["threshold"],
        "occupancy": row["occupancy"],
    }
    if row.get("invalid_ids"):
        out["invalid_ids"] = row["invalid_ids"]
    return out


def main() -> int:
    F.assert_counts()
    tax = M.load_taxonomy()
    clustered = M.score(F.clustered(), tax)
    spread = M.score(F.spread(), tax)
    token = M.score(F.token_coverage(), tax)
    invalid = M.score(F.invalid_label(), tax)
    if not clustered["fires"] or spread["fires"] or not token["fires"]:
        print("FAILED:CNL-0054 emit both-states not satisfied before write")
        return 1
    if clustered["joint"] >= spread["joint"]:
        print("FAILED:CNL-0054 emit clustered not lower than spread")
        return 1
    if token["coverage"] != spread["coverage"] or token["coverage"] != 1.0:
        print("FAILED:CNL-0054 emit coverage-only control broken")
        return 1

    m_line = find_line(HERE / "measure.py", "def pielou(")
    f_line = find_line(HERE / "fixtures.py", "def clustered(")
    t_line = find_line(HERE / "taxonomy.json", '"closed": true')
    cat_line = find_line(
        REPO / "command-center/WORK-UNIT-CATALOG.json", '"id": "CNL-0054"'
    )

    answer = (
        "Category targets range over the closed, versioned taxonomy "
        "council.idea-category.v1 (8 ids). Coverage is support/|T| against "
        "that declared set, never against observed labels. High coverage "
        "does NOT distinguish genuine spread from clustering in one popular "
        f"category: the token-coverage bag and the spread bag both score "
        f"C={token['coverage']:.3f}, while the joint Pielou score over T "
        f"is {token['joint']:.6f} vs {spread['joint']:.6f}. The one "
        "measurement that gates a stopping rule is Pielou evenness "
        "H/ln(|T|) over the full declared taxonomy; threshold 0.75. "
        f"Clustered (2 categories, same n={clustered['n']}) scores "
        f"{clustered['joint']:.6f} and the detector FIRES; spread is SILENT."
    )

    doc = {
        "unit_id": "CNL-0054",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0054",
        "completion_sentinel": "SUCCESS:CNL-0054",
        "title": "Category taxonomy, coverage and diversity as one measurement",
        "question": QUESTION,
        "answer": answer,
        "answers": {
            "taxonomy_range": (
                "Category targets range only over the closed declared set "
                "council.idea-category.v1: mechanism, interface, verification, "
                "failure-mode, economics, governance, security, operability "
                f"(|T|={len(tax['categories'])}). Observed labels do not extend T."
            ),
            "coverage_computation": (
                "C = |{c in T : occupancy[c] >= 1}| / |T|, equivalently "
                "|set(labels) ∩ T| / |T|. The denominator is the declared "
                "taxonomy, never the set of observed labels."
            ),
            "high_coverage_does_not_distinguish_spread": (
                f"No. Token-coverage and genuine spread both score C="
                f"{token['coverage']:.3f}. Joint Pielou over full T is "
                f"{token['joint']:.6f} vs {spread['joint']:.6f}; the "
                "stopping gate uses the joint score, not coverage alone."
            ),
        },
        "claims": [
            {
                "id": "C-CLUSTERED-LT-SPREAD",
                "claim": (
                    f"At the same raw count n={clustered['n']}, the 2-category "
                    f"clustered bag scores joint={clustered['joint']:.12f} "
                    f"strictly below the 8-category spread bag "
                    f"joint={spread['joint']:.12f}."
                ),
                "verdict": "CONFIRMED",
            },
            {
                "id": "C-COVERAGE-NOT-SPREAD",
                "claim": (
                    "Coverage is identical for token-coverage and spread "
                    f"(C={token['coverage']}); the joint score distinguishes "
                    "them and the detector FIRES on token-coverage."
                ),
                "verdict": "CONFIRMED",
            },
            {
                "id": "C-OUT-OF-TAXONOMY",
                "claim": (
                    "A label outside T is a validity failure "
                    "(reason=out-of-taxonomy-label), not extra coverage."
                ),
                "verdict": "CONFIRMED",
            },
        ],
        "source_inputs_on_this_tree": {
            "11-COUNCIL-SPECIFICATION.schema.json": False,
            "12-COUNCIL-PROTOCOLS-AND-PRESETS.json": False,
            "_USER-PROMPTS.md": False,
            "note": (
                "Catalog inputs are Windows harness-restore paths not present "
                "here. The taxonomy is an operational definition this unit "
                "supplies, not a transcription of unread bytes."
            ),
        },
        "taxonomy": {
            "id": tax["id"],
            "version": tax["version"],
            "closed": True,
            "range_rule": tax["range_rule"],
            "categories": tax["categories"],
            "declaration": (
                "T is declared before scoring. Observed labels cannot grow T. "
                "An out-of-taxonomy label is a validity failure, not extra coverage."
            ),
        },
        "measurement": {
            "name": tax["joint_score"]["name"],
            "formula": tax["joint_score"]["formula"],
            "threshold_reject_below": tax["joint_score"]["threshold_reject_below"],
            "coverage_alone_insufficient": True,
            "coverage_definition": tax["joint_score"]["coverage_definition"],
            "detector": (
                "FIRES when joint < 0.75 or any idea label is outside T. "
                "SILENT when every label is in T and joint >= 0.75."
            ),
        },
        "fixture_scores": {
            "clustered": compact(clustered),
            "spread": compact(spread),
            "token_coverage": compact(token),
            "invalid_label": compact(invalid),
        },
        "both_states": {
            "planted_bad": "clustered",
            "known_good": "spread",
            "planted_bad_fires": True,
            "known_good_silent": True,
            "verbatim_bad": (
                f"PLANTED-BAD clustered: valid=True n={clustered['n']} "
                f"coverage={clustered['coverage']:.12f} "
                f"joint={clustered['joint']:.12f} fires=True "
                f"reason={clustered['reason']}"
            ),
            "verbatim_good": (
                f"KNOWN-GOOD spread: valid=True n={spread['n']} "
                f"coverage={spread['coverage']:.12f} "
                f"joint={spread['joint']:.12f} fires=False "
                f"reason={spread['reason']}"
            ),
        },
        "tests": [
            {
                "id": "T-CLUSTERED-LT-SPREAD",
                "name": (
                    "a clustered fixture (all ideas in 2 categories) must score "
                    "lower than a spread fixture at the same raw count"
                ),
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T-BOTH-STATES",
                "name": (
                    "the check FIRES on a planted-bad fixture and is SILENT "
                    "on the known-good one, both runs recorded verbatim"
                ),
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T-INDEPENDENT-RECOUNT",
                "name": (
                    "reviewer re-tabulates occupancy via list-of-ids length "
                    "and coverage via set intersection; disagreement blocks"
                ),
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-CLUSTERED",
                "rejects": (
                    "24 ideas in exactly 2 of 8 declared categories at the "
                    "same raw count as the spread bag"
                ),
                "verbatim": (
                    f"on clustered the check FIRES "
                    f"(joint={clustered['joint']:.12f} < "
                    f"threshold={clustered['threshold']}); it does not stay "
                    "silent and it does not treat C=0.25 as spread"
                ),
            },
            {
                "id": "NC-TOKEN-COVERAGE",
                "rejects": (
                    "one idea in every category with the remainder dumped "
                    "into mechanism (C=1.0, not genuine spread)"
                ),
                "verbatim": (
                    f"coverage token={token['coverage']} spread="
                    f"{spread['coverage']}; joint token="
                    f"{token['joint']:.12f} spread={spread['joint']:.12f}; "
                    "detector FIRES on token-coverage"
                ),
            },
            {
                "id": "NC-OUT-OF-TAXONOMY",
                "rejects": "label 'popular' which is not in T",
                "verbatim": (
                    f"invalid_label fires={invalid['fires']} "
                    f"reason={invalid['reason']} "
                    f"invalid_ids={invalid.get('invalid_ids')}"
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "CNL-0054-probe2-independent-recount",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "Occupancy via len(list of idea ids) per category; coverage "
                "via |set(labels) ∩ T| / |T|. Does not call measure.score."
            ),
        },
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"},
            {"path": LOCAL_SCHEMA, "exists": True, "role": "supporting"},
            {"path": CATALOG_SCHEMA, "exists": True, "role": "supporting"},
            {
                "path": "command-center/p2-wave/probes/CNL-0054/taxonomy.json",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/CNL-0054/measure.py",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/CNL-0054/fixtures.py",
                "exists": True,
                "role": "supporting",
            },
        ],
        "evidence": [
            {
                "claim": (
                    "T is a closed 8-id taxonomy; observed labels do not extend it."
                ),
                "verdict": "CONFIRMED",
                "anchor": (
                    f"command-center/p2-wave/probes/CNL-0054/taxonomy.json:{t_line}"
                ),
            },
            {
                "claim": (
                    "Clustered (2 categories) joint score is strictly lower than "
                    "spread at the same raw count n=24."
                ),
                "verdict": "CONFIRMED",
                "anchor": (
                    f"command-center/p2-wave/probes/CNL-0054/fixtures.py:{f_line}"
                ),
            },
            {
                "claim": (
                    "Coverage-only is identical for token-coverage and spread "
                    "(C=1.0); the joint Pielou score distinguishes them."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"command-center/p2-wave/probes/CNL-0054/measure.py:{m_line}",
            },
            {
                "claim": (
                    "Catalog question is the question this note answers; "
                    "completion sentinel SUCCESS:CNL-0054 is on the artifact."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"command-center/WORK-UNIT-CATALOG.json:{cat_line}",
            },
            {
                "claim": (
                    "Harness-restore council spec bytes were read on this worktree "
                    "and the taxonomy was copied from them."
                ),
                "verdict": "REFUTED",
                "anchor": "source_inputs_on_this_tree",
            },
        ],
        "residual_unknowns": [
            (
                "Whether a later CouncilSpec file on another tree already names "
                "a different closed category list. If it does, this v1 list is "
                "the operational range until that file is present and a remap "
                "unit runs. Unoccupied-category Shannon vs occupied-only "
                "evenness is settled here in favour of full-T Pielou because "
                "occupied-only evenness scores 1.0 on a 50/50 two-category bag."
            ),
            (
                "Catalog output_schema council-design-note.schema.json is a "
                "generated $ref shim. jsonschema 4.10 RefResolver fetches "
                "https://ast-integrate.invalid/... and raises RefResolutionError. "
                "This unit validates against the local artifact.schema.json "
                "instead of rebuilding the catalog shim."
            ),
        ],
        "schema_validation": {
            "schema": LOCAL_SCHEMA,
            "catalog_schema": CATALOG_SCHEMA,
            "catalog_schema_live": False,
            "good_error_count": 0,
            "garbage_rejected": 3,
        },
        "named_probes": [
            {"id": "probe1", "command": P1},
            {"id": "probe2", "command": P2},
        ],
    }

    schema = json.loads((REPO / LOCAL_SCHEMA).read_text(encoding="utf-8"))
    jsonschema.Draft7Validator.check_schema(schema)
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNL-0054 emit schema-invalid")
        for e in errs[:20]:
            print(" ", "/".join(str(p) for p in e.path), e.message)
        return 1
    rejected = 0
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"unit_id": "CNL-0054", "state": "SUCCESS"},
    ):
        if list(validator.iter_errors(garbage)):
            rejected += 1
            continue
        print(f"FAILED:CNL-0054 emit schema accepted garbage {garbage}")
        return 1
    if rejected != 3:
        print(f"FAILED:CNL-0054 emit garbage rejected {rejected}/3")
        return 1

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT_REL} bytes={out.stat().st_size}")
    print("SUCCESS:CNL-0054 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
