#!/usr/bin/env python3
"""Planted both-states corpus for WFA-0123.

Seven rows: two distinct three-way survivors, one alias, one trivial fork,
one unclassified, one unresolved provenance, one licence-string-only (no file).
Naive raw count = 7. Qualified three-way AND after collapse = 2.
"""
from __future__ import annotations

from pathlib import Path

FIX = "command-center/p2-wave/probes/WFA-0123/fixtures"


def planted_records() -> list[dict]:
    alpha = f"{FIX}/alpha/SKILL.md"
    beta = f"{FIX}/beta/SKILL.md"
    return [
        {
            "id": "planted-alpha",
            "name": "planted-alpha-research-loop",
            "does": "retrieve sources, score them, and stop when evidence saturates.",
            "mechanisms": "retrieval, scoring, saturation-gate",
            "classification": "ADOPT-AS-IS",
            "provenance": alpha,
            "license_file": f"{FIX}/alpha/LICENSE",
            "kind": "skill",
            "body": "",
        },
        {
            "id": "planted-beta",
            "name": "planted-beta-design-gate",
            "does": "hold a design gate that blocks merge until the named checks pass.",
            "mechanisms": "gate, checklist, merge-block",
            "classification": "DISTILL",
            "provenance": beta,
            "license_file": f"{FIX}/beta/LICENSE",
            "kind": "skill",
            "body": "",
        },
        {
            "id": "planted-alias-cmd",
            "name": "run-planted-alpha",
            "does": "Use skill planted-alpha",
            "mechanisms": "invoke",
            "classification": "ADOPT-AS-IS",
            "provenance": f"{FIX}/alias-cmd/command.md",
            "license_file": f"{FIX}/alpha/LICENSE",
            "kind": "command",
            "alias_of": "planted-alpha",
            "body": "Use skill planted-alpha",
        },
        {
            "id": "planted-alpha-copy",
            "name": "planted-alpha-research-loop-copy",
            "does": "retrieve sources, score them, and stop when evidence saturates.",
            "mechanisms": "retrieval, scoring, saturation-gate",
            "classification": "ADOPT-AS-IS",
            "provenance": f"{FIX}/fork-alpha/SKILL.md",
            "license_file": f"{FIX}/fork-alpha/LICENSE",
            "kind": "skill",
            "body": "",
        },
        {
            "id": "planted-unclassified",
            "name": "planted-unclassified-probe",
            "does": "a distinct harvest pass over plugin manifests.",
            "mechanisms": "plugin-walk, manifest-parse",
            "classification": "UNKNOWN-NEEDS-PROBE",
            "provenance": f"{FIX}/no-class/SKILL.md",
            "license_file": f"{FIX}/no-class/LICENSE",
            "kind": "skill",
            "body": "",
        },
        {
            "id": "planted-unresolved-prov",
            "name": "planted-unresolved-provenance",
            "does": "a distinct compiler for workflow IR smoke cases.",
            "mechanisms": "ir-load, smoke-case",
            "classification": "REPAIR",
            "provenance": f"{FIX}/no-prov/missing-on-purpose.md",
            "license_file": f"{FIX}/no-prov/LICENSE",
            "kind": "skill",
            "body": "",
        },
        {
            "id": "planted-license-string-only",
            "name": "planted-license-string-only",
            "does": "a distinct adapter from slash-command markdown to IR.",
            "mechanisms": "markdown-parse, ir-emit",
            "classification": "EXTEND",
            "provenance": f"{FIX}/no-lic/SKILL.md",
            "license": "MIT",
            "license_file": "",
            "kind": "skill",
            "body": "",
        },
    ]


def expected() -> dict:
    return {
        "raw_count": 7,
        "qualified_ids": ["planted-alpha", "planted-beta"],
        "qualified_count": 2,
        "alias_excluded": ["planted-alias-cmd"],
        "fork_or_duplicate_excluded": ["planted-alpha-copy"],
        "and_rejected_ids": [
            "planted-unclassified",
            "planted-unresolved-prov",
            "planted-license-string-only",
        ],
        "naive_raw_would_count": 7,
        "license_string_is_not_fetched": True,
    }


def assert_fixture_files(repo: Path) -> None:
    missing = []
    for rec in planted_records():
        if rec["id"] == "planted-unresolved-prov":
            continue
        p = repo / str(rec["provenance"])
        if not p.is_file():
            missing.append(str(rec["provenance"]))
        lf = rec.get("license_file")
        if lf:
            lp = repo / str(lf)
            if not lp.is_file():
                missing.append(str(lf))
    if missing:
        raise SystemExit(f"FAILED:WFA-0123 planted fixtures missing {missing}")
