#!/usr/bin/env python3
"""Probe 2: both-states on live rows plus an independent reviewer phantom.

The reviewer adds a phantom manifest entry the author did not plant in
self_test (a different path) and confirms condition 12 rejects it. Live
currently-valid entries must still PASS, so the gate is not always-red.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import artifact_register as AR  # noqa: E402

ART = "command-center/receipts/CC-0009.json"
PHANTOM = "command-center/receipts/CC-0009-REVIEWER-PHANTOM.json"


def main() -> int:
    art = REPO / ART
    if not art.is_file():
        print("FAILED:CC-0009-probe2 receipt missing")
        return 1
    text = art.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CC-0009-probe2 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:CC-0009" not in text:
        print("FAILED:CC-0009-probe2 sentinel absent")
        return 1

    live_c12 = AR.evaluate_manifest(REPO)
    print(f"live_manifest {live_c12.result}: {live_c12.reason}")
    readings = live_c12.evidence.get("readings") or []
    for item in readings:
        print(
            f"  reader={item.get('reader')} path={item.get('path')} "
            f"first_key={item.get('first_parsed_key')!r} "
            f"records={item.get('record_count')} ok={item.get('ok')}"
        )
        if not item.get("ok"):
            print("FAILED:CC-0009-probe2 live row unreadable")
            return 1
        if item.get("first_parsed_key") is None and item.get("record_count") is None:
            print("FAILED:CC-0009-probe2 live row cited neither key nor count")
            return 1
    if not live_c12.ok:
        print("FAILED:CC-0009-probe2 live currently-valid entries did not pass")
        return 1
    if not any(item.get("path") == ART for item in readings):
        print("FAILED:CC-0009-probe2 live manifest missing CC-0009 receipt row")
        return 1

    mutated = copy.deepcopy(AR.load_manifest(REPO))
    mutated.setdefault("artifacts", []).append(
        {
            "path": PHANTOM,
            "sha256": "b" * 64,
            "bytes": 99,
            "present": True,
            "unit_id": "CC-0009-REVIEWER",
            "consumer": "json",
        }
    )
    phantom_c12 = AR.check_condition_12(REPO, manifest=mutated)
    print(f"reviewer_phantom {phantom_c12.result}: {phantom_c12.reason}")
    if phantom_c12.ok:
        print("FAILED:CC-0009-probe2 reviewer phantom was accepted")
        return 1
    if PHANTOM not in phantom_c12.reason and "absent:" not in phantom_c12.reason:
        print("FAILED:CC-0009-probe2 phantom rejection did not name absence")
        return 1

    garbage_rel = "command-center/p2-wave/probes/CC-0009/_reviewer_garbage.json"
    garbage = REPO / garbage_rel
    garbage.write_text("{not-json", encoding="utf-8")
    try:
        gdoc = copy.deepcopy(AR.load_manifest(REPO))
        sha, n = AR.digest_file(garbage)
        gdoc.setdefault("artifacts", []).append(
            {
                "path": garbage_rel,
                "sha256": sha,
                "bytes": n,
                "present": True,
                "unit_id": "CC-0009-REVIEWER",
                "consumer": "json",
            }
        )
        garbage_c12 = AR.check_condition_12(REPO, manifest=gdoc)
        print(f"reviewer_unparseable {garbage_c12.result}: {garbage_c12.reason}")
        if garbage_c12.ok:
            print("FAILED:CC-0009-probe2 present-but-unparseable was accepted")
            return 1
        if "json-parse" not in garbage_c12.reason:
            print("FAILED:CC-0009-probe2 unparseable rejection did not name json-parse")
            return 1
    finally:
        try:
            garbage.unlink()
        except OSError:
            pass

    reviewer = doc.get("reviewer") or {}
    if reviewer.get("independent") is not True or reviewer.get("verdict") != "PASS":
        print("FAILED:CC-0009-probe2 receipt reviewer is not independent PASS")
        return 1
    if reviewer.get("phantom_path") != PHANTOM:
        print("FAILED:CC-0009-probe2 receipt did not record the reviewer phantom path")
        return 1

    print(
        "SUCCESS:CC-0009-probe2 both-states live-pass "
        f"rows={len(readings)} phantom_rejected=True unparseable_rejected=True"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
