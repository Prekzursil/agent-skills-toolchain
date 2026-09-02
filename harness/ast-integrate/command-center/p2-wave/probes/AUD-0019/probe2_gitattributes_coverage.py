#!/usr/bin/env python3
"""Probe 2: .gitattributes rule-coverage map by extension."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import fixture_git as FG  # noqa: E402
import lib as L  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0019-probe2 {msg}")
    return 1


def run() -> dict:
    live_paths = L.find_gitattributes(L.REPO)
    live_rules: list = []
    if live_paths:
        ordered = sorted(live_paths, key=lambda p: (p != ".gitattributes", p))
        chunks = [
            (L.REPO / rel).read_text(encoding="utf-8", errors="replace")
            for rel in ordered
        ]
        live_rules = L.parse_gitattributes("\n".join(chunks))
    inventory = L.live_worktree_eol_inventory(L.REPO)
    live_cov = L.coverage_by_extension(inventory["extensions_seen"], live_rules)
    fx_rules = L.parse_gitattributes(FG.ATTRS)
    fx_exts = [Path(rel).suffix.lower() for rel in FG.BLOBS if Path(rel).suffix]
    fx_cov = L.coverage_by_extension(fx_exts, fx_rules)
    md_pin = L.eol_pin_for_path("README.md", fx_rules)
    sh_pin = L.eol_pin_for_path("script.sh", fx_rules)
    py_pin = L.eol_pin_for_path("src/tool.py", fx_rules)
    txt_pin = L.eol_pin_for_path("notes.txt", fx_rules)
    return {
        "probe": "probe2-gitattributes-coverage",
        "live": {
            "gitattributes_paths": live_paths,
            "gitattributes_present": bool(live_paths),
            "rule_count": len(live_rules),
            "rules": live_rules,
            "coverage": live_cov,
            "note": (
                "no .gitattributes in this worktree"
                if not live_paths
                else "parsed live .gitattributes"
            ),
        },
        "fixture": {
            "rules": fx_rules,
            "coverage": fx_cov,
            "pins": {
                "README.md": md_pin,
                "script.sh": sh_pin,
                "src/tool.py": py_pin,
                "notes.txt": txt_pin,
            },
            "planted_unpinned_markdown": md_pin is None,
            "planted_pinned_shell": sh_pin == "lf",
        },
    }


def main() -> int:
    data = run()
    fx = data["fixture"]
    if not fx["planted_unpinned_markdown"]:
        return fail("fixture *.md must have no eol pin")
    if not fx["planted_pinned_shell"]:
        return fail("fixture *.sh must pin eol=lf")
    if fx["pins"]["src/tool.py"] != "lf":
        return fail("fixture *.py must pin eol=lf")
    if fx["pins"]["notes.txt"] != "crlf":
        return fail("fixture *.txt must pin eol=crlf")
    if ".md" not in fx["coverage"]["unpinned_extensions"]:
        return fail("coverage map missed unpinned .md")
    live = data["live"]
    if (not live["gitattributes_present"]) and live["coverage"]["pinned_count"] != 0:
        return fail("absent .gitattributes must yield zero pins")
    print(json.dumps(data, sort_keys=True, default=str))
    print(
        "live_gitattributes={0} live_unpinned={1} fixture_unpinned={2}".format(
            live["gitattributes_paths"],
            live["coverage"]["unpinned_extensions"],
            fx["coverage"]["unpinned_extensions"],
        )
    )
    print("SUCCESS:AUD-0019-probe2 gitattributes-coverage-by-extension")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
