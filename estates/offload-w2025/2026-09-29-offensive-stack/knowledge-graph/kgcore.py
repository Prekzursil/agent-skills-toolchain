"""kgcore.py - shared estate knowledge-graph layer on an embedded Kuzu DB.

Single owner of the graph store at D:/opt/knowledge-graph/db (override with
KG_DB_PATH). The database is the standard Kuzu embedded engine v0.11.3
(official prebuilt kuzu_shared.dll, bound in kuzucapi.py) - same on-disk
format as the `kuzu` PyPI package, so a future wheel swap is transparent.

Schema (created idempotently on first open):
  node tables: Host, Credential, Finding, Technique, Engagement (PK: id STRING)
  rel tables:  reached_from    (Host        -> Host)
               authenticated_to(Credential  -> Host)
               exploited_via   (Finding     -> Technique)
               found_during    (Finding     -> Engagement)
  every rel carries a free-form `props STRING` (JSON text).

Secrets policy: Credential.secret_ref holds an indirection (env var name /
vault path / sha8), never a raw secret.

Thread model: one Database + one Connection, all access serialized by a lock
(the gateway may call run() from any thread). No timers, no background work.

Engine notes (verified live against 0.11.3, see README):
  - MERGE works for nodes and rels (SET right after MERGE on a rel does NOT -
    props updates are a separate MATCH+SET query).
  - shortestPath()/SHORTEST syntax does not exist in 0.11.3's parser; shortest
    paths are computed by iterative deepening on exact-depth var-length
    matches, which does work.
  - List comprehensions over nodes(p) are not supported; the path is returned
    as the engine's nodes(p) rendering plus a best-effort parsed hop list.
"""
from __future__ import annotations

import json
import os
import re
import sys
import threading

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import kuzucapi  # noqa: E402

DB_PATH = os.environ.get("KG_DB_PATH", os.path.join(_HERE, "db"))

NODE_LABELS = ("Host", "Credential", "Finding", "Technique", "Engagement")

REL_TYPES = {
    "reached_from": ("Host", "Host"),
    "authenticated_to": ("Credential", "Host"),
    "exploited_via": ("Finding", "Technique"),
    "found_during": ("Finding", "Engagement"),
}

# fixed typed columns per node label; anything else the caller passes in
# `props` is merged into the JSON `props` column
NODE_COLUMNS = {
    "Host": ("id", "name", "ip", "os", "status", "owner", "notes"),
    "Credential": ("id", "kind", "principal", "secret_ref", "realm", "notes"),
    "Finding": ("id", "title", "severity", "target_ref", "notes"),
    "Technique": ("id", "name", "mitre_id", "tactic", "notes"),
    "Engagement": ("id", "name", "status", "scope", "started", "ended", "notes"),
}

DDL_NODE = {
    "Host": "CREATE NODE TABLE Host(id STRING, name STRING, ip STRING, os STRING, "
            "status STRING, owner STRING, notes STRING, props STRING, PRIMARY KEY(id))",
    "Credential": "CREATE NODE TABLE Credential(id STRING, kind STRING, principal STRING, "
                  "secret_ref STRING, realm STRING, notes STRING, props STRING, PRIMARY KEY(id))",
    "Finding": "CREATE NODE TABLE Finding(id STRING, title STRING, severity STRING, "
               "target_ref STRING, notes STRING, props STRING, PRIMARY KEY(id))",
    "Technique": "CREATE NODE TABLE Technique(id STRING, name STRING, mitre_id STRING, "
                 "tactic STRING, notes STRING, props STRING, PRIMARY KEY(id))",
    "Engagement": "CREATE NODE TABLE Engagement(id STRING, name STRING, status STRING, "
                  "scope STRING, started STRING, ended STRING, notes STRING, props STRING, "
                  "PRIMARY KEY(id))",
}
DDL_REL = {
    rel: f"CREATE REL TABLE {rel}(FROM {src} TO {dst}, props STRING)"
    for rel, (src, dst) in REL_TYPES.items()
}


