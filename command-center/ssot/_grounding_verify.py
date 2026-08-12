"""Grounding-lane independent verification of docs/ssot/SSOT-CLONE-INVENTORY.md.

Read-only. Never writes to any checkout. Emits JSON to stdout.
"""
import json
import os
import subprocess

CANON = "C:/Users/Prekzursil/source/agent-skills-toolchain"
INTEG = "C:/Users/Prekzursil/source/ast-integrate"
SSOT = os.path.join(INTEG, "command-center", "ssot")

BRIEFED = [
    "C:/Users/Prekzursil/.claude/codexsrc-work",
    "C:/Users/Prekzursil/.claude/toolchain-audit",
    "C:/Users/Prekzursil/.claude/tw-merge-work",
    "C:/Users/Prekzursil/Documents/Playground",
    "C:/Users/Prekzursil/source/agent-skills-toolchain",
    "C:/Users/Prekzursil/source/ast-patch167",
    "C:/Users/Prekzursil/source/ast-integrate",
    "C:/Users/Prekzursil/work/agent-skills-toolchain-re",
    "D:/sast-depth/agent-skills-toolchain",
]

EXEC_DIRS = [
    "tools/mcp/cloud-hub",
    "tools/mcp/qdx-rush-mcp",
    "tools/mcp/search-hub",
    "tools/mcp/social-hub",
    "tools/scholarly-access-mcp/.venv",
]


def git(repo, *args, timeout=90):
    try:
        p = subprocess.run(
            ["git", "-C", repo] + list(args),
            capture_output=True, text=True, timeout=timeout,
        )
        return p.returncode, p.stdout.strip(), p.stderr.strip()
    except Exception as exc:  # noqa: BLE001
        return -1, "", repr(exc)


out = {}

# ---------------------------------------------------------------- V1 exec-vs-edit, CURRENT main
rc, cur_main, _ = git(INTEG, "rev-parse", "origin/main")
rc2, exec_head, _ = git(CANON, "rev-parse", "HEAD")
rc3, behind, _ = git(CANON, "rev-list", "--count", "HEAD..origin/main")
v1 = {
    "remote_main_now": cur_main,
    "executed_head": exec_head,
    "canonical_behind": behind,
    "inventory_measured_at_main": "ae8205a4aa1f8af4927affb6c1eacdaf61427a3f",
    "main_moved_since_inventory": cur_main != "ae8205a4aa1f8af4927affb6c1eacdaf61427a3f",
}
# the claim: 0 changed files under the 5 executed dirs between executed_head and current main
rc, changed, err = git(
    INTEG, "diff", "--name-only", f"{exec_head}..{cur_main}", "--", *EXEC_DIRS
)
v1["exec_dir_diff_rc"] = rc
v1["exec_dir_changed_files"] = [x for x in changed.splitlines() if x.strip()]
v1["exec_dir_changed_count"] = len(v1["exec_dir_changed_files"])
v1["exec_dir_diff_err"] = err[:400]

# BOTH-STATES CONTROL: the same differ over a dir that definitely DID change.
# If this also returns 0, the differ is broken and the 0 above means nothing.
rc, ctl, err = git(
    INTEG, "diff", "--name-only", f"{exec_head}..{cur_main}", "--", "command-center", "docs"
)
ctl_files = [x for x in ctl.splitlines() if x.strip()]
v1["control_changed_count"] = len(ctl_files)
v1["control_sample"] = ctl_files[:5]
v1["control_fires"] = len(ctl_files) > 0
# second control: whole-tree diff count
rc, allc, _ = git(INTEG, "diff", "--name-only", f"{exec_head}..{cur_main}")
v1["whole_tree_changed_count"] = len([x for x in allc.splitlines() if x.strip()])
v1["verdict"] = (
    "CONFIRMED-latent" if v1["exec_dir_changed_count"] == 0 and v1["control_fires"]
    else ("DETECTOR-BROKEN" if not v1["control_fires"] else "REFUTED-active-drift")
)
out["V1_exec_vs_edit"] = v1

# ---------------------------------------------------------------- V2 kind: worktree vs clone
v2 = []
for p in BRIEFED:
    row = {"path": p, "exists": os.path.isdir(p)}
    if row["exists"]:
        dotgit = os.path.join(p, ".git")
        row["dotgit_is_file"] = os.path.isfile(dotgit)
        row["dotgit_is_dir"] = os.path.isdir(dotgit)
        rc, common, _ = git(p, "rev-parse", "--path-format=absolute", "--git-common-dir")
        row["git_common_dir"] = common
        rc, br, _ = git(p, "rev-parse", "--abbrev-ref", "HEAD")
        row["head"] = br
        rc, url, _ = git(p, "remote", "get-url", "origin")
        row["origin"] = url
        row["origin_is_filesystem_path"] = bool(url) and not url.startswith(
            ("http", "git@", "ssh:")
        )
        # kind from two independent signals
        sig_a = "worktree" if row["dotgit_is_file"] else "clone"
        sig_b = (
            "worktree"
            if common and os.path.normcase(os.path.normpath(common))
            != os.path.normcase(os.path.normpath(os.path.join(p, ".git")))
            else "clone"
        )
        row["kind_sig_dotgit"] = sig_a
        row["kind_sig_commondir"] = sig_b
        row["kind_agree"] = sig_a == sig_b
        row["kind"] = sig_a
        rc, st, _ = git(p, "status", "--porcelain", "-uall")
        row["dirty_uall"] = len([x for x in st.splitlines() if x.strip()])
        rc, stash, _ = git(p, "stash", "list")
        row["stash"] = len([x for x in stash.splitlines() if x.strip()])
    v2.append(row)
out["V2_kind"] = v2

# ---------------------------------------------------------------- V3 do the 25 still exist
try:
    a25 = json.load(open(os.path.join(SSOT, "all25.json")))
    rows = a25.get("rows", [])
    missing = []
    present = 0
    for r in rows:
        p = r.get("path") or r.get("checkout") or ""
        if p and os.path.isdir(p):
            present += 1
        elif p:
            missing.append(p)
    out["V3_fleet_existence"] = {
        "rows_in_all25": len(rows),
        "still_present": present,
        "now_missing": missing,
        "sample_row_keys": list(rows[0].keys()) if rows else [],
    }
except Exception as exc:  # noqa: BLE001
    out["V3_fleet_existence"] = {"error": repr(exc)}

# ---------------------------------------------------------------- V4 canonical-store visibility
# Independent probe of "unique / exists nowhere else": ask the CANONICAL store whether it
# has the object. Mechanically different from the inventory's 18-store --batch-check.
def canon_has(sha):
    rc, _, _ = git(CANON, "cat-file", "-e", f"{sha}^{{commit}}")
    return rc == 0


rc, canon_head, _ = git(CANON, "rev-parse", "HEAD")
v4 = {
    "control_fabricated_sha_present": canon_has("dead" * 10),
    "control_canonical_head_present": canon_has(canon_head),
}
v4["control_both_states_ok"] = (
    v4["control_canonical_head_present"] and not v4["control_fabricated_sha_present"]
)
out["V4_controls"] = v4

print(json.dumps(out, indent=2, default=str))
