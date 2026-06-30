#!/usr/bin/env python
"""tms_core.py - Truth-Maintenance System core (Doyle-1979 semantics, ported).

A justification graph over derived reverse-engineering facts. Each node is a
belief with status IN or OUT.

    A node is IN  iff  it is NOT explicitly retracted
                 AND   its source artifact has NOT drifted (sha still matches)
                 AND   ALL of its premises are IN.

Retracting a node (or OUT-ing it via source drift) cascades along the
justification edges to flip EVERY transitive dependent OUT - the structural
kill for the wrong-but-consistent anchor (a bad base/offset/pid poisoning every
downstream finding). This is dependency-directed: the edges, not a re-derivation,
drive the cascade.

Semantics ported from benthomasson/ftl-reasons (assert / retract / explain /
trace with dependency-directed cascade); NO runtime dependency on that repo.

Stdlib + sqlite3 only. The DB lives at ~/.claude/tms/beliefs.db (override with
the TMS_DB env var, used by the test suite).
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
import time
from pathlib import Path
from typing import Iterable

KINDS = ("offset", "address", "pid", "version", "fact")
STATUS_IN = "IN"
STATUS_OUT = "OUT"

DEFAULT_DB = Path.home() / ".claude" / "tms" / "beliefs.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes (
    id              TEXT PRIMARY KEY,
    statement       TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'IN'  CHECK (status IN ('IN','OUT')),
    kind            TEXT NOT NULL               CHECK (kind IN ('offset','address','pid','version','fact')),
    source_artifact TEXT,
    source_sha      TEXT,
    retracted       INTEGER NOT NULL DEFAULT 0  CHECK (retracted IN (0,1)),
    source_drift    INTEGER NOT NULL DEFAULT 0  CHECK (source_drift IN (0,1)),
    reason          TEXT NOT NULL DEFAULT '',
    ts              TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS justifications (
    node_id    TEXT NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    premise_id TEXT NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    PRIMARY KEY (node_id, premise_id)
);
CREATE INDEX IF NOT EXISTS idx_just_node    ON justifications(node_id);
CREATE INDEX IF NOT EXISTS idx_just_premise ON justifications(premise_id);
"""


# --------------------------------------------------------------------------- #
# Connection / schema
# --------------------------------------------------------------------------- #
def db_path() -> str:
    """Resolve the DB path (TMS_DB env overrides the default)."""
    return os.environ.get("TMS_DB", str(DEFAULT_DB))


def connect(create: bool = True, readonly: bool = False) -> sqlite3.Connection:
    """Open the beliefs DB.

    readonly=True is for the hook: it raises if the file is absent (so callers can
    fail-open) and never creates or migrates. The hook only issues SELECTs, so a
    plain connection is read-only in practice and avoids SQLite URI quirks on
    Windows backslash paths.
    """
    path = db_path()
    if readonly:
        if not os.path.exists(path):
            raise FileNotFoundError(path)
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        return conn
    if create:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(_SCHEMA)
    return conn


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha256_file(path: str | None) -> str | None:
    """SHA-256 of a file, or None if it is missing/unreadable."""
    if not path:
        return None
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 16), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


# --------------------------------------------------------------------------- #
# Graph loading + status evaluation (the cascade)
# --------------------------------------------------------------------------- #
def _load_graph(conn: sqlite3.Connection) -> tuple[dict, dict]:
    nodes = {r["id"]: dict(r) for r in conn.execute("SELECT * FROM nodes")}
    premises: dict[str, list[str]] = {}
    for r in conn.execute("SELECT node_id, premise_id FROM justifications"):
        premises.setdefault(r["node_id"], []).append(r["premise_id"])
    return nodes, premises


