#!/usr/bin/env python3
"""Probe 2: static scan both-states (independent of replay hashes).

Catalog evidence B: a static scan that finds zero banned constructs on the
repaired corpus, proven to fire on a planted wall-clock read first.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.wfa.nondeterminism import (  # noqa: E402
    finding_dicts,
    findings_by_kind,
    scan_path,
    scan_text,
    scan_tree,
)

ART = REPO / "command-center/wfa/WFA-0089-repair-nondeterminism.json"
PLANTED = HERE / "fixtures/planted"
BROKEN = HERE / "fixtures/broken"
REPAIRED = HERE / "fixtures/repaired"
REQUIRED_KINDS = {"wall-clock", "unseeded-random", "interpolated-args", "env-path"}


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0089-probe2 {msg}")
    return 1


def main() -> int:
    planted = scan_tree(PLANTED, repo=REPO)
    planted_kinds = findings_by_kind(planted)
    print(f"planted_hits={len(planted)} kinds={planted_kinds}")
    if not planted:
        return fail("planted wall-clock fixture produced zero hits (detector silent)")
    if planted_kinds.get("wall-clock", 0) < 1:
        return fail("planted fixture did not fire as wall-clock")

    broken = scan_tree(BROKEN, repo=REPO)
    broken_kinds = findings_by_kind(broken)
    print(f"broken_hits={len(broken)} kinds={broken_kinds}")
    missing = REQUIRED_KINDS - set(broken_kinds)
    if missing:
        return fail(f"broken fixture missing construct classes {sorted(missing)}")

    repaired = scan_tree(REPAIRED, repo=REPO)
    repaired_kinds = findings_by_kind(repaired)
    print(f"repaired_hits={len(repaired)} kinds={repaired_kinds}")
    if repaired:
        print(json.dumps(finding_dicts(repaired), indent=2)[:4000])
        return fail("repaired corpus still contains banned constructs")

    clean = (REPAIRED / "saved-workflow.mjs").read_text(encoding="utf-8")
    silent = scan_text(clean, relpath="memory/repaired.mjs")
    if silent:
        return fail("repaired source matched banned patterns in-memory")
    mutant = clean + "\nconst plantedClock = Date.now();\n"
    mutant_hits = scan_text(mutant, relpath="memory/mutant.mjs")
    mutant_kinds = findings_by_kind(mutant_hits)
    print(f"in_memory_mutant_wall_clock={mutant_kinds.get('wall-clock', 0)}")
    if mutant_kinds.get("wall-clock", 0) < 1:
        return fail("in-memory Date.now() plant did not fire")

    with tempfile.TemporaryDirectory(prefix="wfa0089-plant-") as tmp:
        planted_copy = Path(tmp) / "planted.mjs"
        planted_copy.write_text(mutant, encoding="utf-8")
        on_disk = scan_path(planted_copy)
        if findings_by_kind(on_disk).get("wall-clock", 0) < 1:
            return fail("on-disk plant of Date.now() did not fire")

    if not ART.is_file():
        return fail("catalog artifact missing")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:WFA-0089" not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    scan_block = doc.get("static_scan") or {}
    planted_hits = scan_block.get("planted_wall_clock_hits")
    repaired_hits = scan_block.get("repaired_hits")
    if not isinstance(planted_hits, int) or planted_hits < 1:
        return fail("artifact did not record a planted wall-clock hit")
    if repaired_hits != 0:
        return fail("artifact did not record a clean repaired scan")

    print("SUCCESS:WFA-0089-probe2 static scan both-states (planted fires, repaired silent)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
