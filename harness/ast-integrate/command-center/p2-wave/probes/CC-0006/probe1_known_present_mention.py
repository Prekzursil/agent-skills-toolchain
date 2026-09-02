#!/usr/bin/env python3
"""Probe 1: known-present, known-absent, use-vs-mention.

Catalog tests_required:
  * Known-present: the live RELEASE-CHECKLIST.md `git archive` line must fire
    BEFORE the fix (held as fixtures/pre-fix/RELEASE-CHECKLIST.md).
  * Known-absent sentinel: a scratch document with no recipe must score 0 hits.
  * Use-vs-mention: rules/common/windows-shell.md, which quotes the wrong
    recipe in order to forbid it, must NOT fire.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
GATE_PATH = REPO / "command-center" / "wrong_recipe_gate.py"


def load_gate():
    spec = importlib.util.spec_from_file_location("wrong_recipe_gate", GATE_PATH)
    if spec is None or spec.loader is None:
        raise SystemExit("FAILED:CC-0006-probe1 cannot load gate")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    g = load_gate()
    st = g.self_test()
    if st:
        print("FAILED:CC-0006-probe1 labelled-controls")
        for row in st:
            print(" ", row)
        return 1
    print(f"labelled_controls_ok=True n={len(g.LABELLED_CONTROLS)}")

    pre = HERE / "fixtures/pre-fix/RELEASE-CHECKLIST.md"
    pre_hits = g.scan_path(pre, REPO)
    pre_bad = g.prescriptive(pre_hits)
    print(
        f"known_present_prefix_hits={len(pre_bad)} "
        f"line={[h['line'] for h in pre_bad]}"
    )
    if not pre_bad:
        print("FAILED:CC-0006-probe1 pre-fix checklist did not fire")
        print(pre_hits)
        return 1
    if not any("git archive" in (h.get("text") or h.get("text") or "").lower() for h in pre_bad):
        print("FAILED:CC-0006-probe1 pre-fix hit was not the git archive line")
        return 1

    scratch = HERE / "fixtures/scratch-empty.md"
    scratch_hits = g.scan_path(scratch, REPO)
    print(f"known_absent_scratch_hits={len(scratch_hits)}")
    if scratch_hits:
        print("FAILED:CC-0006-probe1 scratch document scored hits")
        print(scratch_hits)
        return 1

    live_shell = REPO / "rules/common/windows-shell.md"
    if not live_shell.is_file():
        print("FAILED:CC-0006-probe1 live windows-shell.md missing")
        return 1
    shell_hits = g.scan_path(live_shell, REPO)
    shell_bad = g.prescriptive(shell_hits)
    print(
        f"use_vs_mention_windows_shell_prescriptive={len(shell_bad)} "
        f"archive_lines={len(shell_hits)}"
    )
    if shell_bad:
        print("FAILED:CC-0006-probe1 windows-shell.md documentary mention fired")
        print(shell_bad)
        return 1
    if not any(h["role"] == "DOCUMENTARY" for h in shell_hits):
        print("FAILED:CC-0006-probe1 windows-shell.md did not even mention git archive")
        return 1

    print("SUCCESS:CC-0006-probe1 known-present known-absent use-vs-mention")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