def _evaluate(nodes: dict, premises: dict) -> tuple[dict, dict]:
    """Memoized DFS computing IN/OUT + a reason for every node. Cycle-safe."""
    status: dict[str, str] = {}
    reason: dict[str, str] = {}
    on_stack: set[str] = set()

    def visit(nid: str) -> str:
        if nid in status:
            return status[nid]
        node = nodes.get(nid)
        if node is None:
            status[nid] = STATUS_OUT
            reason[nid] = f"missing node '{nid}'"
            return STATUS_OUT
        if nid in on_stack:  # safety net; cycles are rejected at assert time
            status[nid] = STATUS_OUT
            reason[nid] = "cycle detected"
            return STATUS_OUT
        on_stack.add(nid)
        try:
            if node["retracted"]:
                status[nid], reason[nid] = STATUS_OUT, "explicitly retracted"
                return STATUS_OUT
            if node["source_drift"]:
                status[nid] = STATUS_OUT
                reason[nid] = (
                    f"source changed since assert (sha drift): {node['source_artifact']}"
                )
                return STATUS_OUT
            prem = premises.get(nid, [])
            out_prem = sorted(p for p in prem if visit(p) == STATUS_OUT)
            if out_prem:
                status[nid] = STATUS_OUT
                reason[nid] = "premise(s) OUT: " + ", ".join(out_prem)
                return STATUS_OUT
            status[nid] = STATUS_IN
            reason[nid] = (
                ("supported by: " + ", ".join(sorted(prem)))
                if prem
                else "asserted premise"
            )
            return STATUS_IN
        finally:
            on_stack.discard(nid)

    for nid in nodes:
        visit(nid)
    return status, reason


def recompute(conn: sqlite3.Connection) -> dict[str, tuple[str, str]]:
    """Re-evaluate the whole graph and persist status/reason. Return flips."""
    nodes, premises = _load_graph(conn)
    status, reason = _evaluate(nodes, premises)
    flips: dict[str, tuple[str, str]] = {}
    cur = conn.cursor()
    for nid, node in nodes.items():
        new_status, new_reason = status[nid], reason[nid]
        if node["status"] != new_status:
            flips[nid] = (node["status"], new_status)
        if node["status"] != new_status or node["reason"] != new_reason:
            cur.execute(
                "UPDATE nodes SET status=?, reason=? WHERE id=?",
                (new_status, new_reason, nid),
            )
    conn.commit()
    return flips


# --------------------------------------------------------------------------- #
# Graph queries
# --------------------------------------------------------------------------- #
def get_node(conn: sqlite3.Connection, nid: str) -> dict | None:
    r = conn.execute("SELECT * FROM nodes WHERE id=?", (nid,)).fetchone()
    return dict(r) if r else None


def get_premises(conn: sqlite3.Connection, nid: str) -> list[str]:
    return [
        r["premise_id"]
        for r in conn.execute(
            "SELECT premise_id FROM justifications WHERE node_id=? ORDER BY premise_id",
            (nid,),
        )
    ]


def get_dependents(conn: sqlite3.Connection, nid: str) -> list[str]:
    return [
        r["node_id"]
        for r in conn.execute(
            "SELECT node_id FROM justifications WHERE premise_id=? ORDER BY node_id",
            (nid,),
        )
    ]


def _closure(edges: dict[str, list[str]], start: str) -> set[str]:
    seen: set[str] = set()
    stack = list(edges.get(start, []))
    while stack:
        x = stack.pop()
        if x in seen:
            continue
        seen.add(x)
        stack.extend(edges.get(x, []))
    return seen


def ancestors(conn: sqlite3.Connection, nid: str) -> set[str]:
    """All nodes nid (transitively) depends on - its premise closure (upward)."""
    fwd: dict[str, list[str]] = {}
    for r in conn.execute("SELECT node_id, premise_id FROM justifications"):
        fwd.setdefault(r["node_id"], []).append(r["premise_id"])
    return _closure(fwd, nid)


def descendants(conn: sqlite3.Connection, nid: str) -> set[str]:
    """All nodes that (transitively) depend on nid - the blast radius (downward)."""
    rev: dict[str, list[str]] = {}
    for r in conn.execute("SELECT node_id, premise_id FROM justifications"):
        rev.setdefault(r["premise_id"], []).append(r["node_id"])
    return _closure(rev, nid)


def would_cycle(
    conn: sqlite3.Connection, node_id: str, premise_ids: Iterable[str]
) -> bool:
    """True if giving node_id these premises would close a cycle."""
    fwd: dict[str, list[str]] = {}
    for r in conn.execute("SELECT node_id, premise_id FROM justifications"):
        fwd.setdefault(r["node_id"], []).append(r["premise_id"])
    seen: set[str] = set()
    stack = list(premise_ids)
    while stack:
        x = stack.pop()
        if x == node_id:
            return True
        if x in seen:
            continue
        seen.add(x)
        stack.extend(fwd.get(x, []))
    return False


