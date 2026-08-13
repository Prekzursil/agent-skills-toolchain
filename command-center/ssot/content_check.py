"""Content-check stranded work against origin/main -- commit-object uniqueness is NOT
content uniqueness.

WHY THIS EXISTS. SSOT-CLONE-INVENTORY.md §2 measured, correctly, that four commits exist as
git OBJECTS in no other store and are reachable from no remote tip, and called that "the
fleet's real data-loss exposure". The object measurement is right; the SENTENCE is wider than
its evidence. Under squash-merge -- this repo's merge mode -- a fully-merged change KEEPS a
unique commit SHA forever, because the squashed commit on main is a different object with
different parents. REPO-TOPOLOGY.md rule 4 says exactly this. So a commit can be
object-unique and content-redundant at the same time, and only a per-file content comparison
can tell the two apart.

That distinction decides real actions: object-unique + content-present = the worktree is
disposable; object-unique + content-absent = retiring it destroys the only copy.

VERDICTS, per file in the stranded commit:
  ABSENT           path does not exist on main at all              -> content may be lost
  IDENTICAL        blob is byte-identical to main                  -> redundant
  MAIN_IS_SUPERSET every non-trivial scratch line is present       -> redundant
  DIVERGED         both sides hold unique lines                    -> needs judgement

The DIVERGED case is the one an LLM systematically misses (fan-out-contract C.D4: 31 of 47
agent errors were DIVERGED read as safe, 100% of errors pointed at data loss), so the
comparison is bidirectional BY CONSTRUCTION here, never "does scratch have extra lines".

Blob reads use `git cat-file -p` / `git show <rev>:<path>`, both of which return the STORED
blob with no EOL conversion on this box. `git archive` is the one that returns CRLF on Windows
and is deliberately not used. Comparison is on LF-normalised text so a pure line-ending
difference is not misreported as divergence.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

MAIN_REPO = "C:/Users/Prekzursil/source/ast-integrate"


def run(args: list[str], repo: str) -> tuple[int, bytes]:
    p = subprocess.run(["git", "-C", repo] + args, capture_output=True, timeout=120)
    return p.returncode, p.stdout


def norm(raw: bytes) -> list[str]:
    """LF-normalise and drop blank lines, so a CRLF-only delta is not 'divergence'."""
    text = (
        raw.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
    )
    return [ln.rstrip() for ln in text.split("\n") if ln.strip()]


def blob_on_main(path: str, ref: str) -> bytes | None:
    rc, out = run(["cat-file", "-p", f"{ref}:{path}"], MAIN_REPO)
    return out if rc == 0 else None


def control_blob_reader(ref: str) -> bool:
    """BOTH-STATES control for the blob reader.

    A reader that returns empty for everything would make every file look ABSENT and
    manufacture a fleet-wide false alarm. Require: a path known to exist returns
    content, and a fabricated path returns None.
    """
    rc, out = run(["ls-tree", "--name-only", ref], MAIN_REPO)
    if rc != 0 or not out.strip():
        print("  CONTROL FAIL: cannot list the tree at all")
        return False
    real = None
    for cand in out.decode().split("\n"):
        cand = cand.strip()
        if cand.endswith(".md"):
            real = cand
            break
    if real is None:
        print("  CONTROL FAIL: no probe file found at tree root")
        return False
    present = blob_on_main(real, ref)
    missing = blob_on_main("this/path/does/not/exist__control.xyz", ref)
    ok = bool(present) and missing is None
    print(
        f"  control: real({real}) -> {'CONTENT' if present else 'EMPTY'} | "
        f"fabricated -> {'None' if missing is None else 'CONTENT'} "
        f"=> {'PASS' if ok else 'FAIL'}"
    )
    return ok


def classify(scratch: bytes, main: bytes | None) -> tuple[str, int, int]:
    if main is None:
        return "ABSENT", len(norm(scratch)), 0
    s, m = norm(scratch), norm(main)
    ss, ms = set(s), set(m)
    only_scratch = [ln for ln in ss - ms if len(ln) > 3]
    only_main = [ln for ln in ms - ss if len(ln) > 3]
    if not only_scratch and not only_main:
        return "IDENTICAL", 0, 0
    if not only_scratch:
        return "MAIN_IS_SUPERSET", 0, len(only_main)
    return "DIVERGED", len(only_scratch), len(only_main)


def check_commit(repo: str, sha: str, ref: str) -> dict:
    rc, out = run(["show", "--format=%s", "--name-only", sha], repo)
    lines = out.decode("utf-8", errors="replace").split("\n")
    subject = lines[0].strip() if lines else "?"
    paths = [ln.strip() for ln in lines[1:] if ln.strip()]
    files = []
    for path in paths:
        rc2, scratch = run(["cat-file", "-p", f"{sha}:{path}"], repo)
        if rc2 != 0:
            files.append({"path": path, "verdict": "DELETED_IN_COMMIT"})
            continue
        verdict, only_s, only_m = classify(scratch, blob_on_main(path, ref))
        files.append(
            {
                "path": path,
                "verdict": verdict,
                "lines_only_in_scratch": only_s,
                "lines_only_on_main": only_m,
            }
        )
    order = {"ABSENT": 0, "DIVERGED": 1, "MAIN_IS_SUPERSET": 2, "IDENTICAL": 3}
    worst = min(
        (f["verdict"] for f in files), key=lambda v: order.get(v, 9), default="EMPTY"
    )
    return {
        "repo": repo,
        "sha": sha,
        "subject": subject,
        "files": files,
        "worst": worst,
    }


def check_staged(repo: str, ref: str) -> dict:
    """Staged-but-uncommitted adds. A staged index is per-worktree and IS destroyed with
    the worktree, so this content is at risk in a way a shared stash is not."""
    rc, out = run(["diff", "--cached", "--name-only"], repo)
    paths = [p.strip() for p in out.decode().split("\n") if p.strip()]
    files = []
    for path in paths:
        rc2, scratch = run(["show", f":{path}"], repo)
        if rc2 != 0:
            files.append({"path": path, "verdict": "UNREADABLE"})
            continue
        verdict, only_s, only_m = classify(scratch, blob_on_main(path, ref))
        files.append(
            {
                "path": path,
                "verdict": verdict,
                "lines_only_in_scratch": only_s,
                "lines_only_on_main": only_m,
            }
        )
    return {"repo": repo, "kind": "STAGED_INDEX", "files": files}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default="origin/main")
    ap.add_argument("--out", default="command-center/ssot/content-check.json")
    args = ap.parse_args()

    print(f"=== blob-reader control against {args.ref} ===")
    if not control_blob_reader(args.ref):
        print("FAILED:content-check blob-reader control did not pass")
        return 2

    # The stranded commits named in SSOT-CLONE-INVENTORY.md §2, plus the staged indexes
    # that a worktree removal would destroy.
    targets = [
        (
            "C:/Users/Prekzursil/.claude/agent-worktrees-salvage/agent-425276811/ast",
            "HEAD",
        ),
        (
            "C:/Users/Prekzursil/.claude/agent-worktrees-salvage/agent-1521081161/_b5-toolchain",
            "HEAD",
        ),
        ("C:/Users/Prekzursil/source/_wu/CRCP-SEC", "HEAD"),
    ]
    results = []
    for repo, sha in targets:
        if not pathlib.Path(repo).exists():
            print(f"\n--- {repo}: PATH ABSENT (checkout gone since the inventory)")
            results.append({"repo": repo, "error": "path-absent"})
            continue
        print(f"\n--- {repo} @ {sha}")
        r = check_commit(repo, sha, args.ref)
        results.append(r)
        print(f"    subject: {r['subject'][:88]}")
        for f in r["files"]:
            print(
                f"      {f['verdict']:17s} {f['path']}"
                + (
                    f"  (+{f.get('lines_only_in_scratch', 0)} scratch-only /"
                    f" +{f.get('lines_only_on_main', 0)} main-only)"
                    if f["verdict"] in ("DIVERGED", "MAIN_IS_SUPERSET")
                    else ""
                )
            )
        print(f"    WORST: {r['worst']}")

    for repo in ["D:/wt-salvage-probe", "D:/inc1-wt/ast-increment1"]:
        if not pathlib.Path(repo).exists():
            continue
        print(f"\n--- {repo} (staged index)")
        r = check_staged(repo, args.ref)
        results.append(r)
        for f in r["files"]:
            print(f"      {f['verdict']:17s} {f['path']}")

    outp = pathlib.Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    with open(outp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"ref": args.ref, "results": results}, fh, indent=2)
    print(f"\nwrote {outp}")
    print(f"SUCCESS:content-check targets={len(results)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
