#!/usr/bin/env python3
"""Probe 1: lexical vote-gate on reasons + every raw anchor re-resolves.

Different field than probe 2: this probe never asks who won the planted
split. It re-reads each cited file:line and checks that no reason cites
agent count.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import adjudicate as A  # noqa: E402
import scenario as S  # noqa: E402

ART = S.REPO / S.OUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:SYN-0011-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "SYN-0011":
        return fail(f"unit_id {doc.get('unit_id')}")
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    sentinel = str(A.catalog_unit(S.REPO, "SYN-0011").get("completion_sentinel") or "")
    if sentinel not in text:
        return fail("completion_sentinel absent from artifact")

    if not A.reason_is_clean("placeholder reason about the planted file bytes"):
        return fail("clean-reason helper rejected an innocent string")
    bad = "because 2 of 3 agents agree and the majority vote settles it"
    if A.reason_is_clean(bad):
        return fail("lexical gate silent on planted vote-reason")

    rows = doc.get("adjudications") or []
    if len(rows) < 3:
        return fail(f"adjudications={len(rows)}")
    if doc.get("vote_citations") != 0:
        return fail("vote_citations not 0")

    for row in rows:
        if not A.reason_is_clean(str(row.get("reason") or "")):
            return fail(f"vote language in {row.get('id')} reason")
        anc = row.get("raw_anchor") or {}
        if anc.get("resolves") is not True:
            return fail(f"{row.get('id')} anchor resolves!=true")
        rel = str(anc.get("path") or "")
        line_no = int(anc.get("line") or 0)
        snippet = str(anc.get("snippet") or "")
        path = S.REPO / rel
        if not path.is_file():
            return fail(f"{row.get('id')} raw file missing {rel}")
        body = path.read_text(encoding="utf-8")
        lines = body.splitlines()
        if line_no < 1 or line_no > len(lines):
            return fail(f"{row.get('id')} line {line_no} oob in {rel}")
        if snippet not in body:
            return fail(f"{row.get('id')} snippet not in {rel}")
        live = lines[line_no - 1]
        if snippet[:12] not in live and snippet[:12] not in body:
            return fail(f"{row.get('id')} snippet prefix missing from {rel}:{line_no}")

    live_ids = {r["id"] for r in A.settle_all(S.REPO)}
    art_ids = {r["id"] for r in rows}
    if live_ids != art_ids:
        return fail(f"id mismatch live={sorted(live_ids)} art={sorted(art_ids)}")

    print(
        json.dumps(
            {
                "probe": "probe1-lexical-and-anchor",
                "unit_id": "SYN-0011",
                "adjudications": len(rows),
                "vote_citations": 0,
                "anchors_re_resolved": True,
                "vote_reason_control_fired": True,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:SYN-0011-probe1 lexical gate and resolving raw anchors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
