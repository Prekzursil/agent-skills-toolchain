#!/usr/bin/env python3
"""Probe 1: catalog known-present / known-broken / whitespace / detector-self controls."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import classifier as C  # noqa: E402
import harvest as H  # noqa: E402

PLANTED = {row["id"]: row for row in H.harvest_planted()}


def must(cid: str, expect: str) -> None:
    row = PLANTED[cid]
    got = C.classify_quote(row["quote"], row["source_path"])
    klass = got["class"]
    print(f"{cid} expect={expect} got={klass} resolution={got.get('resolution')}")
    if klass != expect:
        raise SystemExit(f"FAILED:CNF-0164-probe1 {cid} expected {expect} got {klass}")


def detector_self_check() -> None:
    src_rel = "command-center/p2-wave/probes/CNF-0164/fixtures/source.txt"
    loaded = C.load_source(src_rel)
    if not loaded["ok"]:
        raise SystemExit("FAILED:CNF-0164-probe1 planted source unreadable")
    present = C.known_present_slice(loaded["text"])
    if not present:
        raise SystemExit("FAILED:CNF-0164-probe1 no known-present slice")
    klass = C.classify_loaded(present, loaded["text"])
    print(f"DETECTOR-SELF known_present exact={klass == 'exact'!s} slice={present[:60]!r}")
    if klass != "exact":
        raise SystemExit("FAILED:CNF-0164-probe1 detector cannot find a known-present quote")
    absent_row = PLANTED["CTRL-ABSENT"]
    absent = C.classify_against_text(absent_row["quote"], loaded["text"])
    if not absent["detector_self_check"]:
        raise SystemExit("FAILED:CNF-0164-probe1 absent issued without detector self-check")
    if absent["class"] != "absent":
        raise SystemExit(f"FAILED:CNF-0164-probe1 absent control class={absent['class']}")


def main() -> int:
    for cid, expect in (
        ("CTRL-EXACT", "exact"),
        ("CTRL-EXACT-CRLF", "exact"),
        ("CTRL-PARAPHRASE", "paraphrase"),
        ("CTRL-WHITESPACE", "whitespace-different"),
        ("CTRL-ABSENT", "absent"),
        ("CTRL-EXTERNAL-NO-ARCHIVE", "NOT-CHECKED"),
    ):
        must(cid, expect)
    detector_self_check()
    # Cross-check: one-word-altered must not be exact or whitespace-different
    para = C.classify_quote(
        PLANTED["CTRL-PARAPHRASE"]["quote"],
        PLANTED["CTRL-PARAPHRASE"]["source_path"],
    )
    if para["class"] == "exact":
        raise SystemExit("FAILED:CNF-0164-probe1 paraphrase control classified exact")
    ws = C.classify_quote(
        PLANTED["CTRL-WHITESPACE"]["quote"],
        PLANTED["CTRL-WHITESPACE"]["source_path"],
    )
    if ws["class"] == "paraphrase":
        raise SystemExit("FAILED:CNF-0164-probe1 whitespace control classified paraphrase")
    print("SUCCESS:CNF-0164-probe1 known-present known-broken whitespace detector-self")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
