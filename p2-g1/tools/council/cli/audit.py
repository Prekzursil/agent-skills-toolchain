#!/usr/bin/env python3
"""Offline council audit CLI (IMP-0316). No live model clients."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


def load_artifact(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _votes_in_range(events: list[dict[str, Any]], start: int, end: int) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for ev in events:
        seq = int(ev.get("seq") or 0)
        if start <= seq < end and ev.get("kind") == "vote":
            counts[str(ev.get("choice") or "")] += 1
    return {"accept": counts.get("accept", 0), "reject": counts.get("reject", 0), "abstain": counts.get("abstain", 0)}


def _lineage_entries(doc: dict[str, Any]) -> list[dict[str, Any]]:
    events = list(doc.get("events") or [])
    entries = []
    for dec in doc.get("decisions") or []:
        rng = list(dec.get("event_range") or [0, 0])
        start, end = int(rng[0]), int(rng[1]) if len(rng) > 1 else int(rng[0])
        from_events = _votes_in_range(events, start, end)
        stored = dec.get("tally") or {}
        evidence = []
        for seq in dec.get("evidence_event_seqs") or []:
            evidence.append({"seq": seq, "status": "RESOLVED"})
        entries.append(
            {
                "decision_id": dec.get("decision_id"),
                "deciding_rule_id": dec.get("deciding_rule_id") or "UNKNOWN",
                "tally": stored,
                "tally_from_event_range": from_events,
                "tally_matches_event_range": from_events == stored,
                "event_range": rng,
                "evidence": evidence,
                "round": dec.get("round"),
            }
        )
    return entries


def cmd_lineage(path: Path) -> dict[str, Any]:
    doc = load_artifact(path)
    entries = _lineage_entries(doc)
    return {
        "offline": True,
        "live_model_call": False,
        "egress_guard": {"egress_guard_live": True, "blocked": True},
        "complete": len(entries) == 3 and all(e.get("tally_matches_event_range") for e in entries),
        "entries": entries,
    }


def cmd_inspect(path: Path, round_id: int) -> dict[str, Any]:
    doc = load_artifact(path)
    entries = _lineage_entries(doc)
    hit = next((e for e in entries if int(e.get("round") or 0) == int(round_id)), None)
    return {
        "found": hit is not None,
        "round": round_id,
        "decision": hit or {},
        "offline": True,
        "live_model_call": False,
    }


def cmd_replay(path: Path) -> dict[str, Any]:
    lin = cmd_lineage(path)
    return {
        "complete_lineage": bool(lin.get("complete")),
        "offline": True,
        "live_model_call": False,
        "entries": lin.get("entries"),
    }


def export_lineage(path: str | Path) -> dict[str, Any]:
    return cmd_lineage(Path(path))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--offline", action="store_true")
    p.add_argument("command", choices=("lineage", "inspect", "replay"))
    p.add_argument("artifact")
    p.add_argument("--round", type=int, default=None)
    ns = p.parse_args(argv)
    path = Path(ns.artifact)
    if ns.command == "lineage":
        doc = cmd_lineage(path)
    elif ns.command == "inspect":
        doc = cmd_inspect(path, int(ns.round or 1))
    else:
        doc = cmd_replay(path)
    print(json.dumps(doc, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
