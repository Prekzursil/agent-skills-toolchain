#!/usr/bin/env python3
"""Probe 2: origin tracing is not URL counting; cycle-only is not enough.

Mechanically independent of probe 1's both-states recount:
  * distinct-URL baseline is silent on every planted cycle
  * citation-cycle-only fires on independent CLAIM-18/19 (false positives)
  * content ablation of a planted cycle goes silent
  * injected content without a cycle stays silent; content+cycle fires
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import corpus as C  # noqa: E402
import detector as D  # noqa: E402

UNIT = "RES-0145"
OUT = REPO / (
    "command-center/research/evidence-quality/"
    "RES-0145-circular-citation-detection.json"
)
SENTINEL = "SUCCESS:RES-0145"
FRESH_NONCE = "plutonium hasp stiction of 99.7 newton metres"
FRESH_QTY = "99.7"


def fail(msg: str) -> int:
    print(f"FAILED:RES-0145-probe2 {msg}")
    return 1


def _cluster(docs: list[dict], cid: str) -> list[dict]:
    return [d for d in docs if d["cluster_id"] == cid]


def main() -> int:
    if not OUT.is_file():
        return fail("artifact missing")
    text = OUT.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel absent")
    doc = json.loads(text)

    planted = C.load_corpus()
    gold = C.gold_by_cluster()
    live_docs = C.documents_for_detector(planted)
    grouped: dict[str, list[dict]] = {}
    for row in live_docs:
        grouped.setdefault(row["cluster_id"], []).append(row)

    url_hits_on_cycles = 0
    cycle_only_fp = []
    for cid, members in grouped.items():
        if gold[cid] == "cycle" and D.url_count_fire(members):
            url_hits_on_cycles += 1
        if gold[cid] == "independent" and D.cycle_only_fire(members):
            cycle_only_fp.append(cid)

    print(f"url_count_fire_on_planted_cycles={url_hits_on_cycles}")
    print(f"cycle_only_false_positives={cycle_only_fp}")
    if url_hits_on_cycles != 0:
        return fail("URL-count baseline fired on a planted cycle")
    if set(cycle_only_fp) != {"CLAIM-18", "CLAIM-19"}:
        return fail(f"cycle-only FP set {cycle_only_fp}")

    all_urls = [d["url"] for d in live_docs]
    if len(all_urls) != len(set(all_urls)):
        return fail("corpus URLs are not all distinct; URL baseline is degenerate")

    # Ablation: strip shared content from CLAIM-01, keep the citation cycle.
    stripped = [
        D.mutate_strip_content(d, "c01-ablate") if d["cluster_id"] == "CLAIM-01" else d
        for d in live_docs
    ]
    stripped_res = D.evaluate(stripped)["CLAIM-01"]
    print(
        f"ablate_CLAIM-01 fire={stripped_res['fire']} "
        f"content={stripped_res['content_copy']} cycle={stripped_res['citation_cycle']}"
    )
    if stripped_res["fire"]:
        return fail("CLAIM-01 still fires after content ablation")
    if not stripped_res["citation_cycle"]:
        return fail("CLAIM-01 cycle lost during ablation")

    # Inject fresh distinctive content into CLAIM-11 without adding a cycle.
    injected = [
        D.mutate_inject_content(d, FRESH_NONCE, FRESH_QTY)
        if d["cluster_id"] == "CLAIM-11"
        else d
        for d in live_docs
    ]
    inj = D.evaluate(injected)["CLAIM-11"]
    print(
        f"inject_content_CLAIM-11 fire={inj['fire']} "
        f"content={inj['content_copy']} cycle={inj['citation_cycle']}"
    )
    if inj["fire"]:
        return fail("content without cycle should stay silent")
    if not inj["content_copy"]:
        return fail("injected nonce/qty did not register as content copy")

    cycled = D.mutate_add_cycle(_cluster(injected, "CLAIM-11"))
    rest = [d for d in injected if d["cluster_id"] != "CLAIM-11"]
    both = D.evaluate(rest + cycled)["CLAIM-11"]
    print(
        f"inject_content_and_cycle_CLAIM-11 fire={both['fire']} "
        f"content={both['content_copy']} cycle={both['citation_cycle']}"
    )
    if not both["fire"]:
        return fail("content plus cycle should fire")

    naive = doc.get("naive_baselines") or {}
    if naive.get("distinct_url_count_detection_rate") not in (0, 0.0):
        return fail("artifact URL baseline rate drifted")
    if sorted(naive.get("cycle_only_false_positive_clusters") or []) != [
        "CLAIM-18",
        "CLAIM-19",
    ]:
        return fail("artifact cycle-only FP list drifted")

    print("URL-count is not origin tracing; cycle-only is not origin tracing")
    print("SUCCESS:RES-0145-probe2 url-count not origin")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
