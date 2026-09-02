#!/usr/bin/env python3
"""Probe 1: emit live artifact, then both-states full-rewrite + WFA-0007 plants."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import corpus as CORP  # noqa: E402
import emit_report as EMIT  # noqa: E402
import measures as M  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0008-embedding-duplicate-rescan.json"
SENTINEL = "SUCCESS:WFA-0008"
WANT_BOTH = ("exact-rename", "one-parameter-fork", "reworded-paraphrase")


def main() -> int:
    emitted = EMIT.main()
    if emitted != 0:
        print("FAILED:WFA-0008-probe1 emit failed")
        return 1

    docs = CORP.load_documents()
    index = CORP.by_id(docs)
    seed = index["seed.checkpoint-resume"]
    seed_text = CORP.scoring_text(seed)

    rows = []
    for doc in docs:
        cls = doc.get("class")
        if cls not in WANT_BOTH + ("full-rewrite", "decoy"):
            continue
        scored = M.score_pair(seed_text, CORP.scoring_text(doc))
        rows.append({"id": doc["id"], "class": cls, **scored})
        print(
            f"{cls} {doc['id']} lex={scored['lexical_score']} "
            f"lex_fire={scored['lexical_fired']} "
            f"band={scored['lexical_in_distinct_band']} "
            f"emb={scored['embedding_score']} emb_fire={scored['embedding_fired']}"
        )

    by_cls: dict[str, list] = {}
    for r in rows:
        by_cls.setdefault(r["class"], []).append(r)

    for cls in WANT_BOTH:
        hits = by_cls.get(cls) or []
        if not hits:
            print(f"FAILED:WFA-0008-probe1 missing class {cls}")
            return 1
        if not (hits[0]["lexical_fired"] and hits[0]["embedding_fired"]):
            print(f"FAILED:WFA-0008-probe1 {cls} did not fire under both methods")
            return 1

    decoys = by_cls.get("decoy") or []
    if len(decoys) < 3:
        print(f"FAILED:WFA-0008-probe1 expected 3 decoys, got {len(decoys)}")
        return 1
    for d in decoys:
        if d["flagged"]:
            print(f"FAILED:WFA-0008-probe1 decoy {d['id']} flagged against seed")
            return 1

    rw = (by_cls.get("full-rewrite") or [None])[0]
    if rw is None:
        print("FAILED:WFA-0008-probe1 missing full-rewrite")
        return 1
    if rw["lexical_fired"] or not rw["embedding_fired"]:
        print("FAILED:WFA-0008-probe1 full-rewrite both-states not met")
        return 1
    if not rw["lexical_in_distinct_band"]:
        print(
            "FAILED:WFA-0008-probe1 full-rewrite lexical score "
            f"{rw['lexical_score']} not in 0.05-0.24 band"
        )
        return 1

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:WFA-0008-probe1 artifact missing")
        return 1
    art = json.loads(ART.read_text(encoding="utf-8"))
    if SENTINEL not in json.dumps(art):
        print("FAILED:WFA-0008-probe1 sentinel absent from artifact")
        return 1
    if str(art.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:WFA-0008-probe1 artifact self-declared not delivering")
        return 1
    print("SUCCESS:WFA-0008-probe1 both-states full-rewrite and WFA-0007 plants")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
