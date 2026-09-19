"""SQLite run-history / artifacts store for the biomni-hub (feature #6).

A single durable ledger under the hub's data dir records every task launched
through the hub across all backends, the artifacts fetched for each run, a
cached tool catalog, and the set of MCPs injected into self-hosted backends.
Every other feature tool reads/writes this store, which is what makes
``biomni_run_history`` / ``biomni_cost`` work *across backends* without a live
round-trip and lets ``biomni_inject_mcp`` replay injections after an ephemeral
cluster restart.

Async (aiosqlite) so it composes with FastMCP's async tools. WAL mode + a busy
timeout make it safe for the hub's concurrent tool calls.
"""

from __future__ import annotations

import os
import time
import uuid
from typing import Any

import aiosqlite

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id      TEXT PRIMARY KEY,
    backend     TEXT NOT NULL,
    project_id  TEXT,
    workspace_id TEXT,
    session_id  TEXT,
    task_id     TEXT,
    prompt      TEXT,
    status      TEXT NOT NULL DEFAULT 'pending',
    model       TEXT,
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL,
    started_at  REAL,
    ended_at    REAL,
    duration_s  REAL,
    tokens_in   INTEGER DEFAULT 0,
    tokens_out  INTEGER DEFAULT 0,
    cost_usd    REAL DEFAULT 0.0,
    compute_usd REAL DEFAULT 0.0,
    extra_json  TEXT
);
CREATE INDEX IF NOT EXISTS idx_runs_backend ON runs(backend);
CREATE INDEX IF NOT EXISTS idx_runs_status  ON runs(status);
CREATE INDEX IF NOT EXISTS idx_runs_created ON runs(created_at);

