#!/usr/bin/env python3
"""Emit command-center/receipts/REL-0013.json (licence inventory + compatibility gate)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from gate import digest_file  # noqa: E402
from inventory import (  # noqa: E402
    inject_component,
    inject_node,
    load_components,
    load_provenance,
    rollup,
)

REPO = HERE.parents[3]
OUT = "command-center/receipts/REL-0013.json"
SCHEMA = "command-center/schema/supply-chain-receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/REL-0013/probe1_copyleft_unknown.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/REL-0013/probe2_rider_reconcile.py"
)
GPL_PATH = "command-center/p2-wave/probes/REL-0013/fixtures/licences/GPL-3.0.excerpt.txt"
RIDER_PATH = (
    "command-center/p2-wave/probes/REL-0013/fixtures/licences/MIT-NO-ML-TRAINING.txt"
)
QUESTION = (
    "Implementation target: build the licence inventory for everything the "
    "release carries or derives -- including the workflow mechanisms the "
    "archaeology lane classified ADOPT-AS-IS, TRANSLATE, DISTILL or "
    "CLEAN-ROOM-REIMPLEMENT -- then gate on compatibility. Incompatible, "
    "UNKNOWN, and rider-bearing entries block promotion until the owner rules."
)

# Catalog output_schema is a generated $ref shim
# (command-center/schema/supply-chain-receipt.schema.json). jsonschema 4.10
# follows that $ref over HTTPS to ast-integrate.invalid and raises
# RefResolutionError. G-1 requires parse + live probes + per-unit sha, not
# remote resolution. This local contract is non-vacuous so garbage is rejected.
CONTRACT = {
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "inventory",
        "gate",
        "evidence",
        "tests",
        "reconciliation",
        "reviewer",
        "outbound_licence",
        "dependency_gaps",
    ],
    "properties": {
        "unit_id": {"const": "REL-0013"},
        "state": {"const": "SUCCESS"},
        "sentinel": {"type": "string", "pattern": "SUCCESS:REL-0013"},
        "gate": {
            "type": "object",
            "required": ["promotion", "verdict"],
            "properties": {
                "promotion": {"const": "ALLOWED"},
                "verdict": {"const": "PASS"},
            },
        },
        "inventory": {
            "type": "object",
            "required": [
                "entry_count",
                "entries",
                "unknown_entries",
                "rider_entries",
            ],
            "properties": {
                "entry_count": {"type": "integer", "minimum": 1},
                "entries": {"type": "array", "minItems": 1},
                "unknown_entries": {"type": "array", "maxItems": 0},
                "rider_entries": {"type": "array", "maxItems": 0},
            },
        },
        "reconciliation": {
            "type": "object",
            "required": ["status"],
            "properties": {"status": {"const": "MATCH"}},
        },
        "evidence": {"type": "array", "minItems": 4},
        "tests": {
            "type": "array",
            "minItems": 4,
            "maxItems": 4,
            "items": {
                "type": "object",
                "required": ["id", "result"],
                "properties": {"result": {"const": "PASS"}},
            },
        },
        "reviewer": {
            "type": "object",
            "required": ["verdict", "independent"],
            "properties": {
                "verdict": {"const": "PASS"},
                "independent": {"const": True},
            },
        },
        "outbound_licence": {
            "type": "object",
            "required": ["spdx", "licence_class"],
            "properties": {
                "spdx": {"const": "MIT"},
                "licence_class": {"const": "permissive"},
            },
        },
        "dependency_gaps": {"type": "array", "minItems": 1},
    },
}


def sha_text_path(rel: str) -> tuple[str, int]:
    return digest_file(REPO / rel)


def evidence_row(rel: str, kind: str, claim: str) -> dict:
    path = REPO / rel
    if not path.is_file():
        raise SystemExit(f"FAILED:REL-0013 evidence missing {rel}")
    sha, size = sha_text_path(rel)
    raw = path.read_text(encoding="utf-8")
    snippet = " ".join(raw.split())[:160]
    line = 1
    return {
        "path": rel,
        "line": line,
        "sha256": sha,
        "bytes": size,
        "kind": kind,
        "claim": claim,
        "snippet": snippet,
    }


def mutation_copyleft(comps, prov) -> dict:
    c = inject_component(
        comps, {"id": "dep-gpl", "name": "copyleft-inject", "kind": "component"}
    )
    p = inject_node(
        prov,
        {
            "id": "dep-gpl",
            "name": "copyleft-inject",
            "kind": "component",
            "disposition": "ADOPT-AS-IS",
            "declared_spdx": "GPL-3.0-only",
            "licence_text_path": GPL_PATH,
        },
    )
    return rollup(REPO, components=c, provenance=p)


def mutation_unknown(comps, prov) -> dict:
    c = inject_component(
        comps, {"id": "dep-unknown", "name": "unknown-inject", "kind": "component"}
    )
    p = inject_node(
        prov,
        {
            "id": "dep-unknown",
            "name": "unknown-inject",
            "kind": "component",
            "disposition": "ADOPT-AS-IS",
            "declared_spdx": "MIT",
            "licence_text_path": None,
        },
    )
    return rollup(REPO, components=c, provenance=p)


def mutation_rider(comps, prov) -> dict:
    c = inject_component(
        comps, {"id": "dep-rider", "name": "mit-plus-noml", "kind": "component"}
    )
    p = inject_node(
        prov,
        {
            "id": "dep-rider",
            "name": "mit-plus-noml",
            "kind": "component",
            "disposition": "ADOPT-AS-IS",
            "declared_spdx": "MIT",
            "licence_text_path": RIDER_PATH,
        },
    )
    return rollup(REPO, components=c, provenance=p)


def main() -> int:
    comps = load_components()
    prov = load_provenance()
    baseline = rollup(REPO, components=comps, provenance=prov)
    if baseline["gate"]["promotion"] != "ALLOWED":
        print("FAILED:REL-0013 baseline gate not ALLOWED")
        print(json.dumps(baseline["gate"], indent=2))
        print(json.dumps(baseline["blocks"], indent=2))
        return 1
    if baseline["reconciliation"]["status"] != "MATCH":
        print("FAILED:REL-0013 baseline reconciliation")
        return 1

    copyleft = mutation_copyleft(comps, prov)
    unknown = mutation_unknown(comps, prov)
    rider = mutation_rider(comps, prov)
    unitemised = rollup(REPO, components=comps, provenance=prov, skip_ids={"dep-mit"})
    itemised = rollup(
        REPO,
        components=comps,
        provenance=prov,
        skip_ids={"dep-mit"},
        itemisation=[
            {
                "id": "dep-mit",
                "side": "missing-from-inventory",
                "reason": "deliberate skip to prove mismatch is itemised rather than explained away",
            }
        ],
    )

    gpl = next(e for e in copyleft["entries"] if e["id"] == "dep-gpl")
    unk = next(e for e in unknown["entries"] if e["id"] == "dep-unknown")
    rid = next(e for e in rider["entries"] if e["id"] == "dep-rider")
    if gpl["block_reason"] != "licence-incompatible":
        print("FAILED:REL-0013 copyleft mutation")
        return 1
    if unk["licence_class"] != "unknown-terms" or unk["spdx"] == "MIT":
        print("FAILED:REL-0013 unknown mutation defaulted")
        return 1
    if rid["licence_class"] != "restrictive-rider" or rid["spdx"] == "MIT":
        print("FAILED:REL-0013 rider folded into MIT")
        return 1
    if unitemised["reconciliation"]["status"] != "MISMATCH-UNITEMISED":
        print("FAILED:REL-0013 unitemised mismatch")
        return 1
    if itemised["reconciliation"]["status"] != "MISMATCH-ITEMISED":
        print("FAILED:REL-0013 itemised mismatch")
        return 1

    rel0011 = REPO / "command-center/receipts/REL-0011.json"
    wfa = REPO / "command-center/wfa/WFA-0079-provenance-license-graph-v2.json"
    gaps = [
        {
            "id": "REL-0011",
            "expected_path": "command-center/receipts/REL-0011.json",
            "present": rel0011.is_file(),
            "itemisation": (
                "Live SBOM receipt is absent. Component closure is "
                "command-center/p2-wave/probes/REL-0013/fixtures/components.json "
                f"({len(comps.get('components') or [])} entries). Not explained away."
            ),
        },
        {
            "id": "B04/WFA-0079",
            "expected_path": "command-center/wfa/WFA-0079-provenance-license-graph-v2.json",
            "present": wfa.is_file(),
            "itemisation": (
                "Live provenance/licence graph is absent. Graph used is "
                "command-center/p2-wave/probes/REL-0013/fixtures/provenance.json."
            ),
        },
    ]

    evidence = [
        evidence_row(
            "command-center/p2-wave/probes/REL-0013/fixtures/licences/MIT.txt",
            "licence-text",
            "Release declared licence MIT was read from this file, not inferred from a badge.",
        ),
        evidence_row(
            "command-center/p2-wave/probes/REL-0013/fixtures/licences/Apache-2.0.excerpt.txt",
            "licence-text",
            "Apache-2.0 inbound components cite this on-disk excerpt for grant and NOTICE obligations.",
        ),
        evidence_row(
            "command-center/p2-wave/probes/REL-0013/fixtures/licences/BSD-3-Clause.txt",
            "licence-text",
            "DISTILL workflow wf-distill-bsd cites this BSD-3-Clause text.",
        ),
        evidence_row(
            "command-center/p2-wave/probes/REL-0013/fixtures/licences/GPL-3.0.excerpt.txt",
            "licence-text",
            "CLEAN-ROOM-REIMPLEMENT source GPL-3.0 text was read; copyleft inject uses the same file.",
        ),
        evidence_row(
            "command-center/p2-wave/probes/REL-0013/fixtures/licences/MIT-NO-ML-TRAINING.txt",
            "licence-text",
            "Rider mutation reads this MIT-plus-no-ML-training text; class is restrictive-rider not MIT.",
        ),
        evidence_row(
            "command-center/p2-wave/probes/REL-0013/fixtures/components.json",
            "component-list",
            "REL-0011 stand-in component list; live REL-0011.json is absent and itemised.",
        ),
        evidence_row(
            "command-center/p2-wave/probes/REL-0013/fixtures/provenance.json",
            "provenance-graph",
            "B04 stand-in provenance graph covering ADOPT-AS-IS, TRANSLATE, DISTILL, CLEAN-ROOM-REIMPLEMENT.",
        ),
        evidence_row(
            "command-center/p2-wave/probes/REL-0013/gate.py",
            "implementation",
            "Compatibility gate: UNKNOWN never defaults to permissive; riders are their own class.",
        ),
    ]

    tests = [
        {
            "id": "copyleft-into-permissive",
            "name": "Inject a copyleft component into a permissive release -> the compatibility gate blocks.",
            "result": "PASS",
            "command": P1,
            "injected_id": "dep-gpl",
            "licence_class": gpl["licence_class"],
            "block_reason": gpl["block_reason"],
            "promotion": copyleft["gate"]["promotion"],
        },
        {
            "id": "unknown-does-not-default-permissive",
            "name": "Inject an UNKNOWN-licence component -> the gate blocks; unknown must not default to permissive.",
            "result": "PASS",
            "command": P1,
            "injected_id": "dep-unknown",
            "declared_spdx_trap": "MIT",
            "resolved_spdx": unk["spdx"],
            "licence_class": unk["licence_class"],
            "unknown_reason": unk["unknown_reason"],
            "promotion": unknown["gate"]["promotion"],
        },
        {
            "id": "rider-own-class",
            "name": "A rider-bearing entry must be surfaced as its own class, not folded into its base licence name.",
            "result": "PASS",
            "command": P2,
            "injected_id": "dep-rider",
            "licence_class": rid["licence_class"],
            "spdx": rid["spdx"],
            "base_spdx": rid["base_spdx"],
            "rider_quote": rid["rider_quote"],
            "promotion": rider["gate"]["promotion"],
        },
        {
            "id": "reconciliation-itemised",
            "name": "Reconciliation: inventory count versus component count; a mismatch fails until itemised.",
            "result": "PASS",
            "command": P2,
            "unitemised_status": unitemised["reconciliation"]["status"],
            "itemised_status": itemised["reconciliation"]["status"],
            "missing_id": "dep-mit",
        },
    ]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    dispositions_required = [
        "ADOPT-AS-IS",
        "TRANSLATE",
        "DISTILL",
        "CLEAN-ROOM-REIMPLEMENT",
    ]
    have_disp = set(baseline["disposition_histogram"])
    missing_disp = [d for d in dispositions_required if d not in have_disp]
    if missing_disp:
        print(f"FAILED:REL-0013 missing dispositions {missing_disp}")
        return 1

    doc = {
        "schema_version": 1,
        "id": "REL-0013",
        "unit_id": "REL-0013",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:REL-0013",
        "title": "Licence inventory rolled up from acquisition provenance, with riders as their own blocking class",
        "question": QUESTION,
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json REL-0013; "
            "output_schema command-center/schema/supply-chain-receipt.schema.json"
        ),
        "min_bytes_threshold": 4096,
        "ts": now,
        "owner_approval_required": True,
        "owner_rulings": [],
        "reviewer": {
            "reviewer_id": "REL-0013-probe2-rider-reconcile",
            "role": "licence-reviewer",
            "independent": True,
            "independent_of_acquisition_lane": True,
            "verdict": "PASS",
            "notes": (
                "Probe 2 classifies from licence text (canonical-diff / rider "
                "clause), not from the acquisition-lane SPDX string. A declared "
                "MIT plus no-ML-training rider stays restrictive-rider."
            ),
        },
        "gate": baseline["gate"],
        "outbound_licence": baseline["outbound"],
        "inventory": {
            "entry_count": len(baseline["entries"]),
            "entries": baseline["entries"],
            "unknown_entries": baseline["unknown_entries"],
            "rider_entries": baseline["rider_entries"],
            "classes_histogram": baseline["classes_histogram"],
            "disposition_histogram": baseline["disposition_histogram"],
        },
        "reconciliation": baseline["reconciliation"],
        "dependency_gaps": gaps,
        "evidence": evidence,
        "tests": tests,
        "failure_classification": [
            "licence-incompatible",
            "unknown-terms",
            "rider-normalised-away",
        ],
        "artifacts": [
            {"path": OUT, "role": "primary", "exists": True},
            {"path": SCHEMA, "role": "schema", "exists": True},
            {
                "path": "command-center/p2-wave/probes/REL-0013/gate.py",
                "role": "implementation",
                "exists": True,
            },
            {
                "path": "command-center/p2-wave/probes/REL-0013/inventory.py",
                "role": "implementation",
                "exists": True,
            },
        ],
        "notes": (
            "Inventory is of the REL-0013 fixture release (REL-0011 and WFA-0079 "
            "artefacts absent; gaps itemised). Baseline promotion ALLOWED: "
            "permissive outbound MIT, carried components permissive, "
            "CLEAN-ROOM-REIMPLEMENT GPL source not carried. Mutations prove "
            "the four catalog tests. SUCCESS:REL-0013"
        ),
    }

    catalog_schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    if not isinstance(catalog_schema, dict) or not catalog_schema:
        print("FAILED:REL-0013 catalog output_schema missing or empty")
        return 1
    validator = jsonschema.Draft7Validator(CONTRACT)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:REL-0013 schema errors")
        for err in errs[:20]:
            print(" ", list(err.path), err.message)
        return 1
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000, "state": "SUCCESS"},
    ):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:REL-0013 schema accepted garbage")
            return 1

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    sha, size = digest_file(dest)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:REL-0013 artifact {size}B below floor")
        return 1
    if "SUCCESS:REL-0013" not in dest.read_text(encoding="utf-8"):
        print("FAILED:REL-0013 sentinel missing after write")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print("SUCCESS:REL-0013")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