def root_causes(conn: sqlite3.Connection, nid: str) -> list[tuple[str, str]]:
    """Locally-OUT nodes (retracted or drifted) in nid's premise-closure + self.

    These are the *origins* of an OUT verdict - what must be re-derived. Returns
    [(node_id, why), ...] where why is 'explicitly retracted' or 'source drift'.
    """
    causes: list[tuple[str, str]] = []
    for cid in sorted(ancestors(conn, nid) | {nid}):
        n = get_node(conn, cid)
        if not n:
            continue
        if n["retracted"]:
            causes.append((cid, "explicitly retracted"))
        elif n["source_drift"]:
            causes.append((cid, "source drift"))
    return causes


# --------------------------------------------------------------------------- #
# Mutations
# --------------------------------------------------------------------------- #
def assert_node(
    conn: sqlite3.Connection,
    nid: str,
    statement: str,
    kind: str,
    premises: Iterable[str] | None = None,
    source: str | None = None,
) -> bool:
    """Assert (create or refresh) a belief. Returns True if it already existed.

    Re-asserting clears any retraction/drift and re-hashes the source. Incoming
    justifications (where this node is a premise) are preserved; only this node's
    own premises are replaced.
    """
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}, got {kind!r}")
    prem = [p for p in dict.fromkeys(premises or []) if p != nid]
    missing = [
        p
        for p in prem
        if conn.execute("SELECT 1 FROM nodes WHERE id=?", (p,)).fetchone() is None
    ]
    if missing:
        raise ValueError(
            f"unknown premise(s): {', '.join(missing)} - assert them first"
        )
    if would_cycle(conn, nid, prem):
        raise ValueError(f"asserting {nid!r} with premises {prem} would create a cycle")
    source_sha = sha256_file(source)
    ts = _now()
    exists = (
        conn.execute("SELECT 1 FROM nodes WHERE id=?", (nid,)).fetchone() is not None
    )
    if exists:
        conn.execute(
            "UPDATE nodes SET statement=?, kind=?, source_artifact=?, source_sha=?, "
            "retracted=0, source_drift=0, ts=? WHERE id=?",
            (statement, kind, source, source_sha, ts, nid),
        )
        conn.execute("DELETE FROM justifications WHERE node_id=?", (nid,))
    else:
        conn.execute(
            "INSERT INTO nodes (id, statement, status, kind, source_artifact, source_sha, "
            "retracted, source_drift, reason, ts) VALUES (?,?,?,?,?,?,0,0,'',?)",
            (nid, statement, STATUS_IN, kind, source, source_sha, ts),
        )
    for p in prem:
        conn.execute(
            "INSERT OR IGNORE INTO justifications (node_id, premise_id) VALUES (?,?)",
            (nid, p),
        )
    conn.commit()
    recompute(conn)
    return exists


def retract_node(conn: sqlite3.Connection, nid: str) -> dict[str, tuple[str, str]]:
    """Explicitly retract a belief and cascade. Returns the status flips."""
    if conn.execute("SELECT 1 FROM nodes WHERE id=?", (nid,)).fetchone() is None:
        raise ValueError(f"no such node: {nid}")
    conn.execute("UPDATE nodes SET retracted=1 WHERE id=?", (nid,))
    conn.commit()
    return recompute(conn)


def recheck(
    conn: sqlite3.Connection,
) -> tuple[dict[str, bool], dict[str, tuple[str, str]]]:
    """Re-hash every source artifact; OUT any whose sha changed + cascade.

    Returns (drift_changes, flips). drift_changes maps node_id -> now_drifted(bool)
    for nodes whose drift flag changed this pass.
    """
    rows = conn.execute(
        "SELECT id, source_artifact, source_sha, source_drift FROM nodes "
        "WHERE source_artifact IS NOT NULL AND source_artifact != ''"
    ).fetchall()
    drift_changes: dict[str, bool] = {}
    for r in rows:
        cur_sha = sha256_file(r["source_artifact"])
        drifted = 1 if (cur_sha is None or cur_sha != r["source_sha"]) else 0
        if drifted != r["source_drift"]:
            conn.execute(
                "UPDATE nodes SET source_drift=? WHERE id=?", (drifted, r["id"])
            )
            drift_changes[r["id"]] = bool(drifted)
    conn.commit()
    flips = recompute(conn)
    return drift_changes, flips


def all_nodes(conn: sqlite3.Connection, out_only: bool = False) -> list[dict]:
    sql = "SELECT * FROM nodes"
    if out_only:
        sql += " WHERE status='OUT'"
    sql += " ORDER BY id"
    return [dict(r) for r in conn.execute(sql)]
