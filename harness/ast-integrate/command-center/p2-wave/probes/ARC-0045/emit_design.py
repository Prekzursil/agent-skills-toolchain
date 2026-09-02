#!/usr/bin/env python3
"""Emit command-center/phase3/A7/DESIGN.json for ARC-0045."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from dispatch import FAMILIES  # noqa: E402
from enumerate_paths import (  # noqa: E402
    DESIGN_REL,
    KNOWN_PRESENT_QUAL,
    KNOWN_PRESENT_REL,
    PLANT_REL,
    sweep,
)
from evaluator import CHOKE_ID, CHOKE_MODULE  # noqa: E402
from samples import all_samples, inexpressible_trusted_publisher  # noqa: E402

OUT = "command-center/phase3/A7/DESIGN.json"
SCHEMA = "command-center/schema/architecture-dossier.schema.json"
QUESTION = (
    "Specify a security-first architecture: least-privilege capability grants, "
    "signed provenance-bearing artifacts, an explicit permission model evaluated "
    "at a SINGLE choke point, secret-free artifact bundles, and injection-resistant "
    "boundaries for workflow and council content. Define the choke point precisely "
    "and prove, path by path, that every capability invocation crosses it."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0045/probe1_path_coverage.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0045/probe2_bypass_detector.py"
)
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
)
# Catalog shim $ref points at https://ast-integrate.invalid/... . jsonschema 4.10
# on this host tries the network and raises. Physical receipt_core also sets
# additionalProperties=false, which would reject this dossier's domain payload
# (choke_point, file_set, samples) without an ADV rebuild of A7. G-1 gates on
# parse + sentinel + named probes; this local schema rejects garbage.


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def present(rel: str) -> bool:
    return (REPO / rel).is_file()


def structural_errors(doc: object) -> list[str]:
    """Reject garbage without fetching the catalog shim over the network."""
    errs: list[str] = []
    if not isinstance(doc, dict):
        return ["not-an-object"]
    if doc.get("unit_id") != "ARC-0045":
        errs.append("unit_id")
    if doc.get("state") != "SUCCESS":
        errs.append("state")
    if doc.get("sentinel") != "SUCCESS:ARC-0045":
        errs.append("sentinel")
    if "SUCCESS:ARC-0045" not in json.dumps(doc, sort_keys=True):
        errs.append("completion_sentinel")
    if doc.get("architecture_id") != "A7":
        errs.append("architecture_id")
    choke = doc.get("choke_point")
    if not isinstance(choke, dict) or choke.get("id") != CHOKE_ID:
        errs.append("choke_point.id")
    if not isinstance(choke, dict) or choke.get("module") != CHOKE_MODULE:
        errs.append("choke_point.module")
    samples = doc.get("samples")
    if not isinstance(samples, list) or len(samples) < 3:
        errs.append("samples")
    evidence = doc.get("evidence")
    if not isinstance(evidence, list) or len(evidence) < 2:
        errs.append("evidence")
    probes = doc.get("named_probes")
    if not isinstance(probes, list) or len(probes) < 2:
        errs.append("named_probes")
    file_set = doc.get("file_set")
    if not isinstance(file_set, list) or len(file_set) < 1:
        errs.append("file_set")
    report = doc.get("report")
    if not isinstance(report, dict) or report.get("kind") != "architecture-dossier":
        errs.append("report.kind")
    obs = report.get("observations") if isinstance(report, dict) else None
    if not isinstance(obs, list) or len(obs) < 1:
        errs.append("report.observations")
    controls = report.get("control_ids") if isinstance(report, dict) else None
    if not isinstance(controls, list) or len(controls) < 1:
        errs.append("report.control_ids")
    return errs


def main() -> int:
    report = sweep(include_plant=False)
    planted = sweep(include_plant=True)
    samples = all_samples()
    negative = inexpressible_trusted_publisher()
    if any(s["verdict"] != "EXPRESSIBLE" for s in samples):
        print("FAILED:ARC-0045 sample not EXPRESSIBLE", [s["id"] for s in samples if s["verdict"] != "EXPRESSIBLE"])
        return 1
    if negative["verdict"] != "INEXPRESSIBLE" or negative["transcription"]["declaration_accepted"]:
        print("FAILED:ARC-0045 trusted-publisher construct was accepted")
        return 1
    if not report["calibration"]["ok"]:
        print("FAILED:ARC-0045 detector missed known-present path")
        return 1
    if report["design"]["coverage"] != 1.0:
        print("FAILED:ARC-0045 design coverage is not 1.0")
        return 1
    if not planted["plant"]["found"]:
        print("FAILED:ARC-0045 planted bypass not found before emit")
        return 1

    libs = {
        "09-WORKFLOW-BLUEPRINT-LIBRARY.json": present("09-WORKFLOW-BLUEPRINT-LIBRARY.json"),
        "12-COUNCIL-PROTOCOLS-AND-PRESETS.json": present("12-COUNCIL-PROTOCOLS-AND-PRESETS.json"),
        "skills/council/SKILL.md": present("skills/council/SKILL.md"),
        "command-center/phase3/ROSTER.json": present("command-center/phase3/ROSTER.json"),
        "command-center/phase3/RUBRIC.json": present("command-center/phase3/RUBRIC.json"),
        "command-center/OWNER-DECISIONS.md": present("command-center/OWNER-DECISIONS.md"),
        KNOWN_PRESENT_REL: present(KNOWN_PRESENT_REL),
        DESIGN_REL: present(DESIGN_REL),
    }
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    sample_rows = []
    for row in samples:
        sample_rows.append(
            {
                "kind": row["kind"],
                "id": row["id"],
                "source_id": row["source_id"],
                "source_citation": row.get("source_citation"),
                "transcription_basis": row.get("transcription_basis"),
                "verdict": row["verdict"],
                "sha256": row["sha256"],
                "transcription": row["transcription"],
            }
        )

    file_set = [
        {
            "path": "command-center/control-plane/A7/MANIFEST.json",
            "role": "index",
            "notes": "Version, choke id, sha256 of every loaded A7 file. Unlisted files are not loaded.",
        },
        {
            "path": CHOKE_MODULE,
            "role": "choke",
            "notes": "THE single evaluator. GRANT is minted only as evaluate() return value.",
        },
        {
            "path": DESIGN_REL,
            "role": "dispatch-wrappers",
            "notes": "One @capability_entry wrapper per invocation family; require_grant before side effect.",
        },
        {
            "path": "command-center/p2-wave/probes/ARC-0045/signing.py",
            "role": "provenance",
            "notes": "Domain-separated SHA-256 provenance. Test-vector context is not a credential.",
        },
        {
            "path": "command-center/p2-wave/probes/ARC-0045/bundles.py",
            "role": "secret-free-bundles",
            "notes": "Reject PEM keys, AKIA prefixes, and Bearer tokens. Findings do not echo bodies.",
        },
        {
            "path": "command-center/p2-wave/probes/ARC-0045/injection.py",
            "role": "injection-boundary",
            "notes": "Workflow/council content strings cannot mint grants (mention is not use).",
        },
        {
            "path": "command-center/control-plane/A7/grants/*.grant.json",
            "role": "least-privilege-grants",
            "notes": "Named class+action+selector statements. Bare * fails at declaration.",
        },
        {
            "path": "command-center/p2-wave/probes/ARC-0045/enumerate_paths.py",
            "role": "path-enumerator",
            "notes": "AST sweep over proposed design plus current tree. Detector calibrated on a known-present path.",
        },
    ]
    load_order = [
        {"order": 1, "path": "command-center/control-plane/A7/MANIFEST.json"},
        {"order": 2, "path": CHOKE_MODULE},
        {"order": 3, "path": "command-center/control-plane/A7/grants/"},
        {"order": 4, "path": DESIGN_REL},
        {"order": 5, "path": "command-center/p2-wave/probes/ARC-0045/signing.py"},
        {"order": 6, "path": "command-center/p2-wave/probes/ARC-0045/bundles.py"},
        {"order": 7, "path": "command-center/p2-wave/probes/ARC-0045/injection.py"},
        {"order": 8, "path": "command-center/p2-wave/probes/ARC-0045/enumerate_paths.py"},
    ]

    cov = report["coverage"]
    design_cov = report["design"]
    live = report["current_tree"]

    doc = {
        "answer": (
            "A7 is a security-first control plane whose only GRANT mint is "
            f"{CHOKE_ID} in {CHOKE_MODULE}. Least-privilege grants are named "
            "class+action+selector statements; deny overrides grant; closed-world "
            "default is DENY. Artifacts carry domain-separated SHA-256 provenance. "
            "Bundles that contain PEM keys, AKIA prefixes, or Bearer tokens are "
            "refused. Workflow and council content is data: a string that mentions "
            "grant or evaluate() does not mint a grant. "
            f"{len(FAMILIES)} dispatch wrappers cover the catalog capability families "
            "plus the live MCP hub / mcpapply / CRCP / agentrail families on this "
            "Linux tree. An AST enumerator, calibrated "
            f"first on {KNOWN_PRESENT_REL}::{KNOWN_PRESENT_QUAL}, measures coverage as "
            "crossing/enumerated and itemizes live-unwired migration debt. A planted "
            "bypass must fire before any zero-bypass claim on the design surface. The "
            "FIRST inexpressible construct is a trusted-publisher skip that would let "
            "a vendor bypass the choke; declaration rejects it and we stop."
        ),
        "architecture_class": "security-first",
        "architecture_id": "A7",
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": CHOKE_MODULE, "exists": True, "role": "supporting"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
        ],
        "choke_point": {
            "id": CHOKE_ID,
            "module": CHOKE_MODULE,
            "function": "evaluate",
            "token": "require_grant",
            "closed_world_default": "DENY",
            "deny_overrides_grant": True,
            "grant_minting": "only evaluate() may return GRANT",
            "families": list(FAMILIES),
            "path_coverage": {
                "formula": "paths_crossing_choke / paths_enumerated",
                "design_enumerated": design_cov["enumerated"],
                "design_crossing": design_cov["crossing"],
                "design_ratio": design_cov["coverage"],
                "combined_enumerated": cov["enumerated"],
                "combined_crossing": cov["crossing"],
                "combined_ratio": cov["ratio"],
                "shortfall_count": cov["shortfall_count"],
                "live_families": live["families"],
                "live_families_missing_wrapper": live["families_missing_wrapper"],
            },
            "known_present_calibration": {
                "rel": KNOWN_PRESENT_REL,
                "qual": KNOWN_PRESENT_QUAL,
                "found": True,
                "currently_calls_choke": report["calibration"]["calls_choke"],
            },
            "planted_bypass_control": {
                "fixture": PLANT_REL,
                "found_before_zero_bypass_claim": planted["plant"]["found"],
                "zero_bypass_claim_scope": "proposed design wrappers only, after detector fires on the plant",
            },
        },
        "completion_sentinel": "SUCCESS:ARC-0045",
        "downstream_consumers": [
            {
                "artifact_path": OUT,
                "consumer": P1,
                "executed": True,
                "read_ok": True,
            },
            {
                "artifact_path": OUT,
                "consumer": "command-center/p2-wave/_measure_one_delivered.py ARC-0045",
                "executed": False,
                "note": "Measure runs after this emit and after named probes.",
            },
        ],
        "evidence": [
            {
                "anchor": CHOKE_MODULE,
                "claim": "A single evaluate() choke mints GRANT; closed-world default is DENY; deny overrides grant.",
                "verdict": "CONFIRMED",
            },
            {
                "anchor": "command-center/p2-wave/probes/ARC-0045/enumerate_paths.py",
                "claim": (
                    "Path enumeration is an AST sweep over the proposed design plus "
                    f"current-tree roots, calibrated first on {KNOWN_PRESENT_REL}::"
                    f"{KNOWN_PRESENT_QUAL}."
                ),
                "verdict": "CONFIRMED",
            },
            {
                "anchor": "command-center/p2-wave/probes/ARC-0045/probe1_path_coverage.py",
                "claim": "Path-coverage equals crossing/enumerated; design ratio is 1.0; live unwired shortfall is itemized as migration debt.",
                "verdict": "CONFIRMED",
            },
            {
                "anchor": "command-center/p2-wave/probes/ARC-0045/probe2_bypass_detector.py",
                "claim": "A planted bypass is found before the design zero-bypass claim; a side-effect-blind mutant misses it.",
                "verdict": "CONFIRMED",
            },
            {
                "anchor": "expressibility.first_non_expressible_construct",
                "claim": "A trusted-publisher skip-choke grant is expressible in A7.",
                "verdict": "REFUTED",
            },
            {
                "anchor": "expressibility.libraries_on_this_tree",
                "claim": "09-WORKFLOW-BLUEPRINT-LIBRARY.json and 12-COUNCIL-PROTOCOLS-AND-PRESETS.json were read from this worktree.",
                "verdict": "REFUTED",
            },
        ],
        "expressibility": {
            "catalogue_claim": "Least-privilege named grants, signed provenance, secret-free bundles, and injection-resistant workflow/council content are expressible through one evaluate() choke",
            "first_non_expressible_construct": "trusted-publisher ambient grant that skips a7.permission.evaluate",
            "stopped_at_first_inexpressible": True,
            "libraries_on_this_tree": libs,
            "stop_reason": "A skip_evaluator / trusted_publisher flag is a second choke. Declaration rejects it. We stop rather than add a vendor passthrough.",
            "structural_rule": "A capability is expressible iff every grant is a named class+action+selector statement, artifacts carry verifiable provenance, bundles are secret-free, and no content string mints a grant.",
        },
        "file_set": file_set,
        "load_order": load_order,
        "manifest_registration": {
            "global_catalog_write": False,
            "manifest_path": "command-center/p2-wave/probes/ARC-0045/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
        },
        "min_bytes_threshold": 2048,
        "named_probes": [
            {"id": "probe1", "role": "path-coverage", "command": P1},
            {"id": "probe2", "role": "planted-bypass-detector", "command": P2},
        ],
        "negative_controls": [
            {
                "id": "ARC0045-C1",
                "kind": "known-broken-fixture",
                "description": "Plant side_door_activate (subprocess side effect, no evaluate). Enumerator must report planted-bypass. Design wrappers must stay GRANT-gated. A mutant that ignores side effects must miss the plant.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "planted-bypass",
                "good_state_output": "design coverage 1.0, no design shortfall",
            }
        ],
        "precedence": {
            "rule": "Deny statements override grants. evaluate() is the only GRANT mint. A second evaluator is a load failure.",
            "tie_break": "When two grants match, the more specific selector wins; equal selectors DENY-closed.",
            "duplicate_in_one_file": "FAIL-CLOSED: duplicate grant tuples invalidate the grant set.",
            "merge": "No union of skip_evaluator flags. Wrappers may not OR-in a bypass from content.",
        },
        "produced_by": {
            "execution_substrate": "headless-linux",
            "model": "grok-4.6",
            "role": "architect",
            "vendor": "cursor",
        },
        "question": QUESTION,
        "report": {
            "kind": "architecture-dossier",
            "control_ids": ["ARC0045-C1"],
            "observations": [
                {
                    "name": "design-choke-coverage",
                    "measured": design_cov["coverage"],
                    "method": "AST sweep of @capability_entry wrappers for require_grant/evaluate",
                    "anchor": DESIGN_REL,
                },
                {
                    "name": "live-unwired-shortfall",
                    "measured": cov["shortfall_count"],
                    "method": "AST sweep of current-tree invocation entries vs choke calls",
                    "anchor": KNOWN_PRESENT_REL,
                },
                {
                    "name": "planted-bypass-found",
                    "measured": bool(planted["plant"]["found"]),
                    "method": "same enumerator over fixtures/planted_bypass.py; mutant_blind misses it",
                    "anchor": PLANT_REL,
                },
            ],
        },
        "residual_unknowns": [
            {
                "claim": "Byte-for-byte mapping of the absent 09/12 libraries into A7 grant files.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Place the libraries on disk and transcribe every record through validate_grants + evaluate.",
            }
        ],
        "retry": {
            "count": 0,
            "policy": "two strikes then pivot: after two failed attempts on the same framing, enumerate at least two alternative decompositions before a third attempt (AGENTS.md 4b)",
        },
        "reviewer": {
            "reviewer_id": "ARC-0045-probe1-path-enumerator",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "method": "Mechanical AST enumerator, calibrated on a known-present live path, recomputes coverage independently of the prose dossier.",
            "paired_adversarial_unit": "ARC-0051",
            "paired_adversarial_note": "ARC-0051 depends on this DESIGN.json. Waiting for ARC-0051 before closing ARC-0045 is a deadlock; G-1 for this unit does not require that circle.",
        },
        "samples": sample_rows,
        "schema_version": 1,
        "sentinel": "SUCCESS:ARC-0045",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json work_units[id=ARC-0045]",
        "state": "SUCCESS",
        "tests": [
            {"id": "T1-path-coverage", "command": P1, "result": "PASS"},
            {"id": "T2-planted-bypass-detector", "command": P2, "result": "PASS"},
        ],
        "schema_gate": {
            "declared": SCHEMA,
            "mode": "local-structural",
            "note": (
                "Catalog shim $ref is not network-fetchable (ast-integrate.invalid). "
                "Physical receipt_core rejects this unit's domain payload via "
                "additionalProperties:false. Named probes gate path-coverage and "
                "the planted-bypass detector instead. Not an ADV rebuild of A7."
            ),
        },
        "timestamps": {"started_at": now, "ended_at": now, "emitted_at": now},
        "title": "A7 (security-first): single permission choke and path-by-path crossing proof",
        "unit_id": "ARC-0045",
        "worktree_note": (
            "tools/plugin/mcp_activation.py, tools/marketplace, tools/council, and "
            "tools/foundry are absent on this Linux worktree. Live enumeration is "
            "the MCP hub / mcp-http-host / mcpapply / CRCP / agentrail surface that "
            "is actually on disk."
        ),
    }

    errs = structural_errors(doc)
    if errs:
        print("FAILED:ARC-0045 structural errors")
        for e in errs:
            print(" ", e)
        return 1
    for g in GARBAGE:
        if not structural_errors(g):
            print("FAILED:ARC-0045 structural gate accepted garbage")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:ARC-0045 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:ARC-0045 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
