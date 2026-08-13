#!/usr/bin/env python3
"""One-shot PORTABILITY MEASUREMENT: which rule-audit gates can run on a CI runner?

Not a per-PR gate.  Its job is to CHOOSE the CI plan from measurement rather than from
reading the source, which is the mistake the sibling mcp-audit lane measured the hard way
(11 of 15 gates passed on Ubuntu after all 15 passed on Windows).

The hazard specific to THIS lane is not POSIX-vs-Windows, it is the LIVE TREE.  Seven of the
28 scripts here read ``Path.home()`` -- ``~/.claude/rules``, ``~/.claude/AGENTS.md`` -- which
exists on the owner's box and does NOT exist on a GitHub runner.  A gate that silently
reports "clean" against a home directory that is not there is the fail-open shape this whole
lane exists to catch, so each script is run TWICE:

  STATE A  real HOME              -- the owner's box, live tree present
  STATE B  HOME=<empty temp dir>  -- a faithful stand-in for the CI runner

A script whose rc is 0 in both states, without a live tree to read, is either genuinely
tree-independent or fail-OPEN.  The distinction is resolved by hand from the marker text and
recorded in ci_gate.py's EXCLUDED reasons -- this probe surfaces the candidates, it does not
adjudicate them.

LANE-SCOPED NAME.  ``command-center/mcp-audit/_i1_ci_portability.py`` exists and is a
DIFFERENT probe: it measures POSIX-vs-Windows behaviour of that lane's gates against a Linux
clone.  This one measures live-tree presence for THIS lane's scripts and shares no code with
it (the sibling hardcodes its own directory and gate list).  Same role, same naming
convention, deliberately separate implementations -- the convention this repo already uses
for ``_i3_redproof.py`` in two lanes.

Run::

    python docs/rule-audit/_i1_ci_portability.py
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent

# argv per script.  Anything not listed runs bare.
ARGV: dict[str, list[str]] = {
    "rule_audit.py": ["--self-test"],
    "r2_pathrefs.py": ["--self-test"],
    "r4_receipt_argv_gate.py": [],
    "r2_control_count_gate.py": [],
}

# Never execute: mutates tracked markdown in place.
NEVER_RUN = {"_r4_mark_mentions.py", pathlib.Path(__file__).name}


def run(script: str, argv: list[str], home: str | None) -> tuple[int, str]:
    env = dict(os.environ)
    if home is not None:
        env["HOME"] = home
        env["USERPROFILE"] = home
        env["HOMEDRIVE"] = home[:2]
        env["HOMEPATH"] = home[2:] or "\\"
    try:
        proc = subprocess.run(
            [sys.executable, script, *argv],
            cwd=HERE,
            capture_output=True,
            text=True,
            env=env,
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        return 124, "<timeout 300s>"
    out = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    marker = next(
        (ln for ln in reversed(out) if ln.startswith(("SUCCESS:", "FAILED:"))),
        (out[-1] if out else "<no stdout>"),
    )
    if proc.returncode != 0 and proc.stderr.strip():
        marker = f"{marker} |err| {proc.stderr.strip().splitlines()[-1]}"
    return proc.returncode, marker.strip()[:150]


def main() -> int:
    scripts = sorted(p.name for p in HERE.glob("*.py") if p.name not in NEVER_RUN)
    fake_home = tempfile.mkdtemp(prefix="ruleaudit-nohome-")
    print(f"== rule-audit portability: {len(scripts)} scripts, 2 states ==")
    print(f"   STATE B HOME={fake_home} (empty; stands in for a CI runner)\n")

    rows = []
    for s in scripts:
        argv = ARGV.get(s, [])
        rc_a, m_a = run(s, argv, None)
        rc_b, m_b = run(s, argv, fake_home)
        rows.append(
            {"script": s, "argv": argv, "rc_home": rc_a, "rc_nohome": rc_b,
             "marker_home": m_a, "marker_nohome": m_b}
        )
        flag = "SAME" if rc_a == rc_b else "DIFF"
        print(f"{flag}  {s:32} home rc={rc_a:<3} nohome rc={rc_b:<3}")
        print(f"        A: {m_a}")
        if rc_a != rc_b or m_a != m_b:
            print(f"        B: {m_b}")

    (HERE / "_i1_ci_portability.json").write_text(
        json.dumps(rows, indent=1) + "\n", encoding="utf-8", newline="\n"
    )
    same = sum(1 for r in rows if r["rc_home"] == r["rc_nohome"])
    print(f"\nSUCCESS:i1-portability {len(rows)} scripts measured, {same} rc-stable across states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
