"""The 21 program stopping conditions (spec 11376-11398).

_USER-PROMPTS.md is absent on this worktree. Each text is pinned to a catalog
quote where one exists; reconstructed wording is labelled catalog-derived so a
row never pretends to be a verbatim file read of the spec.
"""
from __future__ import annotations

EVIDENCE_SCHEMA = "stopping-condition-evidence/v1"
PACKET_SCHEMA = "owner-decision-packet/v1"
STOP_DIR = "command-center/receipts/stopping"
REL0003 = "command-center/receipts/REL-0003.json"

# One condition per spec line 11378-11398.
CONDITIONS: list[dict] = [
    {
        "id": 1,
        "spec_line": 11378,
        "text": (
            "Every selected option id is in exactly one terminal state: "
            "IMPLEMENTED, SUPERSEDED, or REJECTED-WITH-OWNER-REASONING."
        ),
        "text_provenance": "catalog-quote",
        "catalog_anchor": "WORK-UNIT-CATALOG.json SYN-0041 / ARC-0111",
        "evidence_path": f"{STOP_DIR}/SC-01.json",
    },
    {
        "id": 2,
        "spec_line": 11379,
        "text": (
            "Every extracted owner requirement is bound to a work unit or an "
            "explicit residual; no requirement silently disappeared."
        ),
        "text_provenance": "catalog-derived",
        "catalog_anchor": "WORK-UNIT-CATALOG.json CC-0024 / BLD-0063",
        "evidence_path": f"{STOP_DIR}/SC-02.json",
    },
    {
        "id": 3,
        "spec_line": 11380,
        "text": (
            "Cited greens are first-run stable: rerun-until-green laundering "
            "does not count as a pass."
        ),
        "text_provenance": "catalog-derived",
        "catalog_anchor": "WORK-UNIT-CATALOG.json ADV-0090 spec_anchor 11380",
        "evidence_path": f"{STOP_DIR}/SC-03.json",
    },
    {
        "id": 4,
        "spec_line": 11381,
        "text": "No required test is red.",
        "text_provenance": "catalog-quote",
        "catalog_anchor": "WORK-UNIT-CATALOG.json SYN-0043 tests_required",
        "evidence_path": f"{STOP_DIR}/SC-04.json",
    },
    {
        "id": 5,
        "spec_line": 11382,
        "text": (
            "Mutation and negative-control coverage demonstrate detector validity."
        ),
        "text_provenance": "catalog-quote",
        "catalog_anchor": "WORK-UNIT-CATALOG.json TST-034x / CC-0014 :11382",
        "evidence_path": f"{STOP_DIR}/SC-05.json",
    },
    {
        "id": 6,
        "spec_line": 11383,
        "text": (
            "Every load-bearing claim carries two mechanically independent signals."
        ),
        "text_provenance": "catalog-derived",
        "catalog_anchor": "WORK-UNIT-CATALOG.json defaults.evidence_requirement",
        "evidence_path": f"{STOP_DIR}/SC-06.json",
    },
    {
        "id": 7,
        "spec_line": 11384,
        "text": (
            "Compatibility-matrix cells are evidence-backed; an untested cell is "
            "never read as a pass."
        ),
        "text_provenance": "catalog-derived",
        "catalog_anchor": "WORK-UNIT-CATALOG.json ARC-0095 inputs :11384",
        "evidence_path": f"{STOP_DIR}/SC-07.json",
    },
    {
        "id": 8,
        "spec_line": 11385,
        "text": (
            "Benchmark results show the intended improvement without material "
            "regression."
        ),
        "text_provenance": "catalog-quote",
        "catalog_anchor": "WORK-UNIT-CATALOG.json :11385 condition 8",
        "evidence_path": f"{STOP_DIR}/SC-08.json",
    },
    {
        "id": 9,
        "spec_line": 11386,
        "text": (
            "No data loss occurs across install, upgrade, rollback and uninstall."
        ),
        "text_provenance": "catalog-derived",
        "catalog_anchor": "WORK-UNIT-CATALOG.json REL-0008 / :11132",
        "evidence_path": f"{STOP_DIR}/SC-09.json",
    },
    {
        "id": 10,
        "spec_line": 11387,
        "text": (
            "Licence terms of shipped components are established; UNKNOWN entries "
            "are listed, never omitted."
        ),
        "text_provenance": "catalog-derived",
        "catalog_anchor": "WORK-UNIT-CATALOG.json REL-0013",
        "evidence_path": f"{STOP_DIR}/SC-10.json",
    },
    {
        "id": 11,
        "spec_line": 11388,
        "text": (
            "All required gates pass on a fresh release-time scan; a stored green "
            "is not reused."
        ),
        "text_provenance": "catalog-quote",
        "catalog_anchor": "WORK-UNIT-CATALOG.json ADV-0016 spec_anchor 11388 / REL-0014",
        "evidence_path": f"{STOP_DIR}/SC-11.json",
    },
    {
        "id": 12,
        "spec_line": 11389,
        "text": "Docs and code agree.",
        "text_provenance": "catalog-quote",
        "catalog_anchor": "WORK-UNIT-CATALOG.json :11389 condition 12",
        "evidence_path": f"{STOP_DIR}/SC-12.json",
    },
    {
        "id": 13,
        "spec_line": 11390,
        "text": "Release/canary succeeds.",
        "text_provenance": "catalog-quote",
        "catalog_anchor": "WORK-UNIT-CATALOG.json REL-0003 / :11390",
        "evidence_path": REL0003,
        "special": "rel-0003-ruling",
    },
    {
        "id": 14,
        "spec_line": 11391,
        "text": "Rollback is tested.",
        "text_provenance": "catalog-quote",
        "catalog_anchor": "WORK-UNIT-CATALOG.json :11391 / IMP-0124",
        "evidence_path": f"{STOP_DIR}/SC-14.json",
    },
    {
        "id": 15,
        "spec_line": 11392,
        "text": (
            "Every residual unknown has a named settling experiment and an "
            "owner-visible impact statement."
        ),
        "text_provenance": "catalog-quote",
        "catalog_anchor": "WORK-UNIT-CATALOG.json :11392 condition 15",
        "evidence_path": f"{STOP_DIR}/SC-15.json",
    },
    {
        "id": 16,
        "spec_line": 11393,
        "text": (
            "At least 160 workflow candidates/mechanisms researched and classified "
            "with provenance/license records."
        ),
        "text_provenance": "catalog-quote",
        "catalog_anchor": "WORK-UNIT-CATALOG.json WFA-0123 :11393",
        "evidence_path": f"{STOP_DIR}/SC-16.json",
    },
    {
        "id": 17,
        "spec_line": 11394,
        "text": (
            "At least 96 materially distinct workflow blueprints executable under "
            "the selected quality tiers."
        ),
        "text_provenance": "catalog-quote",
        "catalog_anchor": "WORK-UNIT-CATALOG.json WFA-0124 :11394",
        "evidence_path": f"{STOP_DIR}/SC-17.json",
    },
    {
        "id": 18,
        "spec_line": 11395,
        "text": "At least 48 council protocols.",
        "text_provenance": "catalog-derived",
        "catalog_anchor": "WORK-UNIT-CATALOG.json SYN-0043 floors 16-19",
        "evidence_path": f"{STOP_DIR}/SC-18.json",
    },
    {
        "id": 19,
        "spec_line": 11396,
        "text": "At least 64 presets.",
        "text_provenance": "catalog-derived",
        "catalog_anchor": "WORK-UNIT-CATALOG.json SYN-0043 floors 16-19",
        "evidence_path": f"{STOP_DIR}/SC-19.json",
    },
    {
        "id": 20,
        "spec_line": 11397,
        "text": "At least 2048 work units.",
        "text_provenance": "catalog-derived",
        "catalog_anchor": "WORK-UNIT-CATALOG.json SYN-0043 floors listed with 16-19",
        "evidence_path": f"{STOP_DIR}/SC-20.json",
    },
    {
        "id": 21,
        "spec_line": 11398,
        "text": "At least 160 platform options.",
        "text_provenance": "catalog-derived",
        "catalog_anchor": "WORK-UNIT-CATALOG.json SYN-0043 floors listed with 16-19",
        "evidence_path": f"{STOP_DIR}/SC-21.json",
    },
]

assert len(CONDITIONS) == 21
assert [c["id"] for c in CONDITIONS] == list(range(1, 22))
assert [c["spec_line"] for c in CONDITIONS] == list(range(11378, 11399))
