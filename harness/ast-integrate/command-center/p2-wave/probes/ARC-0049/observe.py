"""Live observed-use signals for ARC-0049.

Signal 1 reads agent-transcript jsonl `tool_use.name` counts attributed to a
P2-deliver unit id. Signal 2 reads a different field: named-probe command
strings in each unit's SUBAGENT-RETURN.json (python3 vs pwsh tokens).
"""
from __future__ import annotations

import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
PROBES = REPO / "command-center" / "p2-wave" / "probes"

UNIT_DELIVER_RE = re.compile(r"P2-deliver unit ([A-Z]{2,5}-\d{4})")
TIMESTAMP_RE = re.compile(r"<timestamp>([^<]+)</timestamp>")
TS_FMT = "%A, %b %d, %Y, %I:%M %p"

# Transcript tool names -> catalog permission vocabulary.
ALIAS = {
    "Shell": "Bash",
    "Bash": "Bash",
    "StrReplace": "Edit",
    "Edit": "Edit",
    "Read": "Read",
    "Write": "Write",
    "Grep": "Grep",
    "Glob": "Glob",
    "WebSearch": "WebSearch",
    "WebFetch": "WebFetch",
    "PowerShell": "PowerShell",
}

COVERAGE_THRESHOLD = 10


def transcript_roots() -> list[Path]:
    env = (os.environ.get("ARC0049_TRANSCRIPTS") or "").strip()
    candidates: list[Path] = []
    if env:
        candidates.append(Path(env))
    candidates.append(HERE / "fixtures" / "transcripts")
    candidates.append(REPO / "agent-transcripts")
    seen: set[str] = set()
    out: list[Path] = []
    for path in candidates:
        try:
            key = str(path.resolve())
        except OSError:
            continue
        if key in seen or not path.is_dir():
            continue
        seen.add(key)
        out.append(path)
    if not out:
        raise FileNotFoundError(
            "no agent-transcripts directory found; set ARC0049_TRANSCRIPTS"
        )
    return out


def transcript_root() -> Path:
    return transcript_roots()[0]


def parse_timestamp(raw: str) -> datetime | None:
    text = (raw or "").strip()
    if not text:
        return None
    text = text.replace(" (UTC)", "").replace(" UTC", "")
    try:
        return datetime.strptime(text, TS_FMT).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def map_tool(name: str) -> str | None:
    return ALIAS.get(str(name).strip())


def load_catalog_units() -> dict[str, dict[str, Any]]:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    out: dict[str, dict[str, Any]] = {}
    for unit in data.get("work_units") or []:
        if isinstance(unit, dict) and isinstance(unit.get("id"), str):
            out[unit["id"]] = unit
    return out


def declared_permissions(unit: dict[str, Any]) -> list[str]:
    raw = unit.get("tool_permissions") or []
    seen: list[str] = []
    for item in raw:
        perm = str(item).strip()
        if perm and perm not in seen:
            seen.append(perm)
    return seen


def scan_transcripts(root: Path | None = None) -> dict[str, Any]:
    roots = [root] if root is not None else transcript_roots()
    by_unit: dict[str, Counter[str]] = defaultdict(Counter)
    files_n = 0
    events = 0
    stamps: list[datetime] = []
    for root in roots:
        for path in sorted(root.rglob("*.jsonl")):
            files_n += 1
            uid: str | None = None
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            stamps.append(mtime)
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for line in lines:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                msg = row.get("message") or {}
                content = msg.get("content")
                if not isinstance(content, list):
                    continue
                for chunk in content:
                    if not isinstance(chunk, dict):
                        continue
                    if chunk.get("type") == "text":
                        text = str(chunk.get("text") or "")
                        for match in TIMESTAMP_RE.finditer(text):
                            parsed = parse_timestamp(match.group(1))
                            if parsed is not None:
                                stamps.append(parsed)
                        if uid is None:
                            found = UNIT_DELIVER_RE.search(text)
                            if found:
                                uid = found.group(1)
                    if chunk.get("type") == "tool_use" and chunk.get("name"):
                        events += 1
                        mapped = map_tool(str(chunk["name"]))
                        if uid and mapped:
                            by_unit[uid][mapped] += 1
    if not stamps:
        now = datetime.now(timezone.utc)
        stamps = [now]
    return {
        "root": str(roots[0]),
        "roots": [str(r) for r in roots],
        "files": files_n,
        "tool_events": events,
        "start": iso(min(stamps)),
        "end": iso(max(stamps)),
        "by_unit": {uid: dict(counter) for uid, counter in by_unit.items()},
    }


def probe_command_counts(uid: str) -> Counter[str]:
    """Signal 2: command-string tokens, not jsonl tool_use names."""
    counts: Counter[str] = Counter()
    ret = PROBES / uid / "SUBAGENT-RETURN.json"
    if not ret.is_file():
        return counts
    try:
        doc = json.loads(ret.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return counts
    if not isinstance(doc, dict):
        return counts
    cmds: list[str] = []
    for key in ("named_probes", "probes"):
        for item in doc.get(key) or []:
            if isinstance(item, dict) and isinstance(item.get("command"), str):
                cmds.append(item["command"])
    for cmd in cmds:
        low = cmd.lower()
        if "powershell" in low or re.search(r"\bpwsh\b", low):
            counts["PowerShell"] += 1
        if "python3" in low or re.search(r"\bpython\b", low):
            counts["Bash"] += 1
        if re.search(r"\bbash\b", low) and "python" not in low:
            counts["Bash"] += 1
    return counts


def observed_calls(counter: Counter[str] | dict[str, int]) -> list[str]:
    calls: list[str] = []
    for name, n in sorted(counter.items()):
        calls.extend([name] * int(n))
    return calls
