"""Second measurement pass: tracked-vs-untracked, distinct schema logical files, repo shape.

Scope: full recursive walk of the repo (no depth limit), excluding .git/__pycache__/
.pytest_cache/node_modules. Cross-checks the substrate sibling's 234 figure with an
independent algorithm (strip the JSON-Pointer fragment, then set-count).
Run: python platform/architecture/_mkt_measure2.py
"""

import json
import os
import subprocess
from collections import Counter

REPO = "C:/Users/Prekzursil/source/ast-integrate"
EXCL = {".git", "__pycache__", ".pytest_cache", "node_modules"}


def walk(root):
    out = []
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in EXCL]
        for f in fn:
            out.append(os.path.relpath(os.path.join(dp, f), REPO).replace("\\", "/"))
    return out


def git(*args):
    return subprocess.run(
        ["git", "-C", REPO, *args], capture_output=True, text=True, check=True
    ).stdout


def main():
    allf = set(walk(REPO))
    tracked = set(git("ls-files").split("\n")) - {""}
    print("=== REPO SHAPE ===")
    print("files on disk (excl. %s): %d" % (sorted(EXCL), len(allf)))
    print("git-tracked total       : %d" % len(tracked))
    print("on disk but UNTRACKED   : %d" % len(allf - tracked))
    print()

    print("=== TOP-LEVEL DISTRIBUTION (on disk) ===")
    top = Counter(p.split("/")[0] for p in allf)
    for k, v in top.most_common(20):
        tk = len([p for p in tracked if p.split("/")[0] == k])
        print(f"  {k:34s} disk={v:6d} tracked={tk:6d}")
    print()

    print("=== UNTRACKED, BY AREA ===")
    unt = allf - tracked
    ua = Counter("/".join(p.split("/")[:2]) for p in unt)
    for k, v in ua.most_common(20):
        print(f"  {k:40s} {v:6d}")
    print()

    print("=== command-center/schema tracked? ===")
    ccs_disk = {p for p in allf if p.startswith("command-center/schema/")}
    ccs_trk = {p for p in tracked if p.startswith("command-center/schema/")}
    print("  disk:", len(ccs_disk), " tracked:", len(ccs_trk))
    print()

    print("=== output_schema: distinct LOGICAL FILES (independent algorithm) ===")
    with open(
        os.path.join(REPO, "command-center/WORK-UNIT-CATALOG.json"), encoding="utf-8"
    ) as f:
        cat = json.load(f)
    refs = []
    for u in cat["work_units"]:
        v = u.get("output_schema")
        if isinstance(v, str):
            refs.append(v)
        elif isinstance(v, list):
            refs.extend(v)
        else:
            refs.append("<<NON-STRING:%r>>" % type(v).__name__)
    print("  total references        :", len(refs))
    print("  distinct raw strings    :", len(set(refs)))
    logical = {r.split("#")[0] for r in refs}
    print("  distinct after #-strip  :", len(logical))
    http = {r for r in logical if r.startswith("http")}
    print("  of which URL-shaped     :", len(http), sorted(http))
    onfs = {r for r in logical if not r.startswith("http")}
    exists = {r for r in onfs if os.path.exists(os.path.join(REPO, r))}
    print("  filesystem-shaped       :", len(onfs))
    print("  ... that EXIST on disk  :", len(exists))
    print("  ... that DO NOT exist   :", len(onfs - exists), sorted(onfs - exists)[:10])
    pref = Counter(
        r.split("/")[0] + "/" + (r.split("/")[1] if "/" in r[r.find("/") + 1 :] else "")
        for r in onfs
    )
    print("  by top-2 path prefix:")
    for k, v in pref.most_common(12):
        print(f"     {k:40s} {v}")
    print()

    print("=== output_path prefixes (where units WRITE) ===")
    op = Counter()
    for u in cat["work_units"]:
        p = u.get("output_path") or ""
        op["/".join(str(p).split("/")[:2])] += 1
    for k, v in op.most_common(15):
        print(f"  {k:44s} {v}")
    print()

    print("=== execution_substrate / tool_permissions shape ===")
    es = Counter(json.dumps(u.get("execution_substrate")) for u in cat["work_units"])
    for k, v in es.most_common(10):
        print(f"  {k[:80]:82s} {v}")
    print()
    print("SUCCESS:mkt-measure2")


if __name__ == "__main__":
    main()
