"""Diff the 8 always-on rules repo-vs-live and fingerprint their section headings.

Purpose: determine WHICH tree the turn-0 injection reads from, by comparing the
section list of each tree against the section list visible in the agent's own
injected context (recorded separately in the artifact).
"""

import difflib
import hashlib
import os
import re

REPO = r"C:/Users/Prekzursil/source/ast-integrate/rules"
LIVE = r"C:/Users/Prekzursil/.claude/rules"

ALWAYS_ON = [
    "common/agents.md",
    "common/bash-hud-and-terminal-emit.md",
    "common/cross-vendor-dispatch.md",
    "common/fan-out-contract.md",
    "common/harness-vcs-hygiene.md",
    "common/single-signal-verification.md",
    "common/stale-megapr-reconcile.md",
    "common/windows-shell.md",
]


def read(p):
    with open(p, "rb") as fh:
        return fh.read().replace(b"\r\n", b"\n").decode("utf-8", errors="replace")


def headings(t):
    return [ln.strip() for ln in t.split("\n") if re.match(r"^#{1,3}\s", ln)]


for rel in ALWAYS_ON:
    rp, lp = os.path.join(REPO, rel), os.path.join(LIVE, rel)
    rtxt, ltxt = read(rp), read(lp)
    print("=" * 78)
    print(rel)
    print(
        "  repo sha %s  %d chars %d headings"
        % (
            hashlib.sha256(rtxt.encode()).hexdigest()[:12],
            len(rtxt),
            len(headings(rtxt)),
        )
    )
    print(
        "  live sha %s  %d chars %d headings"
        % (
            hashlib.sha256(ltxt.encode()).hexdigest()[:12],
            len(ltxt),
            len(headings(ltxt)),
        )
    )
    if rtxt == ltxt:
        print("  IDENTICAL")
        continue
    rh, lh = headings(rtxt), headings(ltxt)
    only_r = [h for h in rh if h not in lh]
    only_l = [h for h in lh if h not in rh]
    print("  headings ONLY in repo (%d):" % len(only_r))
    for h in only_r:
        print("     +", h[:100])
    print("  headings ONLY in live (%d):" % len(only_l))
    for h in only_l:
        print("     -", h[:100])
    # first differing line for orientation
    sm = difflib.unified_diff(
        ltxt.split("\n"), rtxt.split("\n"), "LIVE", "REPO", n=0, lineterm=""
    )
    shown = 0
    for line in sm:
        if line.startswith(("---", "+++", "@@")):
            continue
        print("     dif", line[:150])
        shown += 1
        if shown >= 8:
            print("     ... (truncated)")
            break
