#!/usr/bin/env python3
"""Probe 2: use-vs-mention control and recall-limit honesty.

A mention-only token must not be counted as a defined/dropped mechanism.
The artifact must list unread live artifacts rather than implying exhaustiveness.
A naive backtick-as-definition mutant must fire on the mention-only plant.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import sweep as S  # noqa: E402

OUT = REPO / "command-center/wfa/WFA-0019-sweep-prior-artifacts.json"
MENTION_ONLY = "named.only-in-inventory"
DROPPED_REQUIRED = ("dropped.hook-pre-tool", "dropped.fusion-cert-map")
KEPT = "kept.stage-gate"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0019-probe2 {msg}")
    return 1


def main() -> int:
    if not OUT.is_file():
        return fail("artifact-missing")
    doc = json.loads(OUT.read_text(encoding="utf-8"))

    extracted_ids = [r["id"] for r in doc.get("extracted_constructs") or []]
    dropped_ids = [r["id"] for r in doc.get("dropped_mechanisms") or []]
    print(f"extracted={extracted_ids}")
    print(f"dropped={dropped_ids}")

    if MENTION_ONLY in extracted_ids or MENTION_ONLY in dropped_ids:
        return fail("mention-only-counted-as-definition")
    for need in DROPPED_REQUIRED:
        if need not in dropped_ids:
            return fail(f"missing-dropped {need}")
        if need not in extracted_ids:
            return fail(f"missing-extracted {need}")
    if KEPT in dropped_ids:
        return fail("kept-mechanism-reported-dropped")
    if KEPT not in extracted_ids:
        return fail("kept-mechanism-not-extracted")

    fab = doc.get("fabricated_anchors") or []
    if len(fab) < 2:
        return fail(f"fabricated-underreported n={len(fab)}")
    kinds = {r.get("kind") for r in fab}
    if kinds != {"fabricated-anchor"}:
        return fail(f"fabricated-kind-mix {kinds}")

    # Naive mutant: backtick mentions become definitions.
    naive = S.sweep_root(S.FIXTURE_CORPUS, naive=True)
    naive_ids = {d["id"] for d in naive["extracted_constructs"]}
    naive_dropped = {d["id"] for d in naive["dropped_mechanisms"]}
    if MENTION_ONLY not in naive_ids:
        return fail("naive-mutant-did-not-see-mention-token")
    if MENTION_ONLY not in naive_dropped:
        return fail("naive-mutant-did-not-drop-mention-token")
    print(
        f"use-vs-mention mention_only={MENTION_ONLY} real_excluded=True "
        f"naive_extracted=True naive_dropped=True"
    )

    recall = doc.get("recall_limit") or {}
    unread = recall.get("live_artifacts_unread") or []
    if recall.get("implied_exhaustiveness") is True:
        return fail("implied-exhaustiveness-true")
    if not isinstance(unread, list) or len(unread) < 8:
        return fail(f"recall-unread-too-small n={len(unread) if isinstance(unread, list) else 'na'}")
    if "00-CURRENT-STATE-INVENTORY.md" not in unread and doc.get("live_corpus_present"):
        # If live was actually read, unread may omit files that were opened.
        pass
    if not doc.get("live_corpus_present"):
        if "00-CURRENT-STATE-INVENTORY.md" not in unread:
            return fail("live-absent-but-00-not-in-unread")
        live_dropped = doc.get("live_dropped_mechanisms")
        if live_dropped not in ([], None):
            return fail("live-absent-but-live-dropped-claimed")
        print("live_corpus_present=False unread_includes_catalog_names=True live_dropped_unclaimed=True")
    else:
        print(f"live_corpus_present=True unread={len(unread)}")

    if "SUCCESS:WFA-0019" not in OUT.read_text(encoding="utf-8"):
        return fail("sentinel-absent")
    print("SUCCESS:WFA-0019-probe2 use-vs-mention recall-limit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
