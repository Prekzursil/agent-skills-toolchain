"""Exact per-file token counts for the always-on set, live tree and repo tree."""

import os

import tiktoken

ENC = tiktoken.get_encoding("cl100k_base")
LIVE = r"C:/Users/Prekzursil/.claude/rules/common"
REPO = r"C:/Users/Prekzursil/source/ast-integrate/rules/common"
NAMES = [
    "windows-shell.md",
    "single-signal-verification.md",
    "fan-out-contract.md",
    "bash-hud-and-terminal-emit.md",
    "cross-vendor-dispatch.md",
    "harness-vcs-hygiene.md",
    "stale-megapr-reconcile.md",
    "agents.md",
]


def tok(p):
    with open(p, "rb") as fh:
        return len(
            ENC.encode(
                fh.read().replace(b"\r\n", b"\n").decode("utf-8", errors="replace")
            )
        )


tl = tr = 0
print("%-38s %8s %8s" % ("file", "LIVE", "REPO"))
for n in NAMES:
    a, b = tok(os.path.join(LIVE, n)), tok(os.path.join(REPO, n))
    tl += a
    tr += b
    print("%-38s %8d %8d" % (n, a, b))
print("%-38s %8d %8d" % ("TOTAL", tl, tr))

print("\nunconditional memory files:")
for lbl, p in [
    ("~/.claude/CLAUDE.md", r"C:/Users/Prekzursil/.claude/CLAUDE.md"),
    ("~/.claude/AGENTS.md", r"C:/Users/Prekzursil/.claude/AGENTS.md"),
    ("~/CLAUDE.md", r"C:/Users/Prekzursil/CLAUDE.md"),
]:
    print("  %-24s %6d" % (lbl, tok(p)))
