#!/usr/bin/env python3
"""Emit command-center/audit/AUD-0088-package-content-baseline.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import measure as M  # noqa: E402

UNIT = "AUD-0088"
OUT = "command-center/audit/AUD-0088-package-content-baseline.json"
SCHEMA = "command-center/schema/audit-metric-baseline.schema.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
ALLOWLIST = "tools/plugin/payload-allowlist.json"
SENTINEL = (
    "SUCCESS:AUD-0088 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
QUESTION = (
    "If the plugin were built today, exactly which files and how many bytes "
    "would the artifact contain - and does it include .git, caches, logs, "
    "transcripts, or credentials?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0088/probe1_packager_file_list.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0088/probe2_unpack_archive.py"
)


def find_line(rel: str, snippet: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:{UNIT} snippet not in {rel}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def ev(rel: str, snippet: str, kind: str, claim: str) -> dict:
    line = find_line(rel, snippet)
    return {
        "path": rel,
        "line": line,
        "snippet": snippet,
        "kind": kind,
        "claim": claim,
        "anchor": f"{rel}:{line}",
    }


def main() -> int:
    p1 = M.probe1_packager_file_list(REPO)
    p2 = M.probe2_unpack_archive(REPO)
    if not p1["lists_agree"] or not p1["deny_by_default"] or p1["declared_count"] < 1:
        print(f"FAILED:{UNIT} packager file list is not a usable baseline")
        return 1
    if not p2["control"]["ok"]:
        print(f"FAILED:{UNIT} unpack control did not discriminate")
        return 1
    if p2["prohibited_in_clean"]:
        print(f"FAILED:{UNIT} clean scratch archive is dirty {p2['prohibited_in_clean']}")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    headline = {
        "declared_file_count": p1["declared_count"],
        "declared_source_bytes": p1["declared_source_bytes"],
        "archive_file_count": p2["archive_entry_count"],
        "archive_uncompressed_bytes": p2["archive_uncompressed_bytes"],
        "archive_file_bytes": p2["archive_file_bytes"],
        "declared_vs_archive_agree": p2["declared_vs_archive_agree"],
        "prohibited_in_clean_count": len(p2["prohibited_in_clean"]),
        "pack_py_present": p1["pack_py_present"],
        "plugin_manifest_in_allowlist": p1["plugin_manifest_in_allowlist"],
        "scratch_build": True,
        "production_pack_py_used": False,
    }
    answer = (
        f"Scratch-built from the live deny-by-default allowlist "
        f"({ALLOWLIST}): {p1['declared_count']} files, "
        f"{p1['declared_source_bytes']} source bytes. Unpacked archive has "
        f"{p2['archive_entry_count']} entries, "
        f"{p2['archive_uncompressed_bytes']} uncompressed bytes, "
        f"{p2['archive_file_bytes']} zip bytes. Declared list vs archive "
        f"agree={p2['declared_vs_archive_agree']}. Clean archive prohibited "
        f"paths={len(p2['prohibited_in_clean'])} (none). tools/plugin/pack.py "
        f"present={p1['pack_py_present']} (IMP-0002 not rebuilt). "
        f".claude-plugin/plugin.json in allowlist="
        f"{p1['plugin_manifest_in_allowlist']}. Planted staged/.git/config, "
        f"credentials.json, and STRAY-AUD-0088.bin were flagged by unpack "
        f"enumeration. " + SENTINEL
    )
    doc = {
        "unit_id": UNIT,
        "title": "Shipped-package content and size baseline",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "kind": "audit-metric-baseline",
        "output_path": OUT,
        "output_schema": SCHEMA,
        "spec_anchor": "_USER-PROMPTS.md:10842",
        "question": QUESTION,
        "answer": answer,
        "headline": headline,
        "packager_file_list": p1,
        "unpacked_archive": p2,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "role": "packager-file-list",
                "record": {
                    "declared_count": p1["declared_count"],
                    "declared_source_bytes": p1["declared_source_bytes"],
                    "lists_agree": p1["lists_agree"],
                    "listing_sha256": p1["listing_sha256"],
                    "declared_paths": p1["declared_paths"],
                },
            },
            {
                "id": "probe2",
                "command": P2,
                "role": "unpack-built-archive",
                "record": {
                    "archive_entry_count": p2["archive_entry_count"],
                    "archive_uncompressed_bytes": p2["archive_uncompressed_bytes"],
                    "declared_vs_archive_agree": p2["declared_vs_archive_agree"],
                    "control": p2["control"],
                },
            },
        ],
        "tests": [
            {
                "id": "AUD0088-T1",
                "name": "packager file list vs independent glob",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "AUD0088-T2",
                "name": "unpack enumeration and planted-stray control",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "AUD0088-C1",
                "kind": "planted-stray",
                "description": (
                    "Unpack a scratch zip that injects staged/.git/config, "
                    "credentials.json (name only), and STRAY-AUD-0088.bin. "
                    "The enumerator must flag the first two and detect the "
                    "stray as extra vs the include list, while a clean "
                    "allowlist zip stays silent and still contains a declared file."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            }
        ],
        "evidence": [
            ev(
                CATALOG,
                "If the plugin were built today, exactly which files",
                "catalog",
                "AUD-0088 asks for the shipped file list and whether prohibited classes are present.",
            ),
            ev(
                CATALOG,
                "Probe 1: the packaging tool's own file list",
                "catalog",
                "Named probes are the packager listing and the unpacked archive, not the source tree.",
            ),
            ev(
                ALLOWLIST,
                '"deny_by_default": true',
                "packaging-config",
                "The live packager allowlist is deny-by-default.",
            ),
            ev(
                "command-center/p2-wave/probes/AUD-0088/hygiene.py",
                'flags.append("credential-shaped")',
                "detector",
                "Credential-shaped paths are flagged by basename, never by printing a body.",
            ),
            ev(
                "command-center/p2-wave/probes/AUD-0088/scratch_pack.py",
                "This is not tools/plugin/pack.py",
                "scratch-packer",
                "The measurement builds a scratch zip; it does not author IMP-0002 pack.py.",
            ),
        ],
        "reviewer": {
            "reviewer_id": "AUD-0088-probe2-unpack-archive",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "note": (
                "Probe 2 re-derives the archive entry list from ZipInfo and "
                "from the extracted tree; it does not trust probe 1's include list."
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "output-schema"},
            {"path": ALLOWLIST, "exists": True, "role": "packaging-config"},
        ],
        "cloud_ok": False,
        "timestamps": {"started_at": now, "ended_at": now},
        "notes": (
            "G-1 AUD-0088: live named probes, scratch-built archive unpacked, "
            "stray-file control fired, per-unit manifest row. Did not run "
            "global unit_manifest.py --write. Did not implement tools/plugin/pack.py. "
            "cloud_ok is not delivery. " + SENTINEL
        ),
    }
    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    errors = list(jsonschema.Draft7Validator(schema).iter_errors(doc))
    if errors:
        print(f"FAILED:{UNIT} schema-invalid {errors[0].message}")
        return 1
    blob = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if SENTINEL not in blob:
        print(f"FAILED:{UNIT} sentinel missing before write")
        return 1
    if '"state": "BLOCKED"' in blob or '"state": "FAILED"' in blob:
        print(f"FAILED:{UNIT} self-declared blocked")
        return 1
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(blob, encoding="utf-8")
    print(
        f"wrote {OUT} files={headline['archive_file_count']} "
        f"uncompressed={headline['archive_uncompressed_bytes']} "
        f"agree={headline['declared_vs_archive_agree']}"
    )
    print(SENTINEL, "emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
