#!/usr/bin/env python3
"""Session discovery: Claude + Codex on-disk state, process table, reconciliation.

Two signals, never one:
  * vendor state directories (Claude projects transcripts, Codex thread/session files)
  * process table (Linux /proc or a Win32-style snapshot)

A process whose command line matches the search needle is not automatically a
session. The probe itself is excluded by pid, by probe-token in argv, and by
the CreationDate-equals-probe-runtime tell.
"""
from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"
CREATION_DATE_WINDOW = timedelta(seconds=5)
PROBE_TOKENS = (
    "IMP-0407",
    "probe1_self_match",
    "probe2_known_present",
    "emit_registry",
    "session_discovery",
)
DEFAULT_NEEDLES = ("claude", "codex")
VENDOR_BIN = re.compile(
    r"(?:^|[\\/\s])(claude|codex)(?:\.exe)?(?:\s|$)",
    re.IGNORECASE,
)
UUID_STEM = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def to_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime(ISO_FMT)


def parse_time(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        m = re.match(
            r"^(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(?:\.\d+)?([+-]\d{3,4})?$",
            text,
        )
        if not m:
            return None
        g = m.groups()
        dt = datetime(
            int(g[0]), int(g[1]), int(g[2]), int(g[3]), int(g[4]), int(g[5]),
            tzinfo=timezone.utc,
        )
        return dt
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass
class ProbeContext:
    pid: int
    ppid: int
    started_at: datetime
    argv: str

    @classmethod
    def capture(cls, started_at: datetime | None = None) -> "ProbeContext":
        return cls(
            pid=os.getpid(),
            ppid=os.getppid(),
            started_at=started_at or utcnow(),
            argv=" ".join(str(x) for x in sys.argv),
        )


@dataclass
class ProcessRow:
    pid: int
    cmdline: str
    cwd: str
    start_time: str
    vendor: str | None = None


@dataclass
class Exclusion:
    pid: int
    cmdline: str
    start_time: str
    reasons: list[str]


@dataclass
class Session:
    vendor: str
    session_id: str
    cwd: str
    start_time: str
    on_disk: bool = True
    in_process_table: bool = False
    pid: int | None = None
    transcript_path: str | None = None
    artifact_dir: str | None = None
    source: str = "on-disk"


def encode_claude_project(cwd: str) -> str:
    p = cwd.replace("\\", "/")
    if not p.startswith("/"):
        p = "/" + p
    return p.replace("/", "-")


def decode_claude_project(name: str) -> str:
    if name.startswith("-"):
        return "/" + name[1:].replace("-", "/")
    return name.replace("-", "/")


def _first_json_records(path: Path, limit: int = 40) -> list[dict]:
    out: list[dict] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    if path.suffix.lower() == ".json":
        try:
            doc = json.loads(text)
        except json.JSONDecodeError:
            return out
        return [doc] if isinstance(doc, dict) else out
    for line in text.splitlines()[:limit]:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out


def _pick(rec: dict, *keys: str) -> Any:
    for key in keys:
        if key in rec and rec[key] not in (None, ""):
            return rec[key]
        payload = rec.get("payload")
        if isinstance(payload, dict) and payload.get(key) not in (None, ""):
            return payload[key]
    return None


def _mtime_iso(path: Path) -> str:
    try:
        return to_iso(datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc))
    except OSError:
        return to_iso(utcnow())


def enumerate_claude(root: Path) -> list[Session]:
    sessions: dict[str, Session] = {}
    projects = root / "projects"
    if not projects.is_dir():
        return []
    for proj in sorted(projects.iterdir()):
        if not proj.is_dir():
            continue
        decoded = decode_claude_project(proj.name)
        for path in sorted(proj.glob("*.jsonl")):
            if path.name.startswith("agent-") or "subagents" in path.parts:
                continue
            recs = _first_json_records(path)
            sid = path.stem
            cwd = decoded
            start = None
            for rec in recs:
                sid = str(_pick(rec, "sessionId", "session_id", "id") or sid)
                cwd = str(_pick(rec, "cwd", "cwdPath", "workingDirectory") or cwd)
                ts = parse_time(_pick(rec, "timestamp", "createdAt", "created_at"))
                if ts is not None and start is None:
                    start = ts
            if not UUID_STEM.match(sid) and not sid:
                continue
            start_iso = to_iso(start) if start else _mtime_iso(path)
            sessions[sid] = Session(
                vendor="claude",
                session_id=sid,
                cwd=cwd,
                start_time=start_iso,
                on_disk=True,
                transcript_path=str(path),
                artifact_dir=str(path.parent),
                source="on-disk",
            )
    return list(sessions.values())


