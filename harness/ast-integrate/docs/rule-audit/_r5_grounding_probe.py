"""RULERESEARCH round-5 grounding probe: what is STILL open?

Read-only. Three measurements the prior rounds left unanswered or that may have drifted:
  A. Fresh frontmatter classification (DoD-1) across the three rule trees.
  B. CI reachability of every rule-audit gate  <-- the INTEGRATE skeleton's unanswered Q.
  C. Contradiction status: fixed-in-repo vs still-wrong-in-live.

Every detector here carries a control. Emits JSON to stdout.
"""

import glob
import hashlib
import json
import os
import re
import subprocess
import sys

REPO = r"C:/Users/Prekzursil/source/ast-integrate"
TREES = {
    "repo": os.path.join(REPO, "rules"),
    "agent_self": os.path.join(REPO, "agent-self/config/rules"),
    "live": r"C:/Users/Prekzursil/.claude/rules",
}


def read_lf(path):
    with open(path, "rb") as fh:
        return fh.read().replace(b"\r\n", b"\n")


def has_frontmatter(text):
    if not text.startswith("---"):
        return False, {}
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return False, {}
    d = {}
    for line in m.group(1).split("\n"):
        mm = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$", line)
        if mm:
            d[mm.group(1)] = mm.group(2).strip()
    return True, d


def tok(text):
    try:
        import tiktoken

        return len(tiktoken.get_encoding("cl100k_base").encode(text))
    except Exception:
        return None


# ---------- A. frontmatter classification ----------
def measure_trees():
    out = {}
    for name, root in TREES.items():
        if not os.path.isdir(root):
            out[name] = {"__MISSING__": root}
            continue
        always, lazy, tot_always, tot_all = [], [], 0, 0
        for p in sorted(glob.glob(os.path.join(root, "**/*.md"), recursive=True)):
            rel = os.path.relpath(p, root).replace("\\", "/")
            text = read_lf(p).decode("utf-8", "replace")
            fm, d = has_frontmatter(text)
            t = tok(text) or 0
            tot_all += t
            if fm:
                lazy.append({"rel": rel, "tok": t, "paths": d.get("paths")})
            else:
                always.append({"rel": rel, "tok": t})
                tot_always += t
        out[name] = {
            "root": root,
            "files": len(always) + len(lazy),
            "always_on_count": len(always),
            "lazy_count": len(lazy),
            "always_on_tok": tot_always,
            "all_tok": tot_all,
            "always_on_files": sorted(a["rel"] for a in always),
            "always_on_detail": sorted(always, key=lambda x: -x["tok"]),
        }
    return out


# ---------- B. CI reachability of rule-audit gates ----------
def measure_ci_wiring():
    """Is each rule-audit gate script referenced by anything CI executes?

    DETECTOR CONTROL: a known-wired file (a ci/tests/test_rules_*.py module) must be
    found by the same search. If the control is not found, the search is broken and
    every 'not wired' verdict below is meaningless.
    """
    gates = sorted(
        os.path.basename(p)
        for p in glob.glob(os.path.join(REPO, "docs/rule-audit/*.py"))
        if not os.path.basename(p).startswith("_")
    )
    # search corpus = everything CI could execute from
    corpus = []
    for pat in [
        ".github/workflows/*.yml",
        ".github/workflows/*.yaml",
        "ci/**/*.py",
        "ci/**/*.yml",
        "ci/**/*.cfg",
        "ci/**/*.toml",
        "scripts/**/*.ps1",
        "scripts/**/*.py",
        "*.toml",
        "*.cfg",
    ]:
        corpus += glob.glob(os.path.join(REPO, pat), recursive=True)
    corpus = sorted(set(corpus))
    blob = {}
    for p in corpus:
        try:
            blob[p] = read_lf(p).decode("utf-8", "replace")
        except Exception:
            pass

    def refs(token):
        return [
            os.path.relpath(p, REPO).replace("\\", "/")
            for p, t in blob.items()
            if token in t
        ]

    result = {"corpus_files": len(blob), "gates": {}, "control": {}}
    for g in gates:
        stem = g[:-3]
        hits = refs(g) or refs(stem)
        result["gates"][g] = {"wired": bool(hits), "referenced_by": hits}

    # CONTROL 1 (positive): a known-wired CI test module must be found.
    ctrl_hits = refs("test_rules_integrity")
    result["control"]["positive_test_rules_integrity"] = {
        "found": bool(ctrl_hits),
        "referenced_by": ctrl_hits,
    }
    # CONTROL 2 (negative): a token that exists nowhere must NOT be found.
    result["control"]["negative_nonexistent_token"] = {
        "found": bool(refs("zzz_no_such_gate_qqq")),
    }
    result["control"]["VALID"] = bool(ctrl_hits) and not refs("zzz_no_such_gate_qqq")
    return result


