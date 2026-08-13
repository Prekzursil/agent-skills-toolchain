"""Stranded-commit verification, batched.

Fix vs v1: one `git cat-file --batch-check` process per store instead of one `cat-file -e`
spawn per commit (v1 needed ~16k Windows spawns and blew a 900s budget).
Read-only. Both-states controls on every detector.
"""

import json
import os
import subprocess

CANON = "C:/Users/Prekzursil/source/agent-skills-toolchain"

SCRATCH = [
    "C:/Users/Prekzursil/.claude/agent-worktrees-salvage/agent-1521081161/_b5-toolchain",
    "C:/Users/Prekzursil/.claude/agent-worktrees-salvage/agent-425276811/ast",
    "C:/Users/Prekzursil/source/_wu/CRCP-SEC",
    "C:/Users/Prekzursil/work/agent-skills-toolchain-re",
]

FAKE = "dead" * 10  # 40 hex chars, valid shape, cannot exist


def git(repo, *args, timeout=180):
    try:
        p = subprocess.run(
            ["git", "-C", repo] + list(args),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return p.returncode, p.stdout.strip(), p.stderr.strip()
    except Exception as exc:  # noqa: BLE001
        return -1, "", repr(exc)


def batch_present(repo, shas, timeout=300):
    """Return set of shas that EXIST as commits in `repo`. One process."""
    if not shas:
        return set()
    payload = "\n".join(shas) + "\n"
    try:
        p = subprocess.run(
            ["git", "-C", repo, "cat-file", "--batch-check"],
            input=payload,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except Exception:  # noqa: BLE001
        return set()
    present = set()
    for line in p.stdout.splitlines():
        parts = line.split()
        # present: "<sha> commit <size>"; absent: "<sha> missing"
        if len(parts) >= 2 and parts[1] == "commit":
            present.add(parts[0])
    return present


out = {"controls": {}, "checkouts": []}

rc, canon_head, _ = git(CANON, "rev-parse", "HEAD")

# ---- both-states control on the BATCH detector (the instrument actually used)
ctl = batch_present(CANON, [canon_head, FAKE])
out["controls"]["batch_sees_real_head"] = canon_head in ctl
out["controls"]["batch_rejects_fake"] = FAKE not in ctl
out["controls"]["batch_ok"] = (
    out["controls"]["batch_sees_real_head"] and out["controls"]["batch_rejects_fake"]
)

# ---- remote tips (reachability, not just tip equality)
rc, ls, err = git(CANON, "ls-remote", "--heads", "--tags", "origin", timeout=240)
remote_tips = [ln.split()[0] for ln in ls.splitlines() if ln.split()]
out["controls"]["remote_tip_count"] = len(remote_tips)
out["controls"]["ls_remote_err"] = err[:200]
# which remote tips does canonical actually have locally (for reachability tests)
canon_has_tips = batch_present(CANON, remote_tips)
out["controls"]["remote_tips_present_in_canonical"] = len(canon_has_tips)

for path in SCRATCH:
    row = {"path": path, "exists": os.path.isdir(path)}
    if not row["exists"]:
        out["checkouts"].append(row)
        continue
    rc, common, _ = git(path, "rev-parse", "--path-format=absolute", "--git-common-dir")
    row["git_common_dir"] = common
    row["kind"] = "worktree" if os.path.isfile(os.path.join(path, ".git")) else "clone"
    rc, head, _ = git(path, "rev-parse", "HEAD")
    row["head"] = head
    rc, st, _ = git(path, "status", "--porcelain", "-uall")
    row["dirty_uall"] = len([x for x in st.splitlines() if x.strip()])
    rc, stash, _ = git(path, "stash", "list")
    row["stash"] = len([x for x in stash.splitlines() if x.strip()])
    rc, url, _ = git(path, "remote", "get-url", "origin")
    row["origin"] = url

    rc, rl, err = git(path, "rev-list", "--all", "--reflog")
    shas = [x for x in rl.splitlines() if x.strip()]
    row["reachable_commit_count"] = len(shas)
    row["rev_list_err"] = err[:200]

    # ONE batch call against canonical
    in_canon = batch_present(CANON, shas)
    row["present_in_canonical"] = len(in_canon)
    candidates = [s for s in shas if s not in in_canon]
    row["absent_from_canonical"] = len(candidates)

    # of those, which are NOT a remote tip (tip equality is a weak but cheap second filter)
    tipset = set(remote_tips)
    stranded = [s for s in candidates if s not in tipset]
    row["stranded_count"] = len(stranded)

    # describe up to 25, newest first by committer date
    desc = []
    for sha in stranded[:25]:
        rc, meta, _ = git(
            path, "show", "-s", "--format=%h|%ad|%an|%s", "--date=short", sha
        )
        desc.append(meta)
    row["stranded_sample"] = desc
    out["checkouts"].append(row)

out["total_stranded"] = sum(c.get("stranded_count", 0) for c in out["checkouts"])
print(json.dumps(out, indent=2, default=str))
