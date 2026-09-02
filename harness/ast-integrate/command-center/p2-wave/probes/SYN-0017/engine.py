"""SYN-0017 mechanism-dedup engine: score pairs, collapse, prove planted controls."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

import contract as C
import findings as F
import tokens as T


def agreement(lex_hit: bool, emb_hit: bool) -> str:
    if lex_hit and emb_hit:
        return "BOTH"
    if lex_hit:
        return "LEXICAL-ONLY"
    if emb_hit:
        return "EMBEDDING-ONLY"
    return "NEITHER"


def score_pair(left: dict, right: dict) -> dict[str, Any]:
    ta, tb = F.finding_text(left), F.finding_text(right)
    lex = T.jaccard(ta, tb)
    emb = T.cosine(T.embed(ta, C.EMBED_DIM), T.embed(tb, C.EMBED_DIM))
    lex_hit = lex >= C.LEXICAL_THRESHOLD
    emb_hit = emb >= C.EMBEDDING_THRESHOLD
    agr = agreement(lex_hit, emb_hit)
    return {
        "left_id": left["id"],
        "right_id": right["id"],
        "lexical_score": round(lex, 6),
        "embedding_score": round(emb, 6),
        "lexical_hit": lex_hit,
        "embedding_hit": emb_hit,
        "agreement": agr,
        "collapse": agr != "NEITHER",
        "canonical_mechanism_match": left.get("canonical_mechanism")
        == right.get("canonical_mechanism"),
    }


def all_pairs(rows: list[dict]) -> list[dict]:
    ordered = sorted(rows, key=lambda r: str(r["id"]))
    out: list[dict] = []
    for i, left in enumerate(ordered):
        for right in ordered[i + 1 :]:
            out.append(score_pair(left, right))
    return out


def _find(parent: dict[str, str], x: str) -> str:
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x


def clusters(rows: list[dict], pairs: list[dict]) -> list[dict]:
    parent = {str(r["id"]): str(r["id"]) for r in rows}
    for p in pairs:
        if not p["collapse"]:
            continue
        ra, rb = _find(parent, p["left_id"]), _find(parent, p["right_id"])
        if ra != rb:
            parent[rb] = ra
    groups: dict[str, list[str]] = defaultdict(list)
    for r in rows:
        groups[_find(parent, str(r["id"]))].append(str(r["id"]))
    index = {str(r["id"]): r for r in rows}
    out: list[dict] = []
    for root, ids in groups.items():
        if len(ids) < 2:
            continue
        members = sorted(ids)
        anchors: list[str] = []
        seen: set[str] = set()
        for mid in members:
            for a in index[mid].get("evidence_anchors") or []:
                if a not in seen:
                    seen.add(a)
                    anchors.append(a)
        out.append(
            {
                "cluster_id": root,
                "member_ids": members,
                "evidence_anchors_union": anchors,
                "kept_id": members[0],
            }
        )
    out.sort(key=lambda c: c["cluster_id"])
    return out


def same_cluster(collapses: list[dict], a: str, b: str) -> bool:
    for c in collapses:
        ids = set(c["member_ids"])
        if a in ids and b in ids:
            return True
    return False


def pair_lookup(pairs: list[dict], a: str, b: str) -> dict:
    want = frozenset({a, b})
    for p in pairs:
        if frozenset({p["left_id"], p["right_id"]}) == want:
            return p
    raise KeyError(f"pair {a}/{b} missing")


def planted_rows(pairs: list[dict], collapses: list[dict]) -> list[dict]:
    specs = (
        ("rename", F.RENAME_ID),
        ("paraphrase", F.PARAPHRASE_ID),
        ("parameter-fork", F.FORK_ID),
    )
    out: list[dict] = []
    for cls, mid in specs:
        p = pair_lookup(pairs, F.BASE_ID, mid)
        out.append(
            {
                "class": cls,
                "mutant_id": mid,
                "base_id": F.BASE_ID,
                "caught": same_cluster(collapses, F.BASE_ID, mid),
                "lexical_caught": bool(p["lexical_hit"]),
                "embedding_caught": bool(p["embedding_hit"]),
                "agreement": p["agreement"],
                "lexical_score": p["lexical_score"],
                "embedding_score": p["embedding_score"],
            }
        )
    return out


def distinct_control(pairs: list[dict], collapses: list[dict]) -> dict:
    p = pair_lookup(pairs, F.DISTINCT_A_ID, F.DISTINCT_B_ID)
    return {
        "left_id": F.DISTINCT_A_ID,
        "right_id": F.DISTINCT_B_ID,
        "collapsed": same_cluster(collapses, F.DISTINCT_A_ID, F.DISTINCT_B_ID),
        "lexical_score": p["lexical_score"],
        "embedding_score": p["embedding_score"],
        "agreement": p["agreement"],
    }


def rewrite_coverage(pairs: list[dict], collapses: list[dict]) -> dict:
    p = pair_lookup(pairs, F.BASE_ID, F.REWRITE_ID)
    collapsed = same_cluster(collapses, F.BASE_ID, F.REWRITE_ID)
    return {
        "full_rewrite_id": F.REWRITE_ID,
        "base_id": F.BASE_ID,
        "lexical_score": p["lexical_score"],
        "embedding_score": p["embedding_score"],
        "agreement": p["agreement"],
        "collapsed": collapsed,
        "scores_like_distinct": (not collapsed) and p["agreement"] == "NEITHER",
        "disclosure": (
            "Lexical Jaccard and the hashed-n-gram cosine embedding are both "
            "surface-form detectors. A full rewrite of report-time manifest "
            "verification (fail-closed reserved-name wording) scores in the "
            "distinct band, same as two genuinely different mechanisms. That "
            "is lexical-only coverage: a neural embedding is ABSENT on this "
            "worktree, and canonical_mechanism is fixture-only because "
            "CLAIM-REGISTRY.json is not on disk, so it is not used as the "
            "collapse rule. The gap is disclosed, not claimed closed."
        ),
    }


def union_holds(rows: list[dict], collapses: list[dict]) -> tuple[bool, str]:
    index = {str(r["id"]): r for r in rows}
    for c in collapses:
        expected: list[str] = []
        seen: set[str] = set()
        for mid in c["member_ids"]:
            for a in index[mid].get("evidence_anchors") or []:
                if a not in seen:
                    seen.add(a)
                    expected.append(a)
        got = list(c.get("evidence_anchors_union") or [])
        if set(got) != set(expected):
            return False, f"cluster {c['cluster_id']} union {got} != {expected}"
        if not expected:
            return False, f"cluster {c['cluster_id']} empty union"
    return True, "ok"


def invariants(result: dict) -> list[str]:
    errors: list[str] = []
    mutants = result["planted_mutants"]
    classes = {m["class"] for m in mutants}
    if classes != {"rename", "paraphrase", "parameter-fork"}:
        errors.append(f"planted classes {classes}")
    for m in mutants:
        if not m["caught"]:
            errors.append(
                f"{m['class']} not collapsed with base "
                f"lex={m['lexical_score']} emb={m['embedding_score']}"
            )
        if not (m["lexical_caught"] or m["embedding_caught"]):
            errors.append(f"{m['class']} neither detector fired")
    dc = result["distinct_pair_control"]
    if dc["collapsed"]:
        errors.append(
            "distinct pair collapsed "
            f"lex={dc['lexical_score']} emb={dc['embedding_score']}"
        )
    loc = result["lexical_only_coverage"]
    if loc["collapsed"]:
        errors.append("full rewrite was collapsed (would hide lexical-only coverage)")
    if not loc["scores_like_distinct"]:
        errors.append("full rewrite did not score like a distinct entry")
    ok, msg = union_holds(result["findings"], result["collapses"])
    if not ok:
        errors.append(msg)
    if not result["collapses"]:
        errors.append("no collapse clusters (mutants were not merged)")
    return errors


def run(rows: list[dict] | None = None) -> dict[str, Any]:
    findings = list(rows if rows is not None else F.corpus())
    pairs = all_pairs(findings)
    cols = clusters(findings, pairs)
    result = {
        "findings": findings,
        "pairs": pairs,
        "collapses": cols,
        "planted_mutants": planted_rows(pairs, cols),
        "distinct_pair_control": distinct_control(pairs, cols),
        "lexical_only_coverage": rewrite_coverage(pairs, cols),
        "lexical_threshold": C.LEXICAL_THRESHOLD,
        "embedding_threshold": C.EMBEDDING_THRESHOLD,
    }
    result["errors"] = invariants(result)
    result["ok"] = not result["errors"]
    return result