CREATE TABLE IF NOT EXISTS artifacts (
    artifact_id  TEXT PRIMARY KEY,
    run_id       TEXT,
    name         TEXT NOT NULL,
    size         INTEGER,
    url          TEXT,
    local_path   TEXT,
    sha256       TEXT,
    content_type TEXT,
    source       TEXT,          -- 'download' | 'url_only'
    fetched_at   REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_art_run ON artifacts(run_id);

CREATE TABLE IF NOT EXISTS tool_catalog (
    backend     TEXT NOT NULL,
    name        TEXT NOT NULL,
    category    TEXT,
    description TEXT,
    enabled     INTEGER DEFAULT 1,
    source      TEXT,
    updated_at  REAL NOT NULL,
    PRIMARY KEY (backend, name)
);

CREATE TABLE IF NOT EXISTS injected_mcps (
    backend    TEXT NOT NULL,
    ref        TEXT NOT NULL,   -- fleet name or logical id
    spec_json  TEXT NOT NULL,
    status     TEXT DEFAULT 'active',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    PRIMARY KEY (backend, ref)
);
"""

_WINDOWS = {"today": 86_400.0, "24h": 86_400.0, "7d": 604_800.0, "30d": 2_592_000.0}


def _now() -> float:
    return time.time()


def window_start(window: str) -> float:
    """Return the epoch cutoff for a rolling window label (0.0 == 'all')."""
    span = _WINDOWS.get(window.lower())
    return 0.0 if span is None else _now() - span


class RunStore:
    """Async SQLite façade over the hub's run/artifact/catalog/injection tables."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    async def ensure_schema(self) -> None:
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(_SCHEMA)
            await db.commit()

    async def _connect(self) -> aiosqlite.Connection:
        db = await aiosqlite.connect(self.db_path)
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA busy_timeout=5000")
        return db

    # ---- runs -----------------------------------------------------------
    async def upsert_run(
        self,
        *,
        backend: str,
        run_id: str | None = None,
        prompt: str | None = None,
        status: str = "pending",
        **fields: Any,
    ) -> str:
        """Insert a new run or update an existing one. Returns the run_id."""
        rid = run_id or uuid.uuid4().hex
        now = _now()
        cols: dict[str, Any] = {
            "run_id": rid,
            "backend": backend,
            "prompt": prompt,
            "status": status,
            "updated_at": now,
        }
        allowed = {
            "project_id", "workspace_id", "session_id", "task_id", "model",
            "started_at", "ended_at", "duration_s", "tokens_in", "tokens_out",
            "cost_usd", "compute_usd", "extra_json",
        }
        cols.update({k: v for k, v in fields.items() if k in allowed})
        db = await self._connect()
        try:
            names = ", ".join(cols)
            placeholders = ", ".join(f":{k}" for k in cols)
            updates = ", ".join(f"{k}=excluded.{k}" for k in cols if k != "run_id")
            await db.execute(
                f"INSERT INTO runs ({names}, created_at) "  # noqa: S608 (fixed cols)
                f"VALUES ({placeholders}, :created_at) "
                f"ON CONFLICT(run_id) DO UPDATE SET {updates}",
                {**cols, "created_at": now},
            )
            await db.commit()
        finally:
            await db.close()
        return rid

    async def get_run(self, run_id: str) -> dict[str, Any] | None:
        db = await self._connect()
        try:
            cur = await db.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
            row = await cur.fetchone()
            return dict(row) if row else None
        finally:
            await db.close()

    async def list_runs(
        self,
        *,
        backend: str | None = None,
        status: str | None = None,
        project_id: str | None = None,
        since: float = 0.0,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if backend:
            clauses.append("backend = ?")
            params.append(backend)
        if status:
            clauses.append("status = ?")
            params.append(status)
        if project_id:
            clauses.append("project_id = ?")
            params.append(project_id)
        if since:
            clauses.append("created_at >= ?")
            params.append(since)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(max(1, min(int(limit), 1000)))
        db = await self._connect()
        try:
            cur = await db.execute(
                f"SELECT * FROM runs {where} ORDER BY created_at DESC LIMIT ?",  # noqa: S608
                params,
            )
            rows = await cur.fetchall()
            return [dict(r) for r in rows]
        finally:
            await db.close()

    async def cost_rollup(
        self, *, backend: str | None = None, since: float = 0.0
    ) -> list[dict[str, Any]]:
        """Aggregate cost/tokens grouped by backend over a window."""
        clauses: list[str] = []
        params: list[Any] = []
        if backend:
            clauses.append("backend = ?")
            params.append(backend)
        if since:
            clauses.append("created_at >= ?")
            params.append(since)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        db = await self._connect()
        try:
            cur = await db.execute(
                "SELECT backend, COUNT(*) AS runs, "
                "COALESCE(SUM(cost_usd),0) AS cost_usd, "
                "COALESCE(SUM(compute_usd),0) AS compute_usd, "
                "COALESCE(SUM(tokens_in),0) AS tokens_in, "
                "COALESCE(SUM(tokens_out),0) AS tokens_out, "
                "COALESCE(SUM(duration_s),0) AS duration_s "
                f"FROM runs {where} GROUP BY backend",  # noqa: S608
                params,
            )
            rows = await cur.fetchall()
            return [dict(r) for r in rows]
        finally:
            await db.close()

    # ---- artifacts ------------------------------------------------------
    async def add_artifact(
        self,
        *,
        run_id: str | None,
        name: str,
        size: int | None = None,
        url: str | None = None,
        local_path: str | None = None,
        sha256: str | None = None,
        content_type: str | None = None,
        source: str = "download",
    ) -> str:
        aid = uuid.uuid4().hex
        db = await self._connect()
        try:
            await db.execute(
                "INSERT INTO artifacts (artifact_id, run_id, name, size, url, "
                "local_path, sha256, content_type, source, fetched_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (aid, run_id, name, size, url, local_path, sha256,
                 content_type, source, _now()),
            )
            await db.commit()
        finally:
            await db.close()
        return aid

    async def get_artifact(self, artifact_id: str) -> dict[str, Any] | None:
        db = await self._connect()
        try:
            cur = await db.execute(
                "SELECT * FROM artifacts WHERE artifact_id = ?", (artifact_id,)
            )
            row = await cur.fetchone()
            return dict(row) if row else None
        finally:
            await db.close()

    async def list_artifacts(self, run_id: str) -> list[dict[str, Any]]:
        db = await self._connect()
        try:
            cur = await db.execute(
                "SELECT * FROM artifacts WHERE run_id = ? ORDER BY fetched_at DESC",
                (run_id,),
            )
            rows = await cur.fetchall()
            return [dict(r) for r in rows]
        finally:
            await db.close()

    async def count_artifacts(self, run_id: str) -> int:
        db = await self._connect()
        try:
            cur = await db.execute(
                "SELECT COUNT(*) FROM artifacts WHERE run_id = ?", (run_id,)
            )
            row = await cur.fetchone()
            return int(row[0]) if row else 0
        finally:
            await db.close()

    # ---- tool catalog cache --------------------------------------------
    async def cache_catalog(
        self, backend: str, tools: list[dict[str, Any]]
    ) -> int:
        now = _now()
        db = await self._connect()
        try:
            for t in tools:
                await db.execute(
                    "INSERT INTO tool_catalog (backend, name, category, "
                    "description, enabled, source, updated_at) "
                    "VALUES (?,?,?,?,?,?,?) "
                    "ON CONFLICT(backend, name) DO UPDATE SET "
                    "category=excluded.category, description=excluded.description, "
                    "enabled=excluded.enabled, source=excluded.source, "
                    "updated_at=excluded.updated_at",
                    (backend, t.get("name"), t.get("category"),
                     t.get("description"), 1 if t.get("enabled", True) else 0,
                     t.get("source"), now),
                )
            await db.commit()
        finally:
            await db.close()
        return len(tools)

    async def read_catalog(
        self, backend: str, *, include_disabled: bool = True
    ) -> list[dict[str, Any]]:
        db = await self._connect()
        try:
            sql = "SELECT * FROM tool_catalog WHERE backend = ?"
            if not include_disabled:
                sql += " AND enabled = 1"
            cur = await db.execute(sql + " ORDER BY category, name", (backend,))
            rows = await cur.fetchall()
            return [dict(r) for r in rows]
        finally:
            await db.close()

    # ---- injected MCPs --------------------------------------------------
    async def record_injection(
        self, backend: str, ref: str, spec_json: str, status: str = "active"
    ) -> None:
        now = _now()
        db = await self._connect()
        try:
            await db.execute(
                "INSERT INTO injected_mcps (backend, ref, spec_json, status, "
                "created_at, updated_at) VALUES (?,?,?,?,?,?) "
                "ON CONFLICT(backend, ref) DO UPDATE SET "
                "spec_json=excluded.spec_json, status=excluded.status, "
                "updated_at=excluded.updated_at",
                (backend, ref, spec_json, status, now, now),
            )
            await db.commit()
        finally:
            await db.close()

    async def list_injections(
        self, backend: str | None = None, *, active_only: bool = True
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if backend:
            clauses.append("backend = ?")
            params.append(backend)
        if active_only:
            clauses.append("status = 'active'")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        db = await self._connect()
        try:
            cur = await db.execute(
                f"SELECT * FROM injected_mcps {where} ORDER BY created_at",  # noqa: S608
                params,
            )
            rows = await cur.fetchall()
            return [dict(r) for r in rows]
        finally:
            await db.close()
