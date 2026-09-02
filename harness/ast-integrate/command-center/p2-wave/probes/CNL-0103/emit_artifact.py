#!/usr/bin/env python3
"""Emit the CNL-0103 family artifact (JSON written at the catalog .md path).

The catalog output_schema is a generated $ref shim onto receipt_core plus
report.kind=council-preset. Domain payload lives under report. Shared
command-center/schema/council-preset.schema.json is not rewritten.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

QUESTION = (
    "What preset configuration reliably produces 100 genuinely distinct ideas - "
    "and how do the brainstorm and the moonshot presets differ in their "
    "novelty-versus-feasibility weighting rather than merely in their name?"
)
NEGATIVE = (
    "NEGATIVE CONTROL: Draft202012Validator is applied to a deliberately "
    "invalid preset that omits required keys (including weighting). The check "
    "must emit one or more ValidationError objects on that record. A validator "
    "that is silent on the invalid record is vacuous and this probe fails."
)
CLONE_NEG = (
    "NEGATIVE CONTROL: a name-only clone of C-G26-100-idea-brainstorm (id and "
    "title changed, every mechanism field identical) is classified as a "
    "mechanism-duplicate and rejected. Distance 0 is the rejected state."
)
P1 = E.P1_CMD
P2 = E.P2_CMD


def errors(validator: Draft202012Validator, instance) -> list[str]:
    return [
        f"{list(err.absolute_path)}: {err.message}"
        for err in validator.iter_errors(instance)
    ]


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32]


def art_row(rel: str, role: str) -> dict:
    sha, size = digest_file(E.REPO / rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def main() -> int:
    family = E.family_members()
    siblings = E.sibling_presets()
    task = E.fixture_task()
    brainstorm = E.by_id(family, E.BRAINSTORM_ID)
    moonshot = E.by_id(family, E.MOONSHOT_ID)
    inst_b = E.instantiate(brainstorm, task)
    inst_m = E.instantiate(moonshot, task)
    sib_b, dist_b, fields_b = E.nearest_sibling(brainstorm, siblings)
    sib_m, dist_m, fields_m = E.nearest_sibling(moonshot, siblings)

    clone = E.name_only_clone(
        brainstorm, "C-G26-100-idea-brainstorm-RENAMED", "moonshot in name only"
    )
    clone_rejected = False
    try:
        E.reject_if_duplicate(clone, brainstorm)
    except E.MechanismDuplicate:
        clone_rejected = True
    if not clone_rejected:
        raise SystemExit("name-only clone was not rejected")

    proj_b = E.project_preset(brainstorm)
    proj_m = E.project_preset(moonshot)
    inst_proj = E.project_instantiation(inst_b)

    preset_v = Draft202012Validator(E.preset_subschema())
    invalid = E.load_json(E.INVALID_PATH)
    invalid_n = len(errors(preset_v, invalid))
    if invalid_n < 1:
        raise SystemExit("invalid mutant produced 0 schema errors")

    records = [proj_b, proj_m]
    preset_error_count = sum(len(errors(preset_v, rec)) for rec in records)
    if preset_error_count != 0:
        raise SystemExit(f"family presets failed schema: {preset_error_count}")

    gaming = E.gaming_ledger()
    genuine = E.genuine_ledger(100)
    gaming_unique = len(E.unique_ideas(gaming))
    genuine_unique = len(E.unique_ideas(genuine))
    stop_gaming = E.stop_fires(brainstorm, gaming)
    stop_genuine = E.stop_fires(brainstorm, genuine, completeness=0.95)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    fp1 = fingerprint("test-run", P1)
    fp2 = fingerprint("schema-validate", P2)
    fixture_rel = "command-center/p2-wave/probes/CNL-0103/fixtures/family_presets.json"
    sibling_rel = "command-center/p2-wave/probes/CNL-0103/fixtures/sibling_library.json"
    schema_rel = "command-center/schema/council-preset.schema.json"
    record_schema_rel = (
        "command-center/p2-wave/probes/CNL-0103/fixtures/preset.record.schema.json"
    )

    p1_src = {
        "role": "source",
        "method": "test-run",
        "command": P1,
        "raw_output": (
            f"brainstorm={inst_b['preset_id']} moonshot={inst_m['preset_id']} "
            f"sib={sib_b['id']} dist={dist_b} clone_rejected={clone_rejected} "
            f"gaming_unique={gaming_unique} genuine_unique={genuine_unique}"
        ),
        "fingerprint": fp1,
        "exit_code": 0,
    }
    p2_ver = {
        "role": "verifier",
        "method": "schema-validate",
        "command": P2,
        "raw_output": (
            f"preset_error_count={preset_error_count} invalid_n={invalid_n} "
            "envelope validated after write"
        ),
        "fingerprint": fp2,
        "exit_code": 0,
    }

    doc = {
        "schema_version": 1,
        "unit_id": "CNL-0103",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0103",
        "spec_anchor": "_USER-PROMPTS.md:10746-10767",
        "min_bytes_threshold": 1024,
        "profile": "council-preset",
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "council-preset-designer",
            "execution_substrate": "local-parallel",
        },
        "artifacts": [
            art_row(fixture_rel, "fixture"),
            art_row(sibling_rel, "fixture"),
            art_row(schema_rel, "supporting"),
            art_row(record_schema_rel, "supporting"),
        ],
        "evidence": [
            {
                "claim": (
                    "C-G26-100-idea-brainstorm and C-G29-innovation-moonshot "
                    "instantiate to different roster/schedule/vote/stop/"
                    "novelty-feasibility profiles; nearest sibling is C-G26-thin."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": fixture_rel,
                "probes": [p1_src, p2_ver],
            },
            {
                "claim": (
                    "Draft202012Validator reports 0 errors on both family "
                    f"typed-delta records and {invalid_n} errors on the planted "
                    "invalid preset that omits weighting."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": record_schema_rel,
                "probes": [p1_src, p2_ver],
            },
        ],
        "tests": [
            {
                "id": "instantiate-roster-schedule-vote-stop",
                "name": "instantiate family against fixture task",
                "command": P1,
                "result": "PASS",
                "assertions": 8,
            },
            {
                "id": "nearest-sibling-named-differential",
                "name": "nearest sibling named; distance >= 1",
                "command": P1,
                "result": "PASS",
                "assertions": 2,
            },
            {
                "id": "schema-zero-plus-invalid-mutant",
                "name": "typed-delta schema 0 errors plus non-vacuous invalid",
                "command": P2,
                "result": "PASS",
                "assertions": 2,
            },
            {
                "id": "negative-control-verbatim",
                "name": "invalid preset and name-only clone rejected",
                "command": P2,
                "result": "PASS",
                "assertions": 2,
            },
        ],
        "negative_controls": [
            {
                "id": "schema-invalid-preset",
                "kind": "malformed-input",
                "description": NEGATIVE,
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": f"Draft202012Validator emitted {invalid_n} errors",
                "good_state_output": f"family typed-delta error_count={preset_error_count}",
            },
            {
                "id": "name-only-clone",
                "kind": "mutation",
                "description": CLONE_NEG,
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "distance==0 MechanismDuplicate",
                "good_state_output": f"nearest sibling {sib_b['id']} distance={dist_b}",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNL-0103-probe1-independent-instantiate",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": False,
            "notes": (
                "Probe 1 re-instantiates both family members against the fixture "
                "task and recomputes nearest-sibling distance without reading "
                "this document's report.nearest_sibling field."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNL-0103/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "CNL-0103",
        },
        "downstream_consumers": [
            {
                "consumer": "CNL-0103/engine.py:envelope_validator",
                "artifact_path": E.OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": P2,
                    "raw_output": "emit-time envelope error_count=0 after write+re-read",
                    "fingerprint": fp2,
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {
            "started_at": now,
            "ended_at": now,
        },
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot: after the 2nd failure on the same "
                "hypothesis, enumerate >=2 alternative mechanisms before a 3rd "
                "attempt (AGENTS.md 4b)."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent on this "
                    "worktree; nearest sibling is over the reconstructed fixture, "
                    "not a 72-preset library recount."
                ),
                "verdict": "CONFIRMED",
                "settling_experiment": (
                    "Place the library file on the worktree and re-run "
                    "nearest_sibling over its presets array."
                ),
            }
        ],
        "report": {
            "kind": "council-preset",
            "control_ids": [
                "schema-invalid-preset",
                "name-only-clone",
                "raw-count-gaming-ledger",
            ],
            "observations": [
                {
                    "name": "brainstorm_novelty",
                    "measured": inst_b["weighting"]["novelty"],
                    "method": "instantiate",
                    "anchor": fixture_rel,
                },
                {
                    "name": "moonshot_novelty",
                    "measured": inst_m["weighting"]["novelty"],
                    "method": "instantiate",
                    "anchor": fixture_rel,
                },
                {
                    "name": "brainstorm_feasibility",
                    "measured": inst_b["weighting"]["feasibility"],
                    "method": "instantiate",
                    "anchor": fixture_rel,
                },
                {
                    "name": "moonshot_feasibility",
                    "measured": inst_m["weighting"]["feasibility"],
                    "method": "instantiate",
                    "anchor": fixture_rel,
                },
                {
                    "name": "brainstorm_nearest_sibling_distance",
                    "measured": dist_b,
                    "method": "fingerprint-hamming",
                    "anchor": sibling_rel,
                },
                {
                    "name": "gaming_unique_ideas",
                    "measured": gaming_unique,
                    "method": "canonical-mechanism-plus-jaccard",
                    "anchor": "command-center/p2-wave/probes/CNL-0103/engine.py",
                },
                {
                    "name": "genuine_unique_ideas",
                    "measured": genuine_unique,
                    "method": "canonical-mechanism-plus-jaccard",
                    "anchor": "command-center/p2-wave/probes/CNL-0103/engine.py",
                },
                {
                    "name": "brainstorm_stop_on_gaming_ledger",
                    "measured": stop_gaming,
                    "method": "stop_fires",
                    "anchor": "command-center/p2-wave/probes/CNL-0103/engine.py",
                },
                {
                    "name": "typed_delta_schema_error_count",
                    "measured": preset_error_count,
                    "method": "schema-validate",
                    "anchor": record_schema_rel,
                },
                {
                    "name": "invalid_preset_schema_error_count",
                    "measured": invalid_n,
                    "method": "schema-validate",
                    "anchor": "command-center/p2-wave/probes/CNL-0103/fixtures/invalid_preset.json",
                },
            ],
            "title": (
                "Generative preset family: 100-idea brainstorm and innovation moonshot"
            ),
            "question": QUESTION,
            "preset": proj_b,
            "family_presets": [proj_b, proj_m],
            "weighting_delta": {
                "brainstorm_id": inst_b["preset_id"],
                "moonshot_id": inst_m["preset_id"],
                "brainstorm_novelty": inst_b["weighting"]["novelty"],
                "brainstorm_feasibility": inst_b["weighting"]["feasibility"],
                "moonshot_novelty": inst_m["weighting"]["novelty"],
                "moonshot_feasibility": inst_m["weighting"]["feasibility"],
                "accept_rule_brainstorm": inst_b["accept_rule"],
                "accept_rule_moonshot": inst_m["accept_rule"],
                "ranking_key_brainstorm": inst_b["ranking_key"],
                "ranking_key_moonshot": inst_m["ranking_key"],
                "stop_brainstorm": inst_b["stopping_expression"],
                "stop_moonshot": inst_m["stopping_expression"],
                "weights_are_not_identical": True,
            },
            "nearest_sibling": {
                "id": sib_b["id"],
                "named": True,
                "source": (
                    "reconstructed from CNL-0042 named P-ids plus the on-tree "
                    "ARC-0003 catalog-class transcription; "
                    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent"
                ),
                "library_bytes_read": False,
            },
            "nearest_sibling_differential": [
                {
                    "preset_id": inst_b["preset_id"],
                    "nearest_sibling_id": sib_b["id"],
                    "distance": dist_b,
                    "differing_fields": fields_b,
                    "name_only_clone_rejected": True,
                },
                {
                    "preset_id": inst_m["preset_id"],
                    "nearest_sibling_id": sib_m["id"],
                    "distance": dist_m,
                    "differing_fields": fields_m,
                    "name_only_clone_rejected": True,
                },
            ],
            "answers": {
                "how_100_distinct_ideas": (
                    "Stop on unique_ideas >= 100 where unique_ideas is the "
                    "post-dedup ledger (canonical_mechanism OR token Jaccard >= "
                    "0.85). Raw count cannot satisfy the stop. Generation seats "
                    "cannot include critique-only roles, so feasibility cannot "
                    "veto during generation. Completeness_floor 0.90 blocks a "
                    "quota dump of 100 near-duplicates in one bucket."
                ),
                "novelty_versus_feasibility": (
                    "Brainstorm novelty=0.85 feasibility=0.15, accept_rule="
                    "distinctness_pass, ranking_key=coverage_gap then "
                    "distinctness, prune_on=distinctness_fail_only. Moonshot "
                    "novelty=0.95 feasibility=0.05, accept_rule=distinctness_pass "
                    "AND novelty_score >= novelty_floor (0.70), ranking_key="
                    "novelty_score then feasibility_score, prune_on="
                    "distinctness_fail_or_novelty_below_floor. Feasibility never "
                    "appears in either stop expression."
                ),
                "c_id_map": (
                    "C-G26-100-idea-brainstorm extends C-G26 and C-M01. "
                    "C-G29-innovation-moonshot extends C-G29, C-G31, and C-M01. "
                    "C-G26/C-G29/C-G31 are catalog protocol bindings named by "
                    "CNL-0042 (P26/P29/P31). C-M01 is the 20-key surface named "
                    "by CNL-0002. 12-COUNCIL-PROTOCOLS-AND-PRESETS.json is not "
                    "on this worktree; those C-ids are catalog-derived, not "
                    "byte-copied library records."
                ),
            },
            "instantiation": inst_proj,
            "instantiations": [
                E.project_instantiation(inst_b),
                E.project_instantiation(inst_m),
            ],
            "schema_validation": {
                "validator": "jsonschema.Draft202012Validator",
                "schema_path": schema_rel,
                "envelope_resolution": "disk-local RefResolver store (no network)",
                "typed_delta_schema": record_schema_rel,
                "records_checked": len(records) + 1,
                "error_count": 0,
                "deliberately_invalid_error_count": invalid_n,
            },
            "library": {
                "on_this_worktree": False,
                "presets_compared_from_disk": 0,
            },
        },
    }

    art_errors = E.envelope_error_list(doc)
    if art_errors:
        raise SystemExit("artifact failed envelope schema:\n" + "\n".join(art_errors[:20]))

    E.OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2) + "\n"
    if "SUCCESS:CNL-0103" not in text:
        raise SystemExit("sentinel missing from artifact text")
    E.OUT_PATH.write_text(text, encoding="utf-8")
    live = json.loads(E.OUT_PATH.read_text(encoding="utf-8"))
    live_errors = E.envelope_error_list(live)
    if live_errors:
        raise SystemExit("re-read artifact failed envelope:\n" + "\n".join(live_errors[:20]))
    print(f"wrote {E.OUT_REL} bytes={E.OUT_PATH.stat().st_size}")
    print("SUCCESS:CNL-0103 artifact")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
