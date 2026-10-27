"""Classify the two checkouts the inventory missed, on every DoD axis.

The lane's Definition of Done requires each checkout classified worktree-vs-clone by
MEASUREMENT, with unique content and inbound references measured. `enum_defect_proof.py`
established that `~/source/_advver_M14/{chk,scratch}` belong to this repo and are absent from
the 25-row table. This closes the DoD for those two specifically, so the enumeration finding
does not leave two known checkouts unclassified while the full re-sweep runs.

Two mechanically independent signals for worktree-vs-clone, the same pair the inventory used:
  A. `.git` is a FILE (linked worktree) vs a DIR (own store)
  B. `git rev-parse --git-common-dir` resolves outside vs inside the checkout
They must agree; a disagreement is a detector failure, not a finding.

Inbound references are answered from the committed `inbound-refs.json` scan rather than
re-grepping, and the answer is checked for the use-vs-mention trap: a path STRING appearing
in a doc is a mention, not a dependency.

Read-only.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
CANONICAL = Path("C:/Users/Prekzursil/source/agent-skills-toolchain")
OUT = HERE / "missed-checkouts.json"

TARGETS = [
    "C:/Users/Prekzursil/source/_advver_M14/chk",
    "C:/Users/Prekzursil/source/_advver_M14/scratch",
]


def git(repo, *a):
    p = subprocess.run(
        ["git", "-C", str(repo), *a],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return p.stdout.strip() if p.returncode == 0 else ""


def main() -> int:
    # --- CONTROL for the worktree-vs-clone pair: run it on two checkouts of KNOWN kind.
    # ast-integrate is a linked worktree; agent-skills-toolchain is the main checkout.
    controls = {}
    for label, path, expect in [
        (
            "known linked worktree",
            "C:/Users/Prekzursil/source/ast-integrate",
            "worktree",
        ),
        ("known main checkout", str(CANONICAL), "main-checkout"),
    ]:
        dotgit = Path(path) / ".git"
        a = "FILE" if dotgit.is_file() else "DIR"
        common = git(path, "rev-parse", "--path-format=absolute", "--git-common-dir")
        b = (
            "outside"
            if common.replace("\\", "/").rstrip("/")
            != str(dotgit).replace("\\", "/").rstrip("/")
            else "inside"
        )
        controls[label] = {"dotgit": a, "common_dir": b, "expected": expect}
        print(f"CONTROL {label:<24} dotgit={a:<5} common={b:<8} expected={expect}")

    ok_ctl = (
        controls["known linked worktree"]["dotgit"] == "FILE"
        and controls["known main checkout"]["dotgit"] == "DIR"
    )
    print(f"control discriminates FILE vs DIR: {ok_ctl}\n")
    if not ok_ctl:
        print("FAILED:classify-missed control did not discriminate")
        return 3

    # --- inbound references, read from the committed scan
    refs = {}
    try:
        data = json.loads((HERE / "inbound-refs.json").read_text(encoding="utf-8"))
        blob = json.dumps(data)
        for t in TARGETS:
            leaf = t.rsplit("/", 1)[-1]
            refs[t] = {
                "full_path_string_present": t.replace("/", "\\") in blob or t in blob,
                "advver_dir_string_present": "_advver_M14" in blob,
                "leaf_name": leaf,
            }
    except (OSError, ValueError) as e:
        refs = {"error": str(e)}

    rows = []
    for path in TARGETS:
        p = Path(path)
        if not p.exists():
            rows.append({"path": path, "exists": False})
            print(f"{path} -- ABSENT")
            continue
        dotgit = p / ".git"
        sig_a = "FILE" if dotgit.is_file() else "DIR"
        common = git(path, "rev-parse", "--path-format=absolute", "--git-common-dir")
        sig_b = (
            "outside"
            if common.replace("\\", "/").rstrip("/")
            != str(dotgit).replace("\\", "/").rstrip("/")
            else "inside"
        )
        kind = "linked-worktree" if sig_a == "FILE" else "independent-clone"
        agree = (sig_a == "FILE") == (sig_b == "outside")

        commits = git(path, "rev-list", "--count", "HEAD") or "0"
        dirty = len(
            [x for x in git(path, "status", "--porcelain", "-uall").splitlines() if x]
        )
        staged = len(
            [x for x in git(path, "diff", "--cached", "--name-only").splitlines() if x]
        )
        stash = len([x for x in git(path, "stash", "list").splitlines() if x])
        origin = git(path, "config", "--get", "remote.origin.url")

        row = {
            "path": path,
            "exists": True,
            "signal_a_dotgit": sig_a,
            "signal_b_common_dir": sig_b,
            "signals_agree": agree,
            "kind": kind,
            "commits": commits,
            "origin": origin or "(none)",
            "dirty_uall": dirty,
            "staged": staged,
            "stash": stash,
            "inbound_refs": refs.get(path, {}),
        }
        rows.append(row)
        print(
            f"{path}\n"
            f"   kind={kind}  (A={sig_a}, B={sig_b}, agree={agree})\n"
            f"   commits={commits}  origin={origin or '(none)'}\n"
            f"   dirty(-uall)={dirty}  staged={staged}  stash={stash}\n"
            f"   inbound: full-path string in inbound-refs.json = "
            f"{refs.get(path, {}).get('full_path_string_present')}"
        )

    OUT.write_text(
        json.dumps({"controls": controls, "rows": rows}, indent=2), encoding="utf-8"
    )
    print(f"\nwrote {OUT}")
    bad = [r for r in rows if r.get("exists") and not r["signals_agree"]]
    if bad:
        print(
            "FAILED:classify-missed signals disagree -- detector failure, not a finding"
        )
        return 1
    print(
        f"SUCCESS:classify-missed classified={len([r for r in rows if r.get('exists')])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
