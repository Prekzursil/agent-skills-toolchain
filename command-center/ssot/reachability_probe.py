"""Is the at-risk content REACHABLE, or merely PRESENT?

The distinction this file exists for
-----------------------------------
`git cat-file -e <blob>` answers "does this object exist in the store". That is NOT the
question. `D:/wt-salvage-probe` is a LINKED WORKTREE of the canonical store, so `git add`
writes its blobs into the SHARED object database. A blob sitting in the index of a worktree
is *present* in canonical and simultaneously reachable from NO ref -- which means
`git gc --prune` is entitled to delete it, and `git worktree remove` destroys the index that
was the only thing pointing at it.

An existence probe reports those two states identically. It cannot distinguish
  H1: the content is preserved in history and recoverable
  H2: the content is a loose object hanging off an index, one gc from gone
so it is not a control for this question. This file measures REACHABILITY instead:
membership in `git rev-list --objects --all`, which is exactly the set gc keeps.

Read-only. Writes one JSON report under command-center/ssot/.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

CANONICAL = Path("C:/Users/Prekzursil/source/agent-skills-toolchain")
B5 = Path(
    "C:/Users/Prekzursil/.claude/agent-worktrees-salvage/agent-1521081161/_b5-toolchain"
)
PROBE = Path("D:/wt-salvage-probe")
OUT = Path(__file__).resolve().parent / "reachability.json"


def run(args, cwd, text=True):
    return subprocess.run(
        args,
        cwd=str(cwd),
        capture_output=True,
        text=text,
        encoding="utf-8" if text else None,
    )


def reachable_objects(repo: Path) -> set[str]:
    """Every object id reachable from ANY ref. This is the set `git gc` preserves."""
    p = run(["git", "rev-list", "--objects", "--all"], repo)
    out = set()
    for line in p.stdout.splitlines():
        sha = line.split(" ", 1)[0].strip()
        if len(sha) == 40:
            out.add(sha)
    return out


def main() -> int:
    report: dict = {}

    # ---------------------------------------------------------------- controls
    # The reachable-set reader must be shown to answer BOTH ways, or a set that is
    # empty/universal would make every verdict below vacuous.
    canon_reach = reachable_objects(CANONICAL)
    head_readme = run(["git", "rev-parse", "HEAD:README.md"], CANONICAL).stdout.strip()
    fabricated = "0" * 39 + "1"
    ctl = {
        "reachable_set_size": len(canon_reach),
        "known_reachable_blob": head_readme,
        "known_reachable_in_set": head_readme in canon_reach,
        "fabricated_sha": fabricated,
        "fabricated_in_set": fabricated in canon_reach,
    }
    ctl["discriminates"] = (
        ctl["known_reachable_in_set"] and not ctl["fabricated_in_set"]
    )
    report["control"] = ctl
    print(
        f"CONTROL: canonical reachable objects={len(canon_reach)}  "
        f"known-reachable={ctl['known_reachable_in_set']}  "
        f"fabricated={ctl['fabricated_in_set']}  -> discriminates={ctl['discriminates']}"
    )
    if not ctl["discriminates"] or len(canon_reach) < 1000:
        print(
            "FAILED:reachability control did not discriminate (or set implausibly small)"
        )
        return 3

    # ------------------------------------------------- 1. wt-salvage-probe index
    probe_rows = []
    if PROBE.exists():
        common = run(["git", "rev-parse", "--git-common-dir"], PROBE).stdout.strip()
        names = run(["git", "diff", "--cached", "--name-only"], PROBE).stdout.split()
        for n in names:
            sha = run(["git", "rev-parse", f":{n}"], PROBE).stdout.strip()
            probe_rows.append(
                {
                    "path": n,
                    "sha": sha,
                    "exists_in_store": run(
                        ["git", "cat-file", "-e", sha], PROBE
                    ).returncode
                    == 0,
                    "reachable_from_any_ref": sha in canon_reach,
                    "path_on_main": run(
                        ["git", "cat-file", "-e", f"origin/main:{n}"], CANONICAL
                    ).returncode
                    == 0,
                }
            )
        report["wt_salvage_probe"] = {
            "path": str(PROBE),
            "git_common_dir": common,
            "shares_canonical_store": "agent-skills-toolchain"
            in common.replace("\\", "/"),
            "staged": probe_rows,
        }
        print(f"\n[D:/wt-salvage-probe]  common-dir={common}")
        for r in probe_rows:
            print(
                f"  {r['path']}\n"
                f"     exists_in_store={r['exists_in_store']}  "
                f"REACHABLE={r['reachable_from_any_ref']}  path_on_main={r['path_on_main']}"
            )
    else:
        report["wt_salvage_probe"] = {"path": str(PROBE), "exists": False}
        print("\n[D:/wt-salvage-probe] ABSENT")

    # ------------------------------------------------------- 2. b5-toolchain
    if B5.exists():
        head = run(["git", "rev-parse", "HEAD"], B5).stdout.strip()
        # Which refs -- local or remote-tracking -- contain HEAD?
        contains_all = run(
            ["git", "branch", "-a", "--contains", head], B5
        ).stdout.strip()
        contains_remote = run(
            ["git", "branch", "-r", "--contains", head], B5
        ).stdout.strip()
        # Does the ORIGIN repo (canonical) know this commit at all?
        in_canonical = run(["git", "cat-file", "-t", head], CANONICAL).returncode == 0
        # The honest "unpushed" query, with its exit code checked.
        unp = run(["git", "log", "--format=%H", "HEAD", "--not", "--remotes"], B5)
        unpushed = [c for c in unp.stdout.split() if c]

        files = run(
            ["git", "show", "--pretty=", "--name-only", head], B5
        ).stdout.splitlines()
        rows = []
        for f in [x.strip() for x in files if x.strip()]:
            sha = run(["git", "rev-parse", f"{head}:{f}"], B5).stdout.strip()
            rows.append(
                {
                    "path": f,
                    "sha": sha,
                    "reachable_in_canonical": sha in canon_reach,
                    "path_on_main": run(
                        ["git", "cat-file", "-e", f"origin/main:{f}"], CANONICAL
                    ).returncode
                    == 0,
                }
            )
        report["b5_toolchain"] = {
            "path": str(B5),
            "head": head,
            "head_in_canonical_store": in_canonical,
            "refs_containing_head": contains_all.splitlines(),
            "remote_refs_containing_head": contains_remote.splitlines(),
            "unpushed_query_rc": unp.returncode,
            "unpushed_query_stderr": unp.stderr.strip()[:300],
            "unpushed_commits": unpushed,
            "files": rows,
        }
        print(f"\n[_b5-toolchain] HEAD={head}")
        print(f"  head present in canonical store : {in_canonical}")
        print(f"  refs containing HEAD            : {contains_all.splitlines()}")
        print(
            f"  REMOTE refs containing HEAD     : {contains_remote.splitlines() or 'NONE'}"
        )
        print(f"  `--not --remotes` rc={unp.returncode} -> {len(unpushed)} commit(s)")
        if unp.stderr.strip():
            print(f"     stderr: {unp.stderr.strip()[:200]}")
        for r in rows:
            print(
                f"    {r['path']:<45} reachable_in_canonical={r['reachable_in_canonical']}"
                f"  path_on_main={r['path_on_main']}"
            )
    else:
        report["b5_toolchain"] = {"path": str(B5), "exists": False}
        print("\n[_b5-toolchain] ABSENT")

    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nwrote {OUT}")
    print("SUCCESS:reachability-probe")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
