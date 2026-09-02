#!/usr/bin/env python3
"""Probe 2: distinct findings stay apart; collapse keeps the union of anchors.

Both-states: the detector is silent on two genuinely different mechanisms
and fires on a known-duplicate pair, preserving every evidence anchor.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import contract as C  # noqa: E402
import engine as E  # noqa: E402
import findings as F  # noqa: E402
import schema_local as SL  # noqa: E402

ART = REPO / C.OUTPUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:SYN-0017-probe2 {msg}")
    return 1


def main() -> int:
    run = E.run()
    if not run["ok"]:
        print("errors=" + " | ".join(run["errors"]))
        return fail("live detector invariants failed")

    dc = run["distinct_pair_control"]
    print(
        f"distinct {dc['left_id']}/{dc['right_id']} collapsed={dc['collapsed']} "
        f"lex={dc['lexical_score']} emb={dc['embedding_score']} "
        f"agreement={dc['agreement']}"
    )
    if dc["collapsed"]:
        return fail("two genuinely distinct findings were collapsed")
    if dc["lexical_score"] >= C.LEXICAL_THRESHOLD:
        return fail("distinct pair leaked over the lexical threshold")
    if dc["embedding_score"] >= C.EMBEDDING_THRESHOLD:
        return fail("distinct pair leaked over the embedding threshold")

    loc = run["lexical_only_coverage"]
    print(
        f"rewrite collapsed={loc['collapsed']} scores_like_distinct="
        f"{loc['scores_like_distinct']} lex={loc['lexical_score']} "
        f"emb={loc['embedding_score']}"
    )
    if loc["collapsed"] or not loc["scores_like_distinct"]:
        return fail("full-rewrite coverage disclosure invalid")

    ok, msg = E.union_holds(run["findings"], run["collapses"])
    print(f"anchor_union={msg}")
    if not ok:
        return fail(msg)

    index = {str(r["id"]): r for r in run["findings"]}
    pair_cluster = None
    for c in run["collapses"]:
        ids = set(c["member_ids"])
        if F.BASE_ID in ids and F.RENAME_ID in ids:
            pair_cluster = c
            break
    if pair_cluster is None:
        return fail("incumbent/rename cluster missing")
    want = set(index[F.BASE_ID]["evidence_anchors"]) | set(
        index[F.RENAME_ID]["evidence_anchors"]
    )
    got = set(pair_cluster["evidence_anchors_union"])
    print(f"rename_pair_union_has_both={want <= got} want={sorted(want)}")
    if not want <= got:
        return fail("collapse dropped an evidence anchor from incumbent or rename")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if C.SENTINEL not in text:
        return fail("catalog completion_sentinel absent from artifact")
    doc = json.loads(text)
    schema_errs = SL.errors(doc)
    if schema_errs:
        return fail("schema " + "; ".join(schema_errs[:8]))
    art_dc = SL.pick(doc, "distinct_pair_control") or {}
    if art_dc.get("collapsed") is not False:
        return fail("artifact distinct_pair_control.collapsed is not false")
    if str(art_dc.get("left_id")) != dc["left_id"] or str(art_dc.get("right_id")) != dc["right_id"]:
        return fail("artifact distinct pair ids drifted")

    art_loc = SL.pick(doc, "lexical_only_coverage") or {}
    if art_loc.get("scores_like_distinct") is not True:
        return fail("artifact did not disclose lexical-only full-rewrite coverage")

    print("SUCCESS:SYN-0017-probe2 distinct pair kept apart; collapse union holds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
