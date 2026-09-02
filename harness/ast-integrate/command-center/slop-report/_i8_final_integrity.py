"""INTEGRATE / step I8 -- final integrity: ancestry, scope, frozen evidence.

Four questions, each answered by execution:
  A  are all five of this round's commits ancestors of HEAD? (the tree moved under me 6+ times)
  B  did any commit touch a path outside the declared scope?
  C  are the two frozen-evidence directories untouched, by signals that can DISAGREE?
  D  what is the gate's own verdict at the final HEAD?

C carries a hasher control, because "every frozen file hashed OK" is exactly what a
constant-returning hasher prints, and a count floor, because three git queries returning
silence about a NONEXISTENT pathspec is indistinguishable from silence about an untouched one.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path("C:/Users/Prekzursil/source/ast-integrate")
OUT = ROOT / "command-center/slop-report/_i8_final_integrity.out.json"

MINE = ["c488f55b", "96362031", "f1014b19", "f3a1410c", "f1c57145"]
ALLOWED = (".github/workflows/no-runtime-junk.yml", "command-center/slop-report/")
FROZEN = ["command-center/casualty/probes", "command-center/p2-wave/probes"]


def git(*args):
    return subprocess.run(
        ["git", "-C", str(ROOT), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def main() -> int:
    res: dict = {"head": git("rev-parse", "HEAD").stdout.strip()}

    # ---- A: ancestry --------------------------------------------------------------
    res["A_ancestry"] = {
        c: git("merge-base", "--is-ancestor", c, "HEAD").returncode == 0 for c in MINE
    }

    # ---- B: scope, per commit -----------------------------------------------------
    scope = {}
    for c in MINE:
        names = [
            n
            for n in git("show", "--name-only", "--format=", c).stdout.splitlines()
            if n.strip()
        ]
        foreign = [n for n in names if not n.startswith(ALLOWED)]
        dels = [
            n
            for n in git(
                "show", "--diff-filter=D", "--name-only", "--format=", c
            ).stdout.splitlines()
            if n.strip()
        ]
        scope[c] = {"files": len(names), "foreign": foreign, "deletions": dels}
    res["B_scope"] = scope
    res["B_zero_foreign"] = all(not v["foreign"] for v in scope.values())
    res["B_zero_deletions"] = all(not v["deletions"] for v in scope.values())

    # ---- C: frozen evidence, with controls ----------------------------------------
    frozen: dict = {}
    for d in FROZEN:
        files = sorted(p for p in (ROOT / d).rglob("*") if p.is_file())
        frozen[d] = {
            "n_files": len(files),
            "commits_touching_since_my_first": len(
                [
                    x
                    for x in git(
                        "log", "--format=%h", f"{MINE[0]}~1..HEAD", "--", d
                    ).stdout.splitlines()
                    if x.strip()
                ]
            ),
            "tracked_diff_lines": len(
                [
                    x
                    for x in git(
                        "diff", "--name-only", f"{MINE[0]}~1", "HEAD", "--", d
                    ).stdout.splitlines()
                    if x.strip()
                ]
            ),
            "dirty_lines": len(
                [
                    x
                    for x in git("status", "--porcelain", "--", d).stdout.splitlines()
                    if x.strip()
                ]
            ),
            "digest": hashlib.sha256(
                b"".join(sha(f).encode() for f in files)
            ).hexdigest()[:16],
        }
    # Control: the hasher must NOT be constant. Re-hash the same bytes (equal) and a mutated
    # copy in memory (different). Without this, "all digests computed" proves only that the
    # function returned.
    sample = sorted(p for p in (ROOT / FROZEN[0]).rglob("*") if p.is_file())[0]
    b = sample.read_bytes()
    res["C_frozen"] = frozen
    res["C_control"] = {
        "stable_rehash_equal": hashlib.sha256(b).hexdigest()
        == hashlib.sha256(b).hexdigest(),
        "mutated_differs": hashlib.sha256(b).hexdigest()
        != hashlib.sha256(b + uuid.uuid4().bytes).hexdigest(),
        "found_files_both_dirs": all(v["n_files"] > 0 for v in frozen.values()),
    }
    res["C_untouched"] = all(
        v["commits_touching_since_my_first"] == 0
        and v["tracked_diff_lines"] == 0
        and v["dirty_lines"] == 0
        and v["n_files"] > 0
        for v in frozen.values()
    ) and all(res["C_control"].values())

    # ---- D: the gate at the final HEAD --------------------------------------------
    g = subprocess.run(
        [sys.executable, "command-center/slop-report/check_published_commands.py"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    res["D_gate"] = {"rc": g.returncode, "tail": g.stdout.strip().splitlines()[-1:]}

    checks = {
        "A_all_commits_are_ancestors": all(res["A_ancestry"].values()),
        "B_no_foreign_path_in_any_commit": res["B_zero_foreign"],
        "B_no_deletions_in_any_commit": res["B_zero_deletions"],
        "C_frozen_evidence_untouched": res["C_untouched"],
        "D_gate_green_at_head": res["D_gate"]["rc"] == 0,
    }
    res["checks"] = checks
    res["verdict"] = "INTEGRITY-OK" if all(checks.values()) else "FAILED"

    OUT.write_text(
        json.dumps(res, indent=1, sort_keys=True), encoding="utf-8", newline="\n"
    )
    print(json.dumps(res, indent=1, sort_keys=True))
    return 0 if res["verdict"] == "INTEGRITY-OK" else 1


if __name__ == "__main__":
    sys.exit(main())
