"""SYNTHESIS-REVIEW: whole-repo ruff, classified tracked vs untracked, with a detector control."""
import json
import os
import re
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
out = {}


def run(args, cwd=ROOT, timeout=900):
    p = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout, p.stderr


rc, so, se = run(["uvx", "ruff@0.15.17", "check", ".", "--output-format", "concise"])
lines = [ln for ln in (so or "").splitlines() if re.match(r"^[^\s].*:\d+:\d+: ", ln)]
out["ruff_rc"] = rc
out["n_findings"] = len(lines)

rc2, tracked_out, _ = run(["git", "ls-files"])
tracked = {p.replace("/", os.sep).lower() for p in tracked_out.splitlines()}

tracked_hits, untracked_hits = [], []
for ln in lines:
    path = ln.split(":", 1)[0].strip()
    norm = os.path.normpath(path).lower()
    (tracked_hits if norm in tracked else untracked_hits).append(ln)
out["tracked_findings"] = tracked_hits
out["n_tracked"] = len(tracked_hits)
out["n_untracked"] = len(untracked_hits)
out["untracked_sample"] = untracked_hits[:15]

# DETECTOR CONTROL: the tracked-set matcher must be able to see a tracked path.
# Feed it a synthetic finding line on a known-tracked file and require classification=tracked.
probe = "tools/measure-guard/launchpath.py:1:1: F401 synthetic"
pn = os.path.normpath(probe.split(":", 1)[0]).lower()
out["control_matcher_sees_tracked_file"] = pn in tracked
# and a known-untracked one must classify untracked
probe2 = "command-center/_synthrev_ruff.py:1:1: F401 synthetic"
pn2 = os.path.normpath(probe2.split(":", 1)[0]).lower()
out["control_matcher_sees_untracked_file"] = pn2 not in tracked

out["verdict"] = (
    "SUCCESS:synthrev-ruff tracked=%d untracked=%d; matcher control both-states OK"
    % (len(tracked_hits), len(untracked_hits))
    if out["control_matcher_sees_tracked_file"] and out["control_matcher_sees_untracked_file"]
    else "FAILED:synthrev-ruff matcher control did not pass"
)
print(json.dumps(out, indent=1))