def _codex_session_from_records(path: Path, recs: list[dict]) -> Session | None:
    sid = path.stem
    cwd = ""
    start = None
    for rec in recs:
        sid = str(
            _pick(rec, "id", "session_id", "sessionId", "thread_id", "threadId")
            or sid
        )
        cwd = str(_pick(rec, "cwd", "cwd_path", "cwdPath", "working_directory") or cwd)
        ts = parse_time(
            _pick(rec, "created_at", "createdAt", "timestamp", "started_at")
        )
        if ts is not None and start is None:
            start = ts
        payload = rec.get("payload")
        if isinstance(payload, dict):
            sid = str(payload.get("id") or payload.get("session_id") or sid)
            cwd = str(payload.get("cwd") or payload.get("cwd_path") or cwd)
            ts = parse_time(payload.get("timestamp") or payload.get("created_at"))
            if ts is not None and start is None:
                start = ts
    if path.name.startswith("rollout-") and sid == path.stem:
        parts = path.stem.split("-")
        if len(parts) >= 5:
            maybe = parts[-1]
            if UUID_STEM.match(maybe) or len(maybe) >= 8:
                sid = maybe
    if not sid:
        return None
    if not cwd:
        cwd = str(path.parent)
    start_iso = to_iso(start) if start else _mtime_iso(path)
    return Session(
        vendor="codex",
        session_id=sid,
        cwd=cwd,
        start_time=start_iso,
        on_disk=True,
        transcript_path=str(path),
        artifact_dir=str(path.parent),
        source="on-disk",
    )


def enumerate_codex(root: Path) -> list[Session]:
    sessions: dict[str, Session] = {}
    if not root.is_dir():
        return []
    paths: list[Path] = []
    threads = root / "threads"
    if threads.is_dir():
        paths.extend(sorted(threads.glob("*.json")))
    sess_root = root / "sessions"
    if sess_root.is_dir():
        paths.extend(sorted(sess_root.rglob("*.jsonl")))
        paths.extend(sorted(sess_root.rglob("*.json")))
    for path in paths:
        recs = _first_json_records(path)
        row = _codex_session_from_records(path, recs)
        if row is None:
            continue
        prev = sessions.get(row.session_id)
        if prev is None:
            sessions[row.session_id] = row
            continue
        if prev.transcript_path and row.transcript_path:
            if row.transcript_path.endswith(".jsonl") and not prev.transcript_path.endswith(
                ".jsonl"
            ):
                sessions[row.session_id] = row
    return list(sessions.values())


def vendor_from_cmdline(cmdline: str) -> str | None:
    m = VENDOR_BIN.search(cmdline or "")
    if m:
        return m.group(1).lower()
    low = (cmdline or "").lower()
    if re.search(r"--(?:pattern|search|needle)\s+claude\b", low):
        return "claude"
    if re.search(r"--(?:pattern|search|needle)\s+codex\b", low):
        return "codex"
    return None


def matches_needle(cmdline: str, needles: Iterable[str]) -> bool:
    low = (cmdline or "").lower()
    return any(n.lower() in low for n in needles if n)


def self_match_reasons(
    proc: ProcessRow,
    probe: ProbeContext,
    needles: Iterable[str],
) -> list[str]:
    reasons: list[str] = []
    if proc.pid == probe.pid:
        reasons.append("pid-equals-probe")
    if proc.pid == probe.ppid:
        reasons.append("pid-equals-probe-parent")
    cmd = proc.cmdline or ""
    for tok in PROBE_TOKENS:
        if tok in cmd:
            reasons.append(f"cmdline-contains:{tok}")
            break
    start = parse_time(proc.start_time)
    if start is not None and matches_needle(cmd, needles):
        delta = abs((start - probe.started_at).total_seconds())
        if delta <= CREATION_DATE_WINDOW.total_seconds():
            reasons.append("creation-date-equals-probe-runtime")
    return reasons


