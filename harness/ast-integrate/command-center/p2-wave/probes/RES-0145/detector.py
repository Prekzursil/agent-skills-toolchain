"""Four-signal origin-descent detector for RES-0145.

Signals (mechanically independent):
  1. shared verbatim 6-grams that are distinctive vs the rest of the corpus
  2. shared distinctive numeric tokens (planted factual errors / unique quantities)
  3. publication-date ordering consistent with a copy chain
  4. explicit backlinks: a directed cycle in the within-cluster citation graph

FIRE rule: content copy (1 or 2) AND a citation cycle (4).
Date order (3) is corroboration; it never fires alone.
Distinct URL counts never count as independence or as origin descent.

Gold labels are not read.
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import date
from typing import Any

NGRAM_N = 6
STOP = frozenset(
    """
    a an the of to in for and or is are was were with that this from by on as
    at be it we they their its not no also into over after before without
    same figure notes origin secondary tertiary blog copies restates were
    filed first write-up
    """.split()
)
NUM_RE = re.compile(r"\b\d+\.\d+\b|\b\d{3,}\b")
WORD_RE = re.compile(r"[A-Za-z0-9]+(?:\.[0-9]+)?")


def tokenize(text: str) -> list[str]:
    return [m.group(0).lower() for m in WORD_RE.finditer(text or "")]


def ngrams(tokens: list[str], n: int = NGRAM_N) -> set[str]:
    out: set[str] = set()
    if len(tokens) < n:
        return out
    for i in range(len(tokens) - n + 1):
        window = tokens[i : i + n]
        content = [t for t in window if t not in STOP and not t.isdigit()]
        if len(content) < 3:
            continue
        out.add(" ".join(window))
    return out


def quantities(text: str) -> set[str]:
    return set(NUM_RE.findall(text or ""))


def parse_day(value: str) -> date:
    y, m, d = (int(p) for p in str(value).split("-")[:3])
    return date(y, m, d)


def _cluster_id(doc: dict[str, Any]) -> str:
    return str(doc.get("cluster_id") or doc.get("cluster_id") or "")


def _when(doc: dict[str, Any]) -> str:
    return str(doc.get("published_at") or doc.get("published_at") or "")


def _cites(doc: dict[str, Any]) -> list[str]:
    return [str(x) for x in (doc.get("cites") or doc.get("cites") or [])]


def citation_graph(docs: list[dict[str, Any]]) -> dict[str, list[str]]:
    ids = {str(d["id"]) for d in docs}
    graph: dict[str, list[str]] = {str(d["id"]): [] for d in docs}
    for doc in docs:
        src = str(doc["id"])
        for dst in _cites(doc):
            if dst in ids and dst != src and dst not in graph[src]:
                graph[src].append(dst)
    return graph


def has_directed_cycle(graph: dict[str, list[str]]) -> bool:
    white, gray, black = 0, 1, 2
    color = {node: white for node in graph}

    def dfs(node: str) -> bool:
        color[node] = gray
        for nxt in graph[node]:
            if color[nxt] == gray:
                return True
            if color[nxt] == white and dfs(nxt):
                return True
        color[node] = black
        return False

    return any(dfs(node) for node in graph if color[node] == white)


def cycle_members(graph: dict[str, list[str]]) -> list[list[str]]:
    found: list[list[str]] = []
    seen_key: set[tuple[str, ...]] = set()

    def rec(start: str, node: str, path: list[str], stacked: set[str]) -> None:
        for nxt in graph.get(node, []):
            if nxt == start and len(path) >= 2:
                key = tuple(sorted(path))
                if key not in seen_key:
                    seen_key.add(key)
                    found.append(path + [start])
            elif nxt not in stacked:
                rec(start, nxt, path + [nxt], stacked | {nxt})

    for node in graph:
        rec(node, node, [node], {node})
    found.sort(key=lambda c: (len(c), c[0]))
    return found


def _shared_distinctive(
    per_doc: dict[str, set[str]],
    cluster_ids: list[str],
    all_ids: list[str],
) -> list[str]:
    members = [per_doc[i] for i in cluster_ids]
    if len(members) < 2:
        return []
    shared: set[str] = set()
    for i, a in enumerate(members):
        for b in members[i + 1 :]:
            shared |= a & b
    outside: set[str] = set()
    cluster_set = set(cluster_ids)
    for did in all_ids:
        if did not in cluster_set:
            outside |= per_doc[did]
    return sorted(x for x in shared if x not in outside)


def date_chain(docs: list[dict[str, Any]], content_ids: set[str]) -> dict[str, Any]:
    tagged = [d for d in docs if d["id"] in content_ids]
    if len(tagged) < 2:
        return {
            "applicable": False,
            "consistent": False,
            "earliest_id": None,
            "reason": "fewer-than-two-content-sharing-members",
        }
    ordered = sorted(tagged, key=lambda d: (_when(d), d["id"]))
    earliest = ordered[0]
    later_ok = all(
        parse_day(_when(d)) > parse_day(_when(earliest)) for d in ordered[1:]
    )
    return {
        "applicable": True,
        "consistent": later_ok,
        "earliest_id": earliest["id"],
        "ordered_ids": [d["id"] for d in ordered],
        "reason": "copies-after-origin" if later_ok else "copy-predates-origin",
    }


def classify_cluster(
    docs: list[dict[str, Any]],
    ngram_index: dict[str, set[str]],
    qty_index: dict[str, set[str]],
    all_ids: list[str],
) -> dict[str, Any]:
    ids = [str(d["id"]) for d in docs]
    ngrams_hit = _shared_distinctive(ngram_index, ids, all_ids)
    qtys_hit = _shared_distinctive(qty_index, ids, all_ids)
    content = bool(ngrams_hit) or bool(qtys_hit)
    graph = citation_graph(docs)
    cycles = cycle_members(graph)
    cycle = has_directed_cycle(graph)
    content_ids: set[str] = set()
    if ngrams_hit or qtys_hit:
        for doc in docs:
            grams = ngram_index[doc["id"]]
            qtys = qty_index[doc["id"]]
            if (set(ngrams_hit) & grams) or (set(qtys_hit) & qtys):
                content_ids.add(doc["id"])
    dates = date_chain(docs, content_ids if content_ids else {d["id"] for d in docs})
    urls = [d["url"] for d in docs]
    unique_urls = sorted(set(urls))
    fire = bool(content and cycle)
    return {
        "cluster_id": _cluster_id(docs[0]) if docs else None,
        "member_ids": ids,
        "fire": fire,
        "verdict": "SINGLE-ORIGIN-CYCLE" if fire else "INDEPENDENT",
        "signals": {
            "shared_verbatim_ngrams": {
                "fired": bool(ngrams_hit),
                "examples": ngrams_hit[:5],
                "n": len(ngrams_hit),
            },
            "shared_factual_errors": {
                "fired": bool(qtys_hit),
                "examples": qtys_hit[:5],
                "n": len(qtys_hit),
            },
            "publication_date_ordering": dates,
            "explicit_backlinks": {
                "fired": cycle,
                "n_cycles": len(cycles),
                "example_path": cycles[0] if cycles else [],
            },
        },
        "content_copy": content,
        "citation_cycle": cycle,
        "unique_url_count": len(unique_urls),
        "member_count": len(docs),
        "urls_all_distinct": len(unique_urls) == len(docs),
    }


def indexes(
    documents: list[dict[str, Any]]
) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    ngram_index: dict[str, set[str]] = {}
    qty_index: dict[str, set[str]] = {}
    for doc in documents:
        ngram_index[doc["id"]] = ngrams(tokenize(doc["body"]))
        qty_index[doc["id"]] = quantities(doc["body"])
    return ngram_index, qty_index


def evaluate(documents: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for doc in documents:
        grouped[_cluster_id(doc)].append(doc)
    ngram_index, qty_index = indexes(documents)
    all_ids = [str(d["id"]) for d in documents]
    out: dict[str, dict[str, Any]] = {}
    for cid in sorted(grouped):
        members = sorted(grouped[cid], key=lambda d: d["id"])
        out[cid] = classify_cluster(members, ngram_index, qty_index, all_ids)
    return out


def url_count_fire(docs: list[dict[str, Any]]) -> bool:
    """Naive baseline: distinct URLs mean independence. Fires only on URL reuse."""
    urls = [d["url"] for d in docs]
    return len(set(urls)) < len(urls)


def cycle_only_fire(docs: list[dict[str, Any]]) -> bool:
    """Known-broken: citation cycle without content-copy evidence."""
    return has_directed_cycle(citation_graph(docs))


def summarize(
    results: dict[str, dict[str, Any]], gold: dict[str, str]
) -> dict[str, Any]:
    tp = fp = tn = fn = 0
    per: list[dict[str, Any]] = []
    for cid in sorted(gold):
        row = results[cid]
        fired = bool(row["fire"])
        label = gold[cid]
        if label == "cycle" and fired:
            tp += 1
            outcome = "TP"
        elif label == "cycle" and not fired:
            fn += 1
            outcome = "FN"
        elif label == "independent" and fired:
            fp += 1
            outcome = "FP"
        else:
            tn += 1
            outcome = "TN"
        per.append(
            {
                "cluster_id": cid,
                "gold": label,
                "fire": fired,
                "verdict": row["verdict"],
                "outcome": outcome,
            }
        )
    n_cycle = sum(1 for v in gold.values() if v == "cycle")
    n_ind = sum(1 for v in gold.values() if v == "independent")
    detection_rate = (tp / n_cycle) if n_cycle else 0.0
    false_positive_rate = (fp / n_ind) if n_ind else 0.0
    both = tp == n_cycle and fp == 0 and fn == 0 and tn == n_ind
    return {
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "n_cycle": n_cycle,
        "n_independent": n_ind,
        "detection_rate": detection_rate,
        "false_positive_rate": false_positive_rate,
        "both_states_pass": both,
        "both_states_pass": both,
        "per_cluster": per,
    }


def mutate_strip_content(doc: dict[str, Any], salt: str) -> dict[str, Any]:
    """Replace body with a short, per-document phrase.

    A shared ablation template would itself become a distinctive 6-gram and
    keep content_copy true, which would not test the fire rule.
    """
    out = dict(doc)
    out["body"] = f"{doc['id']} {salt}"
    return out


def mutate_inject_content(
    doc: dict[str, Any], nonce: str, qty: str
) -> dict[str, Any]:
    out = dict(doc)
    out["body"] = f"{doc['body']} {nonce} marker {qty}"
    return out


def mutate_add_cycle(docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ids = [d["id"] for d in docs]
    out = []
    for i, doc in enumerate(docs):
        row = dict(doc)
        row["cites"] = [ids[(i + 1) % len(ids)]]
        out.append(row)
    return out


# Names used by emit.py / probes.
quantities = quantities
url_count_fire = url_count_fire
cycle_only_fire = cycle_only_fire
mutate_strip_content = mutate_strip_content
mutate_inject_content = mutate_inject_content
mutate_add_cycle = mutate_add_cycle
citation_graph = citation_graph
has_directed_cycle = has_directed_cycle
