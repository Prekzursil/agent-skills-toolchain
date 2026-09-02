"""AUDIT probe 7: the 51-vs-52 divergence. Which tree does the split actually count?

My probe-5 control found: worktree => 51 blocked units, COMMITTED HEAD => 52, and the single
differing unit is ADV-0041. If ADV-0041 is BLOCKED in the committed tree, then the committed
rail-blocked remainder is 42, not 41 -- and 41 is only true of a worktree carrying a sibling's
UNCOMMITTED edit. That matters because 41 is the number the owner is told to price `codex login`
against.

Prints ADV-0041's state at: worktree, HEAD, the builder's last commit (d6cb3c8c), the builder's
first commit (899ff779), and the pre-builder base (899ff779^). Plus who last committed the file.
"""

from __future__ import annotations

import io
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
P = "command-center/adversarial/ADV-0041-path-and-identity-disclosure.json"


def sh(*args):
    return subprocess.run(
        list(args), cwd=REPO, capture_output=True, text=True, encoding="utf-8"
    )


def state_at(rev):
    r = sh("git", "show", f"{rev}:{P}")
    if r.returncode != 0:
        return f"<absent at {rev}>"
    o = json.loads(r.stdout)
    rv = o.get("reviewer") or {}
    f = o.get("failure") or {}
    return {
        "state": o.get("state"),
        "reviewer.verdict": rv.get("verdict"),
        "reviewer.vendor": rv.get("vendor"),
        "reviewer.independent": rv.get("independent"),
        "blocked_on": (f.get("blocked_on") or "")[:180],
        "classification": f.get("classification"),
    }


wt = json.load(io.open(REPO / P, encoding="utf-8"))
rvw = wt.get("reviewer") or {}
fw = wt.get("failure") or {}
print(
    "WORKTREE   :",
    json.dumps(
        {
            "state": wt.get("state"),
            "reviewer.verdict": rvw.get("verdict"),
            "reviewer.vendor": rvw.get("vendor"),
            "reviewer.independent": rvw.get("independent"),
            "blocked_on": (fw.get("blocked_on") or "")[:180],
            "classification": fw.get("classification"),
        },
        indent=1,
    ),
)

for rev in ("HEAD", "d6cb3c8c", "899ff779", "899ff779^"):
    print(f"\n{rev:12}:", json.dumps(state_at(rev), indent=1))

print("\n--- last commits touching the file ---")
print(sh("git", "log", "--oneline", "-5", "--", P).stdout)
print("--- is it dirty? ---")
print(sh("git", "status", "--porcelain", "--", P).stdout or "(clean)")
