#!/usr/bin/env python3
"""Probe 2: independent overclaim / novelty / anchor review.

Re-runs corpus scan and classification. Delphi, jury, and quorum must not be
adopted when the catalog already specifies them. Source anchors must resolve.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import corpus  # noqa: E402
from classify import classify_all  # noqa: E402
from ir import IR_SOURCE  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0065-crossdomain-mechanism-transfer.json"
MUST_NOT_ADOPT = (
    "xfer.delphi.anonymous-iterated-feedback",
    "xfer.jury.deciders-without-advocacy",
    "xfer.consensus.quorum-barrier",
    "xfer.paxos.byzantine-replicas",
    "xfer.ics.numeric-span-3-to-7",
)


def resolve_anchor(anchor: str) -> tuple[bool, str]:
    if ":" in anchor and not anchor.startswith("http"):
        rel, _, rest = anchor.partition(":")
        path = REPO / rel
        if not path.is_file():
            return False, f"missing {rel}"
        try:
            line_no = int(rest)
        except ValueError:
            text = path.read_text(encoding="utf-8")
            return True, f"file {rel} no-line"
        lines = path.read_text(encoding="utf-8").splitlines()
        if line_no < 1 or line_no > len(lines):
            return False, f"oob {rel}:{line_no}"
        return True, f"{rel}:{line_no} {lines[line_no - 1][:80]!r}"
    path = REPO / anchor
    if path.is_file():
        return True, anchor
    return False, f"unresolved {anchor}"


def main() -> int:
    if not ART.is_file():
        print("FAILED:WFA-0065-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    scan = corpus.scan()
    expected = classify_all(scan)
    adopted = {r["id"] for r in doc.get("evidence_backed_transfers") or []}
    speculative = {r["id"] for r in doc.get("speculative_transfers") or []}
    already = {r["id"] for r in doc.get("already_specified_in_catalog") or []}
    oos = {r["id"] for r in doc.get("out_of_scope") or []}
    live = {}
    for tid, disp in expected.items():
        if disp == "ADOPTED":
            live[tid] = "evidence"
        elif disp == "SPECULATIVE":
            live[tid] = "speculative"
        elif disp == "ALREADY-SPECIFIED-IN-CATALOG":
            live[tid] = "already"
        else:
            live[tid] = "oos"
    art_map = {}
    for tid in adopted:
        art_map[tid] = "evidence"
    for tid in speculative:
        art_map[tid] = "speculative"
    for tid in already:
        art_map[tid] = "already"
    for tid in oos:
        art_map[tid] = "oos"
    if live != art_map:
        print(f"FAILED:WFA-0065-probe2 classify mismatch live={live} art={art_map}")
        return 1
    print(f"classify_match=True n={len(live)}")

    for tid in MUST_NOT_ADOPT:
        if tid in adopted:
            print(f"FAILED:WFA-0065-probe2 overclaim adopted {tid}")
            return 1
        print(f"not_adopted {tid} ok")

    if doc.get("ir", {}).get("spec_artifact_present") is True:
        if not (REPO / IR_SOURCE["artifact_path"]).is_file():
            print("FAILED:WFA-0065-probe2 overclaim IR spec present")
            return 1
    if doc.get("vocabulary", {}).get("WFA-0058_present") is True:
        v = REPO / "command-center/wfa/WFA-0058-mechanism-vocabulary.json"
        if not v.is_file():
            print("FAILED:WFA-0065-probe2 overclaim vocabulary present")
            return 1
    if doc.get("candidate_registry", {}).get("present") is True:
        print("FAILED:WFA-0065-probe2 overclaim registry present")
        return 1

    for i, ev in enumerate(doc.get("evidence") or []):
        ok, why = resolve_anchor(str(ev.get("anchor") or ""))
        print(f"anchor[{i}] ok={ok} {why}")
        if not ok:
            print("FAILED:WFA-0065-probe2 unresolved evidence anchor")
            return 1

    for i, row in enumerate(doc.get("evidence_backed_transfers") or []):
        ok, why = resolve_anchor(str(row.get("source_anchor") or ""))
        print(f"source[{i}] {row.get('id')} ok={ok} {why}")
        if not ok:
            print("FAILED:WFA-0065-probe2 unresolved source anchor")
            return 1
        if not (row.get("falsification") or {}).get("attempted"):
            print(f"FAILED:WFA-0065-probe2 adopted without falsification {row.get('id')}")
            return 1

    rev = doc.get("reviewer") or {}
    if rev.get("independent") is not True or rev.get("scope_not_agreement") is not True:
        print("FAILED:WFA-0065-probe2 reviewer is not independent scope-only")
        return 1
    if "SUCCESS:WFA-0065" not in ART.read_text(encoding="utf-8"):
        print("FAILED:WFA-0065-probe2 sentinel absent")
        return 1
    print("SUCCESS:WFA-0065-probe2 overclaim novelty anchors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
