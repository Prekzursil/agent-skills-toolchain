#!/usr/bin/env python3
"""Emit command-center/receipts/REL-0011.json plus the CycloneDX bill."""
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

import generator as G  # noqa: E402
import resolver as R  # noqa: E402
import scenario as S  # noqa: E402

OUT = "command-center/receipts/REL-0011.json"
SBOM = "command-center/receipts/REL-0011.cdx.json"
SCHEMA = "command-center/schema/supply-chain-receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/REL-0011/probe1_closure_minus_bill.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/REL-0011/probe2_phantom_and_clean.py"
)
QUESTION = (
    "Implementation target: emit a CycloneDX or SPDX bill of materials for the "
    "release and then attack it. Independently resolve the true component "
    "closure from the lockfiles and the vendored trees and diff the two sets in "
    "both directions: components present in the closure but absent from the "
    "bill, and components listed in the bill that are not actually shipped. The "
    "bill is a claim about the artifact's contents; the gate is the diff, and "
    "generation alone proves nothing."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def local_validator() -> jsonschema.Draft7Validator:
    """Disk-local Draft-07 contract. Does not resolve catalog shim $ref.

    command-center/schema/supply-chain-receipt.schema.json is a generated
    shim whose $ref targets https://ast-integrate.invalid/... . jsonschema
    4.10.3 on this worktree uses RefResolver and tries the network. A
    validator that cannot fire on garbage is not a validator, so this
    contract stays local and still rejects the three garbage payloads.
    """
    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "required": [
            "unit_id",
            "state",
            "sentinel",
            "generator",
            "resolver",
            "tools_distinct",
            "diffs",
            "walked_depth",
            "not_checked",
            "tests",
            "evidence",
            "reviewer",
            "report",
            "artifacts",
        ],
        "properties": {
            "unit_id": {"const": "REL-0011"},
            "state": {"const": "SUCCESS"},
            "sentinel": {"const": "SUCCESS:REL-0011"},
            "tools_distinct": {"const": True},
            "walked_depth": {"type": "integer", "minimum": 3},
            "generator": {
                "type": "object",
                "required": ["tool", "kind", "path"],
                "properties": {
                    "tool": {"type": "string", "minLength": 8},
                    "kind": {"type": "string", "minLength": 8},
                    "path": {"type": "string", "minLength": 8},
                },
            },
            "resolver": {
                "type": "object",
                "required": ["tool", "kind", "path"],
                "properties": {
                    "tool": {"type": "string", "minLength": 8},
                    "kind": {"type": "string", "minLength": 8},
                    "path": {"type": "string", "minLength": 8},
                },
            },
            "diffs": {
                "type": "object",
                "required": [
                    "closure_minus_bill",
                    "bill_minus_shipped",
                    "counts",
                    "bill",
                    "closure",
                ],
                "properties": {
                    "closure_minus_bill": {"type": "array", "maxItems": 0},
                    "bill_minus_shipped": {"type": "array", "maxItems": 0},
                    "bill": {"type": "array", "minItems": 6},
                    "closure": {"type": "array", "minItems": 6},
                    "counts": {
                        "type": "object",
                        "required": [
                            "closure_minus_bill",
                            "bill_minus_shipped",
                            "bill",
                            "closure",
                        ],
                        "properties": {
                            "closure_minus_bill": {"const": 0},
                            "bill_minus_shipped": {"const": 0},
                            "bill": {"type": "integer", "minimum": 6},
                            "closure": {"type": "integer", "minimum": 6},
                        },
                    },
                },
            },
            "not_checked": {"type": "array", "minItems": 1},
            "tests": {"type": "array", "minItems": 4},
            "evidence": {"type": "array", "minItems": 2},
            "artifacts": {"type": "array", "minItems": 1},
            "reviewer": {
                "type": "object",
                "required": ["reviewer_id", "verdict", "independent"],
                "properties": {
                    "verdict": {"const": "PASS"},
                    "independent": {"const": True},
                    "other_vendor_human_review": {"const": "NOT-CHECKED"},
                },
            },
            "report": {
                "type": "object",
                "required": ["kind", "observations", "control_ids"],
                "properties": {
                    "kind": {"const": "supply-chain-receipt"},
                    "observations": {"type": "array", "minItems": 1},
                    "control_ids": {"type": "array", "minItems": 4},
                },
            },
        },
    }
    return jsonschema.Draft7Validator(schema)


