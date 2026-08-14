"""Close round 2's residual #2, and re-test the alias assumption at the new population size.

TWO QUESTIONS, both left open when round 2 scored its DoD.

(A) ALIAS DOUBLE-COUNT. Round 1's dedupe collapsed a 4,447-entry walk to 1,840 real paths by
    realpath, and the round-1 audit measured 0 realpath collisions -- but across the 170-row
    population. Round 2 added 8 rc=128-resolved rows, and two rows in the CURRENT population
    are spelled through the Windows legacy junction `Local Settings` (-> AppData/Local). If
    the real path is ALSO in the population, 178 is inflated. Re-measure at 178 rather than
    inherit a count taken at 170.

(B) THE `unpushed = null` HOLE. Round 2's DoD table scored "unique-content measured per clone"
    as PASS while five checkouts carry `unpushed: null` -- "no_remote: unpushed is undefined,
    not 0". `null` is the ABSENCE of a measurement, and these five are the highest-risk rows
    on the board: with no remote, nothing in them is in git anywhere else by definition of the
    remote. Round 2 named the settling experiment in its own residual #2 and did not run it:
    "test each commit's presence in canonical's store".

    This runs it, at BLOB level rather than commit level. Commit-object identity is the wrong
    instrument -- REPO-TOPOLOGY.md rule 4 and this lane's own round-1 finding both record that
    squash-merge keeps a unique commit SHA forever, so a commit absent from another store says
    nothing about whether its CONTENT is absent. What matters for data loss is whether the
    BYTES exist somewhere else.

CONTROLS, both states:
  alias      a known junction pair must resolve EQUAL and a known-distinct pair must NOT.
  blob       a blob known to be in canonical must read present, and a fabricated SHA absent,
             against the same batched reader. Reader plausibility floor: canonical must hold
             more than 1,000 objects or the reader is broken, not the store empty.

Read-only: `cat-file --batch-check` and `ls-tree` only. No checkout, no write, no worktree
subcommand, nothing deleted.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "noremote-alias.json"
POP_SRC = HERE / "identity-by-ancestry.json"
CLASSIFIED = HERE / "population-classified.json"

CANONICAL = "C:/Users/Prekzursil/source/agent-skills-toolchain"
FAB_SHA = "0" * 39 + "1"


def git(args: list[str], cwd: str, stdin: str | None = None) -> tuple[int, str]:
    p = subprocess.run(
        args,
        cwd=cwd,
        input=stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return p.returncode, p.stdout


def batch_present(store: str, shas: list[str]) -> dict[str, bool]:
    """One `cat-file --batch-check` spawn for the whole list, not one per object.

    Round 1 measured the naive shape at ~16k Windows process spawns and blew a 900s budget.
    """
    if not shas:
        return {}
    rc, out = git(
        ["git", "cat-file", "--batch-check", "--buffer"],
        store,
        stdin="\n".join(shas) + "\n",
    )
    res: dict[str, bool] = {}
    for line, sha in zip(out.splitlines(), shas):
        res[sha] = " missing" not in line and not line.endswith("missing")
    for s in shas:
        res.setdefault(s, False)
    return res


def main() -> int:
    paths = json.loads(POP_SRC.read_text(encoding="utf-8"))["all_checkout_paths"]
    print(f"population: {len(paths)}")

    # ------------------------------------------------------------------ (A) aliases
    # CONTROL: a known junction pair must collapse, a known-distinct pair must not.
    ctl_a = os.path.realpath("C:/Users/Prekzursil/Local Settings/Application Data")
    ctl_b = os.path.realpath("C:/Users/Prekzursil/AppData/Local")
    ctl_c = os.path.realpath("C:/Users/Prekzursil/source")
    alias_ok = (ctl_a.lower() == ctl_b.lower()) and (ctl_a.lower() != ctl_c.lower())
    print(f"CONTROL junction pair equal: {ctl_a.lower() == ctl_b.lower()}")
    print(f"CONTROL distinct pair equal: {ctl_a.lower() == ctl_c.lower()}")
    print(f"  discriminates: {alias_ok}")
    if not alias_ok:
        print("FAILED:noremote-alias realpath control did not discriminate")
        return 3

    groups: dict[str, list[str]] = {}
    for p in paths:
        groups.setdefault(os.path.realpath(p).replace("\\", "/").lower(), []).append(p)
    collisions = {k: v for k, v in groups.items() if len(v) > 1}
    print(f"\nrealpath groups: {len(groups)}   collisions: {len(collisions)}")
    for real, members in collisions.items():
        print(f"  ALIAS GROUP -> {real}")
        for m in members:
            print(f"      {m}")
    print(f"  distinct real checkouts: {len(groups)}  (population rows: {len(paths)})")

    # ------------------------------------------------------------- (B) the 5 no-remote
    classified = json.loads(CLASSIFIED.read_text(encoding="utf-8"))
    no_remote = classified["no_remote"]
    print(f"\nno-remote checkouts: {len(no_remote)}")

    # CONTROL: the blob reader, both states, against canonical.
    rc, cnt = git(["git", "rev-list", "--objects", "--all"], CANONICAL)
    canon_objs = len(cnt.splitlines())
    rc_h, head = git(["git", "rev-parse", "HEAD"], CANONICAL)
    rc_t, tree = git(["git", "ls-tree", "-r", "HEAD"], CANONICAL)
    known_sha = ""
    for ln in tree.splitlines():
        parts = ln.split()
        if len(parts) >= 3 and parts[1] == "blob":
            known_sha = parts[2]
            break
    probe = batch_present(CANONICAL, [known_sha, FAB_SHA])
    blob_ok = probe.get(known_sha) is True and probe.get(FAB_SHA) is False
    print(
        f"CONTROL canonical objects={canon_objs} known-blob={probe.get(known_sha)} "
        f"fabricated={probe.get(FAB_SHA)}  discriminates: {blob_ok}"
    )
    if canon_objs < 1000 or not blob_ok:
        print("FAILED:noremote-alias blob reader control did not discriminate")
        return 3

    rows = []
    for p in no_remote:
        row: dict = {"path": p, "exists": Path(p).exists()}
        if not row["exists"]:
            rows.append(row)
            continue
        rc_h, head = git(["git", "rev-parse", "HEAD"], p)
        if rc_h != 0:
            row["head"] = None
            row["commits"] = 0
            row["note"] = (
                "no HEAD (0-commit working copy); nothing is committed to compare"
            )
            rows.append(row)
            print(f"\n  {p}\n    0-commit working copy -- no committed content to test")
            continue
        row["head"] = head.strip()[:8]
        rc_c, commits = git(["git", "rev-list", "HEAD"], p)
        clist = [c for c in commits.split() if c]
        row["commits"] = len(clist)
        rc_t, tree = git(["git", "ls-tree", "-r", "HEAD"], p)
        blobs: dict[str, str] = {}
        for ln in tree.splitlines():
            parts = ln.split(maxsplit=3)
            if len(parts) >= 4 and parts[1] == "blob":
                blobs[parts[2]] = parts[3].strip()
        present = batch_present(CANONICAL, sorted(blobs))
        missing = sorted(sha for sha, ok in present.items() if not ok)
        row["tracked_blobs"] = len(blobs)
        row["blobs_absent_from_canonical"] = len(missing)
        row["examples_absent"] = [blobs[s] for s in missing[:8]]
        commits_present = batch_present(CANONICAL, clist)
        row["commits_absent_from_canonical"] = sum(
            1 for ok in commits_present.values() if not ok
        )
        rows.append(row)
        print(f"\n  {p}")
        print(f"    commits={len(clist)}  tracked blobs={len(blobs)}")
        print(
            f"    commits absent from canonical : {row['commits_absent_from_canonical']}"
        )
        print(
            f"    BLOBS   absent from canonical : {len(missing)}   <- the data-loss number"
        )
        for ex in row["examples_absent"][:5]:
            print(f"        {ex}")

    report = {
        "population_rows": len(paths),
        "distinct_real_checkouts": len(groups),
        "alias_collisions": {k: v for k, v in collisions.items()},
        "alias_control": {
            "junction_pair_equal": ctl_a.lower() == ctl_b.lower(),
            "distinct_pair_equal": ctl_a.lower() == ctl_c.lower(),
            "discriminates": alias_ok,
        },
        "blob_reader_control": {
            "canonical_objects": canon_objs,
            "known_blob_present": probe.get(known_sha),
            "fabricated_present": probe.get(FAB_SHA),
            "discriminates": blob_ok,
        },
        "no_remote_rows": rows,
    }
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(report, fh, indent=2)
    print(f"\nwrote {OUT}")
    at_risk = sum(1 for r in rows if r.get("blobs_absent_from_canonical", 0) > 0)
    print(
        f"SUCCESS:noremote-alias rows={len(paths)} distinct={len(groups)} "
        f"collisions={len(collisions)} no_remote={len(no_remote)} holding_unique_bytes={at_risk}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
