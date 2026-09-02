#!/usr/bin/env python3
"""Probe 1: score the three planted mutants under both measures (live)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import corpus as CORP  # noqa: E402
import measures as M  # noqa: E402

REPO = HERE.parents[3]
ART = REPO / "command-center/confirmation/CNF-0078-distinctness-remeasure.json"
SENTINEL_FRAGMENT = (
    "SUCCESS:CNF-0078 emitted only when the artifact at output_path exists"
)


def main() -> int:
    docs = CORP.load_documents()
    index = CORP.by_id(docs)
    seed = index["seed.checkpoint-resume"]
    rows = []
    for cls in ("exact-rename", "paraphrase", "full-rewrite"):
        mutant = next(d for d in docs if d.get("class") == cls)
        scored = M.score_pair(seed["text"], mutant["text"])
        rows.append({"class": cls, "id": mutant["id"], **scored})
        print(
            f"{cls} lex={scored['lexical_score']} fired={scored['lexical_fired']} "
            f"emb={scored['embedding_score']} fired={scored['embedding_fired']}"
        )

    rename, para, rw = rows
    ok = (
        rename["lexical_fired"]
        and rename["embedding_fired"]
        and para["lexical_fired"]
        and para["embedding_fired"]
        and (not rw["lexical_fired"])
        and rw["embedding_fired"]
    )
    if not ok:
        print("FAILED:CNF-0078-probe1 planted firing pattern not met")
        return 1

    decoys = [d for d in docs if d.get("role") == "decoy"]
    for d in decoys:
        scored = M.score_pair(seed["text"], d["text"])
        print(
            f"decoy {d['id']} lex={scored['lexical_score']} fired={scored['lexical_fired']} "
            f"emb={scored['embedding_score']} fired={scored['embedding_fired']}"
        )
        if scored["flagged"]:
            print(f"FAILED:CNF-0078-probe1 decoy {d['id']} flagged against seed")
            return 1

    if not ART.is_file():
        print("FAILED:CNF-0078-probe1 artifact missing")
        return 1
    art = json.loads(ART.read_text(encoding="utf-8"))
    if SENTINEL_FRAGMENT not in json.dumps(art):
        print("FAILED:CNF-0078-probe1 sentinel absent from artifact")
        return 1
    print("SUCCESS:CNF-0078-probe1 planted mutants scored under both measures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
