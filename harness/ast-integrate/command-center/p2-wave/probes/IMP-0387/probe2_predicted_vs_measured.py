#!/usr/bin/env python3
"""Probe 2: predicted load_mode vs instrument-measured load_mode.

Two-column table over every scanned rules file. Predicted = YAML resolver.
Measured = inspect_load.py in a subprocess (grok inspect equivalent).
Disagreements are findings; the instrument wins. A census with zero ALWAYS-ON
rows is a broken instrument, not evidence of universal laziness.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

ART = S.RECEIPT
WELL_FORMED = {
    "always-on-no-frontmatter.md",
    "always-on-other-keys.md",
    "always-on-nested-paths.md",
    "lazy-globstar.md",
    "lazy-narrow.md",
    "lazy-empty-paths-list.md",
    "mention-in-body.md",
}


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:IMP-0387-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if S.SENTINEL not in text:
        print("FAILED:IMP-0387-probe2 sentinel absent")
        return 1

    R = S.load_resolver()
    census = S.full_census(resolver=R)
    table = census["table"]
    if census["n_always_on"] < 1:
        print("FAILED:IMP-0387-probe2 instrument named zero ALWAYS-ON files")
        return 1
    if census["n_lazy"] < 1:
        print("FAILED:IMP-0387-probe2 census has zero LAZY files")
        return 1

    fixture_rows = [r for r in table if r["label"] == "fixture_rules"]
    if len(fixture_rows) < 5:
        print("FAILED:IMP-0387-probe2 fixture census too small", len(fixture_rows))
        return 1

    known_always = known_lazy = None
    for row in fixture_rows:
        if row["path"].endswith("always-on-no-frontmatter.md"):
            known_always = row
        if row["path"].endswith("lazy-globstar.md"):
            known_lazy = row
    if known_always is None or known_always["measured_load_mode"] != S.ALWAYS_ON:
        print("FAILED:IMP-0387-probe2 known always-on fixture not ALWAYS-ON under instrument")
        return 1
    if known_lazy is None or known_lazy["measured_load_mode"] != S.LAZY:
        print("FAILED:IMP-0387-probe2 globstar fixture not LAZY under instrument")
        return 1

    for path in R.iter_rule_files(S.FIXTURE_RULES):
        predicted = R.resolve_load_mode(path.read_text(encoding="utf-8"))
        measured = S.inspect_via_subprocess(path)
        if path.name == "always-on-no-frontmatter.md" and measured != S.ALWAYS_ON:
            print("FAILED:IMP-0387-probe2 subprocess inspect missed always-on", measured)
            return 1
        if path.name == "lazy-globstar.md" and measured != S.LAZY:
            print("FAILED:IMP-0387-probe2 subprocess inspect missed lazy", measured)
            return 1
        if path.name in WELL_FORMED and predicted != measured:
            print(
                f"FAILED:IMP-0387-probe2 well-formed fixture disagreement "
                f"{path.name} pred={predicted} meas={measured}"
            )
            return 1

    recorded = doc.get("load_mode_table") or []
    if len(recorded) != len(table):
        print(
            f"FAILED:IMP-0387-probe2 receipt table size {len(recorded)} live {len(table)}"
        )
        return 1
    live_by_path = {r["path"]: r for r in table}
    for rec_row in recorded:
        live_row = live_by_path.get(rec_row.get("path"))
        if live_row is None:
            print("FAILED:IMP-0387-probe2 receipt row missing live", rec_row.get("path"))
            return 1
        if rec_row.get("predicted_load_mode") != live_row["predicted_load_mode"]:
            print("FAILED:IMP-0387-probe2 predicted drift", rec_row.get("path"))
            return 1
        if rec_row.get("measured_load_mode") != live_row["measured_load_mode"]:
            print("FAILED:IMP-0387-probe2 measured drift", rec_row.get("path"))
            return 1

    roots = S.live_roots()
    print(
        f"rows={census['n_rows']} always_on={census['n_always_on']} "
        f"lazy={census['n_lazy']} disagree={census['n_disagree']} "
        f"claude_rules={roots['claude_rules'].is_dir()} "
        f"repo_rules={roots['repo_rules'].is_dir()} "
        f"grok={census['grok']['present']} "
        f"capability_index={census['capability_index']['present']}"
    )
    print("SUCCESS:IMP-0387-probe2 predicted-vs-measured table; instrument can name ALWAYS-ON")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
