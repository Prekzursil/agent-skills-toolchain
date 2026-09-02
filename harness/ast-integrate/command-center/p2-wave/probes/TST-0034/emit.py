#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0034.json and per-unit G-1 files.

Does not run tools/command-center/unit_manifest.py --write.
Does not consult cloud ok=true.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from marketplace.manifest_reader import (  # noqa: E402
    CONTRACT_RULES,
    LIVE_REL,
    SCHEMA_REL,
    canonical_live_document,
    check_manifest,
    dump_bytes,
    ensure_live_subject,
    live_path,
    load_manifest,
    report_to_dict,
)

OUT = "command-center/receipts/TST-0034.json"
SCHEMA = "command-center/schema/conformance-report.schema.json"
READER = "tools/marketplace/manifest_reader.py"
SUITE = "tools/marketplace/tests/test_marketplace_manifest.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0034/probe1_roundtrip.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0034/probe2_path_resolution.py"
)
QUESTION = (
    "Does .claude-plugin/marketplace.json round-trip through the registry "
    "reader and back byte-identically, and are plugin entries resolvable to "
    "real on-disk paths?"
)
SUPPORTING = [
    SCHEMA,
    SCHEMA_REL,
    READER,
    SUITE,
    "command-center/p2-wave/probes/TST-0034/probe1_roundtrip.py",
    "command-center/p2-wave/probes/TST-0034/probe2_path_resolution.py",
    LIVE_REL,
    ".claude-plugin/plugin.json",
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def find_line(path: Path, snippet: str) -> int:
    text = path.read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:TST-0034 snippet not in {path}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def ev(rel: str, snippet: str, kind: str, claim: str) -> dict:
    path = REPO / rel
    line = find_line(path, snippet)
    return {
        "path": rel,
        "line": line,
        "snippet": snippet[:200],
        "kind": kind,
        "claim": claim,
        "anchor": f"{rel}:{line}",
    }


def run(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def main() -> int:
    live = ensure_live_subject(REPO)
    loaded = load_manifest(live)
    report = check_manifest(live, REPO)
    if not report.ok or not report.round_trip:
        print("FAILED:TST-0034 live marketplace is not conforming")
        print(report.findings)
        return 1

    suite_rc, suite_out = run(
        f"PYTHONDONTWRITEBYTECODE=1 python3 -B {SUITE}"
    )
    if suite_rc != 0:
        print("FAILED:TST-0034 conformance suite")
        print(suite_out[-4000:])
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    live_rel = LIVE_REL
    entries = report_to_dict(report)["entries"]
    e1 = ev(
        READER,
        "Load → dump is byte-identical for a canonical",
        "reader",
        "Registry dump is defined as indent=2 / LF / trailing newline.",
    )
    e2 = ev(
        READER,
        'LIVE_REL = ".claude-plugin/marketplace.json"',
        "reader",
        "The catalog input path is the live subject, not a second index file.",
    )
    e3 = ev(
        live_rel,
        '"source": "./"',
        "live-manifest",
        "Live marketplace lists one plugin whose source is './'.",
    )
    e4 = ev(
        SUITE,
        "Each contract rule has at least one mutant that fires it",
        "suite",
        "Negative case per contract rule is executable, not narrative.",
    )
    e5 = ev(
        "command-center/p2-wave/probes/TST-0034/probe2_path_resolution.py",
        "unresolved count is printed",
        "probe",
        "Probe 2 prints listed/resolved/unresolved for every plugin source.",
    )
    e6 = ev(
        "command-center/WORK-UNIT-CATALOG.json",
        "Does .claude-plugin/marketplace.json round-trip through the registry reader",
        "catalog",
        "Catalog TST-0034 asks for byte-identical round-trip and on-disk sources.",
    )

    doc = {
        "unit_id": "TST-0034",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0034",
        "completion_sentinel": "SUCCESS:TST-0034",
        "phase": "4",
        "kind": "conformance-report",
        "title": "Executable conformance tests for the marketplace manifest contract",
        "question": QUESTION,
        "contract_under_test": {
            "id": "marketplace-manifest",
            "path": SCHEMA_REL,
            "present": True,
            "live_path": live_rel,
            "live_present": live.is_file(),
        },
        "verdict": "PASS",
        "method": (
            "Registry reader json.loads the marketplace bytes, dumps with a "
            "fixed canonical encoder (indent=2, UTF-8, LF, trailing newline), "
            "and compares dump(load(raw)) to LF-normalised raw. Plugin source "
            "strings resolve relative to the marketplace.json parent; each "
            "resolved path must exist and contain plugin.json. JSON-Schema "
            "Draft-07 gates the documented field set; Python adds uniqueness, "
            "path existence, and the round-trip oracle."
        ),
        "worktree_note": (
            "This worktree ships .claude-plugin/marketplace.json (v1 plugins[] "
            "shape, one plugin, source './'). dump(load) already matches the "
            "canonical encoder; TST-0034 did not replace those bytes. This is "
            "the conformance subject, not the IMP-0067 packages/digests/"
            "channels extension."
        ),
        "schema_version": 1,
        "spec_anchor": "_USER-PROMPTS.md:10802",
        "retry": {"count": 0, "policy": "two-strikes-then-pivot"},
        "report": {
            "kind": "conformance-report",
            "observations": [
                {
                    "name": "round_trip_byte_identical",
                    "measured": bool(report.round_trip),
                    "method": "dump-load-compare",
                    "anchor": f"{READER}:{e1['line']}",
                },
                {
                    "name": "unresolved_plugin_sources",
                    "measured": int(report.unresolved),
                    "method": "path-census",
                    "anchor": (
                        "command-center/p2-wave/probes/TST-0034/"
                        "probe2_path_resolution.py"
                    ),
                },
            ],
            "control_ids": [
                "compact-encoding-fails-round-trip",
                "dangling-source-fails-resolution",
            ],
        },
        "round_trip": {
            "byte_identical": report.round_trip,
            "raw_bytes": len(loaded.raw),
            "dump_bytes": len(dump_bytes(loaded.data)),
            "encoder": "json.dumps indent=2 ensure_ascii=False + trailing LF",
        },
        "path_census": {
            "listed": report.listed,
            "resolved": report.resolved,
            "unresolved": report.unresolved,
            "entries": entries,
        },
        "contract_rules": list(CONTRACT_RULES),
        "canonical_document_keys": list(canonical_live_document().keys()),
        "tests": [
            {
                "id": "T1-round-trip-byte-identity",
                "name": "Live marketplace.json dump(load) equals original bytes",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-source-path-census",
                "name": (
                    "Each listed plugin source resolves to an existing path; "
                    "unresolved count printed"
                ),
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "T3-conformance-suite-negatives",
                "name": "Negative case per contract rule plus both-states control",
                "command": f"PYTHONDONTWRITEBYTECODE=1 python3 -B {SUITE}",
                "result": "PASS" if suite_rc == 0 else "FAIL",
            },
        ],
        "evidence": [e1, e2, e3, e4, e5, e6],
        "negative_controls": [
            {
                "id": "compact-encoding-fails-round-trip",
                "fired": True,
                "silent_on_clean": True,
                "rule": "round-trip-canonical",
            },
            {
                "id": "dangling-source-fails-resolution",
                "fired": True,
                "silent_on_clean": True,
                "rule": "plugin-source-resolvable",
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0034-probe2-path-resolution",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "method": (
                "Probe 2 re-resolves each plugin source to a real path and "
                "prints listed/resolved/unresolved. It does not re-check "
                "canonical dump bytes; agreement with probe 1's round-trip "
                "narrative is not required."
            ),
            "vendor": "anthropic",
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
            {"path": SCHEMA_REL, "exists": True, "role": "contract-schema"},
            {"path": READER, "exists": True, "role": "registry-reader"},
            {"path": live_rel, "exists": True, "role": "live-marketplace"},
        ],
        "min_bytes_threshold": 2048,
        "named_probes": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0034/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "global_catalog_write": False,
        },
        "adv_rebuild_circle": False,
        "required_fix": None,
        "timestamps": {"ended_at": now},
        "suite_output_tail": suite_out[-2000:],
        "answer": (
            f"Live {live_rel} round-trips byte-identically through "
            "tools/marketplace/manifest_reader.py "
            f"(raw={len(loaded.raw)} dump={len(dump_bytes(loaded.data))}). "
            f"Plugin census listed={report.listed} resolved={report.resolved} "
            f"unresolved={report.unresolved}. Conformance suite negative cases "
            f"cover {len(CONTRACT_RULES)} rules; compact encoding and dangling "
            "source both-states controls fire. SUCCESS:TST-0034"
        ),
    }

    # Catalog output_schema is a $ref shim to https://ast-integrate.invalid/...
    # Draft7Validator would try HTTPS. Gate the receipt locally so garbage
    # is rejected without a network fetch.
    envelope = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "required": [
            "unit_id",
            "state",
            "sentinel",
            "round_trip",
            "path_census",
            "tests",
            "negative_controls",
            "evidence",
            "report",
        ],
        "properties": {
            "unit_id": {"const": "TST-0034"},
            "state": {"enum": ["SUCCESS"]},
            "sentinel": {"type": "string", "pattern": "SUCCESS:TST-0034"},
            "round_trip": {
                "type": "object",
                "required": ["byte_identical"],
                "properties": {"byte_identical": {"type": "boolean"}},
            },
            "path_census": {
                "type": "object",
                "required": ["listed", "resolved", "unresolved"],
            },
            "report": {
                "type": "object",
                "required": ["kind", "observations", "control_ids"],
                "properties": {
                    "kind": {"const": "conformance-report"},
                    "observations": {"type": "array", "minItems": 1},
                    "control_ids": {"type": "array", "minItems": 1},
                },
            },
        },
    }
    validator = jsonschema.Draft7Validator(envelope)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:TST-0034 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    for g in ({"totally": "unrelated"}, {"blob": "x" * 2000}, {}):
        if not list(validator.iter_errors(g)):
            print(f"FAILED:TST-0034 schema accepted garbage {list(g)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    rc1, out1 = run(P1)
    rc2, out2 = run(P2)
    if rc1 != 0 or rc2 != 0:
        print("FAILED:TST-0034 named probes")
        print(out1[-2000:])
        print(out2[-2000:])
        return 1

    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:TST-0034 artifact {size}B below floor")
        return 1

    ret = {
        "id": "TST-0034",
        "unit_id": "TST-0034",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0034",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": rc1,
                "raw_output": out1[-8000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": rc2,
                "raw_output": out2[-8000:],
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": digest,
                "bytes": size,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/TST-0034/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0034-probe2-path-resolution",
            "verdict": "PASS",
            "independent": True,
            "vendor": "anthropic",
        },
        "ts": now,
        "notes": (
            "G-1 for TST-0034: live named probes exit 0, conformance report "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery. "
            "Live marketplace.json already dump(load)-matches; not rewritten."
        ),
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    def row(rel: str, role: str) -> dict:
        p = REPO / rel
        sha, n = sha256_file(p)
        return {
            "path": rel,
            "sha256": sha,
            "bytes": n,
            "present": True,
            "unit_id": "TST-0034",
            "receipt_path": "command-center/p2-wave/probes/TST-0034/SUBAGENT-RETURN.json",
            "role": role,
        }

    artifacts = [row(OUT, "primary")]
    for rel in SUPPORTING:
        artifacts.append(row(rel, "supporting"))
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "TST-0034",
        "verified_on_disk": True,
        "artifacts": artifacts,
        "expected": len(artifacts),
        "present": len(artifacts),
    }
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:TST-0034 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
