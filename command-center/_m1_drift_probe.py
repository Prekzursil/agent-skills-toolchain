"""LANE B / R-M02 probe: repo-vs-live drift for the monitorcore package.

Read-only. Compares every *.py in each repo copy against the LIVE deployed copy, twice:
raw bytes and CRLF-normalised bytes (windows-shell.md 8b -- a CRLF-only difference is not
behavioural drift). Detector control: also compares a repo copy against ITSELF (must be
0 differing) and against a deliberately mutated buffer (must be 1 differing).
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib

HOME = pathlib.Path(os.path.expanduser("~"))
REPO = pathlib.Path(__file__).resolve().parents[1]

LIVE = HOME / ".agents/skills/workflow-monitor/monitorcore"
COPIES = {
    "tools/monitorcore/monitorcore": REPO / "tools/monitorcore/monitorcore",
    "skills/workflow-monitor/monitorcore": REPO / "skills/workflow-monitor/monitorcore",
    ".agents/skills/workflow-monitor/monitorcore": REPO
    / ".agents/skills/workflow-monitor/monitorcore",
}


def h(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()[:12]


def norm(b: bytes) -> bytes:
    return b.replace(b"\r\n", b"\n")


def names(d: pathlib.Path) -> set[str]:
    return {p.name for p in d.glob("*.py")}


def compare(a: pathlib.Path, b: pathlib.Path) -> dict:
    na, nb = names(a), names(b)
    raw_diff, norm_diff = [], []
    for n in sorted(na & nb):
        ba, bb = (a / n).read_bytes(), (b / n).read_bytes()
        if h(ba) != h(bb):
            raw_diff.append(n)
            if h(norm(ba)) != h(norm(bb)):
                norm_diff.append(n)
    return {
        "count_a": len(na),
        "count_b": len(nb),
        "only_a": sorted(na - nb),
        "only_b": sorted(nb - na),
        "raw_differ": raw_diff,
        "raw_differ_n": len(raw_diff),
        "content_differ": norm_diff,
        "content_differ_n": len(norm_diff),
    }


out = {"live": str(LIVE), "live_exists": LIVE.is_dir(), "comparisons": {}}
for label, path in COPIES.items():
    out["comparisons"][label + " -> LIVE"] = (
        compare(path, LIVE) if path.is_dir() else {"error": "missing"}
    )

# detector control: identical dir vs itself must be 0
ctrl = compare(COPIES["skills/workflow-monitor/monitorcore"], COPIES["skills/workflow-monitor/monitorcore"])
out["control_self_vs_self_raw_differ_n"] = ctrl["raw_differ_n"]
# detector control: a known-mutated buffer must register as differing
src = COPIES["skills/workflow-monitor/monitorcore"] / "unified.py"
mutated = src.read_bytes() + b"\n# mutation\n"
out["control_mutated_detected"] = h(mutated) != h(src.read_bytes())

# also: repo mirror parity (skills vs .agents)
out["repo_mirror_skills_vs_agents"] = compare(
    COPIES["skills/workflow-monitor/monitorcore"],
    COPIES[".agents/skills/workflow-monitor/monitorcore"],
)
out["repo_pkgsrc_vs_skills"] = compare(
    COPIES["tools/monitorcore/monitorcore"],
    COPIES["skills/workflow-monitor/monitorcore"],
)

print(json.dumps(out, indent=2))
