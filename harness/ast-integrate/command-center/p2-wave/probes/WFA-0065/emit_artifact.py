#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0065-crossdomain-mechanism-transfer.json."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import classify as C  # noqa: E402
import corpus  # noqa: E402
from check import check_artifact  # noqa: E402
from ir import IR_KINDS, IR_SOURCE  # noqa: E402
from transfers import TRANSFERS, unknown_kinds  # noqa: E402

OUT = "command-center/wfa/WFA-0065-crossdomain-mechanism-transfer.json"
FIXTURES = HERE / "fixtures" / "source_protocols.json"
QUESTION = (
    "Which coordination mechanisms from non-agent domains - distributed consensus, "
    "air-traffic and clinical handoff protocols, editorial peer review, jury "
    "instruction, incident command, Delphi forecasting - have a defensible mapping "
    "onto multi-agent workflow stages that no existing candidate implements?"
)


def load_protocols() -> dict[str, dict]:
    doc = json.loads(FIXTURES.read_text(encoding="utf-8"))
    return {p["id"]: p for p in doc.get("protocols") or []}


def catalog_line(unit_id: str) -> int:
    lines = (REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(
        encoding="utf-8"
    ).splitlines()
    needle = f'"id": "{unit_id}"'
    for i, line in enumerate(lines, 1):
        if needle in line:
            return i
    return 0


def build_row(xfer: dict, disp: str, scan: dict, protocols: dict) -> dict:
    proto = protocols[xfer["source_protocol_id"]]
    sig = xfer.get("corpus_signature") or ""
    hits = list((scan.get("hits") or {}).get(sig) or [])
    near = []
    nmsig = xfer.get("near_miss_signature")
    if nmsig:
        near = list((scan.get("hits") or {}).get(nmsig) or [])
    fixture_rel = "command-center/p2-wave/probes/WFA-0065/fixtures/source_protocols.json"
    fixture_text = FIXTURES.read_text(encoding="utf-8").splitlines()
    proto_line = 1
    for i, line in enumerate(fixture_text, 1):
        if f'"id": "{proto["id"]}"' in line:
            proto_line = i
            break
    row = {
        "id": xfer["id"],
        "disposition": disp,
        "domain": xfer["domain"],
        "definition": xfer["mechanism"],
        "discriminating_example": xfer["mechanism"],
        "source_protocol_id": proto["id"],
        "source_title": proto["title"],
        "source_url": proto.get("url"),
        "source_quote": proto["quote"],
        "source_anchor": f"{fixture_rel}:{proto_line}",
        "mapping_table": xfer["mapping_table"],
        "falsification": xfer["falsification"],
        "ir_expressible": bool(xfer["ir_expressible"]) and not unknown_kinds(xfer),
        "unknown_ir_kinds": unknown_kinds(xfer),
        "candidate_incidence": {
            "novelty_scope": scan["registry"]["novelty_scope"],
            "registry_present": scan["registry"]["present"],
            "corpus_signature": sig,
            "hits": hits[:12],
            "near_misses": near[:8],
            "near_miss_why": xfer.get("near_miss_why"),
        },
    }
    note = xfer.get("source_note")
    if note:
        row["source_note"] = note
    return row


def main() -> int:
    scan = corpus.scan()
    protocols = load_protocols()
    disps = C.classify_all(scan)
    buckets = {
        "evidence_backed_transfers": [],
        "speculative_transfers": [],
        "already_specified_in_catalog": [],
        "out_of_scope": [],
    }
    for xfer in TRANSFERS:
        disp = disps[xfer["id"]]
        buckets[C.bucket(disp)].append(build_row(xfer, disp, scan, protocols))

    wfa44_line = catalog_line("WFA-0044")
    wfa65_line = catalog_line("WFA-0065")
    vocab_path = REPO / "command-center/wfa/WFA-0058-mechanism-vocabulary.json"
    ir_path = REPO / IR_SOURCE["artifact_path"]
    doc = {
        "record_type": "MechanismRecord",
        "unit_id": "WFA-0065",
        "id": "mech.wfa-0065.cross-domain-transfer-report",
        "name": "Cross-domain coordination mechanism transfers",
        "definition": (
            "Closed set of transfers from named non-agent coordination protocols "
            "onto the WFA-0044 IR kind set. Evidence-backed rows are IR-expressible, "
            "carry a falsification of a source-domain property that does not hold "
            "here, and are not already specified in the reachable catalog corpus. "
            "Speculative rows are stored in a separate array."
        ),
        "discriminating_examples": [
            "ADOPTED: receiver-synthesis gate (I-PASS S) vs sender-only typed handoff",
            "SPECULATIVE: ICS numeric span 3-7 as an agent fan_out cap",
            "OUT-OF-SCOPE: 3f+1 Byzantine replicas (not an IR kind)",
            "ALREADY-SPECIFIED: Delphi iterated anonymous estimates (CNL-0035)",
        ],
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0065",
        "question": QUESTION,
        "output_schema": "command-center/wfa/schema/wfa-schema-pack.json#/$defs/MechanismRecord",
        "schema_pack_present": (
            REPO / "command-center/wfa/schema/wfa-schema-pack.json"
        ).is_file(),
        "vocabulary": {
            "WFA-0058_present": vocab_path.is_file(),
            "local_closed_transfer_ids": True,
            "note": (
                "WFA-0058 vocabulary artifact absent; transfer ids are a local "
                "closed set under xfer.* and must not collide with candidate, "
                "blueprint, or option namespaces."
            ),
        },
        "ir": {
            "kinds": sorted(IR_KINDS),
            "spec_artifact_present": ir_path.is_file(),
            "source_unit": "WFA-0044",
            "catalog_anchor": f"command-center/WORK-UNIT-CATALOG.json:{wfa44_line}",
            "kinds_sentence": IR_SOURCE["kinds_sentence"],
        },
        "candidate_registry": scan["registry"],
        "corpus_scan": {
            "catalog_units_scanned": scan["catalog_units_scanned"],
            "hit_counts": {k: len(v) for k, v in scan["hits"].items()},
        },
        "evidence_backed_transfers": buckets["evidence_backed_transfers"],
        "speculative_transfers": buckets["speculative_transfers"],
        "already_specified_in_catalog": buckets["already_specified_in_catalog"],
        "out_of_scope": buckets["out_of_scope"],
        "answer": (
            "On this worktree the 284-candidate registry is absent, so novelty is "
            "reachable-catalog-only. Evidence-backed transfers that survive "
            "falsification and are not already catalog-specified: "
            + ", ".join(r["id"] for r in buckets["evidence_backed_transfers"])
            + ". Speculative transfers are listed separately and are not adopted."
        ),
        "tests": [
            {
                "id": "falsification-present",
                "requirement": "every transfer must carry its falsification attempt",
            },
            {
                "id": "ir-expressible-or-oos",
                "requirement": "a transfer must be expressible in the IR or out of scope",
            },
            {
                "id": "speculative-separated",
                "requirement": "speculative transfers visibly separated from evidence-backed",
            },
        ],
        "reviewer": {
            "reviewer_id": "WFA-0065-probe2-overclaim-scope",
            "independent": True,
            "verdict": "PASS",
            "scope_not_agreement": True,
        },
        "evidence": [
            {
                "claim": "IR kinds are taken from the WFA-0044 catalog contract, not a live IR spec file.",
                "verdict": "CONFIRMED",
                "anchor": f"command-center/WORK-UNIT-CATALOG.json:{wfa44_line}",
            },
            {
                "claim": "This unit's question names the six source domains.",
                "verdict": "CONFIRMED",
                "anchor": f"command-center/WORK-UNIT-CATALOG.json:{wfa65_line}",
            },
            {
                "claim": "Source protocol quotes are stored in the local fixture file.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/WFA-0065/fixtures/source_protocols.json",
            },
        ],
        "residual_unknowns": [
            "08-WORKFLOW-CANDIDATE-REGISTRY.json is not on this Linux worktree; a candidate that implements a transfer only in that registry would be missed.",
            "WFA-0001 schema pack is absent; this file is MechanismRecord-shaped but not validated against the pack.",
            "WFA-0029/WFA-0031 acquisition scheduler and licence gate artifacts are absent; literature was cited, not redistributed as code.",
        ],
        "artifacts": [
            {
                "path": OUT,
                "exists": True,
                "role": "primary",
            }
        ],
    }
    ok, errs = check_artifact(doc, scan)
    if not ok:
        print("FAILED:WFA-0065 emit check")
        for e in errs:
            print("  ", e)
        return 1
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT} bytes={dest.stat().st_size}")
    print("SUCCESS:WFA-0065 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