def _cyq(value) -> str:
    """Quote a python value as a Cypher single-quoted string literal."""
    if value is None:
        return "''"
    s = str(value)
    s = s.replace("\\", "\\\\").replace("'", "\\'")
    s = s.replace("\r", " ").replace("\n", "\\n").replace("\t", "\\t")
    return "'" + s + "'"


def _parse_nodes_p(rendered: str) -> list[dict]:
    """Best-effort parse of the engine's nodes(p) rendering:
    [{_ID: 0:0, _LABEL: Host, id: h-01, name: a, props: {}},{...}] -> dicts.
    One level of nested braces (props: {...}) is tolerated; property values
    containing ', ' can still confuse the per-field match - the raw rendering
    is always returned alongside (path_raw)."""
    hops = []
    for seg in re.findall(r"\{((?:[^{}]|\{[^{}]*\})*)\}", rendered):
        m_id = re.search(r"_ID: ([0-9]+:[0-9]+)", seg)
        m_lab = re.search(r"_LABEL: (\w+)", seg)
        m_pid = re.search(r"(?:^|, )id: ([^,}]*)", seg)
        hops.append({"_id": m_id.group(1) if m_id else None,
                     "label": m_lab.group(1) if m_lab else None,
                     "id": m_pid.group(1) if m_pid else None})
    return hops


class _Store:
    """Process-wide singleton around one embedded Kuzu database."""

    def __init__(self):
        self._lock = threading.Lock()
        self._db = None

    def _ensure(self):
        with self._lock:
            return self._ensure_locked()

    def _ensure_locked(self):
        if self._db is None:
            self._db = kuzucapi.Database(DB_PATH)
            self._bootstrap_locked()
        return self._db

    def _bootstrap_locked(self):
        existing = set()
        r = self._db.query("CALL show_tables() RETURN name")
        if r["ok"]:
            existing = {row[0] for row in r["rows"]}
        for label in NODE_LABELS:
            if label not in existing:
                self._db.query(DDL_NODE[label])
        for rel in REL_TYPES:
            if rel not in existing:
                self._db.query(DDL_REL[rel])

    def query(self, cypher: str) -> dict:
        db = self._ensure()
        with self._lock:
            return db.query(cypher)

    def close(self):
        with self._lock:
            if self._db is not None:
                self._db.close()
                self._db = None


_STORE = _Store()


# --- tools -----------------------------------------------------------------


def add_node(args: dict) -> dict:
    """args: {label, id, props?{...}} - upsert one node (MERGE on id)."""
    label = args.get("label", "")
    node_id = args.get("id")
    if label not in NODE_LABELS:
        return {"ok": False, "error": f"label must be one of {list(NODE_LABELS)}", "got": label}
    if not node_id:
        return {"ok": False, "error": "id is required"}
    props = dict(args.get("props") or {})
    cols = NODE_COLUMNS[label]
    sets, extra = [], {}
    for k, v in props.items():
        if k in cols:
            sets.append(f"n.{k} = {_cyq(v)}")
        else:
            extra[k] = v
    sets.append(f"n.props = {_cyq(json.dumps(extra, ensure_ascii=False))}")
    cy = (f"MERGE (n:{label} {{id:{_cyq(node_id)}}}) "
          f"SET {', '.join(sets)} RETURN n.id")
    r = _STORE.query(cy)
    if not r["ok"]:
        return {"ok": False, "error": r["error"], "cypher": cy}
    return {"ok": True, "label": label, "id": node_id,
            "known_fields_set": [s.split(" = ")[0].split(".")[1] for s in sets[:-1]],
            "extra_props": extra}


