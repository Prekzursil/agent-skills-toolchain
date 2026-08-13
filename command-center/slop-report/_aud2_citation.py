"""AUDIT probe 2: reconstruct the builder's cited/uncited split WITHOUT circularity.

My probe 1 had a real defect: its corpus was `git ls-files command-center/` only, so a
citer outside command-center (e.g. platform/lib/test_schema_resolver.py) was invisible.
The control caught it -- positive_expected_citer_present was False.

Fix: use `git grep -F -l <name> <pre-lane-tree>` over the WHOLE tree at the commit BEFORE
the lane's first commit. That is (a) the tree the builder actually measured against,
(b) mechanically different from a python read of the worktree, and (c) immune to the
circularity where the lane's own report now cites all 45 names.
"""

import json
import re
import subprocess
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
CC = REPO / "command-center"


def git(*args):
    r = subprocess.run(
        ["git", "-C", str(REPO), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return r.returncode, r.stdout, r.stderr


out = {}
rc, so, _ = git("rev-parse", "f5b596e6^")
pre = so.strip()
out["pre_lane_tree"] = pre

on_disk = sorted(p.name for p in CC.glob("_*.py") if p.is_file())
out["on_disk_count"] = len(on_disk)

rc, so, _ = git("ls-files", "command-center/")
pat = re.compile(r"^command-center/_[A-Za-z0-9_]+\.py$")
tracked_probes = sorted(Path(x).name for x in so.splitlines() if pat.match(x))
tracked_set = set(tracked_probes)
out["tracked_now"] = len(tracked_probes)


def grep_tree(tree, name):
    # -F fixed string, -l names only, on a TREE (not the worktree)
    rc, so, _ = git("grep", "-F", "-l", name, tree)
    if rc != 0:
        return []
    return [x.split(":", 1)[1] for x in so.splitlines() if ":" in x]


cited, uncited, citers_map = [], [], {}
for n in on_disk:
    hits = grep_tree(pre, n)
    # a probe script naming ITSELF in a committed copy is not an external citation;
    # at the pre-lane tree none of the 123 were tracked, so no self-hit is possible.
    if hits:
        cited.append(n)
        citers_map[n] = hits
    else:
        uncited.append(n)

out["cited_count_pre_lane"] = len(cited)
out["cited_bytes_pre_lane"] = sum((CC / n).stat().st_size for n in cited)
out["uncited_count_pre_lane"] = len(uncited)

# CONTROL, both states, on the SAME mechanism
ctrl_pos = grep_tree(pre, "_gen_schema_substrate.py")
ctrl_neg = grep_tree(pre, "_zzz_definitely_not_a_real_probe_9182.py")
out["control"] = {
    "positive_hits": len(ctrl_pos),
    "positive_expected_citer_present": any(
        "test_schema_resolver" in h for h in ctrl_pos
    ),
    "positive_sample": sorted(ctrl_pos)[:4],
    "negative_hits": len(ctrl_neg),
    "states_distinguishable": len(ctrl_pos) > 0 and len(ctrl_neg) == 0,
}

# THE AUDIT QUESTION: does the committed set == the cited set?
out["cited_but_NOT_committed"] = {
    n: citers_map[n] for n in sorted(set(cited) - tracked_set)
}
out["committed_but_NOT_cited"] = sorted(tracked_set - set(cited))
out["set_equality"] = set(cited) == tracked_set

print(json.dumps(out, indent=2))
Path(__file__).with_suffix(".out.json").write_text(
    json.dumps(out, indent=2), encoding="utf-8", newline="\n"
)