# ---------- C. contradiction status: repo vs live ----------
CONTRADICTIONS = [
    {
        "id": "4.2",
        "file": "common/harness-vcs-hygiene.md",
        "fixed_marker": "-Report` selects the OUTPUT FORMAT",
        "wrong_marker": "-Report json` to see drift",
        "what": "sync-from-live.ps1 bare -Report json WRITES (data loss)",
    },
    {
        "id": "4.3",
        "file": "common/cross-vendor-dispatch.md",
        "fixed_marker": "Reconciliation with AGENTS.md",
        "wrong_marker": "NEVER `--background`",
        "what": "dispatch rule contradicts AGENTS.md 4a and its own 7",
    },
]


def measure_contradictions():
    out = []
    for c in CONTRADICTIONS:
        row = {"id": c["id"], "file": c["file"], "what": c["what"]}
        for tree in ("repo", "live"):
            p = os.path.join(TREES[tree], c["file"])
            if not os.path.isfile(p):
                row[tree] = "MISSING"
                continue
            text = read_lf(p).decode("utf-8", "replace")
            row[tree] = {
                "has_fix": c["fixed_marker"] in text,
                "has_wrong": c["wrong_marker"] in text,
                "sha256": hashlib.sha256(text.encode()).hexdigest()[:12],
            }
        out.append(row)
    return out


def measure_repo_live_drift():
    """How many rule files still differ repo vs live, and which always-on ones."""
    repo_root, live_root = TREES["repo"], TREES["live"]
    if not os.path.isdir(live_root):
        return {"__MISSING__": live_root}
    diffs, always_diffs = [], []
    for p in sorted(glob.glob(os.path.join(repo_root, "**/*.md"), recursive=True)):
        rel = os.path.relpath(p, repo_root).replace("\\", "/")
        lp = os.path.join(live_root, rel)
        if not os.path.isfile(lp):
            diffs.append({"rel": rel, "state": "only_in_repo"})
            continue
        a, b = read_lf(p), read_lf(lp)
        if a != b:
            fm, _ = has_frontmatter(a.decode("utf-8", "replace"))
            diffs.append({"rel": rel, "state": "differs", "always_on": not fm})
            if not fm:
                always_diffs.append(rel)
    live_only = []
    for p in sorted(glob.glob(os.path.join(live_root, "**/*.md"), recursive=True)):
        rel = os.path.relpath(p, live_root).replace("\\", "/")
        if not os.path.isfile(os.path.join(repo_root, rel)):
            live_only.append(rel)
    return {
        "differ_count": len([d for d in diffs if d.get("state") == "differs"]),
        "only_in_repo": [d["rel"] for d in diffs if d.get("state") == "only_in_repo"],
        "only_in_live": live_only,
        "always_on_differing": always_diffs,
    }


def main():
    res = {
        "A_trees": measure_trees(),
        "B_ci_wiring": measure_ci_wiring(),
        "C_contradictions": measure_contradictions(),
        "D_repo_live_drift": measure_repo_live_drift(),
        "git_head": subprocess.run(
            ["git", "-C", REPO, "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
        ).stdout.strip(),
    }
    json.dump(res, sys.stdout, indent=1)


if __name__ == "__main__":
    main()
