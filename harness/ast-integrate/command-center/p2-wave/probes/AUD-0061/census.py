#!/usr/bin/env python3
"""AUD-0061 live MCP process census: parent-session groups + working set.

The process table is the source of truth. Config intent is a claim.

Self-match control (catalog tests_required): the reported set excludes this
probe's pid, any argv that names this unit, and any process whose /proc
starttime equals this probe's starttime.

Use-vs-mention: a python/bash -c payload that merely contains the substring
mcp-server is not an MCP server process.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

PROC = Path("/proc")
def _page_size() -> int:
    sysconf = getattr(os, "sysconf", None)
    if callable(sysconf):
        try:
            return int(sysconf("SC_PAGESIZE") or 4096)
        except (OSError, ValueError, TypeError):
            return 4096
    return 4096


PAGE_SIZE = _page_size()

CATALOG_CLAIM_SESSIONS = 23
CATALOG_CLAIM_SERVERS = 65
CATALOG_CLAIM_PROCESSES = 2037
CATALOG_ARITHMETIC_PRODUCT = CATALOG_CLAIM_SESSIONS * CATALOG_CLAIM_SERVERS  # 1495

MCP_TOKEN_MARKERS: tuple[str, ...] = (
    "mcp-server",
    "mcp_server",
    "mcp-stdio",
    "@modelcontextprotocol",
    "modelcontextprotocol",
)
SELF_MARKERS: tuple[str, ...] = (
    "probes/AUD-0061",
    "probes/aud-0061",
    "AUD-0061",
    "_measure_one_delivered",
    "mcp_process_guard",
)
AGENT_COMM: frozenset[str] = frozenset({"claude", "codex", "cursor", "cursor-agent"})
AGENT_ARGV_MARKERS: tuple[str, ...] = (
    "cursor-agent",
    "claude-code",
    "codex --",
    "agent --print",
    "agent -p ",
)
SECRET_RE = re.compile(r"(key|token|secret|password|authorization|api[_-]?key)", re.I)
DASH_C = frozenset({"-c", "-lc", "-cc"})
INTERPRETERS = frozenset({"python", "python3", "bash", "sh", "dash", "zsh"})


@dataclass(frozen=True)
class ProcObs:
    pid: int
    ppid: int
    sid: int
    comm: str
    argv: tuple[str, ...]
    starttime: int
    rss_bytes: int
    server_id: str | None = None

    @property
    def blob(self) -> str:
        return " ".join(self.argv) + " " + self.comm


def catalog_claim() -> dict:
    return {
        "sessions": CATALOG_CLAIM_SESSIONS,
        "servers": CATALOG_CLAIM_SERVERS,
        "claimed_processes": CATALOG_CLAIM_PROCESSES,
        "arithmetic_product": CATALOG_ARITHMETIC_PRODUCT,
        "arithmetic_consistent": CATALOG_ARITHMETIC_PRODUCT == CATALOG_CLAIM_PROCESSES,
        "note": (
            "Catalog input records 23 sessions x 65 servers = 2037 processes. "
            "23*65=1495, not 2037. The process table is source of truth; the "
            "catalog product is recorded as inconsistent, not repeated as fact."
        ),
    }


def parse_stat(text: str) -> tuple[int, str, int, int, int]:
    """pid, comm, ppid, session, starttime from /proc/<pid>/stat."""
    left = text.find("(")
    right = text.rfind(")")
    if left < 0 or right < 0 or right <= left:
        raise ValueError("malformed /proc/stat")
    pid = int(text[:left].strip())
    comm = text[left + 1 : right]
    rest = text[right + 2 :].split()
    ppid = int(rest[1])
    sid = int(rest[3])
    starttime = int(rest[19])
    return pid, comm, ppid, sid, starttime


def rss_bytes_from_statm(text: str, page_size: int = PAGE_SIZE) -> int:
    parts = text.split()
    if len(parts) < 2:
        return 0
    return int(parts[1]) * page_size


def self_starttime(proc_root: Path | None = None) -> int:
    root = proc_root or PROC
    text = (root / "self" / "stat").read_text(encoding="utf-8", errors="replace")
    return parse_stat(text)[4]


def looks_self(argv: Sequence[str], comm: str, *, pid: int, probe_pid: int) -> bool:
    if pid == probe_pid:
        return True
    blob = (" ".join(argv) + " " + comm).replace("\\", "/")
    return any(m in blob for m in SELF_MARKERS)


def _token_is_mcp_server(tok: str) -> bool:
    t = tok.replace("\\", "/").lower()
    base = Path(t).name.lower()
    if any(m in t for m in ("@modelcontextprotocol", "modelcontextprotocol")):
        return True
    if base.startswith("mcp-server") or base.startswith("mcp_server"):
        return True
    if "mcp-stdio" in t:
        return True
    if "/mcp-server" in t or "/mcp_server" in t:
        return True
    return False


def looks_like_mcp(argv: Sequence[str], comm: str) -> bool:
    """True only when a dedicated server token is present, not a -c mention."""
    comm_l = comm.lower()
    argv_l = [a.lower() for a in argv]
    if comm_l in INTERPRETERS and any(a in DASH_C for a in argv_l):
        for tok in argv:
            if tok.lower() in DASH_C:
                continue
            if tok.startswith("-"):
                continue
            if _token_is_mcp_server(tok):
                return True
        return False
    if comm_l.startswith("mcp-server") or comm_l.startswith("mcp_server"):
        return True
    return any(_token_is_mcp_server(tok) for tok in argv)


def naive_blob_is_mcp(argv: Sequence[str], comm: str) -> bool:
    """Strawman: substring match on the whole cmdline, including -c payloads."""
    blob = (" ".join(argv) + " " + comm).lower()
    return any(m in blob for m in MCP_TOKEN_MARKERS)


def looks_like_session_leader(argv: Sequence[str], comm: str) -> bool:
    if comm.lower() in AGENT_COMM:
        return True
    blob = (" ".join(argv) + " " + comm).lower()
    return any(m in blob for m in AGENT_ARGV_MARKERS)


def infer_server_id(argv: Sequence[str], comm: str) -> str | None:
    if not looks_like_mcp(argv, comm):
        return None
    for tok in argv:
        base = Path(tok).name
        if base.startswith("mcp-server-"):
            return base[len("mcp-server-") :]
        if base.startswith("mcp_server"):
            return base
    if comm.startswith("mcp"):
        return comm
    for tok in reversed(argv):
        if tok.startswith("-"):
            continue
        name = Path(tok).stem
        if name and name not in {"node", "python", "python3", "npx", "uvx", "uv"}:
            return name
    return comm or "mcp-unknown"


def redact_argv(argv: Sequence[str]) -> tuple[str, ...]:
    out: list[str] = []
    for tok in argv:
        if SECRET_RE.search(tok):
            out.append("<redacted>")
        elif len(tok) > 180:
            out.append(tok[:80] + "...")
        else:
            out.append(tok)
    return tuple(out)


def snapshot_proc(
    proc_root: Path | None = None,
    *,
    probe_pid: int | None = None,
    probe_starttime: int | None = None,
    exclude_pids: Iterable[int] | None = None,
) -> tuple[ProcObs, ...]:
    root = proc_root or PROC
    self_pid = probe_pid if probe_pid is not None else os.getpid()
    exclude = {self_pid, os.getppid()}
    if exclude_pids:
        exclude.update(int(p) for p in exclude_pids)
    t0 = probe_starttime
    if t0 is None:
        try:
            t0 = self_starttime(root)
        except (OSError, ValueError, IndexError):
            t0 = -1
    rows: list[ProcObs] = []
    try:
        entries = list(root.iterdir())
    except FileNotFoundError:
        return tuple()
    for entry in entries:
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        if pid in exclude:
            continue
        try:
            raw_cmd = (entry / "cmdline").read_bytes()
            stat_text = (entry / "stat").read_text(encoding="utf-8", errors="replace")
            statm_text = (entry / "statm").read_text(encoding="utf-8", errors="replace")
        except (FileNotFoundError, PermissionError, ProcessLookupError, OSError):
            continue
        argv = tuple(x.decode("utf-8", "replace") for x in raw_cmd.split(b"\0") if x)
        try:
            _pid, comm, ppid, sid, starttime = parse_stat(stat_text)
        except (ValueError, IndexError):
            continue
        if starttime == t0:
            continue
        if looks_self(argv, comm, pid=_pid, probe_pid=self_pid):
            continue
        rss = rss_bytes_from_statm(statm_text)
        server_id = infer_server_id(argv, comm)
        rows.append(
            ProcObs(
                pid=_pid,
                ppid=ppid,
                sid=sid,
                comm=comm,
                argv=redact_argv(argv),
                starttime=starttime,
                rss_bytes=rss,
                server_id=server_id,
            )
        )
    return tuple(sorted(rows, key=lambda r: r.pid))


def group_by_parent_session(rows: Sequence[ProcObs]) -> list[dict]:
    by_pid = {r.pid: r for r in rows}
    mcp_rows = [r for r in rows if r.server_id]
    groups: dict[str, dict] = {}
    for r in mcp_rows:
        leader = None
        cur = r
        seen: set[int] = set()
        while cur is not None and cur.pid not in seen:
            seen.add(cur.pid)
            if looks_like_session_leader(cur.argv, cur.comm):
                leader = cur
                break
            cur = by_pid.get(cur.ppid)
        if leader is not None:
            key = f"leader:{leader.pid}"
            label = leader.comm
            leader_pid = leader.pid
        else:
            parent = by_pid.get(r.ppid)
            key = f"ppid:{r.ppid}:sid:{r.sid}"
            label = parent.comm if parent is not None else f"ppid:{r.ppid}"
            leader_pid = r.ppid
        g = groups.setdefault(
            key,
            {
                "session_key": key,
                "leader_pid": leader_pid,
                "leader_comm": label,
                "mcp_count": 0,
                "rss_bytes_mcp": 0,
                "children": [],
            },
        )
        child = {
            "pid": r.pid,
            "ppid": r.ppid,
            "sid": r.sid,
            "comm": r.comm,
            "server_id": r.server_id,
            "rss_bytes": r.rss_bytes,
            "argv": list(r.argv[:8]),
        }
        g["children"].append(child)
        g["mcp_count"] += 1
        g["rss_bytes_mcp"] += r.rss_bytes
    return [groups[k] for k in sorted(groups)]


def session_count(rows: Sequence[ProcObs]) -> int:
    ids: set[str] = set()
    for r in rows:
        if looks_like_session_leader(r.argv, r.comm):
            ids.add(f"leader:{r.pid}")
        elif r.server_id:
            ids.add(f"sid:{r.sid}")
    return len(ids)


def census_dict(
    rows: Sequence[ProcObs],
    *,
    source: str,
    probe_pid: int,
    probe_starttime: int,
    excluded_self_pids: Sequence[int],
) -> dict:
    mcp = [r for r in rows if r.server_id]
    groups = group_by_parent_session(rows)
    n_sess = session_count(rows)
    rss_total = sum(r.rss_bytes for r in mcp)
    per_session = len(mcp) / n_sess if n_sess else None
    return {
        "source": source,
        "probe_pid": probe_pid,
        "probe_starttime": probe_starttime,
        "excluded_self_pids": list(excluded_self_pids),
        "mcp_count": len(mcp),
        "session_count": n_sess,
        "multiplier": per_session,
        "multiplier_undefined_reason": (
            None
            if n_sess
            else "session_count=0; processes/sessions is undefined, not zero"
        ),
        "rss_bytes_mcp_total": rss_total,
        "by_parent_session": groups,
        "self_pid_in_reported_set": any(r.pid == probe_pid for r in mcp),
        "same_starttime_in_reported_set": any(
            r.starttime == probe_starttime for r in rows
        ),
    }


def live_census(proc_root: Path | None = None) -> dict:
    root = proc_root or PROC
    probe_pid = os.getpid()
    try:
        t0 = self_starttime(root)
    except (OSError, ValueError, IndexError):
        t0 = -1
    rows = snapshot_proc(root, probe_pid=probe_pid, probe_starttime=t0)
    return census_dict(
        rows,
        source=str(root),
        probe_pid=probe_pid,
        probe_starttime=t0,
        excluded_self_pids=(probe_pid, os.getppid()),
    )


def synthetic_stdio_rows(
    n_sessions: int,
    servers: Sequence[str],
    *,
    pid0: int = 1000,
    start0: int = 10_000,
    rss: int = 12 * 1024 * 1024,
) -> list[ProcObs]:
    rows: list[ProcObs] = []
    pid = pid0
    st = start0
    for s in range(n_sessions):
        leader = pid
        sid = pid
        rows.append(
            ProcObs(
                pid=pid,
                ppid=1,
                sid=sid,
                comm="cursor-agent",
                argv=("cursor-agent", "--print", f"--session=sess-{s:02d}"),
                starttime=st,
                rss_bytes=40 * 1024 * 1024,
            )
        )
        pid += 1
        st += 10
        for name in servers:
            rows.append(
                ProcObs(
                    pid=pid,
                    ppid=leader,
                    sid=sid,
                    comm=f"mcp-server-{name}",
                    argv=("npx", "-y", f"mcp-server-{name}"),
                    starttime=st,
                    rss_bytes=rss,
                    server_id=name,
                )
            )
            pid += 1
            st += 10
    return rows


def apply_live_exclusions(
    rows: Sequence[ProcObs],
    *,
    probe_pid: int,
    probe_starttime: int,
) -> list[ProcObs]:
    kept: list[ProcObs] = []
    for r in rows:
        if r.pid == probe_pid:
            continue
        if r.starttime == probe_starttime:
            continue
        if looks_self(r.argv, r.comm, pid=r.pid, probe_pid=probe_pid):
            continue
        kept.append(r)
    return kept


def self_match_control(probe_starttime: int = 4242, probe_pid: int = 77) -> dict:
    """Both-states: same-starttime probe row must drop; real mcp-server must stay.

    Also proves a python -c mention of mcp-server is not a server (use-vs-mention).
    """
    probe_row = ProcObs(
        pid=probe_pid,
        ppid=1,
        sid=1,
        comm="python3",
        argv=(
            "python3",
            "-c",
            "markers=('mcp-server',); open('probes/AUD-0061/probe1.py')",
        ),
        starttime=probe_starttime,
        rss_bytes=8 * 1024 * 1024,
    )
    same_tick_server = ProcObs(
        pid=9001,
        ppid=1,
        sid=1,
        comm="mcp-server-files",
        argv=("npx", "-y", "mcp-server-files"),
        starttime=probe_starttime,
        rss_bytes=12 * 1024 * 1024,
        server_id="files",
    )
    real_server = ProcObs(
        pid=9002,
        ppid=80,
        sid=80,
        comm="mcp-server-git",
        argv=("npx", "-y", "mcp-server-git"),
        starttime=probe_starttime + 50,
        rss_bytes=12 * 1024 * 1024,
        server_id="git",
    )
    mention = ProcObs(
        pid=9003,
        ppid=1,
        sid=1,
        comm="python3",
        argv=(
            "python3",
            "-c",
            "markers=('mcp-server','mcp_server'); print(markers)",
        ),
        starttime=probe_starttime + 80,
        rss_bytes=4 * 1024 * 1024,
    )
    planted = [probe_row, same_tick_server, real_server, mention]

    naive_hits = [r.pid for r in planted if naive_blob_is_mcp(r.argv, r.comm)]
    token_hits = [r.pid for r in planted if looks_like_mcp(r.argv, r.comm)]
    filtered = apply_live_exclusions(
        planted, probe_pid=probe_pid, probe_starttime=probe_starttime
    )
    filtered_mcp = [r for r in filtered if looks_like_mcp(r.argv, r.comm)]
    filtered_pids = [r.pid for r in filtered_mcp]

    mention_naive = mention.pid in naive_hits
    mention_token = mention.pid in token_hits
    probe_naive = probe_pid in naive_hits
    probe_token = probe_pid in token_hits
    good_keeps_only_real = filtered_pids == [real_server.pid]
    fired_bad = mention_naive and probe_naive
    silent_good = good_keeps_only_real and not mention_token and not probe_token

    return {
        "fired_on_bad_state": fired_bad,
        "silent_on_good_state": silent_good,
        "naive_blob_pids": naive_hits,
        "token_pids": token_hits,
        "filtered_mcp_pids": filtered_pids,
        "probe_pid_excluded": probe_pid not in filtered_pids,
        "same_starttime_server_excluded": same_tick_server.pid not in filtered_pids,
        "real_server_kept": real_server.pid in filtered_pids,
        "mention_counted_by_naive": mention_naive,
        "mention_counted_by_token": mention_token,
        "probe_counted_by_naive": probe_naive,
        "probe_counted_by_token": probe_token,
        "pass": fired_bad and silent_good,
    }


def artifact_named_probes(doc: dict) -> list:
    """named_probes live in report/extensions: receipt_core forbids extra keys."""
    if not isinstance(doc, dict):
        return []
    for src in (
        doc.get("named_probes"),
        (doc.get("extensions") or {}).get("named_probes")
        if isinstance(doc.get("extensions"), dict)
        else None,
        (doc.get("report") or {}).get("named_probes")
        if isinstance(doc.get("report"), dict)
        else None,
    ):
        if isinstance(src, list) and src:
            return src
    return []


def stdio_multiplication_model(n_sessions: int, n_servers: int, rss_each: int) -> dict:
    product = n_sessions * n_servers
    return {
        "sessions": n_sessions,
        "servers": n_servers,
        "stdio_process_count": product,
        "shared_http_process_count": n_servers,
        "extra_processes_vs_shared": product - n_servers if n_sessions else 0,
        "rss_bytes_stdio": product * rss_each,
        "rss_bytes_shared": n_servers * rss_each,
        "kind": "model-from-counts-not-a-live-incident",
    }