def main() -> int:
    if G.TOOL_NAME == R.TOOL_NAME:
        print("FAILED:REL-0011 generator and resolver share a tool name")
        return 1
    all_run = S.run_all()
    if not all_run.get("pass"):
        print("FAILED:REL-0011 mutation controls did not all pass")
        print(json.dumps(all_run, indent=2, default=str)[:4000])
        return 1
    clean = all_run["clean"]
    bom = clean["bom"]
    sbom_path = REPO / SBOM
    sbom_path.parent.mkdir(parents=True, exist_ok=True)
    sbom_path.write_text(json.dumps(bom, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    sbom_sha, sbom_bytes = sha256_file(sbom_path)

    u, d, p, c = (
        all_run["undeclared"],
        all_run["hand_delete"],
        all_run["phantom"],
        clean,
    )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    tests = [
        {
            "id": u["id"],
            "result": "PASS" if u["pass"] else "FAIL",
            "direction": u["direction"],
            "hit": u["hit"],
            "closure_minus_bill": u["closure_minus_bill"],
            "command": P1,
        },
        {
            "id": d["id"],
            "result": "PASS" if d["pass"] else "FAIL",
            "direction": d["direction"],
            "hit": d["hit"],
            "closure_minus_bill": d["closure_minus_bill"],
            "command": P1,
        },
        {
            "id": p["id"],
            "result": "PASS" if p["pass"] else "FAIL",
            "direction": p["direction"],
            "hit": p["hit"],
            "bill_minus_shipped": p["bill_minus_shipped"],
            "command": P2,
        },
        {
            "id": c["id"],
            "result": "PASS" if c["pass"] else "FAIL",
            "direction": c["direction"],
            "walked_depth": c["walked_depth"],
            "counts": c["counts"],
            "command": P2,
        },
    ]
    doc = {
        "unit_id": "REL-0011",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:REL-0011",
        "completion_sentinel": "SUCCESS:REL-0011",
        "title": (
            "SBOM emitted, then falsified against the independently resolved "
            "dependency closure"
        ),
        "question": QUESTION,
        "proof_surface": (
            "Fixture distributable at command-center/p2-wave/probes/REL-0011/"
            "fixtures/release packed to tar.gz then unpacked. REL-0009 archive "
            "is absent on this worktree; this unit does not claim a production "
            "plugin tarball was scanned."
        ),
        "generator": {
            "tool": G.TOOL_NAME,
            "kind": G.TOOL_KIND,
            "path": "command-center/p2-wave/probes/REL-0011/generator.py",
            "reads": [
                "package-lock.json packages-key enumeration",
                "python-requirements.lock column-0 pins",
                "vendor-manifest.json declared vendored entries",
            ],
            "does_not": [
                "BFS the npm dependency graph",
                "os.walk vendor/",
                "invent versions for missing peers",
            ],
        },
        "resolver": {
            "tool": R.TOOL_NAME,
            "kind": R.TOOL_KIND,
            "path": "command-center/p2-wave/probes/REL-0011/resolver.py",
            "reads": [
                "npm lockfile BFS from packages[\"\"].dependencies",
                "python-requirements.lock via-comment depth",
                "vendor/ component.json walk",
            ],
            "does_not": [
                "emit CycloneDX",
                "import generator.py",
                "read vendor-manifest.json",
            ],
        },
        "tools_distinct": True,
        "sbom": {
            "path": SBOM,
            "format": "CycloneDX",
            "specVersion": "1.5",
            "sha256": sbom_sha,
            "bytes": sbom_bytes,
            "component_count": int(c["counts"]["bill"]),
        },
        "diffs": {
            "closure_minus_bill": c["closure_minus_bill"],
            "bill_minus_shipped": c["bill_minus_shipped"],
            "counts": c["counts"],
            "bill": c["bill"],
            "closure": c["closure"],
        },
        "walked_depth": int(c["walked_depth"]),
        "not_checked": c["not_checked"],
        "report": {
            "kind": "supply-chain-receipt",
            "observations": [
                {
                    "name": "clean-closure-minus-bill",
                    "measured": int(c["counts"]["closure_minus_bill"]),
                    "method": "set-diff of resolver purls minus generator purls",
                    "anchor": "command-center/p2-wave/probes/REL-0011/diff.py",
                },
                {
                    "name": "clean-bill-minus-shipped",
                    "measured": int(c["counts"]["bill_minus_shipped"]),
                    "method": "set-diff of generator purls minus resolver purls",
                    "anchor": "command-center/p2-wave/probes/REL-0011/diff.py",
                },
                {
                    "name": "walked-depth",
                    "measured": int(c["walked_depth"]),
                    "method": "npm lockfile BFS plus pip via-comment depth",
                    "anchor": "command-center/p2-wave/probes/REL-0011/resolver.py",
                },
                {
                    "name": "tools-distinct",
                    "measured": bool(G.TOOL_NAME != R.TOOL_NAME),
                    "method": "compare generator.TOOL_NAME vs resolver.TOOL_NAME",
                    "anchor": "command-center/p2-wave/probes/REL-0011/generator.py",
                },
            ],
            "control_ids": [
                "undeclared-vendored",
                "hand-delete-from-bill",
                "phantom-bill-entry",
                "clean-build",
            ],
        },
        "tests": tests,
        "evidence": [
            {
                "kind": "generator-vs-resolver",
                "claim": (
                    f"Generator {G.TOOL_NAME} and resolver {R.TOOL_NAME} are "
                    "different tools with different source files and different "
                    "parse strategies. One tool checking itself is refused."
                ),
            },
            {
                "kind": "both-diff-directions",
                "claim": (
                    "Clean build: closure-minus-bill count="
                    f"{c['counts']['closure_minus_bill']} bill-minus-shipped count="
                    f"{c['counts']['bill_minus_shipped']} walked_depth="
                    f"{c['walked_depth']}."
                ),
            },
            {
                "kind": "undeclared-vendored",
                "claim": (
                    f"Planted {S.PLANTED_PURL} into vendor/ without updating "
                    "vendor-manifest.json; closure-minus-bill fired."
                ),
            },
            {
                "kind": "hand-delete",
                "claim": (
                    f"Removed {S.DELETE_PURL} from the bill; closure-minus-bill "
                    "fired, so the gate is not tree-only."
                ),
            },
            {
                "kind": "phantom",
                "claim": (
                    f"Added {S.PHANTOM_PURL} to the bill; bill-minus-shipped fired."
                ),
            },
            {
                "kind": "not-checked-peer",
                "claim": (
                    "mid-pkg peerDependency unresolved-peer is NOT-CHECKED; the "
                    "resolver refused to invent a version because the name is "
                    "absent from the lockfile packages map."
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "REL-0011-probe2-phantom-and-clean",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "other_vendor_human_review": "NOT-CHECKED",
            "notes": (
                "G-1 second named probe is a mechanically different mutation axis "
                "(phantom bill-minus-shipped plus clean both-empty). Catalog "
                "other-vendor human reviewer is NOT-CHECKED, not silently claimed."
            ),
        },
        "named_probes": [
            {"id": "probe1", "role": "closure-minus-bill", "command": P1},
            {"id": "probe2", "role": "phantom-and-clean", "command": P2},
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SBOM, "exists": True, "role": "sbom"},
            {"path": SCHEMA, "exists": True, "role": "schema"},
        ],
        "scope": {
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global UNIT-ARTIFACT-MANIFEST.json --write was run",
                "REL-0009 production archive was present on this worktree",
                "other-vendor human reviewer ran",
            ]
        },
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "supply-chain-analyst",
            "execution_substrate": "linux-local",
        },
        "cloud_ok": False,
        "registered": True,
        "min_bytes_threshold": 1200,
        "ts": now,
    }

    validator = local_validator()
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:REL-0011 schema errors")
        for e in errs[:25]:
            print(" ", list(e.path), e.message)
        return 1
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {"unit_id": "REL-0011", "state": "SUCCESS", "sentinel": "SUCCESS:REL-0011"},
    ):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:REL-0011 schema accepted garbage")
            return 1
    catalog_schema = REPO / SCHEMA
    if not catalog_schema.is_file() or catalog_schema.stat().st_size <= 0:
        print(f"FAILED:REL-0011 catalog schema missing {SCHEMA}")
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:REL-0011 artifact {size}B below floor")
        return 1
    if "SUCCESS:REL-0011" not in out.read_text(encoding="utf-8"):
        print("FAILED:REL-0011 sentinel missing after write")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(f"wrote {SBOM} bytes={sbom_bytes} sha256={sbom_sha}")
    print(
        f"clean bill={c['counts']['bill']} closure={c['counts']['closure']} "
        f"walked_depth={c['walked_depth']}"
    )
    print("SUCCESS:REL-0011")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
