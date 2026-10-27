"""LANE D1 re-verify: count the 29 contracted artifacts per-tree AND against the committed repo.

Read-only. No catalog writes. Prints JSON.
"""
import json
import os
import re
import subprocess
import sys

HOME = "C:/Users/Prekzursil"
TREE1 = HOME + "/.claude/harness-restore-20260806"
TREE2 = HOME + "/.claude/platform-redesign-2026-07-19"
REPO = HOME + "/source/ast-integrate"
PROMPTS = TREE1 + "/_USER-PROMPTS.md"

MIN_BYTES = 2048  # audit's own "non-trivial (<2KB)" rule


def contracted_items():
    """Parse the numbered artifact list straight out of the contract, not from memory.

    ANCHORED ON CONTENT, not line offsets. `_USER-PROMPTS.md` contains lone \\r bytes, so
    Python universal-newline reading yields DIFFERENT line numbers than `grep -n`
    (measured: grep line 7829 == a different Python index). Any absolute-offset slice into
    this file is therefore reader-dependent and unsafe.
    """
    with open(PROMPTS, "r", encoding="utf-8", errors="replace", newline="") as fh:
        raw = fh.read()
    lines = re.split(r"\r\n|\n", raw)  # \n-only + CRLF, matching grep's line model
    start = None
    for i, ln in enumerate(lines):
        if ln.strip() == "## Required artifacts":
            start = i
            break
    if start is None:
        raise SystemExit("ANCHOR NOT FOUND: '## Required artifacts'")
    block = []
    for ln in lines[start + 1 : start + 60]:
        if ln.strip().startswith("The JSON option universe must be valid"):
            break
        block.append(ln)
    items = []
    for ln in block:
        m = re.match(r"^(\d{1,2})\.\s+(.*)$", ln.strip())
        if m:
            n = int(m.group(1))
            body = m.group(2)
            fm = re.match(r"^`([^`]+)`", body)
            items.append({"n": n, "name": fm.group(1) if fm else None, "raw": body})
    return items


def repo_tracked_basenames():
    out = subprocess.run(
        ["git", "-C", REPO, "ls-tree", "-r", "--name-only", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.split("\n")
    idx = {}
    for p in out:
        p = p.strip()
        if not p:
            continue
        idx.setdefault(os.path.basename(p), []).append(p)
    return idx


def repo_worktree_basenames():
    idx = {}
    for root, dirs, files in os.walk(REPO):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", "node_modules", ".venv")]
        for f in files:
            idx.setdefault(f, []).append(os.path.relpath(os.path.join(root, f), REPO).replace("\\", "/"))
    return idx


def present_in_tree(tree, name):
    p = os.path.join(tree, name)
    if os.path.isfile(p):
        return {"present": True, "bytes": os.path.getsize(p), "path": p.replace("\\", "/")}
    return {"present": False, "bytes": 0, "path": None}


def diagrams(tree):
    d = os.path.join(tree, "diagrams")
    if not os.path.isdir(d):
        return {"present": False, "count": 0, "dir": None}
    mds = [f for f in os.listdir(d) if f.lower().endswith(".md")]
    return {"present": len(mds) >= 8, "count": len(mds), "dir": d.replace("\\", "/"),
            "files": sorted(mds)}


def git_toplevel(path):
    r = subprocess.run(["git", "-C", path, "rev-parse", "--show-toplevel"],
                       capture_output=True, text=True)
    return {"rc": r.returncode, "out": r.stdout.strip(), "err": r.stderr.strip()[:160]}


def main():
    items = contracted_items()
    tracked = repo_tracked_basenames()
    wt = repo_worktree_basenames()

    rows = []
    for it in items:
        name = it["name"]
        if name is None:
            # item 29 - diagrams
            d1, d2 = diagrams(TREE1), diagrams(TREE2)
            rows.append({
                "n": it["n"], "name": "(item29 diagrams)",
                "tree1": d1, "tree2": d2,
                "repo_head": {"present": False, "paths": []},
                "repo_worktree": {"present": False, "paths": []},
                "note": "special-cased: >=8 diagram .md files",
            })
            continue
        t1 = present_in_tree(TREE1, name)
        t2 = present_in_tree(TREE2, name)
        rows.append({
            "n": it["n"], "name": name,
            "tree1": t1, "tree2": t2,
            "repo_head": {"present": name in tracked, "paths": tracked.get(name, [])},
            "repo_worktree": {"present": name in wt, "paths": wt.get(name, [])},
        })

    file_rows = [r for r in rows if r["name"] != "(item29 diagrams)"]
    d29 = [r for r in rows if r["name"] == "(item29 diagrams)"][0]

    def cnt(key, sub="present"):
        return sum(1 for r in file_rows if r[key][sub])

    nontrivial_t1 = sum(1 for r in file_rows if r["tree1"]["present"] and r["tree1"]["bytes"] >= MIN_BYTES)
    nontrivial_t2 = sum(1 for r in file_rows if r["tree2"]["present"] and r["tree2"]["bytes"] >= MIN_BYTES)
    union = sum(1 for r in file_rows if r["tree1"]["present"] or r["tree2"]["present"])
    both = [r["name"] for r in file_rows if r["tree1"]["present"] and r["tree2"]["present"]]
    t2_only = [r["name"] for r in file_rows if r["tree2"]["present"] and not r["tree1"]["present"]]
    t1_only = [r["name"] for r in file_rows if r["tree1"]["present"] and not r["tree2"]["present"]]
    missing_union = [r["name"] for r in file_rows if not (r["tree1"]["present"] or r["tree2"]["present"])]

    # DETECTOR CONTROL: the presence probe must fire NEGATIVE on a name known absent
    # and POSITIVE on a name known present.
    control = {
        "known_present_tree1_07_OPTION_UNIVERSE_md": present_in_tree(TREE1, "07-OPTION-UNIVERSE.md")["present"],
        "known_absent_synthetic": present_in_tree(TREE1, "99-THIS-FILE-DOES-NOT-EXIST.md")["present"],
        "known_present_repo_head_AGENTS_md": "AGENTS.md" in tracked,
        "known_absent_repo_head_synthetic": "99-THIS-FILE-DOES-NOT-EXIST.md" in tracked,
    }
    control["PASS"] = (control["known_present_tree1_07_OPTION_UNIVERSE_md"] is True
                       and control["known_absent_synthetic"] is False
                       and control["known_present_repo_head_AGENTS_md"] is True
                       and control["known_absent_repo_head_synthetic"] is False)

    result = {
        "contract_items_parsed": len(items),
        "file_shaped_items": len(file_rows),
        "detector_control": control,
        "version_control_status": {
            "tree1_git": git_toplevel(TREE1),
            "tree2_git": git_toplevel(TREE2),
            "home_git": git_toplevel(HOME),
            "repo_git": git_toplevel(REPO),
        },
        "counts": {
            "tree1_only_tree_present": cnt("tree1"),
            "tree2_only_tree_present": cnt("tree2"),
            "tree1_nontrivial_ge_2KB": nontrivial_t1,
            "tree2_nontrivial_ge_2KB": nontrivial_t2,
            "union_present": union,
            "repo_HEAD_present": cnt("repo_head"),
            "repo_worktree_present": cnt("repo_worktree"),
        },
        "sets": {
            "in_both_trees": both,
            "tree1_only": t1_only,
            "tree2_only": t2_only,
            "missing_from_union": missing_union,
        },
        "item29_diagrams": d29,
        "rows": rows,
    }
    json.dump(result, sys.stdout, indent=1)


if __name__ == "__main__":
    main()
