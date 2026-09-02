"""Probe-1 instrument: search hook logs AND event ledgers for per-hook fire records.

Two parsers (log regex vs jsonl). A searcher that is silent on a planted
fire is broken. A searcher that fires on the silent fixture is broken.
Live-path absence is NOT-CHECKED, not 'did not fire'.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import inventory as I  # noqa: E402

FIRE_RE = re.compile(
    r"hook=(?P<id>[A-Za-z0-9._-]+)\s+event=(?P<event>\S+)\s+status=fired\b",
    re.IGNORECASE,
)
PLANTED = HERE / "fixtures" / "planted-log"
SILENT = HERE / "fixtures" / "silent-log"


def parse_hook_log(text: str, registered: set[str]) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    for line in text.splitlines():
        m = FIRE_RE.search(line)
        if not m:
            continue
        hid = m.group("id")
        if hid not in registered:
            continue
        found.append({"hook_id": hid, "event": m.group("event"), "source": "hook-log"})
    return found


def parse_event_ledger(text: str, registered: set[str]) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        hid = str(obj.get("hook_id") or "")
        if hid not in registered:
            continue
        fired = obj.get("fired") is True or str(obj.get("status") or "") == "fired"
        if not fired:
            continue
        found.append(
            {
                "hook_id": hid,
                "event": str(obj.get("event") or ""),
                "source": "event-ledger",
            }
        )
    return found


def search_pair(log_path: Path, ledger_path: Path, registered: set[str]) -> dict[str, Any]:
    log_text = log_path.read_text(encoding="utf-8") if log_path.is_file() else ""
    led_text = ledger_path.read_text(encoding="utf-8") if ledger_path.is_file() else ""
    log_hits = parse_hook_log(log_text, registered)
    led_hits = parse_event_ledger(led_text, registered)
    log_ids = sorted({h["hook_id"] for h in log_hits})
    led_ids = sorted({h["hook_id"] for h in led_hits})
    return {
        "log_path": str(log_path.relative_to(HERE)) if HERE in log_path.parents or log_path == HERE else str(log_path),
        "ledger_path": str(ledger_path.relative_to(HERE)) if HERE in ledger_path.parents or ledger_path == HERE else str(ledger_path),
        "log_exists": log_path.is_file(),
        "ledger_exists": ledger_path.is_file(),
        "log_hits": log_hits,
        "ledger_hits": led_hits,
        "log_ids": log_ids,
        "ledger_ids": led_ids,
        "union_ids": sorted(set(log_ids) | set(led_ids)),
        "both_ids": sorted(set(log_ids) & set(led_ids)),
    }


def live_search(registered: set[str]) -> dict[str, Any]:
    inv = I.inventory()
    searched: list[dict[str, Any]] = []
    hits: list[dict[str, str]] = []
    log_rows = [I._row(p, role) for p, role in I.log_search_paths()]
    log_present = any(
        r["exists"] and (r["is_file"] or r["file_count"] > 0) for r in log_rows
    )
    for row in log_rows:
        path = Path(row["path"])
        entry: dict[str, Any] = {
            "path": row["path"],
            "role": row["role"],
            "exists": row["exists"],
            "parsed": False,
            "hit_count": 0,
        }
        if path.is_file() and path.suffix in {".log", ".txt"}:
            text = path.read_text(encoding="utf-8", errors="replace")
            found = parse_hook_log(text, registered)
            entry["parsed"] = True
            entry["hit_count"] = len(found)
            hits.extend(found)
        elif path.is_file() and path.suffix == ".jsonl":
            text = path.read_text(encoding="utf-8", errors="replace")
            found = parse_event_ledger(text, registered)
            entry["parsed"] = True
            entry["hit_count"] = len(found)
            hits.extend(found)
        elif path.is_dir():
            for child in sorted(path.rglob("*")):
                if not child.is_file():
                    continue
                if child.suffix == ".log":
                    found = parse_hook_log(
                        child.read_text(encoding="utf-8", errors="replace"), registered
                    )
                    entry["parsed"] = True
                    entry["hit_count"] += len(found)
                    hits.extend(found)
                elif child.suffix == ".jsonl":
                    found = parse_event_ledger(
                        child.read_text(encoding="utf-8", errors="replace"), registered
                    )
                    entry["parsed"] = True
                    entry["hit_count"] += len(found)
                    hits.extend(found)
        searched.append(entry)
    return {
        "inventory": inv,
        "searched": searched,
        "hits": hits,
        "hit_ids": sorted({h["hook_id"] for h in hits}),
        "any_source_present": log_present,
        "log_present_count": sum(
            1 for r in log_rows if r["exists"] and (r["is_file"] or r["file_count"] > 0)
        ),
    }


def detector_control() -> dict[str, Any]:
    registered = set(I.registered_ids())
    planted = search_pair(
        PLANTED / "hook.log", PLANTED / "event-ledger.jsonl", registered
    )
    silent = search_pair(
        SILENT / "hook.log", SILENT / "event-ledger.jsonl", registered
    )
    want = set(registered)
    planted_ok = set(planted["both_ids"]) == want and set(planted["log_ids"]) == want and set(planted["ledger_ids"]) == want
    silent_ok = silent["union_ids"] == [] and silent["log_hits"] == [] and silent["ledger_hits"] == []
    return {
        "registered_ids": sorted(registered),
        "planted": planted,
        "silent": silent,
        "known_present_ran_first": True,
        "known_present_fired": planted_ok,
        "silent_fixture_empty": silent_ok,
        "absence_reported_only_after": planted_ok and silent_ok,
        "pass": planted_ok and silent_ok,
    }


def _classify(hid: str, live: dict[str, Any]) -> str:
    if hid in live["hit_ids"]:
        return "FOUND"
    if live["any_source_present"]:
        # Present live source with no fire record is still not 'did not fire'.
        return "ABSENT"
    return "NOT-CHECKED"


def run_search() -> dict[str, Any]:
    ctrl = detector_control()
    fixture_ids = list(ctrl["registered_ids"])
    live_ids = I.live_registered_ids()
    union = set(fixture_ids) | set(live_ids)
    live = live_search(union)
    per_hook = {hid: _classify(hid, live) for hid in fixture_ids}
    per_live = {hid: _classify(hid, live) for hid in live_ids}
    return {
        "detector_control": {
            "known_present_ran_first": ctrl["known_present_ran_first"],
            "known_present_fired": ctrl["known_present_fired"],
            "absence_reported_only_after": ctrl["absence_reported_only_after"],
            "silent_fixture_empty": ctrl["silent_fixture_empty"],
            "pass": ctrl["pass"],
            "planted_both_ids": ctrl["planted"]["both_ids"],
            "silent_union_ids": ctrl["silent"]["union_ids"],
            "registered_ids": ctrl["registered_ids"],
        },
        "live": live,
        "per_hook_live_turn_evidence": per_hook,
        "per_live_registered_turn_evidence": per_live,
        "live_registered_ids": live_ids,
        "live_registered_n": len(live_ids),
        "pass": ctrl["pass"],
    }
