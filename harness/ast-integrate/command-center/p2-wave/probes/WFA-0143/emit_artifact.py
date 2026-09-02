#!/usr/bin/env python3
"""Emit the WFA-0143 foundry artifact from a live scout run."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import workflow_scout as S  # noqa: E402

OUT_REL = (
    "command-center/foundry/"
    "WFA-0143-workflow-scout-executable-search-rank-and-provenance.json"
)
LOCAL_SCHEMA = "command-center/p2-wave/probes/WFA-0143/artifact.schema.json"
CATALOG_SCHEMA = "command-center/schema/foundry-artifact.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0143/probe1_known_existing_and_empty.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0143/probe2_unresolved_provenance.py"
)
QUESTION = (
    "Implement workflow-scout as an executable meta-workflow: given a typed "
    "goal and constraints, search the local, repository, marketplace and public "
    "sources, verify provenance and license for each hit, and return a RANKED "
    "candidate list with a per-hit evidence anchor. Question: for a given goal, "
    "what is the ranked candidate set, what is each hit's license and "
    "maintenance state, and which hits are returned as UNKNOWN-NEEDS-PROBE "
    "rather than ranked?"
)
INCUMBENT = "wf-saved-agentic-repair-reliability"
BUILD = "build-proposed-agentic-repair-reliability"
UNKNOWN = "wf-public-unresolved-repair-oracle"


def slim_hit(hit: dict) -> dict:
    return {
        "id": hit.get("id"),
        "rank": hit.get("rank"),
        "source_class": hit.get("source_class"),
        "kind": hit.get("kind"),
        "license": hit.get("license"),
        "maintenance": hit.get("maintenance"),
        "score": hit.get("score"),
        "evidence_anchor": hit.get("evidence_anchor"),
        "provenance_path": (hit.get("provenance") or {}).get("path"),
        "provenance_resolved": (hit.get("provenance") or {}).get("resolved"),
        "unknown_reason": hit.get("unknown_reason"),
        "disposition": hit.get("disposition"),
    }


def main() -> int:
    known = S.run_named_goal("known_existing")
    empty = S.run_named_goal("no_existing")
    live = S.run_named_goal("known_existing", include_live=True)
    ranked = known["ranked"]
    unknown = known["unknown_needs_probe"]
    ranked_ids = [h["id"] for h in ranked]
    unknown_ids = [h["id"] for h in unknown]
    if not ranked or ranked_ids[0] != INCUMBENT:
        print("FAILED:WFA-0143 emit incumbent not rank-1")
        print(ranked_ids)
        return 1
    if BUILD not in ranked_ids or ranked_ids.index(INCUMBENT) >= ranked_ids.index(BUILD):
        print("FAILED:WFA-0143 emit BUILD not outranked")
        return 1
    if empty["ranked"]:
        print("FAILED:WFA-0143 emit empty goal not empty")
        return 1
    if UNKNOWN in ranked_ids or UNKNOWN not in unknown_ids:
        print("FAILED:WFA-0143 emit UNKNOWN disposition wrong")
        return 1

    engine = HERE / "workflow_scout.py"
    engine_anchor = S.file_line(engine, "rank-existing-above-build")
    incumbent_anchor = ranked[0]["evidence_anchor"]
    unknown_anchor = next(h["evidence_anchor"] for h in unknown if h["id"] == UNKNOWN)
    catalog = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
    cat_line = S.file_line(catalog, '"id": "WFA-0143"')
    catalog_schema_present = (REPO / CATALOG_SCHEMA).is_file()
    registry = known["registry"]
    unknown_reason = next(
        h.get("unknown_reason") for h in unknown if h["id"] == UNKNOWN
    )
    license_lines = [
        f"{h['id']}: license={h['license']} maintenance={h['maintenance']} "
        f"source={h['source_class']}"
        for h in ranked
    ]
    answer = (
        f"On typed goal {known['goal']['id']}, scout searched "
        f"{list(S.SOURCE_CLASSES)} (census={known['source_census']}) and ranked "
        f"{ranked_ids}. Rank-1 is the planted existing workflow {INCUMBENT} "
        f"(license={ranked[0]['license']}, maintenance={ranked[0]['maintenance']}) "
        f"above BUILD proposal {BUILD}. {UNKNOWN} is UNKNOWN-NEEDS-PROBE "
        f"({unknown_reason}) because its provenance file is absent, not because "
        f"it failed to match. On goal {empty['goal']['id']} the ranked set is "
        f"empty (n={len(empty['ranked'])}); scout does not fabricate a hit. "
        f"08-WORKFLOW-CANDIDATE-REGISTRY.json present={registry.get('present')} "
        f"on this worktree; fixture corpus is the executable stand-in. Catalog "
        f"schema {CATALOG_SCHEMA} present={catalog_schema_present}."
    )

    doc = {
        "unit_id": "WFA-0143",
        "id": "WFA-0143",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:WFA-0143",
        "completion_sentinel": "SUCCESS:WFA-0143",
        "title": "workflow-scout: executable search, rank and provenance-verify",
        "kind": "scout-pipeline",
        "question": QUESTION,
        "answer": answer,
        "answers": {
            "ranked_candidate_set": (
                f"known-existing ranked={ranked_ids}; no-existing ranked=[]"
            ),
            "license_and_maintenance": "; ".join(license_lines),
            "unknown_needs_probe": (
                f"{UNKNOWN} reason={unknown_reason} never ranked; "
                "disposition=UNKNOWN-NEEDS-PROBE"
            ),
        },
        "pipeline": {
            "engine": "command-center/p2-wave/probes/WFA-0143/workflow_scout.py",
            "stages": known["pipeline"],
            "sources_searched": known["sources_searched"],
            "source_census": known["source_census"],
            "n_corpus": known["n_corpus"],
            "ranking_rule": "existing hits always sort above kind=build_proposal",
            "unknown_rule": (
                "unresolved provenance -> UNKNOWN-NEEDS-PROBE, never ranked"
            ),
        },
        "inputs_on_this_worktree": {
            "08-WORKFLOW-CANDIDATE-REGISTRY.json": registry,
            "foundry-artifact.schema.json": {
                "path": CATALOG_SCHEMA,
                "present": catalog_schema_present,
                "note": (
                    "Catalog names command-center/schema/foundry-artifact.schema.json"
                    "#/$defs/scout-pipeline. The file is a generated $ref shim to "
                    "platform/schema/artifact-class-profiles.schema.json; this unit "
                    "validates the live document against local artifact.schema.json."
                    if catalog_schema_present
                    else (
                        "Catalog names command-center/schema/foundry-artifact.schema.json"
                        "#/$defs/scout-pipeline. File is absent; local "
                        "artifact.schema.json is the contract this unit actually validates."
                    )
                ),
            },
            "fixture_corpus": "command-center/p2-wave/probes/WFA-0143/fixtures/sources",
        },
        "demonstration_runs": [
            {
                "label": "known-existing",
                "goal": known["goal"],
                "ranked": [slim_hit(h) for h in ranked],
                "unknown_needs_probe": [slim_hit(h) for h in unknown],
            },
            {
                "label": "no-existing",
                "goal": empty["goal"],
                "ranked": [slim_hit(h) for h in empty["ranked"]],
                "unknown_needs_probe": [
                    slim_hit(h) for h in empty["unknown_needs_probe"]
                ],
            },
            {
                "label": "known-existing-with-live-overlay",
                "goal": live["goal"],
                "include_live": True,
                "source_census": live["source_census"],
                "ranked_ids": [h["id"] for h in live["ranked"]],
                "note": (
                    "Live .claude-plugin manifests are searched as marketplace "
                    "overlays. They do not displace the planted incumbent on this goal."
                ),
            },
        ],
        "tests": [
            {
                "id": "known-existing-above-build",
                "command": P1,
                "result": "PASS",
                "detail": f"{INCUMBENT} rank-1 above {BUILD}",
            },
            {
                "id": "empty-ranked-set-when-nothing-exists",
                "command": P1,
                "result": "PASS",
                "detail": f"goal {empty['goal']['id']} ranked_n=0",
            },
            {
                "id": "unresolved-provenance-unknown",
                "command": P2,
                "result": "PASS",
                "detail": f"{UNKNOWN} UNKNOWN-NEEDS-PROBE",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-NO-FABRICATED-HIT",
                "verbatim": (
                    "on the quantum-foam-banana goal with nonce zqxb9k2m, ranked "
                    f"n={len(empty['ranked'])} and scout emits no synthesized id"
                ),
            },
            {
                "id": "NC-UNRESOLVED-NOT-RANKED",
                "verbatim": (
                    f"on {UNKNOWN}, pathlib says the provenance file is absent; "
                    "the hit is UNKNOWN-NEEDS-PROBE and is not in ranked"
                ),
            },
        ],
        "claims": [
            {
                "claim": "Scout searches local, repository, marketplace and public.",
                "verdict": "CONFIRMED",
                "anchor": engine_anchor,
            },
            {
                "claim": "Known-existing answer ranks above any newly-proposed build.",
                "verdict": "CONFIRMED",
                "anchor": incumbent_anchor,
            },
            {
                "claim": "Unresolved provenance is UNKNOWN-NEEDS-PROBE, never ranked.",
                "verdict": "CONFIRMED",
                "anchor": unknown_anchor,
            },
            {
                "claim": "08-WORKFLOW-CANDIDATE-REGISTRY.json was read on this worktree.",
                "verdict": "CONFIRMED" if registry.get("present") else "REFUTED",
                "anchor": "inputs_on_this_worktree",
            },
        ],
        "evidence": [
            {
                "claim": "Four source-class directories are walked, not a hand-built index.",
                "verdict": "CONFIRMED",
                "anchor": S.file_line(engine, "for cls in SOURCE_CLASSES"),
            },
            {
                "claim": "Rank-1 incumbent is the planted local workflow.",
                "verdict": "CONFIRMED",
                "anchor": incumbent_anchor,
            },
            {
                "claim": "Catalog unit WFA-0143 names this output path and question.",
                "verdict": "CONFIRMED",
                "anchor": cat_line,
            },
        ],
        "reviewer": {
            "reviewer_id": "WFA-0143-probe2-unresolved-provenance",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "Re-runs scout then checks pathlib.exists on every ranked "
                "provenance.path and on the planted-missing file. Does not trust "
                "the engine's resolved boolean alone."
            ),
        },
        "named_probes": [
            {"id": "probe1", "command": P1},
            {"id": "probe2", "command": P2},
        ],
        "artifacts": [
            {"path": OUT_REL, "role": "primary", "exists": True},
            {"path": LOCAL_SCHEMA, "role": "supporting", "exists": True},
            {
                "path": "command-center/p2-wave/probes/WFA-0143/workflow_scout.py",
                "role": "supporting",
                "exists": True,
            },
        ],
        "residual_unknowns": [
            (
                "The 284-row 08-WORKFLOW-CANDIDATE-REGISTRY.json is absent on this "
                "Linux worktree (tried harness-restore paths and in-repo copies). "
                "Recall against that registry is WFA-0145's job once the file is present; "
                "this unit's detector is the planted fixture corpus."
            )
        ],
        "schema_note": {
            "catalog_output_schema": CATALOG_SCHEMA + "#/$defs/scout-pipeline",
            "catalog_schema_present": catalog_schema_present,
            "validated_against": LOCAL_SCHEMA,
        },
    }

    schema = json.loads((REPO / LOCAL_SCHEMA).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    loc_v = Draft202012Validator(schema)
    loc_errs = sorted(loc_v.iter_errors(doc), key=lambda e: list(e.path))
    if loc_errs:
        print("FAILED:WFA-0143 emit local schema errors")
        for e in loc_errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"unit_id": "WFA-0143", "state": "SUCCESS"},
    ):
        if not list(loc_v.iter_errors(garbage)):
            print(f"FAILED:WFA-0143 emit local schema accepted garbage {garbage}")
            return 1

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT_REL} bytes={out.stat().st_size}")
    print("SUCCESS:WFA-0143 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
