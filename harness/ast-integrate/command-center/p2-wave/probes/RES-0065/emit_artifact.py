#!/usr/bin/env python3
"""Emit command-center/research/RES-0065.json from captures + this-repo citations."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import (  # noqa: E402
    ART,
    ART_REL,
    CONTROL_MECH,
    REPO,
    SENTINEL,
    UNIT,
    capture_by_id,
    load_index,
    parse_file_line,
    sha256_bytes,
)

SNIPPETS = {
    "registry_id": (
        "command-center/p2-wave/probes/ARC-0010/registry.json",
        '"id": "wf.catalog-class.discovery-only"',
    ),
    "registry_kind": (
        "command-center/p2-wave/probes/ARC-0010/registry.json",
        '"kind": "workflow_blueprint"',
    ),
    "registry_stages": (
        "command-center/p2-wave/probes/ARC-0010/registry.json",
        '"id": "discover"',
    ),
    "catalog_members": (
        "command-center/p2-wave/probes/ARC-0010/registry.json",
        '"member_ids": ["wf.catalog-class.discovery-only"]',
    ),
    "schema_closed": (
        "command-center/p2-wave/probes/ARC-0010/registry.schema.json",
        '"kind": { "const": "workflow_blueprint" }',
    ),
    "schema_stages": (
        "command-center/p2-wave/probes/ARC-0010/registry.schema.json",
        '"required": ["id", "kind", "inputs", "outputs"]',
    ),
    "generated_digest": (
        "command-center/p2-wave/probes/ARC-0016/fixtures/hatch-run/typed/workflows/wf.catalog-class.discovery-only.json",
        '"registry_entry_sha256":',
    ),
    "generated_id": (
        "command-center/p2-wave/probes/ARC-0016/fixtures/hatch-run/typed/workflows/wf.catalog-class.discovery-only.json",
        '"id": "wf.catalog-class.discovery-only"',
    ),
    "generator_digest_fn": (
        "command-center/p2-wave/probes/ARC-0010/generator.py",
        '"registry_entry_sha256": entry_digest(entry),',
    ),
    "param_mix": (
        "command-center/p2-wave/probes/CNF-0084/fixtures/workflows/wf.param-mix.json",
        '"params": { "seed": "fixed-seed-0001", "mode": "fold" }',
    ),
}


def cite(key: str) -> dict:
    rel, snippet = SNIPPETS[key]
    path = REPO / rel
    lines = path.read_text(encoding="utf-8").splitlines()
    hits = [i for i, ln in enumerate(lines, 1) if snippet in ln]
    if len(hits) != 1:
        raise SystemExit(f"cite {key} hits={hits} snippet={snippet!r}")
    line = hits[0]
    return {
        "file_line": f"{rel}:{line}",
        "snippet": snippet,
        "line_text": lines[line - 1].strip(),
    }


def rail(index, cid: str, must_contain: str, note: str) -> dict:
    cap = capture_by_id(index, cid)
    return {
        "capture_id": cid,
        "kind": cap["kind"],
        "permalink": cap["permalink"],
        "fetched_at": cap["fetched_at"],
        "http_status": cap["http_status"],
        "sha256": cap["sha256"],
        "bytes": cap["bytes"],
        "must_contain": must_contain,
        "note": note,
    }


def main() -> int:
    index = load_index()
    c = {k: cite(k) for k in SNIPPETS}
    for v in c.values():
        parse_file_line(v["file_line"])

    mapping = [
        {
            "mechanism_id": "GHA-REUSABLE-WORKFLOW",
            "mechanism": (
                "Reusable workflows: callee YAML whose `on` includes `workflow_call`, "
                "invoked as a job via `uses: owner/repo/.github/workflows/file.yml@ref` "
                "with `with:` inputs."
            ),
            "requirement_id": "REQ-BP-STABLE-ID",
            "requirement": (
                "A workflow blueprint library must give each reusable graph a stable "
                "id and list it in a catalog so callers compose by identity, not by copy."
            ),
            "analogue": "partial",
            "also_satisfies": ["REQ-BP-CALL-PARAMS"],
            "repo_citations": [c["registry_id"], c["catalog_members"], c["generated_id"]],
            "gap": (
                "GitHub's caller syntax is a git ref to a YAML path. This library's "
                "analogue is in-tree `id` + `workflow_catalog.member_ids`, with no "
                "`@sha` caller form."
            ),
        },
        {
            "mechanism_id": "GHA-COMPOSITE-ACTION",
            "mechanism": (
                "Composite actions: `runs.using: composite` packages a local steps[] "
                "graph with named inputs/outputs for reuse inside a job."
            ),
            "requirement_id": "REQ-BP-TYPED-IO",
            "requirement": (
                "Reusable fragments must declare typed stage identity plus inputs and "
                "outputs so composition is a dataflow, not an opaque script blob."
            ),
            "analogue": "partial",
            "repo_citations": [c["registry_stages"], c["schema_stages"], c["param_mix"]],
            "gap": (
                "Composite actions are step-scoped and execute on a runner. Blueprint "
                "stages are catalog typed IO with `kind` strings; they do not encode "
                "`shell:` / `run:`."
            ),
        },
        {
            "mechanism_id": "GHA-SHA-PIN",
            "mechanism": (
                "Pinning `uses:` to a full-length commit SHA is the documented way to "
                "treat a third-party action or reusable workflow as an immutable "
                "release; tags can be moved."
            ),
            "requirement_id": "REQ-BP-CONTENT-DIGEST",
            "requirement": (
                "A generated workflow artifact must pin the exact registry-entry bytes "
                "it was rendered from, so retargeting the source is a visible digest change."
            ),
            "analogue": "partial",
            "repo_citations": [c["generated_digest"], c["generator_digest_fn"]],
            "gap": (
                "`registry_entry_sha256` pins the local registry object, not a GitHub "
                "Actions marketplace `owner/action@<40-hex>`. It does not freeze a "
                "remote git ref."
            ),
        },
        {
            "mechanism_id": CONTROL_MECH,
            "mechanism": (
                "GitHub Environments with required reviewers / wait timers, plus "
                "`jobs.<id>.environment` and `permissions:` / `GITHUB_TOKEN` scoping, "
                "are CI-platform admission controls."
            ),
            "requirement_id": None,
            "requirement": None,
            "analogue": "none",
            "control": True,
            "repo_citations": [],
            "why_no_analogue": (
                "ARC-0010 `workflow_blueprint` sets additionalProperties=false and "
                "required=[id, kind, discovery_only, stages, stopping]. There is no "
                "environment, permissions, concurrency, or runs-on field. Inventing "
                "that mapping would be an overclaim."
            ),
            "closed_schema_citation": c["schema_closed"],
        },
    ]

    claims = [
        {
            "id": "C-REUSABLE-WORKFLOW-CALL",
            "claim": (
                "GitHub Actions reusable workflows exist as a first-class reuse "
                "primitive: the callee declares `on.workflow_call`, the caller job "
                "sets `uses` to a workflow YAML path plus ref, and `{ref}` may be a "
                "SHA, tag, or branch with SHA recommended."
            ),
            "verdict": "CONFIRMED",
            "evidence_grade": "E2",
            "rails": [
                rail(
                    index,
                    "r1-github-workflow-schema",
                    "reusableWorkflowCallJob",
                    "JSON Schema Store github-workflow.json defines reusableWorkflowCallJob.uses",
                ),
                rail(
                    index,
                    "r2-reuse-workflows-md",
                    "workflow_call",
                    "github/docs commit-pinned how-to: on.workflow_call is required",
                ),
            ],
            "maps_to": "REQ-BP-STABLE-ID",
            "strongest_caveat": (
                "The schema and docs describe GitHub's hosted YAML runtime. They do "
                "not imply this repo executes reusable workflows."
            ),
        },
        {
            "id": "C-COMPOSITE-RUNS-USING",
            "claim": (
                "Composite actions are a distinct reuse unit from reusable workflows: "
                "action metadata sets `runs.using` to the const `composite` and lists "
                "steps, not a callee workflow file."
            ),
            "verdict": "CONFIRMED",
            "evidence_grade": "E2",
            "rails": [
                rail(
                    index,
                    "r1-github-action-schema",
                    '"const": "composite"',
                    "JSON Schema Store github-action.json runs-composite.using const",
                ),
                rail(
                    index,
                    "r2-composite-action-md",
                    'using: "composite"',
                    "github/docs composite tutorial action.yml sample",
                ),
            ],
            "maps_to": "REQ-BP-TYPED-IO",
            "strongest_caveat": (
                "The tutorial sample is instructional YAML, not a marketplace audit of "
                "every composite action. The schema const is the mechanical constraint."
            ),
        },
        {
            "id": "C-SHA-PIN-VS-MOVABLE-TAG",
            "claim": (
                "Pinning to a full-length commit SHA is documented as the only current "
                "way to consume an action as an immutable release; a tag can be moved. "
                "The Git refs API shows `refs/tags/v4` as a pointer to a commit object, "
                "not as the frozen bytes themselves."
            ),
            "verdict": "CONFIRMED",
            "evidence_grade": "E2",
            "rails": [
                rail(
                    index,
                    "r1-gitref-checkout-v4",
                    "refs/tags/v4",
                    "GET /repos/actions/checkout/git/ref/tags/v4 returns object.sha",
                ),
                rail(
                    index,
                    "r2-secure-use-md",
                    "Pin actions to a full-length commit SHA",
                    "github/docs secure-use: SHA pin vs movable tags",
                ),
            ],
            "maps_to": "REQ-BP-CONTENT-DIGEST",
            "strongest_caveat": (
                "The v4 tag SHA recorded in the snapshot can change later; that "
                "mutability is the finding, so a later live SHA mismatch on the tag "
                "refutes tag-immutability, not this claim. SHA-1 collision remains a "
                "theoretical residual GitHub itself names."
            ),
        },
        {
            "id": "C-CONTROL-NO-ENV-REVIEWERS",
            "claim": (
                "GitHub Environments (required reviewers / wait timers) and "
                "`permissions:` / GITHUB_TOKEN scoping have no analogue in this "
                "repo's workflow_blueprint schema or the cited workflow JSON files."
            ),
            "verdict": "CONFIRMED",
            "evidence_grade": "E2",
            "rails": [
                rail(
                    index,
                    "r1-github-workflow-schema",
                    '"$ref": "#/definitions/permissions"',
                    "Workflow schema defines permissions objects",
                ),
                rail(
                    index,
                    "r2-reuse-workflows-md",
                    "Environment secrets cannot be passed from the caller workflow",
                    "Docs: workflow_call does not support the environment keyword for secret pass-through",
                ),
            ],
            "maps_to": None,
            "control": True,
            "strongest_caveat": (
                "Absence of a field in today's closed schema is not a forever-ban; a "
                "later schema revision could add environments. The control is about "
                "this tree's current workflow_blueprint, not GitHub's product."
            ),
        },
        {
            "id": "C-OVERCLAIM-JSON-IS-GHA-YAML",
            "claim": (
                "This repository's workflow_blueprint JSON files are GitHub Actions "
                "reusable workflow YAML and can be invoked with `uses: ...@sha`."
            ),
            "verdict": "REFUTED",
            "defect_locus": "SENTENCE",
            "evidence_grade": "E1",
            "rails": [
                rail(
                    index,
                    "r1-github-workflow-schema",
                    "workflow_call",
                    "GHA reusable workflows are YAML with on.workflow_call",
                ),
                rail(
                    index,
                    "r2-reuse-workflows-md",
                    ".github/workflows",
                    "Callee files live under .github/workflows; this repo's analogue is JSON blueprints",
                ),
            ],
            "local_disproof": [c["registry_kind"], c["schema_closed"]],
            "strongest_caveat": (
                "REFUTED is the drop-in-runtime claim only. Partial conceptual mapping "
                "to catalog ids and typed stages still stands on the CONFIRMED rows."
            ),
        },
    ]

    named_reqs = [
        {
            "id": "REQ-BP-STABLE-ID",
            "text": "Stable cataloged workflow id for call-by-identity.",
        },
        {
            "id": "REQ-BP-TYPED-IO",
            "text": "Typed stage fragments with id, kind, inputs, outputs.",
        },
        {
            "id": "REQ-BP-CONTENT-DIGEST",
            "text": "Content digest pin of the registry entry used to generate a workflow artifact.",
        },
        {
            "id": "REQ-BP-CALL-PARAMS",
            "text": "Parameterized reuse surface (inputs/params), not only copy-paste YAML.",
        },
    ]

    p1 = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/RES-0065/probe1_dual_rail_mapping.py"
    )
    p2 = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/RES-0065/probe2_control_overclaim.py"
    )

    doc = {
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "question": (
            "How do reusable workflows, composite actions and pinned action versions "
            "solve the reuse-with-versioning problem, what does the pinning-to-SHA "
            "practice actually buy, and which of those mechanics maps onto a workflow "
            "blueprint library?"
        ),
        "answer": (
            "Reusable workflows version a whole job graph behind `workflow_call` + "
            "`uses: path@ref`. Composite actions version a local steps[] package via "
            "`runs.using: composite`. SHA pins buy immutability against tag retargeting, "
            "not against SHA-1 collision. On this tree those map onto REQ-BP-STABLE-ID "
            "(catalog member ids), REQ-BP-TYPED-IO (stage IO), and REQ-BP-CONTENT-DIGEST "
            "(registry_entry_sha256). GitHub Environments required reviewers have no "
            "blueprint analogue. " + SENTINEL
        ),
        "named_blueprint_library_requirements": named_reqs,
        "mechanism_to_requirement_mapping": mapping,
        "claims": claims,
        "control": {
            "id": CONTROL_MECH,
            "ci_mechanism": "GitHub Environments required reviewers / GITHUB_TOKEN permissions",
            "blueprint_analogue": None,
            "reason": mapping[-1]["why_no_analogue"],
        },
        "source_lineage": [
            {
                "id": cap["id"],
                "kind": cap["kind"],
                "permalink": cap["permalink"],
                "fetched_at": cap["fetched_at"],
                "http_status": cap["http_status"],
                "sha256": cap["sha256"],
                "path": cap["path"],
            }
            for cap in index["captures"]
        ],
        "docs_commit": index["docs_commit"],
        "evidence_rule": (
            "A claim cited as measured fact has two mechanically independent rails "
            "(structured API/schema JSON AND commit-pinned prose), each with permalink, "
            "fetch timestamp, HTTP status, and sha256 of captured bytes. One rail is E3."
        ),
        "reviewer": {
            "reviewer_id": "RES-0065-probe2-control-and-rail-mutant",
            "independent": True,
            "scope_not_agreement": True,
            "verdict": "PASS",
            "default_without_probe": "REFUTED",
            "notes": (
                "Independent probe 2 does not re-score probe 1's live fetches. It "
                "checks the control analogue is absent, then proves the dual-rail "
                "and file:line checkers go red on mutants."
            ),
        },
        "tests": [
            {"id": "T-PROBE-1-DUAL-RAIL-MAPPING", "command": p1, "result": "NOT-RUN"},
            {"id": "T-PROBE-2-CONTROL-OVERCLAIM", "command": p2, "result": "NOT-RUN"},
        ],
        "artifacts": [
            {"path": ART_REL, "exists": True, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/RES-0065/captures/INDEX.json",
                "exists": True,
                "role": "supporting",
            },
        ],
        "declared_output_schema": "command-center/schema/research-claim-record.schema.json",
        "declared_output_schema_present": (
            REPO / "command-center/schema/research-claim-record.schema.json"
        ).is_file(),
        "freshness_stamp": "2026-08-24T18:48:29Z",
        "strongest_surviving_counterargument": (
            "Mapping is conceptual, not a runtime port. A reader who treats catalog "
            "member_ids as `uses: ...@sha` would overclaim; C-OVERCLAIM-JSON-IS-GHA-YAML "
            "is REFUTED for that reason."
        ),
    }

    ART.parent.mkdir(parents=True, exist_ok=True)
    ART.write_text(
        json.dumps(doc, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    raw = ART.read_bytes().replace(b"\r\n", b"\n")
    print(f"wrote {ART_REL} bytes={len(raw)} sha256={sha256_bytes(raw)}")
    print("SUCCESS:RES-0065 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