def add_edge(args: dict) -> dict:
    """args: {type, from_id, to_id, props?{...}} - create-or-update one edge.
    Stored direction: (from_id)-[:type]->(to_id).
    Semantics: reached_from: attacker moved from `from_id` host to `to_id` host;
    authenticated_to: credential authenticates to host; exploited_via: finding
    was achieved via technique; found_during: finding belongs to engagement."""
    rel = args.get("type", "")
    if rel not in REL_TYPES:
        return {"ok": False, "error": f"type must be one of {sorted(REL_TYPES)}", "got": rel}
    src_lbl, dst_lbl = REL_TYPES[rel]
    from_id, to_id = args.get("from_id"), args.get("to_id")
    if not from_id or not to_id:
        return {"ok": False, "error": "from_id and to_id are required"}
    props = dict(args.get("props") or {})
    cy = (f"MATCH (a:{src_lbl} {{id:{_cyq(from_id)}}}), (b:{dst_lbl} {{id:{_cyq(to_id)}}}) "
          f"MERGE (a)-[r:{rel}]->(b)")
    r = _STORE.query(cy)
    if not r["ok"]:
        return {"ok": False, "error": r["error"], "cypher": cy}
    updated = None
    if props:
        cy2 = (f"MATCH (a:{src_lbl} {{id:{_cyq(from_id)}}})-[r:{rel}]->"
               f"(b:{dst_lbl} {{id:{_cyq(to_id)}}}) "
               f"SET r.props = {_cyq(json.dumps(props, ensure_ascii=False))}")
        r2 = _STORE.query(cy2)
        if not r2["ok"]:
            return {"ok": False, "error": "edge created but props update failed: " + r2["error"]}
        updated = props
    return {"ok": True, "type": rel, "from": from_id, "to": to_id,
            "from_label": src_lbl, "to_label": dst_lbl, "props": updated}


def neighbors(args: dict) -> dict:
    """args: {id, label?, rel?, direction? out|in|both, limit?} - adjacent nodes."""
    node_id = args.get("id")
    if not node_id:
        return {"ok": False, "error": "id is required"}
    label = args.get("label") or None
    if label and label not in NODE_LABELS:
        return {"ok": False, "error": f"unknown label '{label}'", "known": list(NODE_LABELS)}
    rel = args.get("rel") or None
    if rel and rel not in REL_TYPES:
        return {"ok": False, "error": f"unknown rel '{rel}'", "known": sorted(REL_TYPES)}
    direction = args.get("direction", "both")
    if direction not in ("out", "in", "both"):
        return {"ok": False, "error": "direction must be out|in|both"}
    limit = int(args.get("limit", 100))
    rels = [rel] if rel else sorted(REL_TYPES)
    labels = [label] if label else list(NODE_LABELS)
    out, warnings = [], []
    for lab in labels:
        for r in rels:
            dirs = [d for d in ("out", "in") if direction in (d, "both")]
            for d in dirs:
                pre, post = ("-", "->") if d == "out" else ("<-", "-")
                cy = (f"MATCH (n:{lab} {{id:{_cyq(node_id)}}}){pre}[e:{r}]{post}"
                      f"(m) RETURN m.id, label(m), label(e), e.props LIMIT {limit}")
                rr = _STORE.query(cy)
                if not rr["ok"]:
                    warnings.append(f"{lab}/{r}/{d}: {rr['error']}")
                    continue
                for row in rr["rows"]:
                    try:
                        props = json.loads(row[3]) if row[3] else {}
                    except (TypeError, ValueError):
                        props = row[3]
                    out.append({"id": row[0], "label": row[1], "rel": row[2],
                                "direction": d, "props": props})
    seen, deduped = set(), []
    for item in out:
        key = (item["id"], item["rel"], item["direction"])
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    res = {"ok": True, "id": node_id, "neighbors": deduped[:limit], "count": len(deduped[:limit])}
    if warnings:
        res["warnings"] = warnings
    return res


