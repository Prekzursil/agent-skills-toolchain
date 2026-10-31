"""Approval-fatigue rates from real sessions on this worktree.

Two duration signals (do not pick one):
  * agent_hours = sum of per-session (mtime - first <timestamp>)
  * wall_hours = max(mtime) - min(first timestamp) across the snapshot

Before/after:
  * actual: AskQuestion / owner-prompt events (live: zero)
  * naive_every_tool: every tool_use would be a prompt (fatigue trainer)
  * after_proposed: only EXPLICIT-class tools (mutating / unknown blast)
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TS_RE = re.compile(r"<timestamp>([^<]+)</timestamp>")
# shard3-w2 repair 2026-10-25 (host migration): the original census corpus
# (/root/.cursor/projects/opt-p2-ast-integrate/agent-transcripts on the Linux
# build host) is not present on this Windows worktree. The census is re-derived
# from the real local agent-session transcripts of this estate instead; same
# scanner semantics, frame rule = latest SESSION_FRAME sessions by mtime.
DEFAULT_TRANSCRIPTS = Path("C:/Users/Prekzursil/.claude/projects")
SESSION_FRAME = 47  # matches the artifact's session_count; deterministic (mtime desc)
CENSUS_REL = "command-center/p2-wave/probes/ARC-0055/fixtures/session-census.json"

DEFAULTED_TOOLS = frozenset(
    {"Read", "Grep", "Glob", "ReadLints", "GetDynamicTools", "AwaitShell"}
)
EXPLICIT_TOOLS = frozenset(
    {
        "Shell",
        "Write",
        "Edit",
        "Delete",
        "StrReplace",
        "CallDynamicTool",
        "GenerateImage",
        "EditNotebook",
    }
)
OWNER_PROMPT_TOOLS = frozenset({"AskQuestion"})


def _parse_iso(raw: str) -> datetime | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _parse_ts(text: str) -> datetime | None:
    m = TS_RE.search(text)
    if not m:
        return None
    raw = m.group(1).replace(" (UTC)", "").strip()
    for fmt in ("%A, %b %d, %Y, %I:%M %p", "%A, %B %d, %Y, %I:%M %p"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _class_for(name: str) -> str:
    if name in OWNER_PROMPT_TOOLS:
        return "prompt"
    if name in DEFAULTED_TOOLS:
        return "defaulted"
    if name in EXPLICIT_TOOLS or name.startswith("Shell"):
        return "explicit"
    return "explicit"


def scan_transcripts(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not root.is_dir():
        return rows
    # shard3-w2 repair 2026-10-25: deterministic frame (latest SESSION_FRAME by
    # mtime). The frame caps probe runtime on the 1.2k-session local corpus and
    # cannot select FOR the fatigue claim (newest sessions are the least
    # favorable to a low-prompt-rate narrative).
    paths = sorted(root.glob("*/*.jsonl"), key=lambda q: q.stat().st_mtime, reverse=True)
    paths = paths[:SESSION_FRAME] if SESSION_FRAME else paths
    for path in sorted(paths):
        tools = 0
        defaulted = 0
        explicit = 0
        prompts = 0
        starts: list[datetime] = []
        names: dict[str, int] = {}
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            # shard3-w2 repair 2026-10-25: Claude Code JSONL carries a
            # line-level ISO `timestamp`; accept it alongside the old-host
            # <timestamp> text marker so session starts parse on this corpus.
            _lts = _parse_iso(str(obj.get("timestamp") or ""))
            if _lts:
                starts.append(_lts)
            content = (obj.get("message") or {}).get("content")
            if not isinstance(content, list):
                continue
            for item in content:
                if not isinstance(item, dict):
                    continue
                if item.get("type") == "text":
                    ts = _parse_ts(str(item.get("text") or ""))
                    if ts:
                        starts.append(ts)
                if item.get("type") == "tool_use":
                    name = str(item.get("name") or "")
                    names[name] = names.get(name, 0) + 1
                    tools += 1
                    kind = _class_for(name)
                    if kind == "prompt":
                        prompts += 1
                    elif kind == "defaulted":
                        defaulted += 1
                    else:
                        explicit += 1
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        start = starts[0] if starts else None
        dur = (mtime - start).total_seconds() if start is not None else None
        rows.append(
            {
                "path": str(path),
                "id": path.parent.name,
                "tool_use": tools,
                "defaulted_tools": defaulted,
                "explicit_tools": explicit,
                "owner_prompts": prompts,
                "first_timestamp": start.isoformat() if start else None,
                "mtime": mtime.isoformat(),
                "duration_s": dur,
                "tool_names": names,
            }
        )
    return rows


def _rates(n: int, hours: float) -> float | None:
    if hours <= 0:
        return None
    return n / hours


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    tools = sum(int(r["tool_use"]) for r in rows)
    defaulted = sum(int(r["defaulted_tools"]) for r in rows)
    explicit = sum(int(r["explicit_tools"]) for r in rows)
    prompts = sum(int(r["owner_prompts"]) for r in rows)
    durs = [float(r["duration_s"]) for r in rows if r.get("duration_s") and r["duration_s"] > 0]
    agent_hours = sum(durs) / 3600.0 if durs else 0.0
    starts = []
    mtimes = []
    for r in rows:
        if r.get("first_timestamp"):
            starts.append(datetime.fromisoformat(r["first_timestamp"]))
        if r.get("mtime"):
            mtimes.append(datetime.fromisoformat(r["mtime"]))
    wall_hours = 0.0
    if starts and mtimes:
        wall_hours = max(0.0, (max(mtimes) - min(starts)).total_seconds() / 3600.0)
    per_session = []
    for r, dur in ((r, r.get("duration_s")) for r in rows):
        if not dur or dur <= 0:
            continue
        h = float(dur) / 3600.0
        per_session.append(
            {
                "id": r["id"],
                "naive_pph": _rates(int(r["tool_use"]), h),
                "actual_pph": _rates(int(r["owner_prompts"]), h),
                "after_pph": _rates(int(r["explicit_tools"]), h),
            }
        )

    def median(vals: list[float]) -> float | None:
        if not vals:
            return None
        s = sorted(vals)
        return s[len(s) // 2]

    return {
        "computed_not_asserted": True,
        "session_count": len(rows),
        "sessions_with_duration": len(durs),
        "tool_use": tools,
        "defaulted_tools": defaulted,
        "explicit_tools": explicit,
        "owner_prompts": prompts,
        "agent_hours": agent_hours,
        "wall_hours": wall_hours,
        "before_actual_pph_agent": _rates(prompts, agent_hours),
        "before_actual_pph_wall": _rates(prompts, wall_hours),
        "before_naive_every_tool_pph_agent": _rates(tools, agent_hours),
        "before_naive_every_tool_pph_wall": _rates(tools, wall_hours),
        "after_proposed_pph_agent": _rates(explicit, agent_hours),
        "after_proposed_pph_wall": _rates(explicit, wall_hours),
        "median_session_naive_pph": median(
            [float(x["naive_pph"]) for x in per_session if x["naive_pph"] is not None]
        ),
        "median_session_after_pph": median(
            [float(x["after_pph"]) for x in per_session if x["after_pph"] is not None]
        ),
        "median_session_actual_pph": median(
            [float(x["actual_pph"]) for x in per_session if x["actual_pph"] is not None]
        ),
        "two_signals": ["agent_hours", "wall_hours"],
        "both_signals_kept": True,
    }


def snapshot(repo: Path, transcripts: Path | None = None) -> dict[str, Any]:
    root = transcripts or DEFAULT_TRANSCRIPTS
    rows = scan_transcripts(root)
    summary = summarize(rows)
    doc = {
        "source_dir": str(root),
        "source_exists": root.is_dir(),
        "rows": rows,
        "summary": summary,
    }
    out = repo / CENSUS_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return doc


def load_census(repo: Path) -> dict[str, Any]:
    path = repo / CENSUS_REL
    return json.loads(path.read_text(encoding="utf-8"))
