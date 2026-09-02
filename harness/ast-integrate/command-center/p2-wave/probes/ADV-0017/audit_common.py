#!/usr/bin/env python3
"""Shared paths, stdlib unshadow, host-tree search, hashing for ADV-0017."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UID = "ADV-0017"
OUT_REL = "command-center/adversarial/ADV-0017-repo-live-two-directional-divergence.json"
SCHEMA_REL = "command-center/schema/refutation-record.schema.json"
FIXTURE_REPO = HERE / "fixtures" / "repo"
FIXTURE_LIVE = HERE / "fixtures" / "live"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0017/probe1_classify.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0017/probe2_provenance.py"
)
QUESTION = (
    "For every file that exists in both the repository and a live deployed "
    "tree, which side holds unique content - and is there any pair where a "
    "one-directional sync in EITHER direction destroys content?"
)
COMPLETION = (
    "SUCCESS:ADV-0017 emitted ONLY when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, records BOTH named probes "
    "verbatim with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, "
    "and records the result of every listed control/negative test. Any "
    "missing control downgrades the unit's verdicts to NOT-CHECKED. "
    "Otherwise FAILED:ADV-0017 <reason>."
)
CATALOG_PIN_LIVE_LARGER = (
    "rules/common/owner-ops-authorization.md",
    "rules/common/performance.md",
    "rules/common/security.md",
)
BANNED_SYNC = (
    "sync-from-live.ps1",
    "sync-rules.ps1",
    "Copy-Item -Force",
)
HOST_CANDIDATES = (
    REPO / "rules",
    REPO / "hooks",
    REPO / "skills",
    REPO / "agents",
    REPO / "commands",
    Path.home() / ".claude",
    Path.home() / ".claude" / "rules",
    Path.home() / ".claude" / "hooks",
    Path.home() / ".claude" / "skills",
    Path("/root/.claude"),
    Path("/root/.claude/rules"),
    Path.home() / ".cursor" / "rules",
)


def unshadow_stdlib() -> None:
    """Drop the worktree (and cwd) from sys.path so stdlib `platform` wins."""
    cleaned: list[str] = []
    for p in sys.path:
        if p in ("", "."):
            continue
        try:
            resolved = Path(p).resolve()
        except OSError:
            cleaned.append(p)
            continue
        if resolved == REPO:
            continue
        cleaned.append(p)
    sys.path[:] = cleaned
    sys.modules.pop("platform", None)


unshadow_stdlib()
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes() if path.is_file() else b""
    return sha256_bytes(raw), len(raw)


def iso_mtime(path: Path) -> str | None:
    if not path.is_file():
        return None
    ts = path.stat().st_mtime
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def iter_rel_files(root: Path) -> dict[str, Path]:
    out: dict[str, Path] = {}
    if not root.is_dir():
        return out
    for p in root.rglob("*"):
        if p.is_file():
            out[p.relative_to(root).as_posix()] = p
    return out


def host_candidates() -> list[dict]:
    rows = []
    for p in HOST_CANDIDATES:
        n = sum(1 for q in p.rglob("*") if q.is_file()) if p.is_dir() else 0
        rows.append(
            {
                "path": str(p),
                "exists": p.exists(),
                "is_dir": p.is_dir(),
                "file_count": n,
            }
        )
    return rows


def host_live_present() -> bool:
    return any(r["is_dir"] and r["file_count"] > 0 for r in host_candidates())


def dump_json(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
