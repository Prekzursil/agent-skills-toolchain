"""GROUNDING R2 census: current state vs round-1/round-2 claims.

Read-only. Emits JSON. Every set carries a detector control.
"""

import json
import os
import subprocess
import sys
import time

REPO = subprocess.run(
    ["git", "rev-parse", "--show-toplevel"],
    capture_output=True,
    text=True,
    check=True,
).stdout.strip()


def git(*args):
    r = subprocess.run(
        ["git", "-C", REPO, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return r.returncode, r.stdout, r.stderr


out = {
    "repo": REPO,
    "measured_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
}

rc, head, _ = git("rev-parse", "HEAD")
out["head"] = head.strip()

# ---- tracked set
rc, tracked_raw, _ = git("ls-files")
tracked = set(tracked_raw.splitlines())
out["tracked_count"] = len(tracked)

# ---- untracked, NOT ignored
rc, unt_raw, _ = git("ls-files", "--others", "--exclude-standard")
untracked = [p for p in unt_raw.splitlines() if p]
out["untracked_count"] = len(untracked)

# ---- ignored
rc, ign_raw, _ = git("ls-files", "--others", "--ignored", "--exclude-standard")
ignored = [p for p in ign_raw.splitlines() if p]
out["ignored_count"] = len(ignored)

# ---- DETECTOR CONTROL: the three sets must be disjoint, and a known file must land right
ctrl = {}
ctrl["README.md_tracked"] = "README.md" in tracked
ctrl["untracked_cap_ignored"] = len(set(untracked) & set(ignored))
ctrl["tracked_cap_untracked"] = len(tracked & set(untracked))
ctrl["tracked_cap_ignored"] = len(tracked & set(ignored))
# negative control: a uuid-shaped name must be in none of them
ctrl["nonexistent_in_any"] = (
    "zz_no_such_file_9f3a17c2.py" in tracked
    or "zz_no_such_file_9f3a17c2.py" in set(untracked)
    or "zz_no_such_file_9f3a17c2.py" in set(ignored)
)
out["controls_census"] = ctrl

# ---- did round-1's R1 action land? are the 45 cited probes tracked now?
cc_probes_tracked = sorted(
    p
    for p in tracked
    if p.startswith("command-center/")
    and os.path.basename(p).startswith("_")
    and p.endswith(".py")
)
cc_probes_root_tracked = [p for p in cc_probes_tracked if p.count("/") == 1]
out["command_center_root_probes_tracked"] = len(cc_probes_root_tracked)
out["command_center_any_probes_tracked"] = len(cc_probes_tracked)

# on-disk root probes
ondisk_root = []
ccdir = os.path.join(REPO, "command-center")
for name in os.listdir(ccdir):
    fp = os.path.join(ccdir, name)
    if os.path.isfile(fp) and name.startswith("_") and name.endswith(".py"):
        ondisk_root.append("command-center/" + name)
out["command_center_root_probes_ondisk"] = len(ondisk_root)
out["command_center_root_probes_untracked"] = sorted(set(ondisk_root) - tracked)
out["command_center_root_probes_untracked_n"] = len(set(ondisk_root) - tracked)

# ---- is the published-commands gate wired + tracked?
out["gate_script_tracked"] = (
    "command-center/slop-report/check_published_commands.py" in tracked
)
out["gate_baseline_tracked"] = (
    "command-center/slop-report/published-commands-baseline.json" in tracked
)
rc, wf, _ = git("show", "HEAD:.github/workflows/no-runtime-junk.yml")
out["gate_wired_in_head_blob"] = "gate-published-commands" in wf
out["gate_wired_control_absent_string"] = (
    "gate-zzz-not-a-real-step" in wf
)  # negative control

# ---- which slop-report artifacts are tracked?
sr = sorted(p for p in tracked if p.startswith("command-center/slop-report/"))
out["slop_report_tracked"] = sr
out["slop_report_tracked_n"] = len(sr)
srdir = os.path.join(REPO, "command-center", "slop-report")
sr_ondisk = sorted(
    "command-center/slop-report/" + n
    for n in os.listdir(srdir)
    if os.path.isfile(os.path.join(srdir, n))
)
out["slop_report_ondisk_n"] = len(sr_ondisk)
out["slop_report_untracked"] = sorted(set(sr_ondisk) - tracked)
out["slop_report_untracked_n"] = len(set(sr_ondisk) - tracked)

# ---- empty dirs (bucket d from R9) - still present?
empty_dirs = []
for root, dirs, files in os.walk(REPO):
    dirs[:] = [d for d in dirs if d not in (".git", "node_modules")]
    if not dirs and not files:
        empty_dirs.append(os.path.relpath(root, REPO).replace("\\", "/"))
out["empty_dirs"] = sorted(empty_dirs)
out["empty_dirs_n"] = len(empty_dirs)

# ---- caches (bucket c)
cache_stats = {}
for cname in ("__pycache__", ".pytest_cache", ".ruff_cache"):
    n = 0
    b = 0
    for root, dirs, files in os.walk(REPO):
        dirs[:] = [d for d in dirs if d != ".git"]
        if os.path.basename(root) == cname:
            for f in files:
                try:
                    b += os.path.getsize(os.path.join(root, f))
                    n += 1
                except OSError:
                    pass
    cache_stats[cname] = {"files": n, "bytes": b}
out["caches"] = cache_stats
out["caches_total_bytes"] = sum(v["bytes"] for v in cache_stats.values())
out["caches_total_files"] = sum(v["files"] for v in cache_stats.values())

# ---- untracked by top-level dir, and by age
now = time.time()
by_dir = {}
ages = []
for p in untracked:
    top = p.split("/")[0]
    by_dir[top] = by_dir.get(top, 0) + 1
    fp = os.path.join(REPO, p.replace("/", os.sep))
    try:
        age_min = (now - os.path.getmtime(fp)) / 60.0
    except OSError:
        age_min = None
    ages.append((p, age_min))
out["untracked_by_topdir"] = dict(sorted(by_dir.items(), key=lambda kv: -kv[1]))
fresh = [(p, round(a, 1)) for p, a in ages if a is not None and a < 30]
out["untracked_fresh_lt30min"] = sorted(fresh, key=lambda t: t[1])
out["untracked_fresh_lt30min_n"] = len(fresh)
stale = [(p, round(a, 1)) for p, a in ages if a is not None and a > 720]
out["untracked_stale_gt12h_n"] = len(stale)
out["untracked_stale_gt12h"] = sorted(stale, key=lambda t: -t[1])[:40]
# mtime CONTROL: a long-committed file must read old
for c in ("README.md", "AGENTS.md"):
    fp = os.path.join(REPO, c)
    if os.path.exists(fp):
        out.setdefault("mtime_controls", {})[c] = round(
            (now - os.path.getmtime(fp)) / 60.0, 1
        )

# ---- frozen evidence: dirty?
for path in ("command-center/casualty/probes", "command-center/p2-wave/probes"):
    rc, st, _ = git("status", "--porcelain", "--", path)
    n_files = len([p for p in tracked if p.startswith(path + "/")])
    out.setdefault("frozen", {})[path] = {
        "dirty_lines": len([x for x in st.splitlines() if x.strip()]),
        "tracked_files": n_files,
    }

json.dump(out, sys.stdout, indent=1)
