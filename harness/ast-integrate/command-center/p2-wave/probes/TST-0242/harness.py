"""Live glue for TST-0242: OS-table monitor + bounded MCP fan-out."""
from __future__ import annotations

import sys
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN = REPO / "tools" / "plugin"
if str(PLUGIN) not in sys.path:
    sys.path.insert(0, str(PLUGIN))

import mcp_activation as act  # noqa: E402
import pressure_guard as pg  # noqa: E402

N_SERVERS = 3
SERVERS = tuple(f"svc-{i}" for i in range(N_SERVERS))
BASE_SESSIONS = 1
FANOUT_MULT = 10
FANOUT_SESSIONS = BASE_SESSIONS * FANOUT_MULT
EAGER_CONTROL_SESSIONS = 4
PROCESS_CEILING = 5
UNIT = "TST-0242"


def sample(mark: str) -> dict[str, Any]:
    """Two independent process-count signals plus commit charge (not working set)."""
    pids = act.iter_stub_pids(mark)
    procfs_n = len(pids)
    ps = act.rss_kb_ps(mark)
    proxy = act.rss_swap_bytes_procfs(mark)
    mem = pg.read_commit_charge()
    return {
        "mark": mark,
        "procfs_n": procfs_n,
        "procfs_pids": pids,
        "ps_n": int(ps.get("n") or 0),
        "ps_rss_kb": int(ps.get("rss_kb") or 0),
        "commit_proxy_bytes": int(proxy.get("commit_proxy_bytes") or 0),
        "rss_bytes": int(proxy.get("rss_bytes") or 0),
        "swap_bytes": int(proxy.get("swap_bytes") or 0),
        "committed_as_kb": int(mem.get("committed_as_kb") or -1),
        "commit_limit_kb": int(mem.get("commit_limit_kb") or -1),
    }


def wait_agree(mark: str, expected: int | None = None, timeout: float = 6.0) -> dict[str, Any]:
    deadline = time.time() + timeout
    last: dict[str, Any] = {}
    while time.time() < deadline:
        last = sample(mark)
        agree = last["procfs_n"] == last["ps_n"]
        match = expected is None or last["procfs_n"] == expected
        if agree and match:
            return last
        time.sleep(0.05)
    raise RuntimeError(
        f"monitor mismatch mark={mark!r} expected={expected} "
        f"procfs_n={last.get('procfs_n')} ps_n={last.get('ps_n')} pids={last.get('procfs_pids')}"
    )


def live_pressure(
    mark: str, ceiling: int, synthetic_commit_ratio: float | None = None
) -> pg.Pressure:
    snap = sample(mark)
    return pg.Pressure(
        committed_as_kb=int(snap["committed_as_kb"]),
        commit_limit_kb=int(snap["commit_limit_kb"]),
        process_count=int(snap["procfs_n"]),
        process_ceiling=ceiling,
        synthetic_commit_ratio=synthetic_commit_ratio,
    )


class BoundedPool:
    """Admit via ResourceGuard, then talk to ActivationPool. Counts spawn attempts."""

    def __init__(
        self,
        pool: act.ActivationPool,
        guard: pg.ResourceGuard,
        servers: Sequence[str] | None = None,
    ) -> None:
        self.pool = pool
        self.guard = guard
        self.servers = list(servers or SERVERS)
        self.live_server_ids: set[str] = set()
        self.spawn_attempts = 0
        self.refusals: list[dict[str, Any]] = []
        self.admits = 0
        self.peak_procfs = 0
        self.peak_ps = 0
        self.peak_commit_proxy = 0
        self.samples: list[dict[str, Any]] = []

    def _project(self) -> int:
        return pg.projected_children(
            self.pool.mode.value, self.live_server_ids, self.servers
        )

    def open_and_use(self, session_id: str, pressure: pg.Pressure | None = None) -> pg.Admit:
        projected = self._project()
        pr = pressure or live_pressure(self.pool.mark, self.guard.process_ceiling)
        admit = self.guard.admit_new_work(pr, projected)
        if not admit.ok:
            self.refusals.append(
                {
                    "session_id": session_id,
                    "reason": admit.reason,
                    "would_spawn": admit.would_spawn,
                    "projected": projected,
                    "process_count": admit.process_count,
                }
            )
            return admit
        self.spawn_attempts += 1
        handle = self.pool.open_session(session_id)
        for sid in self.servers:
            handle.call(sid, {"op": "ping", "session": session_id, "server": sid})
            self.live_server_ids.add(sid)
        self.admits += 1
        snap = sample(self.pool.mark)
        self.peak_procfs = max(self.peak_procfs, int(snap["procfs_n"]))
        self.peak_ps = max(self.peak_ps, int(snap["ps_n"]))
        self.peak_commit_proxy = max(
            self.peak_commit_proxy, int(snap["commit_proxy_bytes"])
        )
        self.samples.append(snap)
        return admit
