"""AUTHORITATIVE side: commit time vs live mtime plus unique-line read, never size."""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from compare import census
from corpus import load_ledger
from paths import LIVE_RULES, REPO_RULES


def parse_iso(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def iso_mtime(path: Path) -> str:
    ts = path.stat().st_mtime
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def newer_side(commit_iso: str, live_iso: str) -> str:
    c, l = parse_iso(commit_iso), parse_iso(live_iso)
    if l > c:
        return "LIVE"
    if c > l:
        return "REPO"
    return "TIE"


def decide(shape: str, newer: str) -> tuple[str, str]:
    """Return (authoritative, reason). Size is not an input."""
    if shape in {"IDENTICAL", "IDENTICAL-MODULO-EOL"}:
        return "EITHER-IDENTICAL", "normalised content matches; timestamps are provenance only"
    if shape == "LIVE-SUPERSET" and newer == "LIVE":
        return (
            "LIVE",
            "live holds unique lines and live mtime is later than the repo commit",
        )
    if shape == "REPO-SUPERSET" and newer == "REPO":
        return (
            "REPO",
            "repo holds unique lines and commit time is later than live mtime",
        )
    if shape == "BOTH-UNIQUE":
        return (
            "OWNER-QUEUE",
            "both sides hold unique lines; a one-directional overwrite would drop content",
        )
    return (
        "OWNER-QUEUE",
        f"content shape {shape} disagrees with newer_side {newer}; size is not used to break the tie",
    )


def adjudicate() -> dict:
    ledger = load_ledger()
    snap = census(REPO_RULES, LIVE_RULES)
    rows = []
    for rec in snap["rows"]:
        rel = rec["path"]
        live_path = LIVE_RULES / rel
        commit_iso = ledger[rel]
        live_iso = iso_mtime(live_path) if live_path.is_file() else None
        newer = newer_side(commit_iso, live_iso) if live_iso else "UNKNOWN"
        auth, reason = decide(rec["shape"], newer)
        rows.append(
            {
                "path": rel,
                "shape": rec["shape"],
                "eol_class": rec.get("eol_class"),
                "repo_bytes": rec.get("repo_bytes"),
                "live_bytes": rec.get("live_bytes"),
                "size_delta_live_minus_repo": rec.get("size_delta_live_minus_repo"),
                "size_used_for_authority": False,
                "commit_iso": commit_iso,
                "commit_source": "fixture-ledger (host git log unavailable)",
                "live_mtime_iso": live_iso,
                "newer_side": newer,
                "repo_unique_line_count": len(rec.get("repo_unique_lines") or []),
                "live_unique_line_count": len(rec.get("live_unique_lines") or []),
                "repo_unique_lines": rec.get("repo_unique_lines") or [],
                "live_unique_lines": rec.get("live_unique_lines") or [],
                "authoritative": auth,
                "reason": reason,
            }
        )
    content = [r for r in rows if r["shape"] not in {"IDENTICAL", "IDENTICAL-MODULO-EOL"}]
    return {
        "counts": snap["counts"],
        "rows": rows,
        "content_differing": content,
        "authority_tally": _tally(content),
    }


def _tally(rows: list[dict]) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in rows:
        out[r["authoritative"]] = out.get(r["authoritative"], 0) + 1
    return out


def size_strawman_would_say(size_delta: int | None) -> str:
    if size_delta is None:
        return "UNKNOWN"
    if size_delta > 0:
        return "LIVE"
    if size_delta < 0:
        return "REPO"
    return "TIE"
