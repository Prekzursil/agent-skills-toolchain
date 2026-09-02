"""Independent recount: set math and string search, no preserve.check() call.

Probe 2 re-derives lost claim ids from the run dict with a second code path
so a green preserve.check cannot be the only signal.
"""
from __future__ import annotations

import json
from typing import Any


def ids_from_transcript(transcript: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for turn in transcript.get("turns") or []:
        if isinstance(turn, dict) and str(turn.get("vote") or "").upper() == "NO":
            cid = str(turn.get("claim_id") or "").strip()
            if cid:
                out.add(cid)
    return out


def ids_from_minority_report(synthesis: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for row in synthesis.get("minority_report") or []:
        if isinstance(row, dict):
            cid = str(row.get("claim_id") or "").strip()
            if cid:
                out.add(cid)
    return out


def lost_ids(run: dict[str, Any]) -> list[str]:
    tr = run.get("transcript") or {}
    syn = run.get("synthesis") or {}
    return sorted(ids_from_transcript(tr) - ids_from_minority_report(syn))


def token_present(run: dict[str, Any], token: str) -> bool:
    blob = json.dumps(run.get("synthesis") or {}, ensure_ascii=True, sort_keys=True)
    return bool(token) and token in blob


def counterexample_present(run: dict[str, Any], cex: str) -> bool:
    blob = json.dumps(run.get("synthesis") or {}, ensure_ascii=True, sort_keys=True)
    return bool(cex) and cex in blob
