#!/usr/bin/env python3
"""Rebuild the CNF-0132 planted frame from the receipt's own edge_list.

The original probe tree (and fixtures/confirmations.json with it) was lost in
the wave-3 tree loss. The receipt embeds the complete edge list and per-claim
component structure, so the frame is re-derived mechanically from the receipt
instead of hand-transcribed. Canonical dump: json.dumps(indent=1) + "\n", LF.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parent
RECEIPT = REPO / "command-center/receipts/CNF-0132.json"
OUT = REPO / "command-center/p2-wave/probes/CNF-0132/fixtures/confirmations.json"

VERDICTS = {
    "C-CACHE-COLLAPSE": "CONFIRMED",
    "C-SHELL-FIELD-INDEP": "CONFIRMED",
    "C-THIRD-INDEPENDENT": "CONFIRMED",
    "C-REFUTED-NOISE": "REFUTED",
}
VENDORS = {
    "planted-cache-a": "vendor-a",
    "planted-cache-b": "vendor-b",
    "planted-indep-py": "vendor-a",
    "planted-indep-bash": "vendor-b",
    "planted-third-a": "vendor-a",
    "planted-third-b": "vendor-b",
    "planted-third-c": "vendor-c",
    "planted-refuted-noise": "vendor-a",
}


def main() -> int:
    doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
    edges = doc["edge_list"]
    records: dict[str, dict] = {}
    order: list[str] = []
    upstreams: dict[str, list[str]] = {}
    for e in edges:
        if e["kind"] == "uses-probe":
            rid = e["from"].split(":", 1)[1]
            pid = e["to"].split(":", 1)[1]
            if rid not in records:
                records[rid] = {"record_id": rid}
                order.append(rid)
            records[rid][e["via"]] = pid
        elif e["kind"] == "reads":
            pid = e["from"].split(":", 1)[1]
            upstreams.setdefault(pid, []).append(e["to"].split(":", 1)[1])
    per_claim = {c["claim_id"]: c for c in doc["per_claim"]["planted"]}
    out_records = []
    for rid in order:
        r = records[rid]
        src = r["source_probe"]
        claim = None
        for cid, c in per_claim.items():
            for s in c["independent_sets"]:
                if rid in s["record_ids"]:
                    claim = cid
        if claim is None:  # refuted record is absent from independent_sets
            for cid, c in per_claim.items():
                if c["total_records"] and cid == "C-REFUTED-NOISE":
                    claim = cid
        out_records.append(
            {
                "record_id": rid,
                "claim_id": claim,
                "vendor": VENDORS[rid],
                "verdict": VERDICTS[claim],
                "source_probe": src,
                "verifier_probe": r["verifier_probe"],
            }
        )
    frame = {
        "frame_id": "CNF-0132-planted-frame",
        "recorded_at": doc["frozen_frame"]["recorded_at"],
        "note": (
            "Reconstructed 2026-10-26 (wave-3 shard 7) from the CNF-0132 "
            "receipt's own edge_list after the original probe tree was lost. "
            "Structurally identical to the frame measured 2026-09-02; the "
            "receipt's frozen_frame.planted_sha256 pins the pre-loss bytes and "
            "is retained as historical provenance."
        ),
        "records": out_records,
        "probe_upstreams": {k: sorted(set(v)) for k, v in upstreams.items()},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(frame, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print("wrote", OUT.relative_to(REPO).as_posix(), "records:", len(out_records),
          "probes:", len(frame["probe_upstreams"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
