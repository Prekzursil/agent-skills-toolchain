#!/usr/bin/env python3
"""Probe 2: append-only rewrite is a gate failure; no-trail collapse is impossible.

Mechanically independent of probe 1: this probe never diffs restored records
against a pre-collapse snapshot. It only checks (a) an in-place rewrite of a
prior trail line is detected / refused, (b) CollapseGate.collapse cannot
mutate the store unless a durable trail record exists.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from engine import (  # noqa: E402
    run_append_only_controls,
    run_entry_point_controls,
    run_rehearsal,
)

UNIT = "WFA-0099"
OUT_REL = "command-center/wfa/WFA-0099-collapse-audit-trail.json"
SENTINEL = "SUCCESS:WFA-0099"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"


def repo_root() -> Path:
    for p in [HERE, *HERE.parents]:
        if (p / CATALOG).is_file():
            return p
    raise SystemExit("FAILED:WFA-0099-probe2 repo root not found")


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    repo = repo_root()
    art = repo / OUT_REL
    if not art.is_file() or art.stat().st_size <= 0:
        return fail("artifact missing")
    text = art.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    with tempfile.TemporaryDirectory(prefix="wfa0099-p2-") as tmp:
        tmp_path = Path(tmp)
        live = run_rehearsal(tmp_path / "trail.jsonl")
        if not live["chain"].get("ok") or live["n_collapses"] < 3:
            return fail("could not build a live trail for append-only control")
        append = run_append_only_controls(tmp_path / "trail.jsonl", tmp_path)
        entry = run_entry_point_controls(tmp_path)

    print("append_only", {k: append[k] for k in append if k != "rewrite_api_error"})
    print("entry_point", entry)
    if not append["pass"]:
        return fail(f"append-only control failed {append}")
    if not entry["pass"]:
        return fail(f"entry-point control failed {entry}")

    art_append = doc.get("append_only") or {}
    if art_append.get("pass") is not True:
        return fail("artifact append_only.pass is not true")
    if art_append.get("intact_ok") is not True:
        return fail("artifact did not record intact chain ok")
    if art_append.get("rewrite_api_raised") is not True:
        return fail("artifact did not record rewrite API raise")
    if art_append.get("mutated_ok") is not False:
        return fail("artifact mutated_ok is not false (detector would be dead)")

    art_entry = doc.get("entry_point") or {}
    if art_entry.get("pass") is not True:
        return fail("artifact entry_point.pass is not true")
    if art_entry.get("direct_commit_raised") is not True:
        return fail("artifact did not record direct-commit refusal")
    if art_entry.get("silent_trail_raised") is not True:
        return fail("artifact did not record silent-trail refusal")

    print(
        "intact_ok={a} rewrite_raised={b} mutated_ok={c} "
        "direct_raised={d} silent_raised={e}".format(
            a=append["intact_ok"],
            b=append["rewrite_api_raised"],
            c=append["mutated_ok"],
            d=entry["direct_commit_raised"],
            e=entry["silent_trail_raised"],
        )
    )
    print(f"SUCCESS:{UNIT}-probe2 append-only rewrite gate; collapse without trail impossible")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
