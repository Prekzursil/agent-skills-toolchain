#!/usr/bin/env python3
"""Probe 1: independent expressibility replication.

A second mapper (reverse-sorted walk + JSON round-trip) remaps the same three
sampled capabilities and must reach the same verdict and canonical sha256 as
the author mapper recorded in DESIGN.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import mapper as M  # noqa: E402

SAMPLES = Path(__file__).resolve().parent / "samples.json"
DESIGN = REPO / "command-center/phase3/A1/DESIGN.json"


def main() -> int:
    samples_doc = json.loads(SAMPLES.read_text(encoding="utf-8"))
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    samples = samples_doc["samples"]
    if len(samples) != 3:
        print("FAILED:ARC-0003-probe1 expected 3 samples")
        return 1
    kinds = [s["kind"] for s in samples]
    if kinds != ["skill", "workflow_blueprint", "council_preset"]:
        print(f"FAILED:ARC-0003-probe1 kinds={kinds}")
        return 1
    by_id = {row["id"]: row for row in design.get("samples") or []}
    rows = []
    fail = False
    for cap in samples:
        author = M.transcribe_author(cap)
        indep = M.transcribe_independent(cap)
        ok, why = M.same_verdict(author, indep)
        recorded = by_id.get(cap["id"]) or {}
        rec_ok = recorded.get("verdict") == author.get("verdict") == "EXPRESSIBLE"
        if recorded.get("sha256") and recorded.get("sha256") != author.get("sha256"):
            rec_ok = False
            why = f"design sha256 drift {recorded.get('sha256')} != {author.get('sha256')}"
        if not ok or not rec_ok:
            fail = True
        rows.append(
            {
                "id": cap["id"],
                "kind": cap["kind"],
                "source_id": cap["source_id"],
                "author_verdict": author.get("verdict"),
                "independent_verdict": indep.get("verdict"),
                "author_sha256": author.get("sha256"),
                "independent_sha256": indep.get("sha256"),
                "match": ok and rec_ok,
                "why": why if ok else why,
            }
        )
        print(
            f"sample id={cap['id']} kind={cap['kind']} source_id={cap['source_id']} "
            f"author={author.get('verdict')} indep={indep.get('verdict')} "
            f"sha_match={author.get('sha256')==indep.get('sha256')} recorded={rec_ok}"
        )
    matched = sum(1 for r in rows if r["match"])
    print(f"matched={matched}/3 fail={fail}")
    if fail or matched != 3:
        print("FAILED:ARC-0003-probe1 independent replication disagreement")
        return 1
    print("SUCCESS:ARC-0003-probe1 independent expressibility replication")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
