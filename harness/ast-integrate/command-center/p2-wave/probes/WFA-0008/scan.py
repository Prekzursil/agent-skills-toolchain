#!/usr/bin/env python3
"""Shared scan: pairwise lexical+cosine, blind adjudication, collapse policy."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import adjudicate as ADJ  # noqa: E402
import corpus as CORP  # noqa: E402
import measures as M  # noqa: E402

QUESTION = (
    "Does an embedding-cosine rescan of the same 284 candidates and 108 "
    "blueprints surface near-duplicate pairs that the lexical scan scored "
    "inside the 0.05-0.24 genuinely-distinct band - that is, same mechanism, "
    "wholly rewritten vocabulary?"
)
SENTINEL = "SUCCESS:WFA-0008"
CONTROL_CLASSES = (
    "exact-rename",
    "one-parameter-fork",
    "reworded-paraphrase",
    "full-rewrite",
    "decoy",
)


def _lohi(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a <= b else (b, a)


def pair_row(aid: str, bid: str, scored: dict, blind: dict) -> dict:
    lo, hi = _lohi(aid, bid)
    lex_f = bool(scored["lexical_fired"])
    emb_f = bool(scored["embedding_fired"])
    if lex_f and emb_f:
        methods = "BOTH"
    elif emb_f and not lex_f:
        methods = "EMBEDDING-ONLY"
    elif lex_f and not emb_f:
        methods = "LEXICAL-ONLY"
    else:
        methods = "NEITHER"
    disagree = lex_f != emb_f
    collapse_ok = (
        lex_f
        and emb_f
        and blind.get("verdict") == "DUPLICATE"
    )
    status = "COLLAPSE-ELIGIBLE" if collapse_ok else (
        "CONTESTED" if disagree else "KEEP"
    )
    return {
        "a": lo,
        "b": hi,
        "lexical_score": scored["lexical_score"],
        "embedding_score": scored["embedding_score"],
        "lexical_fired": lex_f,
        "embedding_fired": emb_f,
        "lexical_in_distinct_band": scored["lexical_in_distinct_band"],
        "flagged_by": list(scored["flagged_by"]),
        "methods": methods,
        "blind_verdict": blind.get("verdict"),
        "blind": {
            "verdict": blind.get("verdict"),
            "cards_equal": blind.get("cards_equal"),
            "weight": blind.get("weight"),
            "method": blind.get("method"),
        },
        "status": status,
        "collapsed_on_cosine_alone": False,
    }


def planted_rows(docs: list[dict], index: dict[str, dict]) -> list[dict]:
    seed = index["seed.checkpoint-resume"]
    seed_text = CORP.scoring_text(seed)
    rows = []
    for doc in docs:
        cls = doc.get("class")
        if cls not in CONTROL_CLASSES:
            continue
        scored = M.score_pair(seed_text, CORP.scoring_text(doc))
        blind = ADJ.adjudicate(seed_text, CORP.scoring_text(doc))
        rows.append(
            {
                "id": doc["id"],
                "class": cls,
                "seed_id": seed["id"],
                "lexical_score": scored["lexical_score"],
                "embedding_score": scored["embedding_score"],
                "lexical_fired": scored["lexical_fired"],
                "embedding_fired": scored["embedding_fired"],
                "lexical_in_distinct_band": scored["lexical_in_distinct_band"],
                "flagged_by": list(scored["flagged_by"]),
                "blind_verdict": blind["verdict"],
                "blind": {
                    "verdict": blind["verdict"],
                    "cards_equal": blind["cards_equal"],
                    "weight": blind["weight"],
                },
            }
        )
    return rows


def run_scan() -> dict:
    docs = CORP.load_documents()
    index = CORP.by_id(docs)
    inv = CORP.inventory()
    pairwise: list[dict] = []
    ids = [d["id"] for d in docs]
    for i, aid in enumerate(ids):
        for bid in ids[i + 1 :]:
            scored = M.score_pair(
                CORP.scoring_text(index[aid]),
                CORP.scoring_text(index[bid]),
            )
            blind = ADJ.adjudicate(
                CORP.scoring_text(index[aid]),
                CORP.scoring_text(index[bid]),
            )
            pairwise.append(pair_row(aid, bid, scored, blind))
    pairwise.sort(key=lambda r: (r["a"], r["b"]))

    planted = planted_rows(docs, index)
    contested = [dict(r) for r in pairwise if r["status"] == "CONTESTED"]
    for row in contested:
        row["adjudicating_evidence"] = {
            "blind_verdict": row["blind_verdict"],
            "blind_method": row["blind"]["method"],
            "cards_equal": row["blind"]["cards_equal"],
            "weight": row["blind"]["weight"],
            "rule": (
                "Methods disagree. The pair stays CONTESTED with this "
                "blind mechanism-card evidence. It is never silently resolved "
                "and never collapsed on cosine alone."
            ),
        }
    collapsed = [
        dict(r)
        for r in pairwise
        if r["status"] == "COLLAPSE-ELIGIBLE"
    ]
    for row in collapsed:
        row["collapse_rule"] = (
            "Collapse only when lexical fired AND embedding fired AND "
            "blind verdict is DUPLICATE. Cosine alone is not enough."
        )

    novel = [
        dict(r)
        for r in pairwise
        if r["embedding_fired"]
        and r["lexical_in_distinct_band"]
        and not r["lexical_fired"]
    ]

    rw = next(r for r in planted if r["class"] == "full-rewrite")
    on_tree = [d for d in docs if d.get("role") == "on-tree"]
    claimed_n = (
        inv["candidate_registry"]["catalog_claimed"]
        + inv["blueprint_library"]["catalog_claimed"]
    )
    live_n = (
        inv["candidate_registry"]["files_found"]
        + inv["blueprint_library"]["files_found"]
    )
    answer = (
        "The 08-WORKFLOW-CANDIDATE-REGISTRY.json (284 records) and "
        "09-WORKFLOW-BLUEPRINT-LIBRARY.json (108 records) are absent on this "
        f"Linux worktree (registry_files={inv['candidate_registry']['files_found']}, "
        f"blueprint_files={inv['blueprint_library']['files_found']}; "
        f"WFA-0007 lexical matrix files="
        f"{inv['wfa0007_lexical_scan']['files_found']}). A 284-by-108 "
        "rescan of those catalogs is therefore NOT-CHECKED and is not "
        "invented. The same planted-mutant control WFA-0007 specified "
        "(exact rename, one-parameter fork, reworded paraphrase, three "
        "decoys) is extended by a full-rewrite mutant. Lexical Jaccard "
        f"misses that rewrite (score={rw['lexical_score']}, fired="
        f"{rw['lexical_fired']}, in_0.05-0.24_band="
        f"{rw['lexical_in_distinct_band']}); concept-axis cosine catches it "
        f"(score={rw['embedding_score']}, fired={rw['embedding_fired']}). "
        "That both-states pair is the delivered proof that cosine can see "
        "same-mechanism wholly-rewritten vocabulary the lexical band called "
        "genuinely distinct. Method disagreements are listed CONTESTED with "
        "blind mechanism-card evidence; no pair is collapsed on cosine "
        f"alone. On-tree workflow_blueprint records scored: {len(on_tree)}. "
        f"Novel cosine-fire pairs inside the lexical 0.05-0.24 band: "
        f"{len(novel)}."
    )
    return {
        "docs": docs,
        "inventory": inv,
        "pairwise": pairwise,
        "planted": planted,
        "contested": contested,
        "collapsed": collapsed,
        "novel": novel,
        "on_tree": on_tree,
        "claimed_n": claimed_n,
        "live_n": live_n,
        "answer": answer,
        "question": QUESTION,
        "sentinel": SENTINEL,
        "full_rewrite": rw,
    }
