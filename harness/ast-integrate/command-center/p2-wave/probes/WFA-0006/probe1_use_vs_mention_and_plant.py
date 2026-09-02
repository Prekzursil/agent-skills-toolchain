#!/usr/bin/env python3
"""Probe 1: use-vs-mention + planted capability-asserting both-states.

Known-broken: any file that names 08/09/10 is a consumer.
Known-good: phrase/negation role scan. Mention-only fixture must stay
DISCOVERY-AWARE. Planted shipped-capability sentence must fire before
all-clear.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import classify_a as A  # noqa: E402
import graph as G  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0006-discovery-only-consumers.json"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0006-probe1 {msg}")
    return 1


def main() -> int:
    rows = G.iter_citations(REPO)
    mention = [r for r in rows if r["kind"] == "planted-mention"]
    plant = [r for r in rows if r["kind"] == "planted-capability"]
    if not mention:
        return fail("mention-only fixture not in reference graph")
    if not plant:
        return fail("capability-plant fixture not in reference graph")
    if not all(G.naive_is_consumer(r) for r in mention):
        return fail("naive namer-as-consumer missed mention fixture")
    for row in mention:
        role = A.classify_sentence(row["quoted_sentence"])
        if role != A.ROLE_DISCOVERY:
            return fail(
                f"mention counted as consumer {row['path']}:{row['line']} {role}"
            )
        if A.is_consumer(row["quoted_sentence"]):
            return fail("mention is_consumer true")
    fired = 0
    for row in plant:
        role = A.classify_sentence(row["quoted_sentence"])
        if role == A.ROLE_CAPABILITY:
            fired += 1
    if fired < 1:
        return fail("planted capability-asserting sentence silent")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if "SUCCESS:WFA-0006" not in text:
        return fail("sentinel absent")
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        return fail(f"self-declared {st}")
    controls = doc.get("controls") or {}
    if not controls.get("plant_detected"):
        return fail("artifact all-clear path without plant detection")
    if not controls.get("mention_clean"):
        return fail("artifact counted mention as consumer")
    if not controls.get("use_vs_mention_discriminates"):
        return fail("artifact use-vs-mention did not discriminate")
    if bool(doc.get("all_clear")) and not controls.get("plant_detected"):
        return fail("all-clear reported before plant fired")

    print(
        f"mention_rows={len(mention)} mention_consumers_a=0 "
        f"naive_mention_consumers={sum(1 for r in mention if G.naive_is_consumer(r))} "
        f"plant_fired={fired} all_clear={doc.get('all_clear')} "
        f"live={doc.get('live_citation_count')}"
    )
    print(
        "SUCCESS:WFA-0006-probe1 use-vs-mention silent; planted "
        "capability-asserting sentence detected"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
