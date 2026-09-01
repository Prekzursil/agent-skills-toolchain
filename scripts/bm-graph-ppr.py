#!/usr/bin/env python3
"""HippoRAG-style linking OVER basic-memory's OWN relation graph.

STARTED (not finished): rank proposed ``relates_to`` targets. Does NOT write
the vault (false-link risk). Apply-with-cap is DEFERRED (M2).

Read-only: copies ``memory.db`` then queries the copy. Never binds :8765.
Never loads FastEmbed. Never walks ``search_vector_chunks``. Stdlib only —
no networkx, scipy, or second memory writer (Mem0 / Graphiti / LynxMCP / CORE).

# A-OTHER: parent will relay additional ambitious item
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import sys
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "bm-graph-ppr.v1"
_CANON_SOURCE = Path(r"C:\Users\Prekzursil\.basic-memory\memory.db")
DEFAULT_SOURCE = (
    _CANON_SOURCE if _CANON_SOURCE.is_file() else Path.home() / ".basic-memory" / "memory.db"
)
DEFAULT_COPY_NAME = "bm-graph-ppr.db"
DEFAULT_OUT = (
    Path.home() / ".agents" / "state" / "harness" / "bm-graph-neighbors.json"
)
DEFAULT_SEEDS = ("estate-locks", "harness")
REQUIRED_RELATION_COLS = ("id", "from_id", "to_id", "to_name", "relation_type")
REQUIRED_ENTITY_COLS = ("id", "title", "permalink", "file_path")

# Intentionally stdlib-only. Do not import networkx, scipy, fastembed,
# sentence_transformers, or any vector stack. Do not bind :8765.


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def pragma_columns(con: sqlite3.Connection, table: str) -> list[dict]:
    rows = con.execute(f"PRAGMA table_info({table})").fetchall()
    return [
        {
            "cid": r[0],
            "name": r[1],
            "type": r[2],
            "notnull": bool(r[3]),
            "pk": bool(r[5]),
        }
        for r in rows
    ]


def require_columns(cols: list[dict], required: tuple[str, ...], table: str) -> None:
    have = {c["name"] for c in cols}
    missing = [name for name in required if name not in have]
    if missing:
        raise SystemExit(f"{table} schema missing columns {missing}; have {sorted(have)}")


def copy_memory_db(source: Path, dest: Path) -> dict:
    """Copy via sqlite backup API (WAL-safe). Fall back to shutil of db+wal+shm."""
    if not source.is_file():
        raise SystemExit(f"source db not found: {source}")
    dest = dest.resolve()
    source = source.resolve()
    if dest == source:
        raise SystemExit("refusing to copy memory.db onto itself")
    dest.parent.mkdir(parents=True, exist_ok=True)
    for extra in (dest, Path(str(dest) + "-wal"), Path(str(dest) + "-shm")):
        try:
            extra.unlink(missing_ok=True)
        except OSError:
            pass
    method = "sqlite_backup"
    try:
        src = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True, timeout=30)
        try:
            dst = sqlite3.connect(str(dest), timeout=30)
            try:
                src.backup(dst)
            finally:
                dst.close()
        finally:
            src.close()
    except sqlite3.Error:
        method = "shutil_copy2"
        shutil.copy2(source, dest)
        for suffix in ("-wal", "-shm"):
            extra = Path(str(source) + suffix)
            if extra.is_file():
                shutil.copy2(extra, Path(str(dest) + suffix))
    return {
        "source": str(source),
        "copy": str(dest),
        "bytes": dest.stat().st_size,
        "method": method,
        "copied_at": utc_now(),
    }


def open_ro(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True, timeout=30)
    con.row_factory = sqlite3.Row
    return con


def load_graph(con: sqlite3.Connection) -> dict:
    rel_cols = pragma_columns(con, "relation")
    ent_cols = pragma_columns(con, "entity")
    require_columns(rel_cols, REQUIRED_RELATION_COLS, "relation")
    require_columns(ent_cols, REQUIRED_ENTITY_COLS, "entity")

    entities: dict[int, dict] = {}
    for row in con.execute(
        "SELECT id, title, permalink, file_path, note_type FROM entity"
    ):
        entities[int(row["id"])] = {
            "id": int(row["id"]),
            "title": row["title"],
            "permalink": row["permalink"],
            "file_path": row["file_path"],
            "note_type": row["note_type"],
        }

    directed: list[tuple[int, int, str]] = []
    unresolved = 0
    type_counts: dict[str, int] = defaultdict(int)
    for row in con.execute(
        "SELECT from_id, to_id, to_name, relation_type FROM relation"
    ):
        rtype = row["relation_type"] or ""
        type_counts[rtype] += 1
        if row["to_id"] is None:
            unresolved += 1
            continue
        src, dst = int(row["from_id"]), int(row["to_id"])
        if src == dst:
            continue
        directed.append((src, dst, rtype))

    return {
        "entities": entities,
        "directed": directed,
        "unresolved": unresolved,
        "type_counts": dict(sorted(type_counts.items(), key=lambda kv: (-kv[1], kv[0]))),
        "relation_schema": rel_cols,
        "entity_schema": [
            {k: c[k] for k in ("cid", "name", "type", "notnull", "pk")}
            for c in ent_cols
        ],
        "entity_count": len(entities),
        "relation_count": sum(type_counts.values()),
    }


def neighbor_sets(
    directed: list[tuple[int, int, str]],
) -> tuple[dict[int, set[int]], dict[int, set[int]]]:
    out_n: dict[int, set[int]] = defaultdict(set)
    in_n: dict[int, set[int]] = defaultdict(set)
    for src, dst, _rtype in directed:
        out_n[src].add(dst)
        in_n[dst].add(src)
    return out_n, in_n


def degree_of(eid: int, out_n: dict[int, set[int]], in_n: dict[int, set[int]]) -> int:
    return len(out_n.get(eid, ())) + len(in_n.get(eid, ()))


def match_score(entity: dict, needle: str) -> int:
    n = needle.lower()
    title = (entity.get("title") or "").lower()
    permalink = (entity.get("permalink") or "").lower()
    file_path = (entity.get("file_path") or "").lower().replace("\\", "/")
    if n not in title and n not in permalink and n not in file_path:
        return 0
    score = 10
    segs = [s for s in permalink.split("/") if s]
    path_segs = [s for s in file_path.split("/") if s]
    if n in segs or any(s == n or s.startswith(n) for s in segs):
        score += 80
    if path_segs and (path_segs[0] == n or n in path_segs):
        score += 40
    if title == n or title.startswith(n):
        score += 50
    if permalink.endswith("/" + n) or permalink.endswith(n):
        score += 30
    score -= min(len(permalink), 400) // 80
    return score


def resolve_seeds(
    query: str,
    entities: dict[int, dict],
    out_n: dict[int, set[int]],
    in_n: dict[int, set[int]],
    all_matches: bool,
) -> list[dict]:
    needle = query.strip()
    if not needle:
        return []
    ranked: list[tuple[int, int, dict]] = []
    for ent in entities.values():
        ms = match_score(ent, needle)
        if ms <= 0:
            continue
        deg = degree_of(ent["id"], out_n, in_n)
        ranked.append((ms, deg, ent))
    ranked.sort(key=lambda t: (0 if t[1] > 0 else 1, -t[1], -t[0], t[2]["id"]))
    if not ranked:
        return []
    if all_matches:
        return [ent for _ms, _deg, ent in ranked]
    return [ranked[0][2]]


def build_adj(
    directed: list[tuple[int, int, str]],
    bidirectional: bool,
) -> dict[int, list[int]]:
    pairs: set[tuple[int, int]] = set()
    for src, dst, _rtype in directed:
        pairs.add((src, dst))
        if bidirectional:
            pairs.add((dst, src))
    adj: dict[int, list[int]] = defaultdict(list)
    for src, dst in sorted(pairs):
        adj[src].append(dst)
        adj.setdefault(dst, [])
    return dict(adj)


def personalized_pagerank(
    adj: dict[int, list[int]],
    seed_ids: list[int],
    teleport: float,
    iters: int,
    tol: float,
) -> dict[int, float]:
    """Topic-sensitive PageRank. ``teleport`` is α (HippoRAG uses 0.5)."""
    nodes = set(seed_ids)
    for src, dests in adj.items():
        nodes.add(src)
        nodes.update(dests)
    nodes = sorted(nodes)
    if not nodes:
        return {}
    index = {nid: i for i, nid in enumerate(nodes)}
    n = len(nodes)
    seeds = [s for s in seed_ids if s in index]
    if not seeds:
        return {}
    pers = [0.0] * n
    w = 1.0 / len(seeds)
    for sid in seeds:
        pers[index[sid]] = w
    rank = pers[:]
    outdeg = [len(adj.get(nid, ())) for nid in nodes]
    damp = 1.0 - teleport
    for _ in range(iters):
        new = [teleport * p for p in pers]
        dangling = 0.0
        for i, nid in enumerate(nodes):
            if outdeg[i] == 0:
                dangling += rank[i]
                continue
            share = damp * rank[i] / outdeg[i]
            for dest in adj[nid]:
                new[index[dest]] += share
        if dangling:
            mass = damp * dangling
            for i in range(n):
                new[i] += mass * pers[i]
        diff = 0.0
        for i in range(n):
            diff += abs(new[i] - rank[i])
        rank = new
        if diff < tol:
            break
    return {nodes[i]: rank[i] for i in range(n)}


def two_hop_scores(
    out_n: dict[int, set[int]],
    in_n: dict[int, set[int]],
    seed_ids: list[int],
) -> dict[int, float]:
    seeds = set(seed_ids)
    hop1: set[int] = set()
    for sid in seeds:
        hop1 |= out_n.get(sid, set())
        hop1 |= in_n.get(sid, set())
    scores: dict[int, float] = defaultdict(float)
    for mid in hop1:
        for nid in out_n.get(mid, set()) | in_n.get(mid, set()):
            if nid not in seeds:
                scores[nid] += 1.0
    return dict(scores)


def already_linked_ids(
    seed_ids: list[int],
    out_n: dict[int, set[int]],
    in_n: dict[int, set[int]],
) -> set[int]:
    linked: set[int] = set()
    for sid in seed_ids:
        linked |= out_n.get(sid, set())
        linked |= in_n.get(sid, set())
    linked -= set(seed_ids)
    return linked


def make_proposals(
    scores: dict[int, float],
    entities: dict[int, dict],
    seed_ids: list[int],
    linked: set[int],
    top: int,
) -> list[dict]:
    seed_set = set(seed_ids)
    ranked = []
    for eid, score in scores.items():
        if eid in seed_set or eid in linked:
            continue
        if score <= 0:
            continue
        ent = entities.get(eid)
        if not ent:
            continue
        ranked.append((score, ent.get("permalink") or "", eid, ent))
    ranked.sort(key=lambda t: (-t[0], t[1], t[2]))
    proposals = []
    for i, (score, _perm, eid, ent) in enumerate(ranked[:top], start=1):
        proposals.append(
            {
                "rank": i,
                "entity_id": eid,
                "title": ent["title"],
                "permalink": ent["permalink"],
                "file_path": ent["file_path"],
                "note_type": ent.get("note_type"),
                "score": round(float(score), 8),
                "proposed_relation": "relates_to",
                "already_linked": False,
            }
        )
    return proposals


def atomic_write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def entity_brief(ent: dict, out_n: dict[int, set[int]], in_n: dict[int, set[int]]) -> dict:
    return {
        "id": ent["id"],
        "title": ent["title"],
        "permalink": ent["permalink"],
        "file_path": ent["file_path"],
        "degree": degree_of(ent["id"], out_n, in_n),
    }


def run_self_test() -> int:
    """Tiny directed chain A->B->C; seed A; C must be the unlinked proposal."""
    directed = [(1, 2, "links_to"), (2, 3, "links_to")]
    entities = {
        1: {"id": 1, "title": "A", "permalink": "a", "file_path": "a.md", "note_type": "note"},
        2: {"id": 2, "title": "B", "permalink": "b", "file_path": "b.md", "note_type": "note"},
        3: {"id": 3, "title": "C", "permalink": "c", "file_path": "c.md", "note_type": "note"},
    }
    out_n, in_n = neighbor_sets(directed)
    adj = build_adj(directed, bidirectional=False)
    scores = personalized_pagerank(adj, [1], teleport=0.5, iters=40, tol=1e-12)
    linked = already_linked_ids([1], out_n, in_n)
    props = make_proposals(scores, entities, [1], linked, top=5)
    if linked != {2}:
        print("FAIL linked", linked, file=sys.stderr)
        return 1
    if not props or props[0]["entity_id"] != 3:
        print("FAIL proposals", props, file=sys.stderr)
        return 1
    if not (scores[1] > scores[2] > scores[3] > 0):
        print("FAIL rank order", scores, file=sys.stderr)
        return 1
    print("self-test ok")
    return 0


def rank_for_seeds(
    seed_ents: list[dict],
    entities: dict[int, dict],
    out_n: dict[int, set[int]],
    in_n: dict[int, set[int]],
    adj: dict[int, list[int]],
    teleport: float,
    iters: int,
    tol: float,
    top: int,
) -> dict:
    seed_ids = [e["id"] for e in seed_ents]
    method = "personalized_pagerank"
    scores = personalized_pagerank(
        adj, seed_ids, teleport=teleport, iters=iters, tol=tol
    )
    linked = already_linked_ids(seed_ids, out_n, in_n)
    proposals = make_proposals(scores, entities, seed_ids, linked, top=top)
    if not proposals:
        method = "two_hop_neighbor_ranking"
        scores = two_hop_scores(out_n, in_n, seed_ids)
        proposals = make_proposals(scores, entities, seed_ids, linked, top=top)
    return {
        "seed_entities": [entity_brief(e, out_n, in_n) for e in seed_ents],
        "already_linked_count": len(linked),
        "already_linked": [
            entity_brief(entities[eid], out_n, in_n)
            for eid in sorted(linked)
            if eid in entities
        ][:50],
        "method": method,
        "proposals": proposals,
        "proposal_count": len(proposals),
    }


def productive_rank(
    hits: list[dict],
    all_matches: bool,
    entities: dict[int, dict],
    out_n: dict[int, set[int]],
    in_n: dict[int, set[int]],
    adj: dict[int, list[int]],
    teleport: float,
    iters: int,
    tol: float,
    top: int,
) -> dict:
    """Prefer a matching seed that actually yields unlinked 2-hop/PPR targets."""
    kwargs = dict(
        entities=entities,
        out_n=out_n,
        in_n=in_n,
        adj=adj,
        teleport=teleport,
        iters=iters,
        tol=tol,
        top=top,
    )
    if all_matches:
        return rank_for_seeds(hits, **kwargs)
    ordered = sorted(
        hits,
        key=lambda e: (
            0 if degree_of(e["id"], out_n, in_n) > 0 else 1,
            -degree_of(e["id"], out_n, in_n),
            e["id"],
        ),
    )
    best: dict | None = None
    for ent in ordered[:15]:
        result = rank_for_seeds([ent], **kwargs)
        if best is None:
            best = result
        if result["proposal_count"] > 0:
            return result
    return best or {
        "seed_entities": [],
        "already_linked_count": 0,
        "already_linked": [],
        "method": "personalized_pagerank",
        "proposals": [],
        "proposal_count": 0,
    }


def pick_connected_seed(
    queries: list[str],
    entities: dict[int, dict],
    out_n: dict[int, set[int]],
    in_n: dict[int, set[int]],
    all_matches: bool,
    allow_fallback: bool,
) -> tuple[str, list[dict], list[dict]]:
    isolated: list[dict] = []
    first_hit: tuple[str, list[dict]] | None = None
    for query in queries:
        hits = resolve_seeds(query, entities, out_n, in_n, all_matches)
        if not hits:
            isolated.append({"query": query, "reason": "no_entity_match"})
            continue
        if first_hit is None:
            first_hit = (query, hits)
        connected = [h for h in hits if degree_of(h["id"], out_n, in_n) > 0]
        if connected:
            return query, (hits if all_matches else [connected[0]]), isolated
        isolated.append(
            {
                "query": query,
                "entity_id": hits[0]["id"],
                "permalink": hits[0]["permalink"],
                "reason": "no_resolved_relations",
            }
        )
        if not allow_fallback:
            return query, hits, isolated
    if first_hit:
        return first_hit[0], first_hit[1], isolated
    return queries[0] if queries else "", [], isolated


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Copy basic-memory's SQLite graph and rank unlinked relates_to "
            "targets via Personalized PageRank (stdlib). Does not write the vault."
        )
    )
    parser.add_argument(
        "--seed",
        action="append",
        dest="seeds",
        help="Entity title/permalink/path substring (repeatable). "
        "Default: try estate-locks then harness.",
    )
    parser.add_argument(
        "--all-matches",
        action="store_true",
        help="Use every matching entity as a PPR teleport seed (topic query).",
    )
    parser.add_argument(
        "--no-fallback",
        action="store_true",
        help="Do not try the next default seed when the first is isolated.",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE,
        help=f"Live memory.db (default: {DEFAULT_SOURCE})",
    )
    parser.add_argument(
        "--copy",
        type=Path,
        default=None,
        help="Destination copy path (default: %%TEMP%%/bm-graph-ppr.db)",
    )
    parser.add_argument(
        "--also-backup",
        action="store_true",
        help="Also copy into ~/.basic-memory/backups/bm-graph-ppr.db",
    )
    parser.add_argument(
        "--no-copy",
        action="store_true",
        help="Read --copy (or default temp copy) without recopying.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"JSON output (default: {DEFAULT_OUT})",
    )
    parser.add_argument("--top", type=int, default=20, help="Max proposals (default 20)")
    parser.add_argument(
        "--teleport",
        type=float,
        default=0.5,
        help="PPR teleport α (HippoRAG 0.5; classic 0.15). Default 0.5.",
    )
    parser.add_argument("--iters", type=int, default=40)
    parser.add_argument("--tol", type=float, default=1e-10)
    parser.add_argument(
        "--directed-only",
        action="store_true",
        help="Rank on directed edges only (default: bidirectional, HippoRAG-style).",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run a 3-node PPR smoke test and exit (no db).",
    )
    args = parser.parse_args(argv)

    if args.self_test:
        return run_self_test()

    if args.top < 1:
        raise SystemExit("--top must be >= 1")
    if not 0.0 < args.teleport < 1.0:
        raise SystemExit("--teleport must be in (0, 1)")

    copy_path = args.copy or (Path(tempfile.gettempdir()) / DEFAULT_COPY_NAME)
    copy_meta: dict
    if args.no_copy:
        if not copy_path.is_file():
            raise SystemExit(f"--no-copy but copy missing: {copy_path}")
        copy_meta = {
            "source": str(args.source),
            "copy": str(copy_path.resolve()),
            "bytes": copy_path.stat().st_size,
            "method": "reused",
            "copied_at": utc_now(),
        }
    else:
        copy_meta = copy_memory_db(args.source, copy_path)
        if args.also_backup:
            backup = Path.home() / ".basic-memory" / "backups" / DEFAULT_COPY_NAME
            copy_memory_db(args.source, backup)
            copy_meta["backup_copy"] = str(backup)

    queries = args.seeds if args.seeds else list(DEFAULT_SEEDS)
    allow_fallback = (not args.seeds) and (not args.no_fallback)

    con = open_ro(copy_path)
    try:
        graph = load_graph(con)
    finally:
        con.close()

    out_n, in_n = neighbor_sets(graph["directed"])
    query, seed_ents, isolated = pick_connected_seed(
        queries,
        graph["entities"],
        out_n,
        in_n,
        all_matches=args.all_matches,
        allow_fallback=allow_fallback,
    )
    if not seed_ents:
        payload = {
            "schema": SCHEMA,
            "error": "seed_not_found",
            "queries": queries,
            "isolated_seeds": isolated,
            "copy": copy_meta,
            "relation_schema": graph["relation_schema"],
            "vault_written": False,
            "apply_with_cap": "DEFERRED_M2",
            "a_other": "parent will relay additional ambitious item",
        }
        atomic_write(args.out, payload)
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 2

    bidirectional = not args.directed_only
    adj = build_adj(graph["directed"], bidirectional=bidirectional)
    rank_kw = dict(
        entities=graph["entities"],
        out_n=out_n,
        in_n=in_n,
        adj=adj,
        teleport=args.teleport,
        iters=args.iters,
        tol=args.tol,
        top=args.top,
    )
    primary_hits = resolve_seeds(
        query, graph["entities"], out_n, in_n, all_matches=True
    ) or seed_ents
    ranked = productive_rank(primary_hits, args.all_matches, **rank_kw)
    seed_ents = [
        graph["entities"][b["id"]]
        for b in ranked["seed_entities"]
        if b["id"] in graph["entities"]
    ] or seed_ents
    by_query: dict[str, dict] = {}
    for other in queries:
        hits = resolve_seeds(other, graph["entities"], out_n, in_n, all_matches=True)
        if not hits:
            by_query[other] = {
                "error": "no_entity_match",
                "proposals": [],
                "proposal_count": 0,
            }
            continue
        by_query[other] = productive_rank(hits, args.all_matches, **rank_kw)

    ppr_nodes = set(adj) | {e["id"] for e in seed_ents}
    for dests in adj.values():
        ppr_nodes.update(dests)

    payload = {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "copy": copy_meta,
        "relation_schema": graph["relation_schema"],
        "graph": {
            "entity_count": graph["entity_count"],
            "relation_count": graph["relation_count"],
            "directed_resolved_edges": len(graph["directed"]),
            "unresolved_to_id_null": graph["unresolved"],
            "relation_type_counts": graph["type_counts"],
            "bidirectional_rank": bidirectional,
            "ppr_nodes": len(ppr_nodes),
        },
        "query": query,
        "queries_tried": queries,
        "isolated_seeds": isolated,
        "seed_entities": ranked["seed_entities"],
        "already_linked_count": ranked["already_linked_count"],
        "already_linked": ranked["already_linked"],
        "method": ranked["method"],
        "params": {
            "teleport": args.teleport,
            "iters": args.iters,
            "tol": args.tol,
            "top": args.top,
            "all_matches": args.all_matches,
        },
        "proposals": ranked["proposals"],
        "proposal_count": ranked["proposal_count"],
        "by_query": by_query,
        "proposed_relation": "relates_to",
        "vault_written": False,
        "apply_with_cap": "DEFERRED_M2",
        "a_other": "parent will relay additional ambitious item",
    }
    atomic_write(args.out, payload)

    print(f"seed query: {query}")
    for ent in seed_ents:
        brief = entity_brief(ent, out_n, in_n)
        print(
            f"  id={brief['id']} degree={brief['degree']} "
            f"{brief['permalink']}  {brief['title']}"
        )
    if isolated:
        print(f"isolated/unmatched: {isolated}")
    print(
        f"graph: {graph['entity_count']} entities, "
        f"{len(graph['directed'])} resolved directed edges, "
        f"{graph['unresolved']} unresolved, method={ranked['method']}"
    )
    print(f"already linked: {ranked['already_linked_count']}")
    print("top proposed relates_to (NOT already linked; vault NOT written):")
    if not ranked["proposals"]:
        print("  (none)")
    for p in ranked["proposals"]:
        print(
            f"  {p['rank']:2d}. {p['score']:.6f}  {p['permalink']}  {p['title']}"
        )
    for other, block in by_query.items():
        if other == query:
            continue
        print(f"also --seed {other}: {block.get('proposal_count', 0)} proposals")
        for p in (block.get("proposals") or [])[:10]:
            print(
                f"  {p['rank']:2d}. {p['score']:.6f}  {p['permalink']}  {p['title']}"
            )
    print(f"wrote {args.out}")
    print("apply-with-cap DEFERRED (M2). A-OTHER: parent will relay additional ambitious item.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
