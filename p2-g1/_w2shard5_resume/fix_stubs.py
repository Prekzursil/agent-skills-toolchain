#!/usr/bin/env python3
"""Normalize the probe-validation stub tails in the seven patched probes and
syntax-verify each file. The stub literal must close: probe} item} list] outer}."""
from __future__ import annotations

import ast
import re
from pathlib import Path

PROBES = Path(r"C:\Users\Prekzursil\p2-g1\command-center\p2-wave\probes")
TARGETS = [
    PROBES / "AUD-0095" / "probe1_freeze_anchors.py",
    PROBES / "BLD-0004" / "probe1_control_recheck.py",
    PROBES / "BLD-0005" / "probe1_controls.py",
    PROBES / "BLD-0005" / "probe2_sample_rescan.py",
    PROBES / "BLD-0013" / "probe1_structure.py",
    PROBES / "BLD-0014" / "probe1_planted_controls.py",
    PROBES / "BLD-0014" / "probe2_anchors_review.py",
]
MARK = "'consumer': 'probe-validation-stub'"


def main() -> int:
    ok_all = True
    for p in TARGETS:
        text = p.read_text(encoding="utf-8")
        try:
            ast.parse(text)
            print(f"OK    {p.name}")
            continue
        except SyntaxError as exc:
            print(f"FIX   {p.name} line {exc.lineno}")

        # rebuild the stub call tail: capture up to the stub's final exit_code
        # marker, then append the exact closer sequence.
        m = re.search(
            r"(?P<head>validate_artifact\(\{\*\*doc, 'downstream_consumers': \["
            r"(?P<stub>\{'consumer': 'probe-validation-stub'.*?'exit_code': 0)"
            r"(?P<tail>\W+?)(?P<rest>,\s*\"command-center)",
            text, flags=re.DOTALL)
        if not m:
            m = re.search(
                r"(?P<head>iter_errors\(\{\*\*doc, 'downstream_consumers': \["
                r"(?P<stub>\{'consumer': 'probe-validation-stub'.*?'exit_code': 0)"
                r"(?P<tail>\W+?)(?P<rest>\)\s*\))",
                text, flags=re.DOTALL)
        if not m:
            print(f"      no stub pattern matched")
            ok_all = False
            continue
        fixed = (text[:m.start("tail")] + "}}]}" + text[m.start("rest"):])
        try:
            ast.parse(fixed)
        except SyntaxError as exc2:
            print(f"      still broken: {exc2.lineno}: {exc2.msg}")
            ok_all = False
            continue
        p.write_text(fixed, encoding="utf-8")
        print(f"      fixed + parses")
    print("ALL-OK" if ok_all else "SOME-FAILED")
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