def shortest_path(args: dict) -> dict:
    """args: {src, dst, src_label?, dst_label?, max_hops?} - BFS by iterative
    deepening over exact-depth var-length matches (undirected, all rel types).
    Returns the hop list parsed from nodes(p) plus the raw rendering."""
    src, dst = args.get("src"), args.get("dst")
    if not src or not dst:
        return {"ok": False, "error": "src and dst are required"}
    max_hops = int(args.get("max_hops", 8))
    src_lab = args.get("src_label") or None
    dst_lab = args.get("dst_label") or None
    if src == dst:
        return {"ok": True, "found": True, "hops": 0, "path": [{"id": src}],
                "src": src, "dst": dst}
    a = f"(a:{src_lab} {{id:{_cyq(src)}}})" if src_lab else f"(a {{id:{_cyq(src)}}})"
    b = f"(b:{dst_lab} {{id:{_cyq(dst)}}})" if dst_lab else f"(b {{id:{_cyq(dst)}}})"
    for k in range(1, max_hops + 1):
        cy = f"MATCH p = {a}-[*{k}]-{b} RETURN nodes(p) LIMIT 1"
        r = _STORE.query(cy)
        if not r["ok"]:
            return {"ok": False, "error": r["error"], "cypher": cy}
        if r["rows"]:
            raw = r["rows"][0][0]
            hops = _parse_nodes_p(raw)
            return {"ok": True, "found": True, "hops": k, "path": hops,
                    "path_raw": raw, "src": src, "dst": dst}
    return {"ok": True, "found": False, "hops": None, "path": [],
            "src": src, "dst": dst, "max_hops": max_hops}


def search(args: dict) -> dict:
    """args: {q, limit?} - case-insensitive substring over id/name/title/notes/props."""
    q = args.get("q", "")
    limit = int(args.get("limit", 50))
    if not q:
        r = _STORE.query("MATCH (n) RETURN label(n), count(*)")
        if not r["ok"]:
            return {"ok": False, "error": r["error"]}
        return {"ok": True, "query": q, "counts": {row[0]: int(row[1]) for row in r["rows"]}}
    needle = _cyq(q)
    cy = ("MATCH (n) WHERE toLower(n.id) CONTAINS toLower(" + needle + ") "
          "OR toLower(coalesce(n.name,'')) CONTAINS toLower(" + needle + ") "
          "OR toLower(coalesce(n.title,'')) CONTAINS toLower(" + needle + ") "
          "OR toLower(coalesce(n.notes,'')) CONTAINS toLower(" + needle + ") "
          "OR toLower(coalesce(n.props,'')) CONTAINS toLower(" + needle + ") "
          f"RETURN n.id, label(n), coalesce(n.name, n.title, '') LIMIT {limit}")
    r = _STORE.query(cy)
    if not r["ok"]:
        return {"ok": False, "error": r["error"], "cypher": cy}
    hits = [{"id": row[0], "label": row[1], "name": row[2]} for row in r["rows"]]
    return {"ok": True, "query": q, "hits": hits, "count": len(hits)}


def cypher(args: dict) -> dict:
    """args: {query, max_rows?} - raw Cypher passthrough (read AND write)."""
    query = args.get("query", "")
    if not query.strip():
        return {"ok": False, "error": "query is required"}
    max_rows = int(args.get("max_rows", 200))
    r = _STORE.query(query)
    if not r["ok"]:
        return {"ok": False, "error": r["error"], "query": query}
    rows = r["rows"][:max_rows]
    return {"ok": True, "columns": r["columns"], "rows": rows, "num_tuples": r["num_tuples"],
            "truncated": r["num_tuples"] > len(rows), "query": query}


TOOLS = {
    "add_node": add_node,
    "add_edge": add_edge,
    "neighbors": neighbors,
    "shortest_path": shortest_path,
    "search": search,
    "cypher": cypher,
}


def run(tool: str, args: dict) -> str:
    """Front contract (mirrors fronts/ conventions): run(tool, args) -> JSON str."""
    fn = TOOLS.get(tool)
    if fn is None:
        return json.dumps({"ok": False, "error": f"unknown tool '{tool}'",
                           "tools": sorted(TOOLS), "db_path": DB_PATH})
    try:
        return json.dumps(fn(args or {}), ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001 - tool errors are result data
        return json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"})


def close():
    """Release the embedded DB handle (used by tests / direct CLI use)."""
    _STORE.close()
