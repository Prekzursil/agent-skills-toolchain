#!/usr/bin/env python3
"""Emit command-center/research/RES-0027.json from captured rails.

Does not author research-claim-record.schema.json (RES-0001 / no ADV circle).
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = REPO / "command-center/research/RES-0027.json"
SENTINEL = (
    "SUCCESS:RES-0027 in the receipt AND a block-composition summary citing "
    "source file:line plus one named non-adoptable feature"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0027/probe1_schema_citation.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0027/probe2_two_rail_overclaim.py"
)

SCHEMA_API = {
    "kind": "structured-api",
    "permalink": (
        "https://api.github.com/repos/continuedev/continue/contents/"
        "packages/config-yaml/src/schemas/index.ts?ref=main"
    ),
    "requested_url": (
        "https://api.github.com/repos/continuedev/continue/contents/"
        "packages/config-yaml/src/schemas/index.ts?ref=main"
    ),
    "final_url": (
        "https://api.github.com/repos/continuedev/continue/contents/"
        "packages/config-yaml/src/schemas/index.ts?ref=main"
    ),
    "fetch_timestamp": "2026-08-24T18:42:20Z",
    "http_status": 200,
    "sha256": "826c2ea99bbe8caabec2b148c3377ad406c31a3d98618e683818ee66a2a761bf",
    "captured_bytes": 12187,
    "snapshot": "command-center/p2-wave/probes/RES-0027/snapshots/github-api-schema.json",
    "instrument": "GitHub Contents API JSON envelope (path, sha, size, encoding=base64, content)",
}
UNROLL_API = {
    "kind": "structured-api",
    "permalink": (
        "https://api.github.com/repos/continuedev/continue/contents/"
        "packages/config-yaml/src/load/unroll.ts?ref=main"
    ),
    "requested_url": (
        "https://api.github.com/repos/continuedev/continue/contents/"
        "packages/config-yaml/src/load/unroll.ts?ref=main"
    ),
    "final_url": (
        "https://api.github.com/repos/continuedev/continue/contents/"
        "packages/config-yaml/src/load/unroll.ts?ref=main"
    ),
    "fetch_timestamp": "2026-08-24T18:42:20Z",
    "http_status": 200,
    "sha256": "bb1757f2a673b9b6a624edaebec20667e9ebb47a95a3f09235391eba4f9adccd",
    "captured_bytes": 35445,
    "snapshot": "command-center/p2-wave/probes/RES-0027/snapshots/github-api-unroll.json",
    "instrument": "GitHub Contents API JSON envelope for unroll.ts",
}
DOCS_REF = {
    "kind": "prose-source",
    "permalink": "https://docs.continue.dev/reference",
    "requested_url": "https://docs.continue.dev/reference",
    "final_url": "https://docs.continue.dev/reference",
    "fetch_timestamp": "2026-08-24T18:43:24Z",
    "http_status": 200,
    "sha256": "81c75a0e22699b4ba1e93e6af731f8be760d2c650f7d4e6191a93631dd2eb0a9",
    "captured_bytes": 196193,
    "snapshot": "command-center/p2-wave/probes/RES-0027/snapshots/docs-reference.html",
    "quote": (
        "Agents are composed of models, rules, and tools (MCP servers). "
        "The top-level properties in the config.yaml configuration file are: "
        "name (required) version (required) schema (required) models context "
        "rules prompts docs mcpServers data"
    ),
}
DOCS_BLOCKS = {
    "kind": "prose-source",
    "permalink": "https://docs.continue.dev/guides/configuring-models-rules-tools",
    "requested_url": "https://docs.continue.dev/guides/configuring-models-rules-tools",
    "final_url": "https://docs.continue.dev/guides/configuring-models-rules-tools",
    "fetch_timestamp": "2026-08-24T18:42:21Z",
    "http_status": 200,
    "sha256": "740ffd7bd9a7dedde18ef5ae613ce32e56d7d3033e1fb8c73238ed21228f602b",
    "captured_bytes": 84100,
    "snapshot": (
        "command-center/p2-wave/probes/RES-0027/snapshots/"
        "docs-configuring-models-rules-tools.html"
    ),
    "quote": (
        "Shared Blocks. Continue uses a slug in the format of owner/item-name "
        "to resolve blocks. Import community blocks using the uses syntax. "
        "Example: models: - uses: anthropic/claude-4-sonnet with: "
        "ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}"
    ),
}


def claim(
    cid: str,
    mechanism: str,
    lineage: str,
    tier: str,
    confidence: str,
    settling: str,
    verdict: str,
    caveat: str,
    rails: list,
    citable: bool,
    snapshot_sha256: str,
    extra: dict | None = None,
) -> dict:
    row = {
        "id": cid,
        "canonical_mechanism": mechanism,
        "source_lineage": lineage,
        "evidence_tier": tier,
        "confidence_band": confidence,
        "settling_probe": settling,
        "freshness_stamp": "2026-08-24T18:43:24Z",
        "snapshot_sha256": snapshot_sha256,
        "verdict": verdict,
        "strongest_caveat": caveat,
        "citable_as_measured_fact": citable,
        "rails": rails,
    }
    if extra:
        row.update(extra)
    return row


def document() -> dict:
    c1 = claim(
        "RES-0027-C1",
        (
            "Continue composes an assistant from config.yaml sections models, "
            "context, rules, prompts, docs, mcpServers, and data"
        ),
        (
            "GitHub Contents API for packages/config-yaml/src/schemas/index.ts "
            "(configYamlSchema) AND docs.continue.dev/reference prose listing "
            "the same top-level keys and 'Agents are composed of models, rules, "
            "and tools (MCP servers)'"
        ),
        "E2",
        "HIGH",
        P1,
        "CONFIRMED",
        (
            "Docs prose names 'tools (MCP servers)' while the source field is "
            "mcpServers; that is a naming alias, not a second composition model. "
            "Zod field names, not the HTML nav chrome, are the contract."
        ),
        [SCHEMA_API, DOCS_REF],
        True,
        SCHEMA_API["sha256"],
        {
            "source_file_line": "packages/config-yaml/src/schemas/index.ts:113",
            "pinned_permalink": (
                "https://github.com/continuedev/continue/blob/"
                "c75262e6928f554140867e939128d2504c5f14f1/"
                "packages/config-yaml/src/schemas/index.ts#L113-L153"
            ),
        },
    )
    c2 = claim(
        "RES-0027-C2",
        (
            "A publishable Continue Block is baseConfigYaml (name, version) AND "
            "exactly one of models|context|data|mcpServers|rules|prompts|docs "
            "with array length(1) (blockSchema)"
        ),
        (
            "Source-only: packages/config-yaml/src/schemas/index.ts:194-206 in "
            "the captured GitHub raw/API bytes. Docs describe shared blocks as "
            "importable owner/item-name units but do not state the Zod length(1) "
            "constraint."
        ),
        "E3",
        "MEDIUM",
        P1,
        "PARTIAL",
        (
            "A claim with one rail is E3 and may not be cited as measured fact. "
            "The singleton cardinality is read from source (tests_required) and "
            "is not independently restated by the prose rail."
        ),
        [
            {
                **SCHEMA_API,
                "note": (
                    "Same git object as the raw file; not a second independent "
                    "rail for the length(1) constraint."
                ),
            }
        ],
        False,
        SCHEMA_API["sha256"],
        {
            "source_file_line": "packages/config-yaml/src/schemas/index.ts:194",
            "pinned_permalink": (
                "https://github.com/continuedev/continue/blob/"
                "c75262e6928f554140867e939128d2504c5f14f1/"
                "packages/config-yaml/src/schemas/index.ts#L194-L206"
            ),
            "snippet": "export const blockSchema = baseConfigYamlSchema.and(",
        },
    )
    c3 = claim(
        "RES-0027-C3",
        (
            "Hub-and-local block composition is uses/with/override unrolling: "
            "unrollBlocks sees uses, decodePackageIdentifier, resolveBlock, "
            "registry.getContent, mergeOverrides"
        ),
        (
            "GitHub Contents API for packages/config-yaml/src/load/unroll.ts "
            "AND docs.continue.dev/guides/configuring-models-rules-tools Shared "
            "Blocks uses: owner/item-name prose"
        ),
        "E2",
        "HIGH",
        P2,
        "CONFIRMED",
        (
            "hub.continue.dev did not resolve on this host (urllib URLError and "
            "socket.gaierror, both ENOENT). Live hub catalog contents are not "
            "measured; the composition contract is the source+docs pair."
        ),
        [UNROLL_API, DOCS_BLOCKS],
        True,
        UNROLL_API["sha256"],
        {
            "source_file_line": "packages/config-yaml/src/load/unroll.ts:413",
            "pinned_permalink": (
                "https://github.com/continuedev/continue/blob/"
                "42030c70b69a7992b47c9d6be5a410443b552fa6/"
                "packages/config-yaml/src/load/unroll.ts#L413-L445"
            ),
            "resolveBlock_file_line": "packages/config-yaml/src/load/unroll.ts:719",
        },
    )
    c4 = claim(
        "RES-0027-C4",
        (
            "Named non-adoptable feature: Continue Hub uses-slug runtime "
            "unrolling cannot be adopted by this program's marketplace"
        ),
        (
            "Continue uses-unroll (C3 two rails) PLUS this tree's A2 generated-"
            "SSOT: registry.schema.json additionalProperties false, "
            "marketplace_entry.plugin_id, and emit_design.py:247 first "
            "inexpressible construct (opaque passthrough). Live "
            "phase3/A2/DESIGN.json is a stub and was not rewritten."
        ),
        "E2",
        "HIGH",
        P2,
        "CONFIRMED",
        (
            "The local half is this worktree's A2 contract (registry.schema.json "
            "plus emit_design.py:247), not a Continue prose page. The live "
            "phase3/A2/DESIGN.json is a stub and was not rewritten. If A2 were "
            "later redesigned to allow opaque YAML imports, this cannot-adopt "
            "verdict would need re-measurement. No such redesign is in scope "
            "(no ADV rebuild)."
        ),
        [UNROLL_API, DOCS_BLOCKS],
        True,
        UNROLL_API["sha256"],
        {
            "named_non_adoptable_feature": "Continue Hub uses-slug runtime unrolling",
            "local_controls": [
                {
                    "path": "command-center/p2-wave/probes/ARC-0010/registry.schema.json",
                    "line": 5,
                    "snippet": '"additionalProperties": false',
                },
                {
                    "path": "command-center/p2-wave/probes/ARC-0010/registry.schema.json",
                    "line": 57,
                    "snippet": '"plugin_id"',
                },
                {
                    "path": "command-center/p2-wave/probes/ARC-0010/emit_design.py",
                    "line": 247,
                    "snippet": (
                        "opaque passthrough / untyped blob field copied into "
                        "generated output"
                    ),
                    "note": (
                        "command-center/phase3/A2/DESIGN.json on this tree is a "
                        "60-line stub (restored_as_source_dossier_for ARC-0065) "
                        "and does not carry expressibility.first_non_expressible_"
                        "construct. Citing ARC-0010 emit_design.py:247 rather "
                        "than rewriting A2 DESIGN.json (no ADV rebuild)."
                    ),
                },
            ],
        },
    )
    c5 = claim(
        "RES-0027-C5",
        (
            "Hypothesis: Continue's hub-and-block composition is a better fit "
            "for this program's marketplace than a generated plugin package"
        ),
        (
            "C1+C3 Continue composition rails AND A2 plugin_manifest + "
            "marketplace_entry binding. The distinctive hub mechanism is "
            "runtime uses-unroll (C4), which A2 forbids."
        ),
        "E2",
        "HIGH",
        P2,
        "REFUTED",
        (
            "Typed block *kinds* (model/rule/prompt/MCP) resemble this program's "
            "already-typed skill/hook/rule/marketplace_entry classes; that "
            "resemblance is not evidence that hub uses-unroll is a better "
            "packaging model. Live hub UX was not observed (DNS NXDOMAIN)."
        ),
        [UNROLL_API, DOCS_BLOCKS],
        False,
        UNROLL_API["sha256"],
        {"defect_locus": "SENTENCE", "hypothesis_id": "RES-0027-H1"},
    )
    return {
        "unit_id": "RES-0027",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "receipt": SENTINEL,
        "title": "Teardown of Continue.dev assistant blocks and its config composition model",
        "question": (
            "How does Continue compose an assistant from blocks (models, rules, "
            "prompts, MCP), and is its hub-and-block composition model a better "
            "fit for this program's marketplace than a monolithic plugin package?"
        ),
        "answer": (
            "Continue composes an assistant by listing models, rules, prompts, "
            "mcpServers (and context/docs/data) in config.yaml, then unrolling "
            "each uses: owner/item-name slug through resolveBlock -> "
            "registry.getContent -> mergeOverrides "
            "(packages/config-yaml/src/schemas/index.ts:113 and "
            "packages/config-yaml/src/load/unroll.ts:413). Hub-and-block "
            "composition is not a better fit for this program's marketplace "
            "than the generated plugin package: the named non-adoptable feature "
            "is Continue Hub uses-slug runtime unrolling, which is an opaque "
            "passthrough of third-party YAML at load time, the construct A2 "
            "refuses (registry additionalProperties false; marketplace_entry "
            "requires plugin_id)."
        ),
        "hub_and_block_better_fit_than_plugin_package": "NO",
        "output_schema": "command-center/schema/research-claim-record.schema.json",
        "output_schema_present": False,
        "schema_note": (
            "RES-0001's eight schema files are absent on this tree. This record "
            "uses the field list from RES-0001 question_or_target (claim id, "
            "canonical mechanism, source lineage, evidence tier E1-E4, "
            "confidence band, named settling probe, contradiction/support "
            "edges, freshness stamp, snapshot sha256) without authoring those "
            "schema files (no ADV/RES-0001 rebuild circle)."
        ),
        "block_composition_summary": {
            "source_file": "packages/config-yaml/src/schemas/index.ts",
            "source_line": 194,
            "source_file_line": "packages/config-yaml/src/schemas/index.ts:194",
            "pinned_permalink": (
                "https://github.com/continuedev/continue/blob/"
                "c75262e6928f554140867e939128d2504c5f14f1/"
                "packages/config-yaml/src/schemas/index.ts#L194-L206"
            ),
            "snippet": "export const blockSchema = baseConfigYamlSchema.and(",
            "unroll_file_line": "packages/config-yaml/src/load/unroll.ts:413",
            "composition": (
                "configYamlSchema lists models, context, data, mcpServers, "
                "rules, prompts, docs; each item may be inline or a uses/with/"
                "override wrapper. unrollBlocks resolves uses via "
                "resolveBlock/registry.getContent and mergeOverrides. A Block "
                "in source is the base YAML object plus exactly one of those "
                "arrays (blockSchema at index.ts:194). The length(1) singleton "
                "is source-only (E3) and is not cited as measured fact."
            ),
            "named_non_adoptable_feature": "Continue Hub uses-slug runtime unrolling",
            "non_adoptable_why": (
                "resolveBlock fetches remote YAML by hub slug and merges it "
                "into the running assistant. That is opaque passthrough of "
                "untyped-to-A2 bytes. A2 generated-SSOT forbids that hatch "
                "(additionalProperties false) and binds each marketplace_entry "
                "to a plugin_id inside a generated plugin package rather than "
                "installing independent hub slugs at runtime."
            ),
        },
        "claims": [c1, c2, c3, c4, c5],
        "edges": [
            {
                "type": "supports",
                "from": "RES-0027-C1",
                "to": "RES-0027-C3",
            },
            {
                "type": "supports",
                "from": "RES-0027-C3",
                "to": "RES-0027-C4",
            },
            {
                "type": "contradicts",
                "from": "RES-0027-C4",
                "to": "RES-0027-C5",
                "note": (
                    "uses-slug unrolling is the hub-and-block distinctive and "
                    "is the named non-adoptable feature, so C5 (better-fit) is "
                    "REFUTED rather than CONFIRMED."
                ),
            },
            {
                "type": "scope-mismatch",
                "from": "RES-0027-C2",
                "to": "RES-0027-C1",
                "note": (
                    "C2's length(1) is a source-only cardinality on Block, not "
                    "a second independent measurement of C1's section list."
                ),
            },
        ],
        "measurements": {
            "hub_continue_dev": {
                "requested_url": "https://hub.continue.dev/",
                "fetch_timestamp": "2026-08-24T18:42:21Z",
                "http_status": None,
                "error": "URLError: [Errno -2] Name or service not known",
                "dns_second_signal": {
                    "instrument": "socket.getaddrinfo",
                    "host": "hub.continue.dev",
                    "error": "gaierror: [Errno -2] Name or service not known",
                },
                "classification": "source-unavailable",
            }
        },
        "tests": [
            {
                "id": "block-schema-from-source",
                "requirement": (
                    "read the block schema from source, not only from docs, "
                    "and cite the file:line"
                ),
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "non-adoptable-control",
                "requirement": (
                    "identify at least one composition feature this program "
                    "CANNOT adopt and say why"
                ),
                "command": P2,
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0027-probe2-two-rail-overclaim",
            "independent": True,
            "shown_conclusion_first": False,
            "verdict": "PASS",
            "defaulted_to_refuted_when_insufficient": True,
            "scope_not_agreement": True,
            "notes": (
                "REFUTED the better-fit hypothesis (C5). REFUTED live-hub "
                "catalog claims (DNS NXDOMAIN on two instruments). Surviving "
                "E2 claims keep two rails. length(1) stays E3/PARTIAL and is "
                "not citable as measured fact."
            ),
        },
        "artifacts": [
            {
                "path": "command-center/research/RES-0027.json",
                "exists": True,
                "role": "primary",
            },
            {
                "path": (
                    "command-center/p2-wave/probes/RES-0027/snapshots/"
                    "github-raw-block-schema.ts"
                ),
                "exists": True,
                "role": "captured-source",
            },
            {
                "path": (
                    "command-center/p2-wave/probes/RES-0027/snapshots/"
                    "github-raw-unroll.ts"
                ),
                "exists": True,
                "role": "captured-source",
            },
        ],
        "named_probes": [
            {"id": "probe1", "command": P1},
            {"id": "probe2", "command": P2},
        ],
        "dependencies_on_this_tree": {
            "RES-0001": "absent-schema-files-not-rebuilt",
            "RES-0003": "e-tier-grader-not-present-inline-two-rail-check-used",
            "RES-0004": "shared-snapshot-store-absent-per-unit-snapshots-used",
        },
        "strongest_surviving_counterargument": (
            "A marketplace of independently versioned typed blocks (without "
            "runtime remote YAML import) could still be a better packaging "
            "shape than a single plugin.json. This unit does not design that "
            "marketplace; it only measures Continue's actual composition "
            "contract and rejects adopting uses-slug unrolling."
        ),
    }


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = document()
    OUT.write_text(
        json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT.relative_to(REPO).as_posix()} bytes={OUT.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
