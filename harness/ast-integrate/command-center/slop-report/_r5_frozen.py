"""DoD-4, round 5 -- the round-4 evidence for this DoD was an INERT control. Fixed here.

WHAT WAS WRONG (audit finding D2, CONFIRMED and reproduced by this probe):
round 4 published

    git status --porcelain -uall -- command-center/p2-wave/probes/*/control   -> 0 lines

as proof that the frozen directory was untouched. As a git PATHSPEC that glob matches
0 tracked files, so the 0 could not distinguish "clean" from "matched nothing". It is
the exact shape the ground floor names: a control that passes identically under both
hypotheses is not a control, it only proves the instrument ran. The CONCLUSION was
true -- but it was unproven, and it was recorded as diligence.

The refutation is measured here, not asserted: R0 prints the tracked-file count under
the glob (expected 0) beside the count under the real path (expected 2). If those two
are ever equal the fix itself is broken.

WHAT THIS PROBE DOES INSTEAD -- five signals, each able to fail:

  R0  the refutation: glob count vs real-path count, both from `git ls-files`.
  C1  FAIL CLOSED ON ZERO. Count the tracked files under each frozen dir and exit
      non-zero if any is 0. A shape change is then loud instead of reporting parity.
  C2  POSITIVE CONTROL, same instrument, same instant, adjacent path. The frozen dir
      `command-center/casualty/probes` must report 0 dirty lines WHILE its parent
      `command-center/casualty` reports MORE than 0. If the parent also reports 0 the
      detector is not live right now and this run measures nothing -> FAIL.
  C3  byte identity against the HEAD blob for every tracked frozen file
      (`git hash-object <worktree file>` == `git rev-parse HEAD:<path>`). Stronger than
      a status read: status can be fooled by an index refresh, a hash cannot.
  C4  BOTH-STATES on the comparator itself. Take the exact HEAD blob bytes, feed them to
      `git hash-object --stdin` (must MATCH -> the route is calibrated), then feed the
      same bytes plus one appended byte (must DIFFER -> the comparator can fail). No
      frozen file is ever opened for write; the mutation happens on bytes in memory.
  C5  no NEW untracked file has appeared inside either frozen dir.

C4 is the one that makes C3 mean something. Without it "all 9 hashes matched" is exactly
what a comparator returning a constant would also print.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

REPO = "C:/Users/Prekzursil/source/ast-integrate"
OUT = os.path.join(REPO, "command-center/slop-report/_r5_frozen.out.json")

FROZEN = [
    "command-center/casualty/probes",
    "command-center/p2-wave/probes/AUD-0006/control",
]
REFUTED_PATHSPEC = "command-center/p2-wave/probes/*/control"
# adjacent, KNOWN-DIRTY parent of a frozen dir -- the positive control for C2
LIVE_CONTROL_PATH = "command-center/casualty"


def git_text(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", REPO, *args], capture_output=True, text=True, errors="replace"
    ).stdout


def git_bytes(*args: str) -> bytes:
    return subprocess.run(["git", "-C", REPO, *args], capture_output=True).stdout


def lines(s: str) -> list[str]:
    return [ln for ln in s.replace("\r\n", "\n").split("\n") if ln.strip()]


def hash_stdin(data: bytes) -> str:
    p = subprocess.run(
        ["git", "-C", REPO, "hash-object", "--stdin"], input=data, capture_output=True
    )
    return p.stdout.decode().strip()


def main() -> int:
    res: dict = {"head": git_text("rev-parse", "HEAD").strip()[:8]}

    # ---- R0: the refutation, measured -------------------------------------
    glob_n = len(lines(git_text("ls-files", "--", REFUTED_PATHSPEC)))
    real_n = len(lines(git_text("ls-files", "--", FROZEN[1])))
    res["R0_refutation"] = {
        "refuted_pathspec": REFUTED_PATHSPEC,
        "tracked_files_under_refuted_pathspec": glob_n,
        "real_path": FROZEN[1],
        "tracked_files_under_real_path": real_n,
        "refutation_holds": glob_n == 0 and real_n > 0,
        "note": "round 4 read the LEFT number as 'clean'; it is 'matched nothing'",
    }

    # ---- C1: counts, fail closed on zero ----------------------------------
    counts = {d: len(lines(git_text("ls-files", "--", d))) for d in FROZEN}
    res["C1_tracked_counts"] = counts
    res["C1_pass"] = all(n > 0 for n in counts.values())

    # ---- C2: the detector is live RIGHT NOW -------------------------------
    frozen_dirty = {
        d: lines(git_text("status", "--porcelain", "-uall", "--", d)) for d in FROZEN
    }
    control_dirty = lines(
        git_text("status", "--porcelain", "-uall", "--", LIVE_CONTROL_PATH)
    )
    res["C2_live_detector"] = {
        "control_path": LIVE_CONTROL_PATH,
        "control_dirty_lines": len(control_dirty),
        "frozen_dirty_lines": {d: len(v) for d, v in frozen_dirty.items()},
        "pass": len(control_dirty) > 0,
        "note": "control > 0 while frozen == 0 -> the 0 is a reading, not a silence",
    }

    # ---- C3: byte identity vs the HEAD blob -------------------------------
    ident: dict[str, dict] = {}
    all_ident = True
    sample_path = None
    for d in FROZEN:
        for path in lines(git_text("ls-files", "--", d)):
            head_blob = git_text("rev-parse", f"HEAD:{path}").strip()
            work_blob = git_text("hash-object", os.path.join(REPO, path)).strip()
            same = bool(head_blob) and head_blob == work_blob
            ident[path] = {
                "head": head_blob[:12],
                "worktree": work_blob[:12],
                "same": same,
            }
            all_ident = all_ident and same
            if sample_path is None:
                sample_path = path
    res["C3_identity"] = ident
    res["C3_files_checked"] = len(ident)
    res["C3_pass"] = all_ident and len(ident) > 0

    # ---- C4: both-states on the comparator --------------------------------
    blob_bytes = git_bytes("cat-file", "-p", f"HEAD:{sample_path}")
    expected = git_text("rev-parse", f"HEAD:{sample_path}").strip()
    clean_state = hash_stdin(blob_bytes)
    broken_state = hash_stdin(blob_bytes + b"x")
    res["C4_both_states"] = {
        "sample": sample_path,
        "clean_state_matches_head_blob": clean_state == expected,
        "mutated_state_differs": broken_state != expected,
        "pass": clean_state == expected and broken_state != expected,
        "note": "mutation is on bytes in memory; no frozen file was opened for write",
    }

    # ---- C5: no new untracked file inside a frozen dir --------------------
    res["C5_untracked_inside_frozen"] = {d: v for d, v in frozen_dirty.items()}
    res["C5_pass"] = all(len(v) == 0 for v in frozen_dirty.values())

    ok = (
        res["R0_refutation"]["refutation_holds"]
        and res["C1_pass"]
        and res["C2_live_detector"]["pass"]
        and res["C3_pass"]
        and res["C4_both_states"]["pass"]
        and res["C5_pass"]
    )
    res["verdict"] = "FROZEN-UNTOUCHED-PROVEN" if ok else "NOT-PROVEN"

    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(res, fh, indent=1, sort_keys=True)
    summary = {k: v for k, v in res.items() if k != "C3_identity"}
    json.dump(summary, sys.stdout, indent=1, sort_keys=True)
    print()
    print("SUCCESS:r5-frozen" if ok else "FAILED:r5-frozen see-controls")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
