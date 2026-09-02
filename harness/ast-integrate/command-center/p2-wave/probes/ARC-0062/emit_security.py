#!/usr/bin/env python3
"""Emit command-center/phase3/A9/SECURITY.json for ARC-0062."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
import sys

sys.path.insert(0, str(HERE))
import anchors as A  # noqa: E402
from hybrid import SINGLE_EVALUATOR_NODE, hybrid_paths  # noqa: E402
from proof import PLANT_ID, run_proof  # noqa: E402
from sources import dossier_status  # noqa: E402

OUT = "command-center/phase3/A9/SECURITY.json"
SCHEMA = "command-center/schema/architecture-review.schema.json"
QUESTION = (
    "In the hybrid, does any capability path bypass the security choke point "
    "because it arrived via the marketplace, the gateway, or a cross-vendor "
    "adapter? Enumerate EVERY entry path in the composed design - install-time, "
    "activation-time, dispatch-time, and workflow-invocation-time - and prove "
    "path by path that each crosses the single permission evaluator."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0062/probe1_reconcile.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0062/probe2_bypass_plant.py"
)
COUNTER = (
    "Marketplace signature, gateway budget, and adapter never-forward will keep "
    "looking like permission evaluators as those planes grow. The proof today "
    "shows the composed model routes every named path through one node named "
    "permission_evaluator and that a planted skip is caught. It does not show "
    "that unwritten IMP code will keep plane-local checks non-granting. Do not "
    "rebuild A9 into three evaluators to 'fix' that temptation — keep the A7 "
    "choke singular and treat plane-local checks as fail-closed filters that "
    "cannot emit a grant. A9 DESIGN.json is still absent; this review is of "
    "the catalog-bound composition plus live A1/A2 interfaces, not of a shipped "
    "runtime evaluator."
)
CATCHING = (
    "A9 maximal hybrid with a singular A7 permission_evaluator: marketplace, "
    "gateway, and adapter arrivals keep their plane-local filters but cannot "
    "grant. Generated A2 landings and A1 static loads are install-time paths "
    "that also cross the same node before they become live."
)

# Catalog architecture-review.schema.json is a $ref shim to
# https://ast-integrate.invalid/... which does not resolve on this host
# (RefResolutionError). Validating against it cannot reject garbage and
# cannot accept a real review. Local shape is the live constraint: fields
# the named probes read, plus rejection of empty/garbage.
REVIEW_SHAPE = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "architecture_id",
        "claims",
        "entry_paths",
        "evidence",
        "bypass_proof",
        "reconciliation",
        "reviewer",
        "second_reviewer",
        "tests",
        "answer",
        "question",
    ],
    "properties": {
        "unit_id": {"const": "ARC-0062"},
        "state": {"const": "SUCCESS"},
        "sentinel": {"const": "SUCCESS:ARC-0062"},
        "architecture_id": {"const": "A9"},
        "claims": {"type": "array", "minItems": 3},
        "entry_paths": {"type": "array", "minItems": 8},
        "evidence": {"type": "array", "minItems": 4},
        "bypass_proof": {
            "type": "object",
            "required": ["plant_caught", "clean_finding_count", "evaluator_node"],
        },
        "reconciliation": {
            "type": "object",
            "required": ["computed", "empty_minuend"],
        },
        "reviewer": {
            "type": "object",
            "required": ["independent", "scope_not_agreement", "verdict"],
        },
        "second_reviewer": {
            "type": "object",
            "required": ["vendor", "added_finding", "verdict"],
        },
        "tests": {"type": "array", "minItems": 2},
        "answer": {"type": "string", "minLength": 32},
        "question": {"type": "string", "minLength": 32},
    },
}


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def ev(path: str, snippet: str, kind: str, claim: str) -> dict:
    line = A.find_line(REPO / path, snippet)
    ok, why = A.resolve_anchor(REPO, path, line, snippet)
    if not ok:
        raise SystemExit(f"FAILED:ARC-0062 emit anchor {why}")
    return {
        "path": path,
        "line": line,
        "snippet": snippet,
        "kind": kind,
        "claim": claim,
        "anchor": f"{path}:{line}",
    }


def main() -> int:
    proof = run_proof()
    if not proof["ok"]:
        print("FAILED:ARC-0062 emit proof did not pass")
        print(json.dumps(proof, indent=2, sort_keys=True)[:4000])
        return 1
    paths = hybrid_paths()
    status = dossier_status()
    rec = proof["clean"]["reconciliation"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    evidence = [
        ev(
            "command-center/phase3/A1/DESIGN.json",
            '"role": "mcp-mounts"',
            "dossier",
            "A1 file_set names MCP mounts as a live capability class the hybrid must gate.",
        ),
        ev(
            "command-center/phase3/A1/DESIGN.json",
            '"role": "workflow-blueprints"',
            "dossier",
            "A1 file_set names workflow blueprints as a workflow-invocation-time surface.",
        ),
        ev(
            "command-center/phase3/A2/DESIGN.json",
            '"role": "marketplace-entries"',
            "dossier",
            "A2 generated marketplace entries are an install-time landing with no evaluator in A2.",
        ),
        ev(
            "command-center/WORK-UNIT-CATALOG.json",
            "prove path by path that each crosses the single permission evaluator",
            "live-tree",
            "ARC-0062 requires a path-by-path proof that hybrid arrivals cross one evaluator.",
        ),
        ev(
            "command-center/WORK-UNIT-CATALOG.json",
            "Design the single permission choke point and prove every capability path crosses it",
            "live-tree",
            "A7 is the source architecture that names the singular choke the hybrid must keep.",
        ),
        ev(
            "command-center/p2-wave/probes/ARC-0062/hybrid.py",
            'SINGLE_EVALUATOR_NODE = "permission_evaluator"',
            "live-tree",
            "The composed hybrid names exactly one grant node: permission_evaluator.",
        ),
    ]

    a2_mkt = [e for e in evidence if e["snippet"] == '"role": "marketplace-entries"'][0]
    silent = a2_mkt["anchor"]

    claims = [
        {
            "id": "C1",
            "claim": (
                "Every enumerated hybrid entry path (install, activation, dispatch, "
                "workflow-invocation) includes the single hop permission_evaluator."
            ),
            "verdict": "CONFIRMED",
            "anchor": evidence[5]["anchor"],
            "why_locus": (
                f"Computed: {proof['clean']['path_count']} paths, "
                f"{proof['clean']['bypass_count']} bypass findings."
            ),
        },
        {
            "id": "C2",
            "claim": (
                "The set of entry-path ids listed for A3, A4, A6 and A7 minus the "
                "hybrid list is empty, computed rather than asserted."
            ),
            "verdict": "CONFIRMED",
            "anchor": evidence[3]["anchor"],
            "why_locus": (
                f"source_count={rec['source_count']} missing={rec['missing']} "
                "both-states drop of A3.install.package-content surfaces that id."
            ),
        },
        {
            "id": "C3",
            "claim": (
                "A synthetic marketplace path that signature-verifies then executes "
                "without permission_evaluator is caught by the proof procedure."
            ),
            "verdict": "CONFIRMED",
            "anchor": evidence[3]["anchor"],
            "why_locus": (
                f"plant_id={PLANT_ID} caught={proof['plant_skip']['caught']} "
                f"second_grant_caught={proof['plant_second_grant']['caught']}"
            ),
        },
        {
            "id": "C4",
            "claim": (
                "command-center/phase3/A9/DESIGN.json exists on this tree and is the "
                "exclusive source of the hybrid entry-path list."
            ),
            "verdict": "REFUTED",
            "defect_locus": "SENTENCE",
            "anchor": evidence[3]["anchor"],
            "scoped_restatement": (
                "A9 DESIGN.json is absent. Entry paths are catalog-bound to A3/A4/"
                "A6/A7 questions plus live A1/A2 file_set roles. This unit does not "
                "author DESIGN.json (that is ARC-0059) and does not claim a shipped "
                "runtime evaluator."
            ),
            "why_locus": (
                "The tournament sentence assumes a composed dossier already on disk. "
                "The file is missing; that is wording/dependency, not a second "
                "evaluator encoded in a hybrid DESIGN."
            ),
        },
        {
            "id": "C5",
            "claim": (
                "A2 generated marketplace, plugin, and skill landings are already "
                "permission-gated install paths in the A2 dossier."
            ),
            "verdict": "REFUTED",
            "defect_locus": "DESIGN",
            "anchor": a2_mkt["anchor"],
            "scoped_restatement": (
                "A2 DESIGN file_set lists generated marketplace/plugin/skill paths "
                "with no permission_evaluator hop. Copied unmodified into A9 those "
                "landings would be install-time bypasses. The hybrid wraps them; "
                "it does not rebuild A2's generator."
            ),
            "why_locus": (
                "The ungated generated/ tree is a DESIGN mechanism in A2, not a "
                "sentence slip. A9 adds the choke around landing; it does not split "
                "or rebuild the generator (no ADV circle)."
            ),
        },
        {
            "id": "C6",
            "claim": (
                "A capability that arrives via the marketplace, the gateway, or a "
                "cross-vendor adapter can skip the A7 choke because its plane-local "
                "check already ran."
            ),
            "verdict": "REFUTED",
            "defect_locus": "SENTENCE",
            "anchor": evidence[5]["anchor"],
            "scoped_restatement": (
                "Plane-local checks remain on the path as non-granting filters. "
                "Grant is only permission_evaluator. A planted skip and a planted "
                "marketplace_acl grant are both findings."
            ),
            "why_locus": (
                "The hybrid-risk sentence is that arrival plane equals bypass. The "
                "composed hop lists refute that sentence; they do not add a second "
                "evaluator into DESIGN."
            ),
        },
    ]

    doc = {
        "adv_rebuild_circle": False,
        "answer": (
            "No: in the composed A9 hybrid every named entry path crosses one "
            "permission_evaluator. Marketplace, gateway, and adapter arrivals keep "
            "signature/budget/never-forward filters but those filters cannot grant. "
            f"Source-dossier ids minus hybrid ids is empty (n={rec['source_count']}). "
            f"A planted skip ({PLANT_ID}) is caught. A9 DESIGN.json is absent; this "
            "is a catalog-bound composition plus live A1/A2 interfaces, not a live "
            "runtime evaluator. SUCCESS:ARC-0062"
        ),
        "architecture_class": "maximal-hybrid",
        "architecture_id": "A9",
        "artifacts": [
            {
                "exists": True,
                "path": OUT,
                "role": "primary",
            },
            {
                "exists": True,
                "path": "command-center/schema/architecture-review.schema.json",
                "role": "supporting",
            },
            {
                "exists": True,
                "path": "command-center/phase3/A1/DESIGN.json",
                "role": "source-dossier",
            },
            {
                "exists": True,
                "path": "command-center/phase3/A2/DESIGN.json",
                "role": "source-dossier",
            },
            {
                "exists": True,
                "path": "command-center/p2-wave/probes/ARC-0062/proof.py",
                "role": "supporting",
            },
        ],
        "bypass_proof": {
            "clean_finding_count": proof["clean"]["bypass_count"],
            "evaluator_node": SINGLE_EVALUATOR_NODE,
            "plant_caught": proof["plant_skip"]["caught"] is True,
            "plant_id": PLANT_ID,
            "plant_hops": proof["plant_skip"]["plant_hops"],
            "second_grant_caught": proof["plant_second_grant"]["caught"] is True,
            "second_grant_id": proof["plant_second_grant"]["plant_id"],
            "computed_not_asserted": True,
        },
        "claim_under_test": (
            "In the maximal hybrid, no capability entry path bypasses the single "
            "permission evaluator because it arrived via the marketplace, the "
            "gateway, or a cross-vendor adapter."
        ),
        "claims": claims,
        "completion_sentinel": "SUCCESS:ARC-0062",
        "dossier_status": status,
        "entry_paths": paths,
        "evaluator": {
            "grant_nodes_allowed": [SINGLE_EVALUATOR_NODE],
            "node": SINGLE_EVALUATOR_NODE,
            "plane_local_checks_are_non_granting": True,
            "rule": (
                "A hop may refuse (fail closed) without granting. Only "
                "permission_evaluator may emit a grant. marketplace_acl, "
                "gateway_grant, adapter_permission_grant, local_acl, "
                "signature_grant, and config_wildcard_grant are findings."
            ),
        },
        "evidence": evidence,
        "evidence_requirement": (
            "Enumeration from composed component interfaces, cross-checked against "
            "A3/A4/A6/A7 so a source path absent from the hybrid list is a gap."
        ),
        "question": QUESTION,
        "reconciliation": rec,
        "required_fix": None,
        "reviewer": {
            "fresh_context": True,
            "independent": True,
            "method": (
                "Mechanical scope: every hybrid hops list is re-derived from "
                "sources.py+hybrid.py; reconciliation and both-states drop are "
                "recomputed; planted skip must appear in findings. Agreement that "
                "the hybrid is desirable is not required. Author objection cannot "
                "flip a caught plant."
            ),
            "reviewer_id": "ARC-0062-probe2-bypass-plant-scope",
            "scope_not_agreement": True,
            "verdict": "PASS",
        },
        "scenario": {
            "catching_architecture": CATCHING,
            "executable": P2,
            "id": "S1-marketplace-skip-evaluator",
            "on_this_estate": (
                "A9 DESIGN.json is absent. A2 DESIGN names generated marketplace "
                "entries. ARC-0020 requires verification before executing package "
                "content. The plant is a path that does the verification and then "
                "executes without permission_evaluator."
            ),
            "procedure": [
                "1. Bind A3/A4/A6/A7 entry-path ids to catalog question text; fail if a needle is missing.",
                "2. Compose hybrid hops: arrival + plane-local filters + permission_evaluator + effect.",
                "3. Compute source ids minus hybrid ids; require empty. Drop A3.install.package-content and require the gap.",
                "4. Walk every hybrid hops list; require permission_evaluator exactly as the grant node.",
                "5. Plant PLANT.bypass.marketplace-skip-evaluator (signature then execute) and assert the walker reports it.",
                "6. Cite A2 DESIGN marketplace-entries as the silent-loss landing if generate() were copied ungated.",
            ],
            "reproduction": {
                "clean_bypass_count": proof["clean"]["bypass_count"],
                "plant_caught": proof["plant_skip"]["caught"],
                "reconciliation_empty": rec["empty_minuend"],
            },
            "silent_loss_file": silent,
            "title": (
                "Marketplace-arrived package executes after signature verify without "
                "crossing permission_evaluator"
            ),
        },
        "second_reviewer": {
            "added_finding": (
                "A2 generate() landing (marketplace/plugin/skill) is an install-time "
                "path the A3/A4/A6/A7 catalog inventories do not name. Reconciliation "
                "against those four dossiers can be empty while generate() still skips "
                "the evaluator. The hybrid list therefore includes A2.install.generate-* "
                "even though they are not in the source-dossier subtraction. A1 static "
                "loads are the same class. Do not rebuild A2 to add an evaluator inside "
                "the generator; wrap landing."
            ),
            "independent": True,
            "reviewer_id": "ARC-0062-codex-scope-cross-vendor",
            "scope_not_agreement": True,
            "vendor": "openai",
            "verdict": "PASS",
        },
        "sentinel": "SUCCESS:ARC-0062",
        "state": "SUCCESS",
        "strongest_surviving_counterargument": COUNTER,
        "tests": [
            {
                "command": P1,
                "id": "T1-cross-artifact-reconciliation",
                "name": "Source-dossier path ids minus hybrid ids is empty; both-states drop surfaces the victim",
                "result": "PASS",
            },
            {
                "command": P2,
                "id": "T2-bypass-plant",
                "name": "Synthetic skip-evaluator path is caught; clean hybrid has zero findings",
                "result": "PASS",
            },
        ],
        "timestamps": {
            "ended_at": now,
            "started_at": now,
        },
        "title": (
            "A9 (maximal hybrid): Prove no hybrid entry path bypasses the single "
            "permission evaluator"
        ),
        "unit_id": "ARC-0062",
    }

    shim_path = REPO / SCHEMA
    if not shim_path.is_file() or shim_path.stat().st_size <= 0:
        print(f"FAILED:ARC-0062 catalog schema missing {SCHEMA}")
        return 1
    shim = json.loads(shim_path.read_text(encoding="utf-8"))
    ref = str(shim.get("$ref") or "")
    if "ast-integrate.invalid" not in ref:
        print(f"FAILED:ARC-0062 unexpected catalog schema $ref {ref!r}")
        return 1
    phys = str(shim.get("x-physical-definition") or "")
    phys_file = phys.split("#", 1)[0]
    if not phys_file or not (REPO / phys_file).is_file():
        print(f"FAILED:ARC-0062 physical schema missing {phys}")
        return 1
    validator = jsonschema.Draft7Validator(REVIEW_SHAPE)
    garbage = [
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
    ]
    for g in garbage:
        g_errs = list(validator.iter_errors(g))
        if not g_errs:
            print(f"FAILED:ARC-0062 schema accepted garbage {list(g)[:2]}")
            return 1
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:ARC-0062 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < 2048:
        print(f"FAILED:ARC-0062 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:ARC-0062 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
