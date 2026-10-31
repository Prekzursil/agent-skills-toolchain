"""RED-PROOF for the round-1 defect: `merge-base --is-ancestor` rc=128 folded into "no".

THE DEFECT (identity_by_ancestry.py:71, as shipped in round 1):

    return rc(["git", "merge-base", "--is-ancestor", root, "HEAD"], path) == 0

`git merge-base --is-ancestor` has THREE outcomes, not two:

    rc=0    yes, an ancestor                      -- a real answer
    rc=1    no, genuinely not an ancestor         -- a real answer
    rc=128  fatal: Not a valid commit name <sha>  -- THE QUESTION COULD NOT BE ASKED

`== 0` collapses 1 and 128 into a single `False`. rc=128 means the root object is not in
this store, which for a SHALLOW clone is the normal state -- `git clone --depth N` truncates
history, so the repo's first commit is simply absent. The checkout is then filed under
"REJECTED (store held the object)" -- a confident negative derived from an error.

This is the lane's own recorded lesson, unapplied one file over. salvage_atrisk.py:24-28
documents the identical shape (`git log --not --remotes` returning EMPTY without a positive
ref, read as "0 unpushed files") and its fix -- "reachability_probe.py prints the query's
return code so the silence cannot be mistaken for an answer again". identity_by_ancestry.py
never printed or branched on the return code.

WHAT THIS SCRIPT PROVES, both states:

  1. All three rc codes really occur in this population (control: if fewer than three
     distinct codes are observed the splitter is not exercising the defect and this script
     FAILS CLOSED rather than reporting a clean bill).
  2. The OLD expression returns the SAME value (False) for rc=1 and rc=128 -- it cannot
     distinguish "not an ancestor" from "could not be asked".
  3. The NEW expression returns different values for those two -- it can.

Read-only. Writes one JSON report.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT_COMMIT = "66e383dd97e4e53bd34085636f9b2a2f83efce02"
OUT = HERE / "rc128-redproof.json"


def run(args: list[str], cwd: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def ancestor_rc(path: str, root: str) -> tuple[int, str]:
    """Return the RAW return code plus stderr, which is what round 1 threw away."""
    p = run(["git", "merge-base", "--is-ancestor", root, "HEAD"], path)
    return p.returncode, p.stderr.strip().splitlines()[0] if p.stderr.strip() else ""


def old_signal(path: str, root: str) -> bool:
    """Round 1's expression, verbatim."""
    return ancestor_rc(path, root)[0] == 0


def new_signal(path: str, root: str) -> str:
    """The fix: three outcomes, because git reports three."""
    code = ancestor_rc(path, root)[0]
    return {0: "ancestor", 1: "not-ancestor"}.get(code, "undecidable")


def main() -> int:
    rows = json.loads((HERE / "enumerate-checkouts.json").read_text(encoding="utf-8"))[
        "rows"
    ]
    seen: dict[str, dict] = {}
    for r in rows:
        rp = os.path.realpath(r["path"]).replace("\\", "/").rstrip("/").lower()
        seen.setdefault(rp, r)
    distinct = list(seen.values())

    buckets: dict[int, list[dict]] = {}
    no_head = 0
    for r in distinct:
        if not run(["git", "rev-parse", "HEAD"], r["path"]).returncode == 0:
            no_head += 1
            continue
        code, err = ancestor_rc(r["path"], ROOT_COMMIT)
        buckets.setdefault(code, []).append({"path": r["path"], "stderr": err})

    codes = sorted(buckets)
    print(f"distinct candidates : {len(distinct)}")
    print(f"no HEAD             : {no_head}")
    for c in codes:
        print(f"  rc={c:<4} rows={len(buckets[c])}")

    # ---- CONTROL: the splitter must actually observe the three-way split. Two codes
    # would mean rc=128 never occurs here and the defect is unexercised -- in which case
    # this proof measures nothing and must fail rather than print a reassuring table.
    control_ok = 0 in buckets and 1 in buckets and 128 in buckets
    print(f"\nCONTROL distinct rc codes observed: {codes}  three-way={control_ok}")
    if not control_ok:
        print(
            "FAILED:rc128-redproof splitter did not observe rc 0/1/128 -- unexercised"
        )
        return 3

    # ---- The both-states comparison, on one representative of each real code.
    sample = {c: buckets[c][0]["path"] for c in (0, 1, 128)}
    table = []
    for c, path in sample.items():
        table.append(
            {
                "rc": c,
                "path": path,
                "old_returns": old_signal(path, ROOT_COMMIT),
                "new_returns": new_signal(path, ROOT_COMMIT),
            }
        )
    print(f"\n{'rc':<5}{'OLD (== 0)':<14}{'NEW (3-way)':<16}path")
    for t in table:
        print(
            f"{t['rc']:<5}{str(t['old_returns']):<14}{t['new_returns']:<16}{t['path']}"
        )

    old_conflates = (
        next(t for t in table if t["rc"] == 1)["old_returns"]
        == next(t for t in table if t["rc"] == 128)["old_returns"]
    )
    new_separates = (
        next(t for t in table if t["rc"] == 1)["new_returns"]
        != next(t for t in table if t["rc"] == 128)["new_returns"]
    )
    print(f"\nOLD conflates rc=1 with rc=128 : {old_conflates}   <- the defect")
    print(f"NEW separates them             : {new_separates}   <- the fix")

    # ---- Is the rc=128 population actually shallow? A second, mechanically different
    # signal for the same rows: git's own shallow flag, which does not consult the root.
    shallow_rows = []
    for row in buckets[128]:
        p = run(["git", "rev-parse", "--is-shallow-repository"], row["path"])
        origin = run(["git", "remote", "get-url", "origin"], row["path"])
        shallow_rows.append(
            {
                "path": row["path"],
                "is_shallow": p.stdout.strip(),
                "origin": origin.stdout.strip() if origin.returncode == 0 else "",
                "stderr": row["stderr"],
            }
        )
    n_shallow = sum(1 for r in shallow_rows if r["is_shallow"] == "true")
    n_toolchain = sum(
        1 for r in shallow_rows if "agent-skills-toolchain" in r["origin"]
    )
    print(f"\nrc=128 rows              : {len(shallow_rows)}")
    print(f"  is-shallow-repository  : {n_shallow}")
    print(f"  origin is THIS repo    : {n_toolchain}")
    for r in shallow_rows:
        if "agent-skills-toolchain" in r["origin"]:
            print(f"    shallow={r['is_shallow']:<6}{r['path']}")

    report = {
        "distinct_candidates": len(distinct),
        "no_head": no_head,
        "rc_histogram": {str(c): len(v) for c, v in sorted(buckets.items())},
        "control_three_way_split": control_ok,
        "both_states": table,
        "old_conflates_1_and_128": old_conflates,
        "new_separates_1_and_128": new_separates,
        "rc128_rows": shallow_rows,
        "rc128_shallow": n_shallow,
        "rc128_origin_is_toolchain": n_toolchain,
    }
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(report, fh, indent=2)
    print(f"\nwrote {OUT}")

    if not (old_conflates and new_separates):
        print("FAILED:rc128-redproof the defect did not reproduce")
        return 1
    print(
        f"SUCCESS:rc128-redproof rc128={len(shallow_rows)} shallow={n_shallow} "
        f"toolchain={n_toolchain}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