def normalize_process(raw: dict) -> ProcessRow | None:
    pid = raw.get("pid") if "pid" in raw else raw.get("ProcessId")
    if pid is None:
        return None
    cmdline = str(
        raw.get("cmdline")
        or raw.get("CommandLine")
        or raw.get("command_line")
        or ""
    )
    cwd = str(raw.get("cwd") or raw.get("ExecutablePath") or "")
    start = raw.get("start_time") or raw.get("CreationDate") or raw.get("creation_date")
    start_dt = parse_time(start) or utcnow()
    vendor = raw.get("vendor") or vendor_from_cmdline(cmdline)
    if vendor not in ("claude", "codex"):
        vendor = vendor_from_cmdline(cmdline)
    return ProcessRow(
        pid=int(pid),
        cmdline=cmdline,
        cwd=cwd,
        start_time=to_iso(start_dt),
        vendor=vendor if vendor in ("claude", "codex") else None,
    )


def _proc_start_iso(pid: int) -> str | None:
    try:
        clk = os.sysconf("SC_CLK_TCK")
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8", errors="replace")
        rparen = stat.rfind(")")
        fields = stat[rparen + 1 :].split()
        start_ticks = int(fields[19])
        uptime = float(Path("/proc/uptime").read_text(encoding="utf-8").split()[0])
        boot = utcnow().timestamp() - uptime
        return to_iso(datetime.fromtimestamp(boot + start_ticks / clk, tz=timezone.utc))
    except (OSError, ValueError, IndexError):
        return None


def read_live_processes(needles: Iterable[str]) -> list[ProcessRow]:
    proc = Path("/proc")
    if not proc.is_dir():
        return []
    rows: list[ProcessRow] = []
    needle_list = list(needles)
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        try:
            raw = (entry / "cmdline").read_bytes()
        except OSError:
            continue
        cmd = raw.replace(b"\x00", b" ").decode("utf-8", "replace").strip()
        if not cmd or not matches_needle(cmd, needle_list):
            continue
        cwd = ""
        try:
            cwd = os.readlink(entry / "cwd")
        except OSError:
            cwd = ""
        start = _proc_start_iso(pid) or to_iso(utcnow())
        rows.append(
            ProcessRow(
                pid=pid,
                cmdline=cmd,
                cwd=cwd,
                start_time=start,
                vendor=vendor_from_cmdline(cmd),
            )
        )
    return rows


def enumerate_processes(
    *,
    snapshot: list[dict] | None = None,
    needles: Iterable[str] = DEFAULT_NEEDLES,
    probe: ProbeContext | None = None,
    exclude_self: bool = True,
) -> tuple[list[ProcessRow], list[Exclusion]]:
    probe = probe or ProbeContext.capture()
    needle_list = list(needles)
    if snapshot is not None:
        candidates = [p for p in (normalize_process(r) for r in snapshot) if p]
        candidates = [p for p in candidates if matches_needle(p.cmdline, needle_list)]
    else:
        candidates = read_live_processes(needle_list)
    kept: list[ProcessRow] = []
    excluded: list[Exclusion] = []
    for proc in candidates:
        reasons = self_match_reasons(proc, probe, needle_list) if exclude_self else []
        if reasons:
            excluded.append(
                Exclusion(
                    pid=proc.pid,
                    cmdline=proc.cmdline,
                    start_time=proc.start_time,
                    reasons=reasons,
                )
            )
            continue
        if proc.vendor is None:
            proc.vendor = vendor_from_cmdline(proc.cmdline)
        kept.append(proc)
    return kept, excluded


def _match_process(session: Session, proc: ProcessRow) -> bool:
    if proc.vendor and proc.vendor != session.vendor:
        return False
    if session.session_id and session.session_id in (proc.cmdline or ""):
        return True
    return False


