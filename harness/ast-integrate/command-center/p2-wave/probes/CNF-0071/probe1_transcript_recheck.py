#!/usr/bin/env python3
"""Probe 1: live re-read of every transcript-sourced claim at the cited offset.

Confirms verbatim presence, role, surrounding-turn meaning, and that the
emitted artifact matches this live pass. Does not trust the artifact's
self-report for classification.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from auditor import (  # noqa: E402
    ABSENT_ID,
    NEGATION_ID,
    USE_IDS,
    artifact_payload,
    audit_all,
    mention_control_pass,
)

ART = REPO / "command-center/confirmation/CNF-0071-transcript-claims.json"
SENTINEL_PREFIX = "SUCCESS:CNF-0071"


def main() -> int:
    rows = audit_all()
    printable = [
        {
            "id": r["id"],
            "verbatim_found": r["verbatim_found"],
            "role": r["role"],
            "verdict": r["verdict"],
            "line": r["source"]["line"],
            "byte_offset": r["source"]["byte_offset"],
        }
        for r in rows
    ]
    print(json.dumps({"probe": "probe1-transcript-recheck", "rows": printable}, sort_keys=True))

    control = mention_control_pass(rows)
    if not control["pass"]:
        print("FAILED:CNF-0071-probe1 mention-only control not MENTION")
        return 1

    by_id = {r["id"]: r for r in rows}
    for uid in USE_IDS:
        r = by_id[uid]
        if r["role"] != "USE" or not r["verbatim_found"]:
            print(f"FAILED:CNF-0071-probe1 {uid} role={r['role']}")
            return 1
        turn = r["surrounding_turn"]
        if r["source"]["quoted_span"] not in turn:
            print(f"FAILED:CNF-0071-probe1 {uid} span missing from surrounding turn")
            return 1
    neg = by_id[NEGATION_ID]
    if not neg["context_changes_meaning"] or neg["verdict"] != "CONTEXT-CHANGES-MEANING":
        print("FAILED:CNF-0071-probe1 negation did not change meaning")
        return 1
    absent = by_id[ABSENT_ID]
    if absent["verbatim_found"] or absent["verdict"] != "QUOTE-NOT-FOUND":
        print("FAILED:CNF-0071-probe1 absent quote not reported")
        return 1

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0071-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    body = artifact_payload(doc)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0071-probe1 self-declared {doc.get('state')}")
        return 1
    text = ART.read_text(encoding="utf-8")
    if SENTINEL_PREFIX not in text:
        print("FAILED:CNF-0071-probe1 sentinel absent")
        return 1
    art_rows = {c["id"]: c for c in body.get("citations") or []}
    for r in rows:
        a = art_rows.get(r["id"])
        if not a:
            print(f"FAILED:CNF-0071-probe1 artifact missing {r['id']}")
            return 1
        live_role = a.get("semantic_role") or a.get("role")
        live_verdict = a.get("audit_verdict") or a.get("verdict")
        if live_role != r["role"]:
            print(f"FAILED:CNF-0071-probe1 role drift on {r['id']}")
            return 1
        if live_verdict != r["verdict"]:
            print(f"FAILED:CNF-0071-probe1 audit_verdict drift on {r['id']}")
            return 1
        quote_ok = a.get("quote_verbatim", a.get("verbatim_found"))
        if quote_ok != r["verbatim_found"]:
            print(f"FAILED:CNF-0071-probe1 verbatim drift on {r['id']}")
            return 1
        art_turn = a.get("surrounding_turn") or a.get("surrounding_context")
        if art_turn != r["surrounding_turn"]:
            print(f"FAILED:CNF-0071-probe1 surrounding_turn drift on {r['id']}")
            return 1
        src = a.get("source") or {}
        byte_off = src.get("byte_offset", a.get("byte_offset", -2))
        if int(byte_off) != int(r["source"]["byte_offset"]):
            print(f"FAILED:CNF-0071-probe1 byte_offset drift on {r['id']}")
            return 1
    moc = body.get("mention_only_control") or {}
    if moc.get("classified_as") != "MENTION" or moc.get("pass") is not True:
        print("FAILED:CNF-0071-probe1 artifact mention_only_control not MENTION")
        return 1
    print("SUCCESS:CNF-0071-probe1 live transcript recheck matches artifact")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
