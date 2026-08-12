"""Content-level check of the stranded security fixes.

REPO-TOPOLOGY.md rule 4: never use commit ancestry as delete authorisation -- squash-merge makes
merged branches report as ahead. Compare CONTENT with `git cat-file -p <rev>:<path>`
(never `git archive`: it applies export-time EOL conversion and returns CRLF on this box).

Question answered: for each stranded commit, are the files it touched byte-identical on
origin/main, a superset, or genuinely absent?
Read-only.
"""
import hashlib
import json
import os
import subprocess

CANON = "C:/Users/Prekzursil/source/agent-skills-toolchain"
INTEG = "C:/Users/Prekzursil/source/ast-integrate"

TARGETS = [
    # (scratch checkout, sha, label)
    ("C:/Users/Prekzursil/source/_wu/CRCP-SEC", "c7ffc20f",
     "fix(crcp): scope OpenAI bearer to allowlist  [SECURITY]"),
    ("C:/Users/Prekzursil/.claude/agent-worktrees-salvage/agent-425276811/ast", "4a4f7c97",
     "fix(mcpctl): strip control bytes BEFORE redacting  [SECURITY]"),
    ("C:/Users/Prekzursil/.claude/agent-worktrees-salvage/agent-1521081161/_b5-toolchain",
     "80130e1f", "feat(mcp-manager): dead-MCP detector"),
]


def git_raw(repo, *args, timeout=120):
    """Return (rc, stdout_bytes)."""
    try:
        p = subprocess.run(
            ["git", "-C", repo] + list(args), capture_output=True, timeout=timeout
        )
        return p.returncode, p.stdout
    except Exception:  # noqa: BLE001
        return -1, b""


def git(repo, *args, timeout=120):
    rc, o = git_raw(repo, *args, timeout=timeout)
    return rc, o.decode("utf-8", "replace").strip()


def norm_sha(data):
    """Hash with line endings normalised, so CRLF-vs-LF is not mistaken for a content diff."""
    if data is None:
        return None
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()[:16]


out = {"controls": {}, "targets": []}

# ---- CONTROL, both states: the blob reader must (a) return content for a path that exists on
# main, and (b) return nothing for a path that does not. A reader that is silent in both states
# would make every file look "absent from main".
rc, real = git_raw(INTEG, "cat-file", "-p", "origin/main:README.md")
rc2, bogus = git_raw(INTEG, "cat-file", "-p", "origin/main:__no_such_file_xyz__.md")
out["controls"]["reader_returns_real_file"] = len(real) > 0
out["controls"]["reader_empty_on_missing"] = len(bogus) == 0
out["controls"]["reader_ok"] = (
    out["controls"]["reader_returns_real_file"] and out["controls"]["reader_empty_on_missing"]
)

for repo, sha, label in TARGETS:
    row = {"scratch": repo, "sha": sha, "label": label, "exists": os.path.isdir(repo)}
    if not row["exists"]:
        out["targets"].append(row)
        continue
    rc, files = git(repo, "diff-tree", "--no-commit-id", "--name-only", "-r", sha)
    paths = [x for x in files.splitlines() if x.strip()]
    row["files_touched"] = len(paths)
    detail = []
    absent = same = differs = 0
    for p in paths:
        rc_s, scratch_blob = git_raw(repo, "cat-file", "-p", f"{sha}:{p}")
        rc_m, main_blob = git_raw(INTEG, "cat-file", "-p", f"origin/main:{p}")
        s_hash = norm_sha(scratch_blob) if rc_s == 0 else None
        m_hash = norm_sha(main_blob) if rc_m == 0 and len(main_blob) > 0 else None
        if m_hash is None:
            state = "ABSENT_FROM_MAIN"
            absent += 1
        elif m_hash == s_hash:
            state = "BYTE_IDENTICAL_ON_MAIN"
            same += 1
        else:
            state = "DIFFERS"
            differs += 1
        detail.append({
            "path": p, "state": state,
            "scratch_bytes": len(scratch_blob), "main_bytes": len(main_blob),
        })
    row["absent_from_main"] = absent
    row["byte_identical_on_main"] = same
    row["differs"] = differs
    row["detail"] = detail
    if absent == 0 and differs == 0:
        row["verdict"] = "REDUNDANT - every touched file already identical on main"
    elif absent > 0:
        row["verdict"] = f"AT RISK - {absent} file(s) absent from main"
    else:
        row["verdict"] = f"DIVERGED - {differs} file(s) differ; needs two-directional line diff"
    out["targets"].append(row)

print(json.dumps(out, indent=2, default=str))