def reconcile(
    disk_sessions: list[Session],
    processes: list[ProcessRow],
) -> dict[str, Any]:
    sessions = [Session(**asdict(s)) for s in disk_sessions]
    used_pids: set[int] = set()
    for sess in sessions:
        for proc in processes:
            if proc.pid in used_pids:
                continue
            if _match_process(sess, proc):
                sess.in_process_table = True
                sess.pid = proc.pid
                sess.source = "both"
                used_pids.add(proc.pid)
                break
        if not sess.in_process_table and sess.cwd:
            cwd_hits = [
                p
                for p in processes
                if p.pid not in used_pids
                and (p.vendor == sess.vendor or p.vendor is None)
                and p.cwd
                and os.path.normpath(p.cwd) == os.path.normpath(sess.cwd)
            ]
            if len(cwd_hits) == 1:
                proc = cwd_hits[0]
                sess.in_process_table = True
                sess.pid = proc.pid
                sess.source = "both"
                used_pids.add(proc.pid)

    disagreements: list[dict[str, Any]] = []
    for sess in sessions:
        if not sess.in_process_table:
            disagreements.append(
                {
                    "id": f"disk-without-process:{sess.vendor}:{sess.session_id}",
                    "kind": "ON_DISK_WITHOUT_PROCESS",
                    "vendor": sess.vendor,
                    "session_id": sess.session_id,
                    "named": (
                        f"on-disk {sess.vendor} session {sess.session_id} "
                        f"cwd={sess.cwd} has no matching process after self-exclusion"
                    ),
                }
            )
    orphans = [p for p in processes if p.pid not in used_pids]
    for proc in orphans:
        disagreements.append(
            {
                "id": f"process-without-disk:{proc.vendor or 'unknown'}:{proc.pid}",
                "kind": "PROCESS_WITHOUT_ON_DISK",
                "vendor": proc.vendor,
                "pid": proc.pid,
                "named": (
                    f"process pid={proc.pid} vendor={proc.vendor} "
                    f"cmdline={proc.cmdline[:120]!r} has no on-disk session"
                ),
            }
        )

    by_vendor = {
        "claude": {"on_disk": 0, "process_table": 0, "registry": 0},
        "codex": {"on_disk": 0, "process_table": 0, "registry": 0},
    }
    for sess in sessions:
        by_vendor[sess.vendor]["on_disk"] += 1
        by_vendor[sess.vendor]["registry"] += 1
    for proc in processes:
        if proc.vendor in by_vendor:
            by_vendor[proc.vendor]["process_table"] += 1
        elif "claude" in (proc.cmdline or "").lower():
            by_vendor["claude"]["process_table"] += 1
        elif "codex" in (proc.cmdline or "").lower():
            by_vendor["codex"]["process_table"] += 1

    on_disk_count = len(sessions)
    process_table_count = len(processes)
    registry_count = len(sessions)
    if registry_count != on_disk_count:
        disagreements.append(
            {
                "id": "registry-count-mismatch",
                "kind": "REGISTRY_COUNT_MISMATCH",
                "named": (
                    f"registry_count={registry_count} != on_disk_count={on_disk_count}"
                ),
            }
        )
    return {
        "sessions": sessions,
        "on_disk_count": on_disk_count,
        "process_table_count": process_table_count,
        "registry_count": registry_count,
        "by_vendor": by_vendor,
        "disagreements": disagreements,
        "orphan_processes": [asdict(p) for p in orphans],
    }


def discover(
    *,
    claude_home: Path,
    codex_home: Path,
    process_snapshot: list[dict] | None = None,
    needles: Iterable[str] = DEFAULT_NEEDLES,
    probe: ProbeContext | None = None,
    exclude_self: bool = True,
) -> dict[str, Any]:
    probe = probe or ProbeContext.capture()
    claude = enumerate_claude(Path(claude_home))
    codex = enumerate_codex(Path(codex_home))
    disk = claude + codex
    procs, excluded = enumerate_processes(
        snapshot=process_snapshot,
        needles=needles,
        probe=probe,
        exclude_self=exclude_self,
    )
    recon = reconcile(disk, procs)
    sessions_out = []
    for s in recon["sessions"]:
        row = asdict(s)
        sessions_out.append(row)
    return {
        "probe": {
            "pid": probe.pid,
            "ppid": probe.ppid,
            "started_at": to_iso(probe.started_at),
        },
        "claude_on_disk": len(claude),
        "codex_on_disk": len(codex),
        "sessions": sessions_out,
        "processes": [asdict(p) for p in procs],
        "exclusions": [asdict(e) for e in excluded],
        "reconciliation": {
            "on_disk_count": recon["on_disk_count"],
            "process_table_count": recon["process_table_count"],
            "registry_count": recon["registry_count"],
            "by_vendor": recon["by_vendor"],
            "disagreements": recon["disagreements"],
        },
        "orphan_processes": recon["orphan_processes"],
    }


def session_ids(result: dict[str, Any], vendor: str | None = None) -> set[str]:
    out = set()
    for s in result.get("sessions") or []:
        if vendor and s.get("vendor") != vendor:
            continue
        out.add(str(s.get("session_id")))
    return out
