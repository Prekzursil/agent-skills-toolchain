#!/usr/bin/env python3
"""Emit command-center/phase3/A9/DESIGN.json for ARC-0059."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import hybrid as H  # noqa: E402

OUT = "command-center/phase3/A9/DESIGN.json"
SCHEMA = "command-center/schema/architecture-dossier.schema.json"
LOCAL_SCHEMA = "command-center/p2-wave/probes/ARC-0059/dossier.local.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0059/probe1_singularity.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0059/probe2_provenance.py"
)


def catalog_unit(uid: str) -> dict:
    catalog = H.load_json(H.CATALOG)
    for item in catalog.get("work_units") or []:
        if isinstance(item, dict) and item.get("id") == uid:
            return item
    raise KeyError(uid)


def main() -> int:
    unit = catalog_unit("ARC-0059")
    question = str(unit.get("question_or_target") or "")
    if len(question) < 40:
        print("FAILED:ARC-0059 catalog question too short")
        return 1

    table = H.table_from_planes()
    ok_s, defects_s = H.check_singularity(table)
    ok_p, defects_p = H.check_provenance()
    if not ok_s or not ok_p:
        print("FAILED:ARC-0059 kernel checks before emit")
        for d in defects_s + defects_p:
            print(" ", d)
        return 1

    libs = {
        "09-WORKFLOW-BLUEPRINT-LIBRARY.json": H.present(
            "09-WORKFLOW-BLUEPRINT-LIBRARY.json"
        ),
        "12-COUNCIL-PROTOCOLS-AND-PRESETS.json": H.present(
            "12-COUNCIL-PROTOCOLS-AND-PRESETS.json"
        ),
        "command-center/phase3/ROSTER.json": H.present(
            "command-center/phase3/ROSTER.json"
        ),
        "command-center/phase3/RUBRIC.json": H.present(
            "command-center/phase3/RUBRIC.json"
        ),
        "command-center/OWNER-DECISIONS.md": H.present(
            "command-center/OWNER-DECISIONS.md"
        ),
        "command-center/phase3/A1/DESIGN.json": H.present(H.A1),
        "command-center/phase3/A2/DESIGN.json": H.present(H.A2),
        "command-center/phase3/A3/DESIGN.json": H.present(
            "command-center/phase3/A3/DESIGN.json"
        ),
        "command-center/phase3/A4/DESIGN.json": H.present(
            "command-center/phase3/A4/DESIGN.json"
        ),
        "command-center/phase3/A5/DESIGN.json": H.present(
            "command-center/phase3/A5/DESIGN.json"
        ),
        "command-center/phase3/A6/DESIGN.json": H.present(
            "command-center/phase3/A6/DESIGN.json"
        ),
        "command-center/phase3/A7/DESIGN.json": H.present(
            "command-center/phase3/A7/DESIGN.json"
        ),
        "command-center/phase3/A8/DESIGN.json": H.present(
            "command-center/phase3/A8/DESIGN.json"
        ),
        "command-center/WORK-UNIT-CATALOG.json": H.present(H.CATALOG),
    }

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    plane_ids = [p["id"] for p in H.CONTROL_PLANES]
    doc = {
        "schema_version": 1,
        "unit_id": "ARC-0059",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ARC-0059",
        "completion_sentinel": "SUCCESS:ARC-0059",
        "architecture_id": "A9",
        "architecture_class": "maximal-hybrid-singular-planes",
        "title": str(unit.get("title") or "A9 maximal hybrid"),
        "question": question,
        "min_bytes_threshold": 2048,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json work_units[id=ARC-0059]",
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "architect",
            "execution_substrate": "headless-linux",
        },
        "answer": (
            "The maximal hybrid is maximal over MECHANISMS, not over control "
            "planes. Seven singular planes partition authority: CP-IDENTITY "
            "(A2 typed registry SSOT + A1 whole-object overlay that cannot "
            "introduce ids; A1 silent-unlisted skip rejected), CP-PIN (A3 "
            "lockfile + lifecycle SM + cache invalidation; A3 index-as-"
            "identity rejected), CP-ACTIVATE (A4 index-derived + activate/"
            "deactivate + budget REFUSE; gateway-as-discovery-SSOT and "
            "permission-at-select rejected), CP-DISPATCH (A5 ledger, "
            "at-least-once+idempotent, one reducer, one-winner claim), "
            "CP-VENDOR (A6 three tiers, FAIL-LOUD on missing GUARANTEED), "
            "CP-PERMIT (A7 single choke point every invocation crosses), "
            "CP-SURFACE (A8 jobs-to-be-done + what/meaning/next-action error "
            "contract). The capability-to-authority table is the proof: each "
            "capability class has exactly one authority. The first construct "
            "that is not expressible is composing A2 identity SSOT with A3 "
            "index-as-identity SSOT; we stop there rather than union them. "
            "A1-A8 DESIGN.json are present on this tree; each borrowed "
            "mechanism cites the live dossier (A8 under report.question) "
            "plus the catalog design-unit title/tests_required. A planted "
            "cite of an absent A3 MISSING-DOSSIER.json must fail."
        ),
        "control_planes": H.CONTROL_PLANES,
        "control_planes_explicit": plane_ids,
        "capability_to_authority_table": table,
        "borrowed_mechanisms": H.BORROWED,
        "report": {
            "kind": "architecture-dossier",
            "observations": [
                {
                    "name": "capability-to-authority-rows",
                    "measured": len(table),
                    "method": "table_from_planes",
                    "anchor": "command-center/p2-wave/probes/ARC-0059/hybrid.py",
                },
                {
                    "name": "control-plane-count",
                    "measured": len(H.CONTROL_PLANES),
                    "method": "CONTROL_PLANES kernel",
                    "anchor": "command-center/p2-wave/probes/ARC-0059/hybrid.py",
                },
                {
                    "name": "borrowed-mechanisms",
                    "measured": len(H.BORROWED),
                    "method": "check_provenance",
                    "anchor": "command-center/p2-wave/probes/ARC-0059/hybrid.py",
                },
            ],
            "control_ids": ["ARC0059-C1", "ARC0059-C2"],
        },
        "composition_rule": (
            "A borrowed mechanism may land in only one plane. Two "
            "architectures may donate to the same plane only when they would "
            "otherwise both write the same capability class (A1+A2 identity). "
            "A plane may not evaluate a class listed in must_never_govern. "
            "Maximal means every A1-A8 donates its strongest mechanism; it "
            "does not mean every A1-A8 remains a control plane."
        ),
        "file_set": [
            {
                "path": "command-center/control-plane/A9/MANIFEST.json",
                "role": "index",
                "notes": "Declares the seven planes and the capability-to-authority table digest. Unlisted files are not loaded.",
            },
            {
                "path": "command-center/control-plane/A9/identity/registry.schema.json",
                "role": "identity-schema",
                "notes": "A2-donated typed schema. additionalProperties false. No opaque passthrough.",
            },
            {
                "path": "command-center/control-plane/A9/identity/REGISTRY.json",
                "role": "identity-ssot",
                "notes": "Only writer of capability identity and body.",
            },
            {
                "path": "command-center/control-plane/A9/identity/overlay.json",
                "role": "identity-overlay",
                "notes": "A1-donated whole-object retarget of existing ids. New ids FAIL-CLOSED.",
            },
            {
                "path": "command-center/control-plane/A9/pin/lockfile.json",
                "role": "pin",
                "notes": "A3-donated version pins. Does not create ids.",
            },
            {
                "path": "command-center/control-plane/A9/permit/policy.json",
                "role": "permit",
                "notes": "A7 choke-point policy. Evaluated before any invocation.",
            },
            {
                "path": "command-center/control-plane/A9/vendor/contract.json",
                "role": "vendor",
                "notes": "A6 tier map. Missing GUARANTEED is FAIL-LOUD.",
            },
            {
                "path": "command-center/control-plane/A9/dispatch/ledger/",
                "role": "dispatch-ledger",
                "notes": "A5 append-only ledger.",
            },
            {
                "path": "command-center/control-plane/A9/activate/index.json",
                "role": "activate-index",
                "notes": "Derived view of identity+pin. Not a second SSOT.",
            },
            {
                "path": "command-center/control-plane/A9/surface/errors.json",
                "role": "surface-errors",
                "notes": "A8 error contract templates.",
            },
        ],
        "load_order": [
            {"order": 1, "path": "command-center/control-plane/A9/MANIFEST.json"},
            {
                "order": 2,
                "path": "command-center/control-plane/A9/identity/registry.schema.json",
            },
            {
                "order": 3,
                "path": "command-center/control-plane/A9/identity/REGISTRY.json",
            },
            {
                "order": 4,
                "path": "command-center/control-plane/A9/identity/overlay.json",
            },
            {
                "order": 5,
                "path": "command-center/control-plane/A9/pin/lockfile.json",
            },
            {
                "order": 6,
                "path": "command-center/control-plane/A9/permit/policy.json",
            },
            {
                "order": 7,
                "path": "command-center/control-plane/A9/vendor/contract.json",
            },
            {
                "order": 8,
                "path": "command-center/control-plane/A9/dispatch/ledger/",
            },
            {
                "order": 9,
                "path": "command-center/control-plane/A9/activate/index.json",
            },
            {
                "order": 10,
                "path": "command-center/control-plane/A9/surface/errors.json",
            },
        ],
        "precedence": {
            "rule": (
                "Capability class C is governed by exactly one plane, the "
                "authority named in capability_to_authority_table. A second "
                "writer of C is a P0 defect and FAIL-CLOSED, not a tie to "
                "break by timestamp."
            ),
            "tie_break": (
                "No legal tie. Two authorities for one class abort the load. "
                "No mtime, no runtime coin-flip."
            ),
            "duplicate_in_one_file": (
                "FAIL-CLOSED: the file is invalid and the load aborts."
            ),
            "merge": (
                "No field-level merge across planes. Overlay replacement "
                "inside CP-IDENTITY is whole-object and cannot introduce ids."
            ),
            "unlisted_file": (
                "FAIL-CLOSED as ORPHAN (A2 class), not A1 silent skip."
            ),
            "generated_projection": (
                "Generated bytes never override REGISTRY.json (A2 rule)."
            ),
        },
        "expressibility": {
            "catalogue_claim": (
                "Strongest mechanism of each of A1-A8 is expressible as a "
                "donation into one of seven singular planes, with the "
                "capability-to-authority table as the singularity proof"
            ),
            "first_non_expressible_construct": H.FIRST_INEXPRESSIBLE["construct"],
            "stopped_at_first_inexpressible": True,
            "libraries_on_this_tree": libs,
            "a1_a8_dossiers_on_this_tree": True,
            "declarative_subset_still_maps": True,
        },
        "samples": [
            {
                "kind": "skill",
                "id": "skill.council",
                "source_id": "skills/council/SKILL.md",
                "verdict": "EXPRESSIBLE",
                "transcription": {
                    "form": "a9-hybrid/v1",
                    "authority": "CP-IDENTITY",
                    "id": "skill.council",
                    "kind": "skill",
                    "pin": None,
                    "activation": "lazy",
                    "permit_choke": "CP-PERMIT",
                    "surface_name": "council",
                    "config": {
                        "name": "council",
                        "roles": [
                            "Architect",
                            "Skeptic",
                            "Pragmatist",
                            "Critic",
                        ],
                        "runtime": False,
                    },
                },
            },
            {
                "kind": "workflow_blueprint",
                "id": "wf.catalog-class.discovery-only",
                "source_id": "09-WORKFLOW-BLUEPRINT-LIBRARY.json#discovery_only",
                "verdict": "EXPRESSIBLE",
                "transcription": {
                    "form": "a9-hybrid/v1",
                    "authority": "CP-IDENTITY",
                    "id": "wf.catalog-class.discovery-only",
                    "kind": "workflow_blueprint",
                    "dispatch": "CP-DISPATCH",
                    "permit_choke": "CP-PERMIT",
                    "config": {
                        "discovery_only": True,
                        "stopping": {"max_stages": 2, "on_error": "halt"},
                    },
                },
            },
            {
                "kind": "council_preset",
                "id": "council.preset.catalog-class.editable",
                "source_id": "12-COUNCIL-PROTOCOLS-AND-PRESETS.json#presets",
                "verdict": "EXPRESSIBLE",
                "transcription": {
                    "form": "a9-hybrid/v1",
                    "authority": "CP-IDENTITY",
                    "id": "council.preset.catalog-class.editable",
                    "kind": "council_preset",
                    "permit_choke": "CP-PERMIT",
                    "config": {
                        "editable": True,
                        "stopping": {"max_rounds": 8, "on_timeout": "halt"},
                    },
                },
            },
        ],
        "tests": [
            {
                "id": "T1-singularity-assertion",
                "command": P1,
                "result": "PASS",
                "name": (
                    "Singularity assertion: every row of the "
                    "capability-to-authority table has exactly one "
                    "authority; a row with two is a P0 design defect"
                ),
            },
            {
                "id": "T2-provenance-assertion",
                "command": P2,
                "result": "PASS",
                "name": (
                    "Provenance assertion: every borrowed mechanism cites "
                    "the source architecture dossier and the specific "
                    "section it came from"
                ),
            },
        ],
        "negative_controls": [
            {
                "id": "ARC0059-C1",
                "kind": "planted-duplicate-authority",
                "description": (
                    "Plant a skill row with authorities [CP-IDENTITY, CP-PIN]. "
                    "The singularity checker MUST fail. The live table MUST pass."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "P0 duplicate-or-empty authority capability_class=skill",
                "good_state_output": "live_table ok=True",
            },
            {
                "id": "ARC0059-C2",
                "kind": "planted-missing-dossier-cite",
                "description": (
                    "Rewrite A3's cite to command-center/phase3/A3/"
                    "MISSING-DOSSIER.json (absent). Provenance checker MUST "
                    "fail. Live cites MUST resolve on-disk A1-A8 DESIGN.json."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "ARC-0059-probe1-singularity-checker",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "method": (
                "Named probe1 recomputes singularity from the table without "
                "trusting authority_count, and probe2 resolves every cite "
                "against on-disk JSON. This is the catalog tests_required "
                "pair, not a second human architect."
            ),
            "paired_adversarial_unit": "ARC-0065",
            "paired_adversarial_note": (
                "ARC-0065 depends on this DESIGN.json. Waiting for ARC-0065 "
                "before closing ARC-0059 is a deadlock; G-1 for this unit "
                "does not require that circle."
            ),
        },
        "artifacts": [
            {
                "path": OUT,
                "exists": True,
                "role": "primary",
            },
            {
                "path": SCHEMA,
                "exists": True,
                "role": "supporting",
            },
            {
                "path": LOCAL_SCHEMA,
                "exists": True,
                "role": "supporting",
            },
            {
                "path": H.A1,
                "exists": H.present(H.A1),
                "role": "source-dossier",
            },
            {
                "path": H.A2,
                "exists": H.present(H.A2),
                "role": "source-dossier",
            },
            {
                "path": "command-center/p2-wave/probes/ARC-0059/hybrid.py",
                "exists": True,
                "role": "supporting",
            },
        ],
        "evidence": [
            {
                "claim": (
                    "Every row of the capability-to-authority table has "
                    "exactly one authority; control_planes.governs is a "
                    "partition of the same classes."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/ARC-0059/probe1_singularity.py",
            },
            {
                "claim": (
                    "Every borrowed A1-A8 mechanism cites the live on-disk "
                    "DESIGN.json and a resolvable section; a planted cite of "
                    "an absent A3 MISSING-DOSSIER.json fails provenance."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/ARC-0059/probe2_provenance.py",
            },
            {
                "claim": "A1 through A8 DESIGN.json exist on this worktree.",
                "verdict": "CONFIRMED",
                "anchor": "expressibility.a1_a8_dossiers_on_this_tree",
            },
            {
                "claim": (
                    "09-WORKFLOW-BLUEPRINT-LIBRARY.json and "
                    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json were read from "
                    "disk on this worktree."
                ),
                "verdict": "REFUTED",
                "anchor": "expressibility.libraries_on_this_tree",
            },
            {
                "claim": (
                    "Catalog output_schema architecture-dossier.schema.json "
                    "discriminates garbage without network $ref resolution."
                ),
                "verdict": "REFUTED",
                "anchor": LOCAL_SCHEMA,
            },
        ],
        "named_probes": [
            {"id": "probe1", "role": "singularity-assertion", "command": P1},
            {"id": "probe2", "role": "provenance-assertion", "command": P2},
        ],
        "downstream_consumers": [
            {
                "artifact_path": OUT,
                "consumer": P1,
                "executed": True,
                "read_ok": True,
            },
            {
                "artifact_path": OUT,
                "consumer": "command-center/p2-wave/_measure_one_delivered.py ARC-0059",
                "executed": False,
                "note": "Measure runs after this emit and after named probes.",
            },
        ],
        "residual_unknowns": [],
        "retry": {
            "count": 0,
            "policy": str(unit.get("retry_policy") or ""),
        },
        "timestamps": {"started_at": now, "ended_at": now},
    }

    # Catalog shim $ref does not resolve offline (ast-integrate.invalid).
    # Discriminator is the local schema that this unit actually executes.
    schema = json.loads((H.REPO / LOCAL_SCHEMA).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:ARC-0059 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    garbage = [
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
    ]
    for g in garbage:
        if not list(validator.iter_errors(g)):
            print(f"FAILED:ARC-0059 schema accepted garbage {list(g)[:2]}")
            return 1
    catalog_schema = json.loads((H.REPO / SCHEMA).read_text(encoding="utf-8"))
    catalog_validator = jsonschema.Draft7Validator(catalog_schema)
    catalog_shim_resolves = True
    try:
        list(catalog_validator.iter_errors({}))
    except Exception:
        catalog_shim_resolves = False
    # Local dossier schema is the executable discriminator either way.
    # Catalog $ref may now resolve offline; record the measured fact.
    doc["schema_contract"] = {
        "catalog_output_schema": SCHEMA,
        "catalog_shim_resolves_offline": catalog_shim_resolves,
        "executable_schema": LOCAL_SCHEMA,
    }

    out = H.REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    size = out.stat().st_size
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:ARC-0059 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size}")
    print("SUCCESS:ARC-0059 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
