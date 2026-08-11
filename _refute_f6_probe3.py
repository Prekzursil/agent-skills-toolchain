#!/usr/bin/env python3
"""refute/codex-stubs/F6 -- probe 3: is gate-skill-surface-manifest ENFORCED?

Mechanically different from the claim's probe (which ran the CLI in a scratch clone
and read an exit code). This one never runs the CLI at all: it does SET MEMBERSHIP
between (a) the required_status_checks contexts in the repo's active ruleset and
(b) the job display names declared in every workflow blob, then cross-checks with
the check-run names GitHub actually reported on a real merged PR head.
"""

from __future__ import annotations

import json
import pathlib
import re
import subprocess

REPO = pathlib.Path(r"C:/Users/Prekzursil/source/ast-integrate")


def sh(*args: str) -> str:
    return subprocess.run(
        list(args), cwd=str(REPO), capture_output=True, check=True
    ).stdout.decode("utf-8", "replace")


# (a) required contexts, from the active ruleset
rs = json.loads(sh("gh", "api", "repos/:owner/:repo/rulesets/18297434"))
required = set()
for rule in rs["rules"]:
    if rule["type"] == "required_status_checks":
        for c in rule["parameters"]["required_status_checks"]:
            required.add(c["context"])

# (b) job display names, from each workflow blob
jobs: dict[str, list[str]] = {}
for wf in sorted(pathlib.Path(REPO, ".github/workflows").glob("*.yml")):
    text = sh("git", "cat-file", "-p", f"HEAD:.github/workflows/{wf.name}")
    jobs[wf.name] = re.findall(r"^    name: (.+)$", text, re.M)

all_jobs = {n for v in jobs.values() for n in v}

print("== (a) REQUIRED contexts in ruleset 'main quality gate' ==")
for c in sorted(required):
    print(f"   REQUIRED  {c}")

print("\n== (b) job display names per workflow (blob) ==")
for wf, names in jobs.items():
    for n in names:
        mark = "REQUIRED" if n in required else "not-required"
        print(f"   {mark:<13} {wf:<26} {n}")

print("\n== DETECTOR CONTROL ==")
print(f"   required contexts found      : {len(required)} (nonzero => API path works)")
print(f"   job names found in blobs     : {len(all_jobs)} (nonzero => regex works)")
matched = required & all_jobs
print(f"   required contexts that MATCH a job name: {len(matched)}/{len(required)}")
print(f"   unmatched required contexts  : {sorted(required - all_jobs)}")

print("\n== VERDICT (set membership) ==")
target = "gate-skill-dual-write"
print(f"   '{target}' is a declared job     : {target in all_jobs}")
print(f"   '{target}' is a REQUIRED check   : {target in required}")
print(
    f"   => a red gate-skill-surface-manifest step BLOCKS merge: {target in required}"
)

# (c) cross-check: names GitHub actually reported on a real merged PR head
sha = sh("git", "rev-parse", "HEAD").strip()
try:
    cr = json.loads(sh("gh", "api", f"repos/:owner/:repo/commits/{sha}/check-runs"))
    print(f"\n== (c) check-runs actually reported on {sha[:9]} ==")
    for run in cr.get("check_runs", []):
        print(f"   {run['name']}  -> {run.get('conclusion')}")
except subprocess.CalledProcessError as exc:
    print(f"\n== (c) check-runs: NOT-CHECKED ({exc.stderr.decode()[:120].strip()}) ==")
