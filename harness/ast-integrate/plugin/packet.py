"""Divergence decision packets. Recommendation is advisory; never auto-resolves."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from plugin.drift import DIVERGED, classify_pair


def _lines(text: str) -> list[str]:
    return (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")


def unique_line_lists(repo_text: str, live_text: str) -> tuple[list[str], list[str]]:
    repo = _lines(repo_text)
    live = _lines(live_text)
    live_set = set(live)
    repo_set = set(repo)
    repo_unique: list[str] = []
    seen_r: set[str] = set()
    for line in repo:
        if line not in live_set and line not in seen_r:
            repo_unique.append(line)
            seen_r.add(line)
    live_unique: list[str] = []
    seen_l: set[str] = set()
    for line in live:
        if line not in repo_set and line not in seen_l:
            live_unique.append(line)
            seen_l.add(line)
    return repo_unique, live_unique


def packet_has_both_unique_sets(pkt: dict[str, Any]) -> bool:
    ru = pkt.get("repo_unique_lines") or []
    lu = pkt.get("live_unique_lines") or []
    return bool(ru) and bool(lu)


def emit_packet(
    *args: Any,
    path: str | None = None,
    repo_text: str | None = None,
    live_text: str | None = None,
    repo_root: Any = None,
    live_path: Any = None,
    ledger: dict | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    if path is None and args:
        path = args[0]
    if repo_text is None and len(args) > 1:
        repo_text = args[1]
    if live_text is None and len(args) > 2:
        live_text = args[2]
    path = str(path or kwargs.get("path") or "")
    repo_text = repo_text if repo_text is not None else str(kwargs.get("repo_text") or "")
    live_text = live_text if live_text is not None else str(kwargs.get("live_text") or "")
    klass = classify_pair(
        repo_text.encode("utf-8"),
        live_text.encode("utf-8"),
    )
    ru, lu = unique_line_lists(repo_text, live_text)
    led = {}
    if isinstance(ledger, dict):
        led = ledger.get(path) if isinstance(ledger.get(path), dict) else {}
    live_mtime = None
    lp = live_path if live_path is not None else kwargs.get("live_path")
    if lp is not None:
        p = Path(lp)
        if p.is_file():
            live_mtime = p.stat().st_mtime
    action = "HOLD-FOR-RECORDED-DECISION" if klass == DIVERGED else "NO-OP"
    return {
        "path": path,
        "classification": klass,
        "repo_unique_lines": ru,
        "live_unique_lines": lu,
        "recommendation": {
            "kind": "advisory",
            "action": action,
            "may_authorize_act": False,
        },
        "decision": {
            "kind": "recorded-owner-decision",
            "status": "UNRECORDED",
        },
        "facts": {"used_as_authorship": False},
        "mtime_is_authorship_signal": False,
        "size_is_authorship_signal": False,
        "last_repo_commit": {
            "git": {
                "command": f"git log -1 --format=%cI -- {path}",
                "iso": led.get("committer_iso"),
                "commit": led.get("commit"),
            }
        },
        "live_mtime": live_mtime,
        "repo_root": str(repo_root) if repo_root is not None else None,
    }


def record_decision(packet: dict[str, Any], choice: str) -> dict[str, Any]:
    out = dict(packet)
    decision = dict(out.get("decision") or {})
    decision["kind"] = "recorded-owner-decision"
    decision["status"] = "RECORDED"
    decision["choice"] = choice
    out["decision"] = decision
    return out


__all__ = [
    "emit_packet",
    "packet_has_both_unique_sets",
    "record_decision",
    "unique_line_lists",
]
