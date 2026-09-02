"""Harvest claims that cite a command plus a recorded output."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURES = HERE / "fixtures" / "claims.json"

_DOLLAR = re.compile(
    r"^\$\s+(.+?)(?:\s+EXIT=\d+)?(?:\s+->\s+(.*))?\s*$"
)


def load_fixtures() -> list[dict[str, Any]]:
    data = json.loads(FIXTURES.read_text(encoding="utf-8"))
    out = []
    for row in data:
        if not isinstance(row, dict) or not row.get("command"):
            continue
        rec = dict(row)
        rec.setdefault("source", "fixture")
        rec.setdefault("source_path", "command-center/p2-wave/probes/CNF-0165/fixtures/claims.json")
        out.append(rec)
    return out


def harvest_markdown(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    rel = path.relative_to(REPO).as_posix()
    claims: list[dict[str, Any]] = []
    lines = text.splitlines()
    i = 0
    n = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        m = _DOLLAR.match(stripped)
        if not m:
            i += 1
            continue
        cmd = m.group(1).strip()
        inline_out = (m.group(2) or "").strip()
        buf: list[str] = []
        if inline_out:
            buf.append(inline_out)
        j = i + 1
        while j < len(lines):
            nxt = lines[j]
            if nxt.strip().startswith("$ "):
                break
            if nxt.strip() in {"```", "~~~"}:
                break
            if nxt.strip() == "" and buf:
                break
            if nxt.strip():
                buf.append(nxt.rstrip())
            j += 1
        n += 1
        claims.append(
            {
                "id": f"md:{rel}:{i + 1}",
                "source": "markdown",
                "source_path": f"{rel}:{i + 1}",
                "command": cmd,
                "recorded_output": ("\n".join(buf) + "\n") if buf else "",
            }
        )
        i = j
    return claims


def harvest_named_probes() -> list[dict[str, Any]]:
    probes = REPO / "command-center" / "p2-wave" / "probes"
    claims: list[dict[str, Any]] = []
    if not probes.is_dir():
        return claims
    for ret_path in sorted(probes.glob("*/SUBAGENT-RETURN.json")):
        if ret_path.parent.name == "CNF-0165":
            continue
        try:
            doc = json.loads(ret_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(doc, dict):
            continue
        rel = ret_path.relative_to(REPO).as_posix()
        for idx, item in enumerate(doc.get("named_probes") or []):
            if not isinstance(item, dict):
                continue
            cmd = item.get("command")
            if not isinstance(cmd, str) or not cmd.strip():
                continue
            raw = item.get("raw_output")
            claims.append(
                {
                    "id": f"probe:{ret_path.parent.name}:{item.get('id') or idx}",
                    "source": "named-probe",
                    "source_path": rel,
                    "command": cmd.strip(),
                    "recorded_output": raw if isinstance(raw, str) else "",
                    "harvest_note": "sibling named probes mutate worktree artifacts; not allowlisted for replay",
                }
            )
    return claims


def all_claims() -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, Any]] = []
    md_paths = [
        REPO / "command-center" / "p2-wave" / "P2-GROUNDING.md",
        REPO / "command-center" / "p2-wave" / "P2-INTEGRATE.md",
        REPO / "command-center" / "p2-wave" / "P2-BUILD-ROUND1.md",
        REPO / "command-center" / "p2-wave" / "P2-BUILD-ROUND2.md",
        REPO / "command-center" / "p2-wave" / "P2-BUILD-ROUND3.md",
    ]
    groups = [load_fixtures()]
    for p in md_paths:
        groups.append(harvest_markdown(p))
    groups.append(harvest_named_probes())
    for group in groups:
        for row in group:
            key = (row["command"], row.get("recorded_output") or "")
            if key in seen:
                continue
            seen.add(key)
            out.append(row)
    return out
