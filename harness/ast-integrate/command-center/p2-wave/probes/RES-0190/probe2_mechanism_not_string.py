#!/usr/bin/env python3
"""Probe 2: mechanism-level MERGE vs string equality; both-states planted pairs."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import cluster as C  # noqa: E402
import engine as E  # noqa: E402

UNIT = "RES-0190"
OUT = REPO / (
    "command-center/research/deep-research-design/"
    "RES-0190-breadth-versus-depth-budget-allocation.json"
)
SENTINEL = "SUCCESS:RES-0190"


def fail(msg: str) -> int:
    print(f"FAILED:RES-0190-probe2 {msg}")
    return 1


def main() -> int:
    if not OUT.is_file():
        return fail("artifact missing")
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    if SENTINEL not in OUT.read_text(encoding="utf-8"):
        return fail("sentinel absent")
    corpus = E.load_corpus()
    pairs = corpus.get("planted_pairs") or []
    if len(pairs) < 12:
        return fail(f"too few planted pairs {len(pairs)}")

    para_ok = 0
    cross_ok = 0
    for pair in pairs:
        row = C.pair_verdict(pair["left"], pair["right"])
        merged = row.get("verdict") == "MERGE"
        print(
            f"{pair['id']} gold_same={pair['gold_same']} verdict={row.get('verdict')} "
            f"j={row.get('jaccard')} c={row.get('cosine')}"
        )
        if pair["gold_same"]:
            if not merged:
                return fail(f"paraphrase {pair['id']} did not MERGE")
            para_ok += 1
            # string-equality mutant: different strings would overcount
            if pair["left"] == pair["right"]:
                return fail(f"{pair['id']} paraphrase texts are identical; mutant collapses")
        else:
            if merged:
                return fail(f"cross {pair['id']} false MERGE")
            cross_ok += 1
    if para_ok < 6 or cross_ok < 6:
        return fail(f"pair counts para={para_ok} cross={cross_ok}")

    live = E.run_experiment()
    arm = live["arms"]["80/20"]
    s_scan = int(arm["scanned_string_distinct"])
    m_scan = int(arm["scanned_mechanism_distinct"])
    print(f"80/20 scanned string_distinct={s_scan} mechanism_distinct={m_scan}")
    if s_scan <= m_scan:
        return fail("string equality did not overcount scanned 80/20 candidates")
    art_arm = (doc.get("arms") or {}).get("80/20") or {}
    if int(art_arm.get("scanned_string_distinct", -1)) != s_scan:
        return fail("artifact 80/20 string scan count drifted")
    if int(art_arm.get("scanned_mechanism_distinct", -1)) != m_scan:
        return fail("artifact 80/20 mechanism scan count drifted")

    # Both-states on a verified-set mutant: string count vs mechanism count
    # for 80/20 scanned pool must differ (overcount) and the mechanism count
    # is the one the policy uses.
    if doc.get("distinctness_rule") != "mechanism-level-AND-gate":
        return fail("artifact did not declare mechanism-level distinctness")

    print(f"paraphrase_merge={para_ok} cross_distinct={cross_ok} string_overcount=True")
    print("SUCCESS:RES-0190-probe2 mechanism not string")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
