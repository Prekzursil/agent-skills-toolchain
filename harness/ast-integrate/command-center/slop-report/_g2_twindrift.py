"""GROUNDING R2: the rules/ twin surface -- is it guarded, and has it drifted?

hooks/** <-> agent-self/config/hooks/** has a pinned-twin parity gate
(ci/tests/test_deployed_hook_twin_parity.py). rules/** <-> agent-self/config/rules/**
is deployed by the SAME two bootstraps and has NO such gate. Measure the drift.

Read-only. Diffs are summarised (line counts + first differing line), never dumped wholesale.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import subprocess
import sys
import time

REPO = subprocess.run(
    ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True
).stdout.strip()


def git(*args):
    return subprocess.run(
        ["git", "-C", REPO, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stdout


def read_lf(p: str) -> list[str] | None:
    try:
        with open(p, "rb") as fh:
            return (
                fh.read()
                .replace(b"\r\n", b"\n")
                .decode("utf-8", "replace")
                .splitlines()
            )
    except OSError:
        return None


def sha_lf(p: str) -> str | None:
    try:
        with open(p, "rb") as fh:
            return hashlib.sha256(fh.read().replace(b"\r\n", b"\n")).hexdigest()[:16]
    except OSError:
        return None


out = {
    "repo": REPO,
    "measured_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "head": git("rev-parse", "HEAD").strip(),
}

tracked = set(git("ls-files").splitlines())

# ---- which twin surfaces exist, and is each GUARDED?
guard = "ci/tests/test_deployed_hook_twin_parity.py"
guard_src = ""
gp = os.path.join(REPO, guard.replace("/", os.sep))
if os.path.exists(gp):
    guard_src = open(gp, encoding="utf-8", errors="replace").read()
out["guard_file"] = guard
out["guard_tracked"] = guard in tracked
out["guard_mentions_rules_tree"] = "config/rules/" in guard_src
out["guard_pinned_pairs"] = guard_src.count('"hooks/')
# CONTROL: the guard must mention the hooks tree it DOES cover -- else my reader is broken
out["controls"] = {
    "guard_mentions_hooks_tree": "agent-self/config/hooks/" in guard_src,
    "guard_src_nonempty": len(guard_src) > 500,
}

# ---- enumerate every repo-root/agent-self twin pair
pairs = []
for p in sorted(tracked):
    if not p.startswith("agent-self/config/"):
        continue
    twin = p[len("agent-self/config/") :]
    if twin in tracked:
        pairs.append((twin, p))

out["twin_pairs_total"] = len(pairs)

by_tree: dict[str, dict] = {}
drifted = []
for a, b in pairs:
    tree = a.split("/")[0]
    ha = sha_lf(os.path.join(REPO, a.replace("/", os.sep)))
    hb = sha_lf(os.path.join(REPO, b.replace("/", os.sep)))
    rec = by_tree.setdefault(tree, {"pairs": 0, "identical": 0, "drifted": 0})
    rec["pairs"] += 1
    if ha == hb:
        rec["identical"] += 1
    else:
        rec["drifted"] += 1
        la = read_lf(os.path.join(REPO, a.replace("/", os.sep))) or []
        lb = read_lf(os.path.join(REPO, b.replace("/", os.sep))) or []
        sm = difflib.SequenceMatcher(None, la, lb)
        added = sum(
            j2 - j1
            for tag, _, _, j1, j2 in sm.get_opcodes()
            if tag in ("insert", "replace")
        )
        removed = sum(
            i2 - i1
            for tag, i1, i2, _, _ in sm.get_opcodes()
            if tag in ("delete", "replace")
        )
        first = None
        for tag, i1, _i2, j1, _j2 in sm.get_opcodes():
            if tag != "equal":
                first = {
                    "op": tag,
                    "repo_line": i1 + 1,
                    "agentself_line": j1 + 1,
                    "repo_text": (la[i1][:120] if i1 < len(la) else ""),
                    "agentself_text": (lb[j1][:120] if j1 < len(lb) else ""),
                }
                break
        drifted.append(
            {
                "repo_path": a,
                "agentself_path": b,
                "repo_lines": len(la),
                "agentself_lines": len(lb),
                "lines_added_in_agentself": added,
                "lines_removed_vs_repo": removed,
                "similarity": round(sm.ratio(), 3),
                "first_difference": first,
                "guarded_by_pinned_twin_test": f'"{a}"' in guard_src,
            }
        )

out["by_tree"] = dict(sorted(by_tree.items(), key=lambda kv: -kv[1]["pairs"]))
out["drifted_n"] = len(drifted)
out["drifted"] = sorted(drifted, key=lambda d: d["similarity"])
out["drifted_unguarded_n"] = sum(
    1 for d in drifted if not d["guarded_by_pinned_twin_test"]
)

# ---- does the guard actually pass right now? (execute it, do not assume)
r = subprocess.run(
    [
        sys.executable,
        "-m",
        "pytest",
        guard,
        "-q",
        "--no-header",
        "-p",
        "no:cacheprovider",
    ],
    cwd=REPO,
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
)
out["guard_execution"] = {
    "rc": r.returncode,
    "tail": (r.stdout or "")[-600:],
}

json.dump(out, sys.stdout, indent=1)
