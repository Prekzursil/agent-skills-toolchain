#!/usr/bin/env python3
"""Probe 1: side-by-side matrix is computed, not asserted.

Independent recompute of descriptor atoms + set intersection must match the
library matrix. Mutating a descriptor must change SHARED / VENDOR-ONLY rows.
A hardcoded common-subset constant cannot survive adding a tool to both
vendors. Schema must reject garbage.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from load_lib import ensure_import, repo  # noqa: E402
from schema_ok import errors as schema_errors  # noqa: E402

ensure_import()
from vendor_adapter.negotiate import (  # noqa: E402
    CONTEXT_THRESHOLDS,
    capability_matrix,
    common_subset,
    load_published_descriptors,
    union_atoms,
)

REPO = repo()
RECEIPT = REPO / "command-center" / "receipts" / "IMP-0419.json"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0419-probe1 {msg}")
    return 1


def independent_atoms(doc: dict) -> set[str]:
    """Second implementation: flatten typed fields without calling the library."""
    atoms: set[str] = set()
    for tool in doc["tools"]:
        atoms.add(f"tool:{tool}")
    perm = doc["permission_model"]
    atoms.add(f"permission_model:{perm['kind']}")
    if perm.get("fail_closed") is True:
        atoms.add("permission:fail_closed")
    if perm.get("output_last_message_file") is True:
        atoms.add("permission:output_last_message_file")
    stream = doc["streaming"]
    if stream.get("token_stream") is True:
        atoms.add("streaming:token_stream")
    if stream.get("blocking_foreground") is True:
        atoms.add("streaming:blocking_foreground")
    schema = doc["schema_support"]
    if schema.get("json_schema") is True:
        atoms.add("schema:json_schema")
    if schema.get("typed_work_result") is True:
        atoms.add("schema:typed_work_result")
    if schema.get("structured_outputs") is True:
        atoms.add("schema:structured_outputs")
    prompt = doc["prompt_transport"]
    if prompt.get("inline_allowed") is True:
        atoms.add("prompt:inline_allowed")
    if prompt.get("file_required") is True:
        atoms.add("prompt:file_required")
    tokens = int(doc["context_window_tokens"])
    for threshold in CONTEXT_THRESHOLDS:
        if tokens >= threshold:
            atoms.add(f"context_window>={threshold}")
    return atoms


def independent_matrix(descriptors: dict[str, dict]) -> list[dict]:
    per = {vendor: independent_atoms(doc) for vendor, doc in descriptors.items()}
    vendors = sorted(per)
    union: set[str] = set()
    for group in per.values():
        union |= group
    n = len(vendors)
    rows = []
    for cap in sorted(union):
        holders = [v for v in vendors if cap in per[v]]
        if len(holders) == n:
            marker = "SHARED"
            exclusive_to = None
        else:
            marker = "VENDOR-ONLY"
            exclusive_to = holders[0] if len(holders) == 1 else None
        rows.append(
            {
                "capability": cap,
                "marker": marker,
                "exclusive_to": exclusive_to,
                "vendors": {v: (cap in per[v]) for v in vendors},
            }
        )
    return rows


def by_cap(rows: list[dict]) -> dict[str, dict]:
    return {r["capability"]: r for r in rows}


def main() -> int:
    descriptors = load_published_descriptors()
    if "anthropic" not in descriptors or "openai" not in descriptors:
        return fail("published descriptors must include anthropic and openai")

    indep = independent_matrix(descriptors)
    live = capability_matrix(descriptors)
    indep_map = by_cap(indep)
    live_map = by_cap(live)
    print(f"independent_rows={len(indep)} library_rows={len(live)}")
    if set(indep_map) != set(live_map):
        extra = sorted(set(live_map) - set(indep_map))
        missing = sorted(set(indep_map) - set(live_map))
        return fail(f"capability set mismatch extra={extra} missing={missing}")

    vendor_only = 0
    shared = 0
    for cap, want in indep_map.items():
        got = live_map[cap]
        if got["marker"] != want["marker"]:
            return fail(f"{cap} marker library={got['marker']} independent={want['marker']}")
        if got["exclusive_to"] != want["exclusive_to"]:
            return fail(f"{cap} exclusive_to mismatch")
        if got["vendors"] != want["vendors"]:
            return fail(f"{cap} vendor booleans mismatch")
        if want["marker"] == "VENDOR-ONLY":
            vendor_only += 1
            if not want["exclusive_to"]:
                return fail(f"{cap} VENDOR-ONLY without exclusive_to")
        else:
            shared += 1
    print(f"marker_tally SHARED={shared} VENDOR-ONLY={vendor_only}")
    if vendor_only < 1:
        return fail("matrix has no VENDOR-ONLY row (vendors cannot be identical)")
    if shared < 1:
        return fail("matrix has no SHARED row")

    indep_inter = set.intersection(
        *(independent_atoms(d) for d in descriptors.values())
    )
    live_inter = set(common_subset(descriptors))
    print(f"independent_intersection={sorted(indep_inter)}")
    print(f"library_intersection={sorted(live_inter)}")
    if indep_inter != live_inter:
        return fail("common subset is not the computed intersection")

    # Mutation A: add WebFetch to both vendors → must enter the intersection.
    both = copy.deepcopy(descriptors)
    for doc in both.values():
        if "WebFetch" not in doc["tools"]:
            doc["tools"] = list(doc["tools"]) + ["WebFetch"]
    if "tool:WebFetch" not in common_subset(both):
        return fail("adding WebFetch to both vendors did not grow the intersection")
    wf = by_cap(capability_matrix(both))["tool:WebFetch"]
    if wf["marker"] != "SHARED":
        return fail("WebFetch on both vendors is not SHARED")
    print("mutation_both_webfetch SHARED and in intersection")

    # Mutation B: add WebFetch to anthropic only → VENDOR-ONLY, not in intersection.
    one = copy.deepcopy(descriptors)
    if "WebFetch" not in one["anthropic"]["tools"]:
        one["anthropic"]["tools"] = list(one["anthropic"]["tools"]) + ["WebFetch"]
    if "tool:WebFetch" in common_subset(one):
        return fail("anthropic-only WebFetch leaked into the intersection")
    wf_one = by_cap(capability_matrix(one))["tool:WebFetch"]
    if wf_one["marker"] != "VENDOR-ONLY" or wf_one["exclusive_to"] != "anthropic":
        return fail(f"anthropic-only WebFetch row {wf_one}")
    print("mutation_anthropic_webfetch VENDOR-ONLY exclusive_to=anthropic")

    # Mutation C: strip a shared tool from openai → it leaves the intersection.
    stripped = copy.deepcopy(descriptors)
    stripped["openai"]["tools"] = [t for t in stripped["openai"]["tools"] if t != "Read"]
    if "tool:Read" in common_subset(stripped):
        return fail("removing Read from openai left it in the intersection")
    read_row = by_cap(capability_matrix(stripped))["tool:Read"]
    if read_row["marker"] != "VENDOR-ONLY" or read_row["exclusive_to"] != "anthropic":
        return fail(f"stripped Read row {read_row}")
    print("mutation_strip_read VENDOR-ONLY exclusive_to=anthropic")

    garbage = {"totally": "unrelated", "passing_tests": 999999}
    g_errs = schema_errors(garbage)
    print(f"garbage_schema_errors={len(g_errs)}")
    if not g_errs:
        return fail("schema accepted unrelated garbage")

    if RECEIPT.is_file():
        receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
        r_errs = schema_errors(receipt)
        if r_errs:
            return fail(f"receipt schema {r_errs[0]}")
        report = receipt.get("report") if isinstance(receipt.get("report"), dict) else {}
        matrix_rows = receipt.get("capability_matrix") or report.get("capability_matrix") or []
        receipt_caps = {
            row["capability"]: row["marker"]
            for row in matrix_rows
        }
        live_caps = {row["capability"]: row["marker"] for row in live}
        if receipt_caps != live_caps:
            return fail("receipt matrix does not match live computed matrix")
        receipt_inter = set(
            receipt.get("negotiated_common_subset")
            or report.get("negotiated_common_subset")
            or []
        )
        if receipt_inter != live_inter:
            return fail("receipt common subset is not the live intersection")
        print("receipt_matches_live_computed_matrix=True")
    else:
        print("receipt_absent_on_this_run (library checks only)")

    union = union_atoms(descriptors)
    print(
        json.dumps(
            {
                "pass": True,
                "probe": "probe1-matrix-computed",
                "unit_id": "IMP-0419",
                "shared": shared,
                "vendor_only": vendor_only,
                "union": len(union),
                "intersection": len(live_inter),
            }
        )
    )
    print("SUCCESS:IMP-0419-probe1 matrix computed not asserted; VENDOR-ONLY present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
