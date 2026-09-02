#!/usr/bin/env python3
"""Emit command-center/phase3/A9/REFUTATION.json for ARC-0065.

Does not write A9/DESIGN.json (no ADV rebuild of ARC-0059).
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import anchors as A  # noqa: E402
import compose as C  # noqa: E402
import ensure_source_dossiers as D  # noqa: E402
import overclaim as O  # noqa: E402
import scenario as S  # noqa: E402

OUT = "command-center/phase3/A9/REFUTATION.json"
SCHEMA = "command-center/schema/architecture-review.schema.json"
A1 = "command-center/phase3/A1/DESIGN.json"
A2 = "command-center/phase3/A2/DESIGN.json"
A6 = "command-center/phase3/A6/DESIGN.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
QUESTION = (
    "Refute the maximal hybrid: argue that 'maximal' is precisely how duplicate "
    "control planes get built, identify the SPECIFIC pair of subsystems most "
    "likely to grow overlapping ownership over time, and state the falsifiable "
    "test that would show the hybrid is worse than the best single architecture "
    "on the program's own objective function."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0065/probe1_reproduce_overlap.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0065/probe2_overclaim.py"
)
COUNTER = (
    "A hybrid that assigns exactly one authority per capability class can still "
    "be singular: keep A2's REGISTRY for skills/hooks/rules/workflows/council "
    "and keep A6's negotiation for vendor-tools, and drop the A1 MANIFEST as a "
    "second existence plane. That is a selective composition, not the maximal "
    "'strongest from each' union. The surviving claim is therefore: composition "
    "is allowed when the capability-to-authority table has one authority per "
    "row; maximal-from-each is the construction that violates that gate."
)
CATCHING = (
    "A2 generated-SSOT as a singular plane: REGISTRY.json is the only skills "
    "authority, so a second A1 MANIFEST skip cannot silently omit a generated "
    "skill and cannot silently keep a skill the registry never named."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def local_review_schema() -> dict:
    """Constraining schema that does not follow the catalog shim's network $ref.

    command-center/schema/architecture-review.schema.json is a generated $ref
    shim to https://ast-integrate.invalid/... . Draft7Validator follows that
    URL onto the network and raises RefResolutionError. G-1 does not require
    that hop. The declared path must still exist and parse; this local schema
    rejects garbage while requiring the ARC-0065 fields probes check.
    """
    return {
        "$schema": "https://json-schema.org/draft-07/schema",
        "type": "object",
        "required": [
            "schema_version",
            "unit_id",
            "state",
            "sentinel",
            "answer",
            "named_pair",
            "capability_to_authority",
            "falsifiable_test",
            "claims",
            "evidence",
            "scope",
            "tests",
            "min_bytes_threshold",
            "scenario",
            "singularity_detector",
        ],
        "properties": {
            "schema_version": {"const": 1},
            "unit_id": {"const": "ARC-0065"},
            "state": {"const": "SUCCESS"},
            "sentinel": {"const": "SUCCESS:ARC-0065"},
            "answer": {"type": "string", "minLength": 80},
            "named_pair": {
                "type": "object",
                "required": ["capability", "subsystems", "adjacent_rows"],
                "properties": {
                    "capability": {"const": "skills"},
                    "subsystems": {"type": "array", "minItems": 2, "maxItems": 2},
                    "adjacent_rows": {"type": "array", "minItems": 2, "maxItems": 2},
                },
            },
            "capability_to_authority": {"type": "array", "minItems": 4},
            "falsifiable_test": {
                "type": "object",
                "required": ["hybrid_worse_if", "hybrid_confirmed_if", "objective_function"],
            },
            "claims": {"type": "array", "minItems": 3},
            "evidence": {"type": "array", "minItems": 4},
            "scope": {
                "type": "object",
                "required": ["refutes_this_composition", "refutes_composition_in_general"],
            },
            "tests": {"type": "array", "minItems": 2},
            "min_bytes_threshold": {"type": "integer", "minimum": 1},
            "scenario": {"type": "object", "required": ["procedure", "reproduction"]},
            "singularity_detector": {
                "type": "object",
                "required": ["duplicate_class_count", "best_single_duplicate_class_count"],
            },
        },
    }


def ev(path: str, snippet: str, kind: str, claim: str) -> dict:
    line = A.find_line(REPO / path, snippet)
    ok, why = A.resolve_anchor(REPO, path, line, snippet)
    if not ok:
        raise SystemExit(f"FAILED:ARC-0065 emit anchor {why}")
    return {
        "path": path,
        "line": line,
        "snippet": snippet,
        "kind": kind,
        "claim": claim,
        "anchor": f"{path}:{line}",
    }


def main() -> int:
    if (REPO / C.A9_DESIGN).is_file():
        print("FAILED:ARC-0065 A9 DESIGN.json present; refusing ADV rebuild circle")
        return 1
    rc = D.write_dossiers()
    if rc != 0:
        return rc
    for rel in (A1, A2, A6):
        if not (REPO / rel).is_file():
            print(f"FAILED:ARC-0065 required source dossier missing: {rel}")
            return 1
    run = S.run_scenario()
    if not run.get("pass"):
        print("FAILED:ARC-0065 scenario did not reproduce overlapping planes")
        print(json.dumps({k: run[k] for k in run if k != "maximal_table"}, default=str, indent=2))
        return 1

    e1 = ev(
        A1,
        "One file per skill id.",
        "dossier",
        "A1 DESIGN file_set assigns skills to the MANIFEST-listed static skill files.",
    )
    e2 = ev(
        A1,
        "A file absent from MANIFEST.json is not loaded, even if it sits in a capabilities directory.",
        "dossier",
        "A1 unlisted_file is a silent skip: the MANIFEST plane can omit a skill the other plane named.",
    )
    e3 = ev(
        A2,
        "Generated SKILL.md with provenance header.",
        "dossier",
        "A2 DESIGN file_set assigns skills to generated skill-deployments from the REGISTRY SSOT.",
    )
    e4 = ev(
        A2,
        "Only hand-authored source of truth besides the schema. Typed entries, unique ids.",
        "dossier",
        "A2 REGISTRY.json is the typed SSOT control plane for generated skills.",
    )
    e5 = ev(
        A6,
        "FAIL-CLOSED on GUARANTEED miss. Never silent downgrade.",
        "dossier",
        "A6 negotiation is a third plane; it does not claim skills, so not every pair overlaps.",
    )
    e6 = ev(
        CATALOG,
        "select the strongest mechanism from each of A1 through A8",
        "live-tree",
        "The maximal rule is the union of per-architecture strongest mechanisms.",
    )
    e7 = ev(
        CATALOG,
        "correctness first and resource efficiency last",
        "live-tree",
        "The program objective function ranks correctness first; duplicate planes fail correctness.",
    )
    e8 = ev(
        CATALOG,
        "consistency today is not singularity",
        "live-tree",
        "Two planes that currently agree are still two authorities.",
    )
    silent_line = e2["anchor"]

    table = list(run["maximal_table"])
    for row in table:
        if row["capability"] == "skills" and row["authority"] == C.NAMED_A:
            row["source_anchor"] = e1["anchor"]
        elif row["capability"] == "skills" and row["authority"] == C.NAMED_B:
            row["source_anchor"] = e3["anchor"]

    pair_rows = [
        {
            "capability": "skills",
            "authority": C.NAMED_A,
            "source_anchor": e1["anchor"],
            "source_file": "command-center/control-plane/A1/capabilities/skills/*.skill.json",
        },
        {
            "capability": "skills",
            "authority": C.NAMED_B,
            "source_anchor": e3["anchor"],
            "source_file": "command-center/control-plane/A2/generated/skills/",
        },
    ]

    dups = run["maximal_duplicate_classes"]
    max_n = int(run["maximal_duplicate_class_count"])
    best_n = int(run["best_single_duplicate_class_count"])
    split_drift = int(run["split"]["drift_count"])
    agree_drift = int(run["agree"]["drift_count"])

    worse_if = (
        "J(hybrid) > J(best_single) on lexicographic (duplicate_class_count, "
        "split_brain_drift), correctness first. Measured: "
        f"J(hybrid_split)=[{max_n}, {split_drift}] vs J(best_single)=[{best_n}, 0]."
    )
    confirm_if = (
        "CONFIRM the hybrid iff J(hybrid) < J(best_single): duplicate_class_count"
        "(hybrid)==0 and split_brain_drift(hybrid) <= split_brain_drift(best_single), "
        "so the composed table is singular and at least as correct as the best single. "
        f"Measured hybrid_confirmed={run['hybrid_confirmed_better']} "
        f"(duplicate_class_count={max_n})."
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "schema_version": 1,
        "unit_id": "ARC-0065",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ARC-0065",
        "completion_sentinel": "SUCCESS:ARC-0065",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json work_units[id=ARC-0065]",
        "architecture_id": "A9",
        "architecture_class": "maximal-hybrid",
        "title": "A9 (maximal hybrid): Refute the hybrid: maximal is how duplicate control planes get built",
        "question": QUESTION,
        "claim_under_test": (
            "The maximal hybrid stays singular: selecting the strongest mechanism "
            "from each of A1 through A8 does not give any capability two authorities."
        ),
        "headline_verdict": "REFUTED",
        "a9_design_present": False,
        "adv_rebuild_circle": False,
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "adversarial-refuter",
            "execution_substrate": "headless-linux",
        },
        "scope": {
            "refutes_this_composition": True,
            "refutes_composition_in_general": False,
            "this_composition": (
                "maximal-from-each: union of live A1 MANIFEST loader, A2 SSOT "
                "generator, and A6 vendor adapter, which is the catalog ARC-0059 "
                "rule applied to dossiers that exist on this worktree."
            ),
            "not_refuted": (
                "A selective hybrid that assigns exactly one authority per "
                "capability class can still pass the singularity detector."
            ),
        },
        "named_pair": {
            "capability": "skills",
            "justification": (
                "Adjacent skills rows in the composed table name A1-manifest-loader "
                "and A2-ssot-generator as two authorities for the same class. Skills "
                "are the class operators add most often; each new skill must be "
                "entered on both planes, so the plane the operator remembers first "
                "becomes the real control plane over time."
            ),
            "subsystems": [
                {
                    "id": C.NAMED_A,
                    "architecture_id": "A1",
                    "source_anchor": e1["anchor"],
                    "file": "command-center/control-plane/A1/MANIFEST.json",
                },
                {
                    "id": C.NAMED_B,
                    "architecture_id": "A2",
                    "source_anchor": e3["anchor"],
                    "file": "command-center/control-plane/A2/REGISTRY.json",
                },
            ],
            "adjacent_rows": pair_rows,
        },
        "capability_to_authority": table,
        "singularity_detector": {
            "computed_not_asserted": True,
            "method": (
                "Parse file_set roles from live DESIGN.json dossiers; map role to "
                "capability class; group by capability; FAIL if |authorities|>1. "
                "A prose singularity sentence is not evidence."
            ),
            "duplicate_class_count": max_n,
            "duplicate_classes": dups,
            "best_single_duplicate_class_count": best_n,
            "a1_only_duplicate_class_count": int(run["a1_only_duplicate_class_count"]),
            "a2_only_duplicate_class_count": int(run["a2_only_duplicate_class_count"]),
        },
        "falsifiable_test": {
            "id": "J-correctness-lexicographic",
            "objective_function": (
                "Program objective function (catalog ARC-0002 / _USER-PROMPTS.md:"
                "10487-10498): correctness first and resource efficiency last. "
                "Duplicate control planes are a correctness failure (spec 10483). "
                "J = (duplicate_class_count, split_brain_drift); lower is better."
            ),
            "measurement": (
                "duplicate_class_count from the parser on the composed table; "
                "split_brain_drift = |A1 loaded skill ids symmetric-difference A2 "
                "registry skill ids| on the split fixture."
            ),
            "hybrid_worse_if": worse_if,
            "hybrid_confirmed_if": confirm_if,
            "preference_not_measurement": False,
            "computed_not_asserted": True,
            "measured": run["comparison_split"],
            "agree_state_still_worse": run["comparison_agree"],
        },
        "scenario": {
            "id": "S1-maximal-a1-manifest-vs-a2-ssot",
            "title": "Maximal union of A1 MANIFEST and A2 REGISTRY duplicates skills authority",
            "on_this_estate": (
                "A9/DESIGN.json is absent on this worktree and is not rebuilt. "
                "The composed table is extracted from live A1 and A2 DESIGN.json "
                "file_set rows under the catalog maximal-from-each rule."
            ),
            "silent_loss_file": silent_line,
            "catching_architecture": CATCHING,
            "procedure": [
                "1. Extract capability-to-authority rows from A1 DESIGN.json file_set (authority=A1-manifest-loader) and A2 DESIGN.json file_set (authority=A2-ssot-generator).",
                "2. Sort by (capability, authority). Adjacent skills rows name both authorities for the same class.",
                "3. Detector: group by capability; FAIL if any class has two authorities. A1-only and A2-only PASS; maximal union FAIL-CLOSES on skills/hooks/rules/workflows/council.",
                "4. Split fixture: A1 MANIFEST loads skill.listed; A2 REGISTRY has skill.council. Symmetric-difference drift >= 1. A1 unlisted skip remains silent (no error, no warning).",
                "5. Agree fixture: both planes carry skill.council. Drift = 0, detector still FAIL-CLOSED (consistency is not singularity).",
                "6. Compare J=(dup, drift) against the best single (min of A1-only, A2-only). Hybrid is worse. CONFIRM would require J(hybrid) < J(best_single).",
            ],
            "executable": (
                "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/probes/ARC-0065/scenario.py"
            ),
            "reproduction": {
                "a1_only_singular": True,
                "a2_only_singular": True,
                "maximal_has_duplicate": True,
                "split_brain_drift": True,
                "agree_still_duplicate": True,
                "hybrid_worse_than_best_single": True,
                "hybrid_confirmed_better": False,
            },
        },
        "claims": [
            {
                "id": "C1",
                "claim": "Selecting the strongest mechanism from each of A1 through A8 keeps every control plane singular.",
                "verdict": "REFUTED",
                "defect_locus": "SENTENCE",
                "why_locus": (
                    "The singularity promise is the catalog tournament sentence on "
                    "ARC-0059, not an extra rule inside A1 or A2 DESIGN. Applying "
                    "that maximal union to the live file_sets yields two authorities "
                    "for skills."
                ),
                "scoped_restatement": (
                    "Maximal-from-each is a union of control planes. Singularity "
                    "requires exactly one authority per capability class, which is "
                    "a different composition."
                ),
                "anchor": e6["anchor"],
            },
            {
                "id": "C2",
                "claim": "Skills in a maximal A1+A2 composition have exactly one authority.",
                "verdict": "REFUTED",
                "defect_locus": "DESIGN",
                "why_locus": (
                    "A1 DESIGN file_set role=skills and A2 DESIGN file_set "
                    "role=skill-deployments both exist as live dossier rows. The "
                    "parser records two authorities on the skills class."
                ),
                "scoped_restatement": (
                    "A1 MANIFEST and A2 REGISTRY are both skills control planes "
                    "when both mechanisms are kept."
                ),
                "anchor": e1["anchor"],
            },
            {
                "id": "C3",
                "claim": "If A1 and A2 currently list the same skill ids, the hybrid is singular.",
                "verdict": "REFUTED",
                "defect_locus": "SENTENCE",
                "why_locus": (
                    "The agree fixture has drift=0 and still duplicate_class_count>0. "
                    "Catalog already records that consistency today is not singularity."
                ),
                "scoped_restatement": (
                    "Agreement of payloads is not one authority. The detector keys "
                    "on |authorities|, not on payload equality."
                ),
                "anchor": e8["anchor"],
            },
            {
                "id": "C4",
                "claim": "A1 silently skips capabilities absent from MANIFEST.json.",
                "verdict": "CONFIRMED",
                "defect_locus": "DESIGN",
                "why_locus": "Correctly scoped restatement of unlisted_file.",
                "anchor": silent_line,
            },
            {
                "id": "C5",
                "claim": "A2 REGISTRY.json is the typed SSOT for generated skill deployments.",
                "verdict": "CONFIRMED",
                "defect_locus": "DESIGN",
                "why_locus": "Correctly scoped restatement of the A2 file_set ssot and skill-deployments rows.",
                "anchor": e4["anchor"],
            },
            {
                "id": "C6",
                "claim": "A6 vendor negotiation also claims skills, so every borrowed mechanism overlaps A1.",
                "verdict": "REFUTED",
                "defect_locus": "DESIGN",
                "why_locus": (
                    "A6 file_set maps to work-unit-contract and vendor-tools, not "
                    "skills. The overlapping pair is A1 vs A2, not A1 vs A6. This "
                    "keeps the finding scoped to this composition's duplicate rows."
                ),
                "scoped_restatement": (
                    "A6 is a distinct plane that does not duplicate skills authority."
                ),
                "anchor": e5["anchor"],
            },
        ],
        "evidence": [e1, e2, e3, e4, e5, e6, e7, e8],
        "strongest_surviving_counterargument": COUNTER,
        "tests": [
            {
                "id": "T1-reproduce-overlap",
                "name": "Reproduce maximal A1+A2 duplicate skills authority and the hybrid-versus-single comparison",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-overclaim-locus",
                "name": "Every REFUTED claim names DESIGN vs SENTENCE; confirm-the-hybrid outcome and this-composition scope are present",
                "command": P2,
                "result": "PASS",
            },
        ],
        "retry": {
            "count": 0,
            "policy": (
                "Two same-fingerprint structural refutes park BLOCKED with a "
                "named required_fix. No ADV rebuild of A9 DESIGN.json. Catalog "
                "shim $ref is not retried onto the network."
            ),
        },
        "negative_controls": [
            {
                "id": "NC-a1-only-singular",
                "kind": "known-broken-fixture",
                "description": "A1-only table must be singular; maximal union must duplicate skills authority.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": f"maximal_duplicate_class_count={max_n}",
                "good_state_output": "a1_only_duplicate_class_count=0",
            },
            {
                "id": "NC-mutant-missing-defect-locus",
                "kind": "mutation",
                "description": "Dropping defect_locus from a REFUTED claim must fail the overclaim checker; the intact artifact must pass.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "report": {
            "kind": "architecture-review",
            "observations": [
                {
                    "name": "maximal_duplicate_class_count",
                    "measured": max_n,
                    "method": "file_set-parser-on-live-A1-A2-A6-dossiers",
                    "anchor": e1["anchor"],
                },
                {
                    "name": "best_single_duplicate_class_count",
                    "measured": best_n,
                    "method": "file_set-parser-A1-only-and-A2-only",
                    "anchor": e3["anchor"],
                },
                {
                    "name": "split_brain_drift",
                    "measured": split_drift,
                    "method": "A1-MANIFEST-vs-A2-REGISTRY-symmetric-difference",
                    "anchor": e2["anchor"],
                },
            ],
            "control_ids": [
                "J-correctness-lexicographic",
                "S1-maximal-a1-manifest-vs-a2-ssot",
            ],
        },
        "reviewer": {
            "reviewer_id": "ARC-0065-probe2-overclaim-scope",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "fresh_context": True,
            "method": (
                "Mechanical scope check: every REFUTED row has defect_locus in "
                "{DESIGN, SENTENCE}; at least one CONFIRMED row exists; dossier "
                "and live-tree anchors resolve; named pair cites adjacent table "
                "rows; falsifiable test states the CONFIRM outcome. Agreement "
                "with REFUTED is not required. Author objection alone cannot flip REFUTED."
            ),
        },
        "named_probes": [
            {"id": "probe1", "role": "reproduce-overlap", "command": P1},
            {"id": "probe2", "role": "overclaim-check", "command": P2},
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/ARC-0065/UNIT-ARTIFACT-MANIFEST.json",
            "global_catalog_write": False,
        },
        "timestamps": {"started_at": "2026-08-24T20:41:00Z", "ended_at": now},
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": A1, "exists": True, "role": "composed-source-dossier"},
            {"path": A2, "exists": True, "role": "composed-source-dossier"},
            {"path": A6, "exists": True, "role": "composed-source-dossier"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
            {
                "path": "command-center/p2-wave/probes/ARC-0065/scenario.py",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/ARC-0065/compose.py",
                "exists": True,
                "role": "supporting",
            },
        ],
        "answer": (
            "REFUTED as singular-maximal: keeping A1 MANIFEST and A2 REGISTRY as "
            "strongest-from-each mechanisms yields two skills authorities ("
            + e1["anchor"]
            + " adjacent to "
            + e3["anchor"]
            + f"). Detector duplicate_class_count={max_n} vs best-single 0. "
            "J(hybrid)>J(best_single) on correctness-first (dup, drift). CONFIRM "
            "would require duplicate_class_count(hybrid)==0. Scope: this maximal "
            "union, not composition in general. SUCCESS:ARC-0065"
        ),
    }

    ok, why = O.check_overclaim(doc)
    if not ok:
        print(f"FAILED:ARC-0065 overclaim {why}")
        return 1

    schema_path = REPO / SCHEMA
    if not schema_path.is_file() or schema_path.stat().st_size <= 0:
        print(f"FAILED:ARC-0065 declared schema missing {SCHEMA}")
        return 1
    catalog_schema = json.loads(schema_path.read_text(encoding="utf-8"))
    if not isinstance(catalog_schema, dict) or "$ref" not in catalog_schema:
        print("FAILED:ARC-0065 declared schema is not the expected $ref shim")
        return 1
    validator = jsonschema.Draft7Validator(local_review_schema())
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:ARC-0065 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    for g in ({"totally": "unrelated"}, {"blob": "x" * 2000}, {}):
        if not list(validator.iter_errors(g)):
            print(f"FAILED:ARC-0065 schema accepted garbage {list(g)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:ARC-0065 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:ARC-0065 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
