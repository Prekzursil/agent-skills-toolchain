"""Synthesis-review pass 2: re-measure the numeric claims in command-center/GRIND-STATUS.md."""

import json
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PY = sys.executable
out = {}


def run(args, cwd=REPO, timeout=600):
    p = subprocess.run(
        args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
        errors="replace",
    )
    return p.returncode, (p.stdout or ""), (p.stderr or "")


# --- 1. which workflows fire on push -> main (the section-1 last column) ----------
wfdir = REPO / ".github" / "workflows"
trig = {}
for f in sorted(wfdir.glob("*.yml")):
    t = f.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
    # crude but sufficient: the on: block is everything up to the first top-level key
    m = re.search(r"^on:\s*\n(.*?)^\S", t, flags=re.S | re.M)
    block = m.group(1) if m else ""
    trig[f.name] = {
        "push": bool(re.search(r"^  push:", block, flags=re.M)),
        "pull_request": bool(re.search(r"^  pull_request:", block, flags=re.M)),
        "workflow_dispatch": bool(
            re.search(r"^  workflow_dispatch:", block, flags=re.M)
        ),
    }
out["workflow_triggers"] = trig

# --- 2. B4: hook_predeploy_gate hazard / finding counts ---------------------------
rc, so, se = run([PY, "command-center/hook-audit/hook_predeploy_gate.py"])
blob = so + se
out["hook_predeploy"] = {
    "rc": rc,
    "HAZARD_count": len(re.findall(r"HAZARD", blob)),
    "numbers_in_tail": re.findall(r"(\d+)\s+(?:HAZARD|finding)", blob)[:6],
    "tail": "\n".join(blob.replace("\r\n", "\n").strip().split("\n")[-6:]),
}

# --- 3. B6: dirty working-tree rows ----------------------------------------------
rc, so, _ = run(["git", "status", "--porcelain", "-uall"])
rows = [r for r in so.split("\n") if r.strip()]
out["worktree"] = {
    "total": len(rows),
    "untracked": sum(1 for r in rows if r.startswith("??")),
    "modified": sum(1 for r in rows if not r.startswith("??")),
}

# --- 4. per-lane commit recency (the DOCS-died claim) ----------------------------
LANES = {
    "SSOT": "ssot",
    "HOOKRESEARCH": "hook-audit",
    "MCPRESEARCH": "mcp-audit",
    "RULERESEARCH": "rule-audit",
    "P2NEXT": "p2-next",
    "SLOP": "slop-report",
    "DOCS": "_LANE-DOCS",
    "SKILLS2": "SKILLS2",
    "CIGREEN": "interpreter",
}
rc, so, _ = run(["git", "log", "--since=36 hours ago", "--pretty=%H%x09%ct%x09%s"])
loglines = [x for x in so.split("\n") if x.strip()]
out["commits_36h_total"] = len(loglines)
now = time.time()
lane_stats = {}
for lane, needle in LANES.items():
    hits = [x for x in loglines if needle.lower() in x.lower()]
    # fall back to a path-scoped log
    rc2, so2, _ = run(
        ["git", "log", "--since=36 hours ago", "--pretty=%ct", "--", f"*{needle}*"]
    )
    ts = [int(x) for x in so2.split("\n") if x.strip().isdigit()]
    lane_stats[lane] = {
        "commits_36h_pathscoped": len(ts),
        "last_commit_hours_ago": round((now - max(ts)) / 3600, 1) if ts else None,
        "subject_hits": len(hits),
    }
out["lane_recency"] = lane_stats

# --- 5. the 6 orphan deliverables are now TRACKED --------------------------------
orphans = [
    "docs/_LANE-DOCS-GROUNDING.md",
    "docs/_LANE-DOCS-ADVERSARIAL.md",
    "docs/_LANE-DOCS-VERIFY.md",
    "command-center/hook-audit/_v4_VERIFIER-NOTES.md",
    "command-center/p2-next/P2NEXT-GROUNDING-R2.md",
    "command-center/p2-next/P2NEXT-VERIFY-R4.md",
    "command-center/p2-next/_g2_independent.py",
]
tracked = {}
for o in orphans:
    rc, so, _ = run(["git", "ls-files", "--error-unmatch", o])
    rc2, so2, _ = run(["git", "cat-file", "-s", f"HEAD:{o}"])
    tracked[o] = {
        "in_index": rc == 0,
        "in_HEAD": rc2 == 0,
        "head_bytes": so2.strip() if rc2 == 0 else None,
    }
out["orphans_now_tracked"] = tracked

# --- 6. SLOP published-command counts --------------------------------------------
rc, so, se = run([PY, "command-center/slop-report/check_published_commands.py"])
blob = (so + se).replace("\r\n", "\n")
out["published_commands"] = {
    "rc": rc,
    "counts": re.findall(r"(\d[\d,]*)\s+(?:published\s+)?commands?", blob)[:4],
    "docs": re.findall(r"(\d[\d,]*)\s+documents?", blob)[:4],
    "new_unrunnable": re.findall(r"(\d+)\s+NEW", blob)[:4],
    "tail": "\n".join(blob.strip().split("\n")[-4:]),
}

# --- 7. two GRIND-STATUS docs cross-link each other ------------------------------
a = (REPO / "command-center/GRIND-STATUS.md").read_text(
    encoding="utf-8", errors="replace"
)
b = (REPO / "docs/GRIND-STATUS.md").read_text(encoding="utf-8", errors="replace")
out["crosslink"] = {
    "cc_names_docs": "docs/GRIND-STATUS.md" in a,
    "docs_names_cc": "command-center/GRIND-STATUS.md" in b,
}

# --- 8. does any open PR touch skill-dual-write.yml? ------------------------------
pr_files = {}
for n in (281, 282, 283):
    rc, so, se = run(
        [
            "gh",
            "api",
            f"repos/Prekzursil/agent-skills-toolchain/pulls/{n}/files",
            "--jq",
            ".[].filename",
        ]
    )
    pr_files[n] = {"rc": rc, "files": [x for x in so.split("\n") if x.strip()]}
out["pr_files"] = pr_files
out["pr_touches_skill_dual_write"] = {
    n: any("skill-dual-write" in f for f in v["files"]) for n, v in pr_files.items()
}

print(json.dumps(out, indent=2, ensure_ascii=False))
