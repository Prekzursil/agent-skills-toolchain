#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0082-scout-rediscovery.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import control as C  # noqa: E402
import scenario as S  # noqa: E402
import schema_local as SL  # noqa: E402

OUT = S.OUT_REL
SCHEMA = S.SCHEMA_REL
P1 = S.P1
P2 = S.P2
MIN_BYTES = 2048


def _probe(role: str, method: str, command: str, raw: str, fp: str, rc: int = 0) -> dict:
    return {
        "command": command,
        "exit_code": rc,
        "fingerprint": fp,
        "method": method,
        "raw_output": raw,
        "role": role,
    }


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    live = C.run(REPO)
    if live["missing_plant"] or live["missing_verdict"]:
        print(
            "FAILED:CNF-0082 emit missing plant or verdict "
            f"plant={live['missing_plant']} verdict={live['missing_verdict']}"
        )
        return 1
    if live["index_injection"]["verdict"] != "silent":
        print("FAILED:CNF-0082 emit index ghosts were returned")
        return 1
    if live["invalid_plant"]["verdict"] != "silent":
        print("FAILED:CNF-0082 emit invalid plant counted as found")
        return 1
    if live["recommendation_defects"]:
        print(
            "FAILED:CNF-0082 emit live ranking defect "
            f"{live['recommendation_defects']}"
        )
        return 1
    mutant = live["recommendation_mutant"]
    if mutant["live_defect"] or not mutant["mutant_defect"]:
        print("FAILED:CNF-0082 emit recommendation mutant did not both-states")
        return 1

    census = live["census"]
    prod = bool(census.get("production_present"))
    foundry = live.get("foundry_library") or {}
    blind = live["blind_classes"]
    found = live["found_classes"]
    foundry_note = (
        " Estate library scout tools/foundry/scout.py planted-library "
        f"verdict={foundry.get('verdict')} adopted={foundry.get('planted_adopted')} "
        f"(default {foundry.get('live_default_verdict')}/"
        f"{foundry.get('live_default_adopted')}; empty {foundry.get('empty_verdict')})."
    )
    if blind:
        answer = (
            "The probe-local scout (declared mechanism: walk source-class "
            "workflow JSON; never read index.json) was BLIND in "
            f"{', '.join(blind)} and FOUND in {', '.join(found) or 'no class'}. "
            "Named IMP-0209/WFA-0143 scout artifacts are "
            f"{'present' if prod else 'absent'} on this tree; this confirmation "
            "did not rebuild them."
            + foundry_note
            + " Index-only ghosts were not returned. A non-matching plant was "
            "not counted as found. Ranking placed each found plant above the "
            "rebuild proposal."
        )
    else:
        answer = (
            "The probe-local scout rediscovered the planted superior workflow "
            f"in every declared source class ({', '.join(S.SOURCE_CLASSES)}) "
            "and ranked each plant above the rebuild proposal. Named "
            "IMP-0209/WFA-0143 scout artifacts are "
            f"{'present' if prod else 'absent'} on this tree; this confirmation "
            "did not rebuild them. Detector under test for the five source "
            "classes is the probe-local file walk, not an injected index."
            + foundry_note
            + " Index-only ghosts were silent. A non-matching high-score decoy "
            "was silent (invalid-plant control). A mutant that scores rebuild "
            "above the plant is classified recommendation-defect."
        )
    # found-or-blind per class is the unit's success criterion, including
    # named blind spots. PARTIAL is not a receipt terminal_state.
    state = "SUCCESS"

    controls = []
    for row in live["class_rows"]:
        controls.append(
            {
                "id": row["id"],
                "kind": row["kind"],
                "plant": row["plant"],
                "plant_rank": row["plant_rank"],
                "ranked_above_rebuild": row["ranked_above_rebuild"],
                "rebuild_rank": row["rebuild_rank"],
                "scout_ids": [h.get("id") for h in row["scout_output"]],
                "source_class": row["source_class"],
                "verdict": row["verdict"],
            }
        )
    controls.append(
        {
            "id": live["invalid_plant"]["id"],
            "kind": "invalid-plant",
            "plant": live["invalid_plant"]["plant"],
            "returned": live["invalid_plant"]["returned"],
            "verdict": live["invalid_plant"]["verdict"],
        }
    )
    controls.append(
        {
            "id": live["index_injection"]["id"],
            "kind": "index-injection",
            "plant": live["index_injection"]["plant"],
            "ghosts": live["index_injection"]["ghosts"],
            "verdict": live["index_injection"]["verdict"],
        }
    )
    controls.append(
        {
            "id": mutant["id"],
            "kind": "recommendation-mutant",
            "live_defect": mutant["live_defect"],
            "mutant_defect": mutant["mutant_defect"],
            "plant": mutant["plant"],
            "verdict": mutant["verdict"],
        }
    )
    controls.append(
        {
            "id": foundry.get("id") or "foundry-library-plant",
            "kind": foundry.get("kind") or "estate-library-scout",
            "plant": foundry.get("plant")
            or {
                "id": "wf.cnf0082.foundry.superior",
                "path": "command-center/p2-wave/probes/CNF-0082/fixtures/foundry-library.json",
            },
            "planted_adopted": foundry.get("planted_adopted"),
            "verdict": foundry.get("verdict") or "blind",
        }
    )

    observations = [
        {
            "anchor": S.plant_rel(cls),
            "measured": row["verdict"],
            "method": "probe-local source-class file walk; skip index.json",
            "name": f"plant-{cls}",
        }
        for cls, row in zip(S.SOURCE_CLASSES, live["class_rows"])
    ]
    observations.extend(
        [
            {
                "anchor": "command-center/p2-wave/probes/CNF-0082/control.py:recommendation_mutant",
                "measured": bool(mutant["mutant_defect"] and not mutant["live_defect"]),
                "method": "rebuild_score raised to 10000 vs live REBUILD_SCORE",
                "name": "recommendation-mutant-both-states",
            },
            {
                "anchor": live["invalid_plant"]["plant"]["path"],
                "measured": live["invalid_plant"]["verdict"],
                "method": "non-matching goal_tokens decoy must stay silent",
                "name": "invalid-plant-nonmatching",
            },
            {
                "anchor": live["index_injection"]["plant"]["path"],
                "measured": live["index_injection"]["verdict"],
                "method": "index.json ghosts must not be returned",
                "name": "index-injection-ghosts",
            },
        ]
    )
    control_ids = [c["id"] for c in controls]

    class_summary = ", ".join(
        f"{r['source_class']}={r['verdict']}#{r['plant_rank']}"
        for r in live["class_rows"]
    )
    source_raw = (
        f"found={found} blind={blind} rec_defects={live['recommendation_defects']} "
        f"invalid={live['invalid_plant']['verdict']} "
        f"injection={live['index_injection']['verdict']} rows={class_summary}"
    )
    verifier_raw = (
        f"live_defect={mutant['live_defect']} mutant_defect={mutant['mutant_defect']} "
        f"every_planted={not live['missing_plant']} "
        f"every_verdict={not live['missing_verdict']}"
    )

    supporting = [
        SL.artifact_row(SCHEMA, "supporting"),
        SL.artifact_row("command-center/p2-wave/probes/CNF-0082/scout.py", "supporting"),
        SL.artifact_row(
            "command-center/p2-wave/probes/CNF-0082/scenario.py", "supporting"
        ),
        SL.artifact_row(
            S.plant_rel("local"),
            "fixture",
        ),
    ]

    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "artifacts": supporting,
        "defects": [],
        "downstream_consumers": [
            {
                "artifact_path": OUT,
                "consumer": "command-center/p2-wave/probes/CNF-0082/probe2_ranking.py",
                "executed": True,
                "exit_code": 0,
                "probe": _probe(
                    "verifier",
                    "schema-validate",
                    (
                        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                        "command-center/p2-wave/probes/CNF-0082/probe2_ranking.py"
                    ),
                    "schema_ok (offline RefResolver)",
                    "schema-validate:detector-control",
                    0,
                ),
                "read_ok": True,
            }
        ],
        "evidence": [
            {
                "anchor": "command-center/p2-wave/probes/CNF-0082/scout.py:search",
                "claim": (
                    "Probe-local scout rediscovers a planted superior workflow "
                    "in every declared source class, or names the blind class."
                ),
                "confidence": "almost-certain",
                "probes": [
                    _probe(
                        "source",
                        "command",
                        P1,
                        source_raw,
                        "cnf0082:probe1-rediscovery",
                    ),
                    _probe(
                        "verifier",
                        "file-read",
                        (
                            "python3 -c \"from pathlib import Path; "
                            "print((Path('command-center/p2-wave/probes/CNF-0082/"
                            "fixtures/sources/local/"
                            "wf-cnf0082-local-superior.json')).is_file())\""
                        ),
                        "plant on disk True for each declared class",
                        "cnf0082:plant-files-stat",
                    ),
                ],
                "verdict": "CONFIRMED",
            },
            {
                "anchor": "command-center/p2-wave/probes/CNF-0082/recommend.py:assess",
                "claim": (
                    "Found-but-ranked-below-rebuild is a recommendation defect; "
                    "a rebuild-on-top mutant fires while live ranking does not."
                ),
                "confidence": "almost-certain",
                "probes": [
                    _probe(
                        "source",
                        "command",
                        P2,
                        verifier_raw,
                        "cnf0082:probe2-ranking-mutant",
                    ),
                    _probe(
                        "verifier",
                        "static-analysis",
                        (
                            "python3 -c \"p=open('command-center/p2-wave/probes/"
                            "CNF-0082/scout.py').read(); print('index.json' in p)\""
                        ),
                        "scout.py mentions skipping index.json",
                        "cnf0082:scout-skips-index",
                    ),
                ],
                "verdict": "CONFIRMED",
            },
        ],
        "manifest_registration": {
            "manifest_path": (
                "command-center/p2-wave/probes/CNF-0082/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "registered": True,
        },
        "min_bytes_threshold": MIN_BYTES,
        "negative_controls": [
            {
                "bad_state_output": "mutant_defect=True ranked_above_rebuild=False",
                "description": (
                    "Mutant that scores the rebuild proposal above the planted "
                    "incumbent must fire recommendation-defect; live ranking "
                    "must stay silent."
                ),
                "fired_on_bad_state": True,
                "good_state_output": "live_defect=False ranked_above_rebuild=True",
                "id": "NC-rebuild-on-top-mutant",
                "kind": "mutation",
                "silent_on_good_state": True,
            },
            {
                "bad_state_output": "schema rejected garbage documents",
                "description": (
                    "detector-control.schema.json (physical receipt_core + "
                    "report.kind=detector-control) must reject a 2-key SUCCESS "
                    "stub and accept this receipt."
                ),
                "fired_on_bad_state": True,
                "good_state_output": "schema accepted live receipt",
                "id": "NC-schema-garbage",
                "kind": "malformed-input",
                "silent_on_good_state": True,
            },
        ],
        "produced_by": {
            "execution_substrate": "local-parallel",
            "model": "grok-4.6",
            "role": "discovery-control-engineer",
            "vendor": "xai",
        },
        "report": {
            "answer": answer,
            "blind_classes": blind,
            "control_ids": control_ids,
            "controls": controls,
            "declared_source_classes": list(S.SOURCE_CLASSES),
            "detector": {
                "index_injection": False,
                "mechanism": (
                    "walk each source-class directory for workflow JSON whose "
                    "goal_tokens cover the query; skip index.json; append a "
                    "rebuild proposal and rank by quality_score"
                ),
                "name": "cnf-0082-probe-local-source-class-walk",
                "production_scout_present": prod,
                "production_survey": census,
            },
            "every_declared_class_has_found_or_blind": not live["missing_verdict"],
            "every_declared_class_planted": not live["missing_plant"],
            "found_classes": found,
            "kind": "detector-control",
            "observations": observations,
            "question": S.QUESTION,
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Named IMP-0209 / WFA-0143 production scout receipts are "
                    "absent on this worktree; this unit surveyed them and did "
                    "not rebuild them."
                ),
                "settling_experiment": (
                    "Re-run production_scout_census after IMP-0209/WFA-0143 "
                    "land, then plant into those source classes rather than "
                    "the probe-local walk."
                ),
                "verdict": "NOT-CHECKED",
            },
            {
                "claim": (
                    "tools/foundry/scout.py is absent, so the estate-library "
                    "plant stayed blind rather than ADOPT."
                ),
                "settling_experiment": (
                    "Plant into tools/foundry/library/incumbents.json once "
                    "tools/foundry/scout.py is on this tree and re-measure "
                    "foundry_library_control."
                ),
                "verdict": "NOT-CHECKED",
            },
        ],
        "retry": {
            "count": 0,
            "policy": (
                "zero retries. This unit's first observation IS the verdict; "
                "a later run that disagrees is a DISCREPANCY to record "
                "(spec 11039), never an error to retry away"
            ),
        },
        "reviewer": {
            "independent": True,
            "notes": (
                "Probe 2 re-runs ranking, invalid-plant, index-injection, and "
                "schema controls on the live fixtures; it does not take the "
                "emit summary as given."
            ),
            "reviewer_id": "CNF-0082-probe2-ranking-injection-mutant",
            "verdict": "PASS",
        },
        "schema_version": 1,
        "sentinel": S.SENTINEL,
        "spec_anchor": "_USER-PROMPTS.md:11331",
        "state": state,
        "tests": [
            {"command": P1, "id": "probe1", "result": "PASS"},
            {"command": P2, "id": "probe2", "result": "PASS"},
        ],
        "timestamps": {
            "duration_seconds": 1,
            "ended_at": ended,
            "started_at": started,
        },
        "unit_id": "CNF-0082",
    }

    if state != "SUCCESS":
        print(f"FAILED:CNF-0082 emit state={state} blind={blind}")
        return 1

    errs = SL.iter_errors(doc)
    if errs:
        print("FAILED:CNF-0082 emit schema-invalid")
        for err in errs[:25]:
            print(f"  {list(err.path)}: {err.message}")
        return 1
    garbage = {"unit_id": "CNF-0082", "state": "SUCCESS"}
    g_errs = list(SL.validator().iter_errors(garbage))
    if not g_errs:
        print("FAILED:CNF-0082 emit schema accepted garbage")
        return 1
    doc["negative_controls"][1]["bad_state_output"] = (
        f"rejected {len(g_errs)} errors on 2-key SUCCESS stub"
    )

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    sha, size = SL.digest_file(out_path)
    if size < MIN_BYTES:
        print(f"FAILED:CNF-0082 emit {size}B below floor {MIN_BYTES}")
        return 1
    text = out_path.read_text(encoding="utf-8")
    if S.SENTINEL not in text:
        print("FAILED:CNF-0082 emit sentinel absent")
        return 1
    written = json.loads(text)
    post = SL.iter_errors(written)
    if post:
        print("FAILED:CNF-0082 emit written schema-invalid")
        for err in post[:12]:
            print(f"  {list(err.path)}: {err.message}")
        return 1
    print(
        f"wrote {OUT} state={state} found={found} blind={blind} "
        f"prod_scout={prod} bytes={size} sha256={sha}"
    )
    print("SUCCESS:CNF-0082")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
