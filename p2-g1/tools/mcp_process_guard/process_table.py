"""Synthetic stdio process table (IMP-0472)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass
class Census:
    source: str
    mcp_count: int
    session_count: int
    multiplier: int
    by_server: dict[str, int]


def synthetic_stdio_table(
    sessions: int,
    servers: Iterable[str],
    shared: Iterable[str] | None = None,
) -> list[dict]:
    servers = tuple(servers)
    shared = tuple(shared or ())
    rows = []
    for s in range(sessions):
        for name in servers:
            rows.append(
                {
                    "pid": 1000 + s * 10 + servers.index(name),
                    "server": name,
                    "session": s,
                    "transport": "stdio-per-session",
                }
            )
    for name in shared:
        rows.append(
            {
                "pid": 9000 + servers.index(name) if name in servers else 9000,
                "server": name,
                "session": None,
                "transport": "shared-long-lived",
            }
        )
    return rows


def census(rows: list[dict], source: str = "injected") -> Census:
    by: dict[str, int] = {}
    sessions = set()
    for row in rows:
        name = row["server"]
        by[name] = by.get(name, 0) + 1
        if row.get("session") is not None:
            sessions.add(row["session"])
    n_sessions = len(sessions) or 1
    mcp = len(rows)
    return Census(
        source=source,
        mcp_count=mcp,
        session_count=n_sessions,
        multiplier=mcp // n_sessions if n_sessions else mcp,
        by_server=by,
    )
