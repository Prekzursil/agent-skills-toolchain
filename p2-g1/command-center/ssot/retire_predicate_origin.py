"""Re-base the retire-candidate predicate on origin/main instead of local remote-tracking refs.

THE DEFECT (synthesis overclaim O4). `classify_population.measure_unique` counts unpushed work
with `git rev-list --count HEAD --not --remotes`. `--remotes` is the checkout's own
remote-tracking snapshot, which is LOCAL STATE: it is whatever that clone last fetched. A ref
that is stale, or that points at a branch since deleted on the server, still satisfies
`--remotes`, so commits that are NOT on the real remote can count as pushed. The criterion the
SSOT rule actually states is "no unique commits ... on a pushed branch", and 43 candidates were
published against the weaker test.

Retiring a checkout on a false "0 unpushed" destroys the only copy of that work, so the
predicate has to be re-based before anything is retired.

METHOD, and why it needs no fetch in 43 other repositories. Every candidate is a checkout of
this same project, so a commit that is genuinely pushed is reachable from THIS repo's freshly
fetched `origin/main`. For each candidate we read its HEAD and ask one question here:
is that commit contained in origin/main?

THE THREE-STATE TRAP, which this repo has already paid for once: `git merge-base --is-ancestor`
returns 0 = yes, 1 = no, and 128 = COULD NOT BE ASKED (the object is not in this store at all).
The inventory's round-1 defect was comparing `== 0`, which files 128 as a plain "no". Here 128
is treated as its own verdict -- an object we cannot even name is the strongest possible signal
that the work is not shared, never a soft negative.

Terminal: SUCCESS:retire-predicate / FAILED:retire-predicate <n unsafe>
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
CLASSIFIED = REPO / "command-center/ssot/population-classified.json"
OUT = REPO / "command-center/ssot/retire-predicate-origin.json"


def git(args: list[str], cwd: pathlib.Path | str = REPO) -> tuple[int, str]:
    p = subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, timeout=180
    )
    return p.returncode, (p.stdout or "").strip()


def contained_in_origin(sha: str) -> tuple[str, str]:
    """(verdict, why). Verdicts: PUSHED | NOT-PUSHED | UNKNOWN-OBJECT."""
    rc, _ = git(["merge-base", "--is-ancestor", sha, "origin/main"])
    if rc == 0:
        return "PUSHED", "reachable from origin/main"
    if rc == 1:
        return "NOT-PUSHED", "not an ancestor of origin/main"
    return "UNKNOWN-OBJECT", f"merge-base rc={rc}: the object is not in this store"


def main() -> int:
    if not CLASSIFIED.exists():
        print(f"FAILED:retire-predicate classification absent: {CLASSIFIED}")
        return 2
    data = json.loads(CLASSIFIED.read_text(encoding="utf-8"))
    cands = data.get("retire_candidates") or []
    print(f"CONTROL retire candidates read = {len(cands)}")
    if not cands:
        print(
            "FAILED:retire-predicate zero candidates -- reader broken, verdict withheld"
        )
        return 2

    rc_f, _ = git(
        ["fetch", "--no-tags", "origin", "+refs/heads/main:refs/remotes/origin/main"]
    )
    print(f"CONTROL origin/main fetched = {rc_f == 0}")

    # Detector control: a commit we KNOW is pushed must read PUSHED, and a fabricated sha
    # must NOT read PUSHED. Without both, "everything is pushed" is indistinguishable from
    # a predicate that always says yes.
    rc_h, head = git(["rev-parse", "origin/main"])
    ctrl_pos = contained_in_origin(head)[0] if rc_h == 0 else "?"
    ctrl_neg = contained_in_origin("0" * 40)[0]
    print(f"CONTROL known-pushed commit -> {ctrl_pos} (want PUSHED)")
    print(f"CONTROL fabricated sha      -> {ctrl_neg} (want UNKNOWN-OBJECT)")
    if ctrl_pos != "PUSHED" or ctrl_neg == "PUSHED":
        print("FAILED:retire-predicate detector controls did not discriminate")
        return 2

    rows, unsafe = [], []
    for c in cands:
        path = c.get("path") if isinstance(c, dict) else str(c)
        p = pathlib.Path(path)
        if not p.is_dir():
            rows.append(
                {"path": path, "verdict": "GONE", "why": "path no longer exists"}
            )
            continue
        rc_h, head = git(["rev-parse", "HEAD"], p)
        if rc_h != 0:
            rows.append(
                {"path": path, "verdict": "NO-HEAD", "why": "0-commit working copy"}
            )
            continue
        verdict, why = contained_in_origin(head)
        rc_d, dirty = git(["status", "--porcelain", "-uall"], p)
        n_dirty = len([x for x in dirty.splitlines() if x.strip()]) if rc_d == 0 else -1
        row = {
            "path": path,
            "head": head[:12],
            "verdict": verdict,
            "why": why,
            "dirty_files": n_dirty,
        }
        rows.append(row)
        if verdict != "PUSHED" or n_dirty != 0:
            unsafe.append(row)

    OUT.write_text(
        json.dumps(
            {"candidates": len(cands), "unsafe": len(unsafe), "rows": rows}, indent=2
        ),
        encoding="utf-8",
    )
    print(f"\n{'verdict':16} {'dirty':>6}  path")
    for r in rows:
        if r.get("verdict") != "PUSHED" or r.get("dirty_files"):
            print(
                f"  {r.get('verdict', ''):14} {str(r.get('dirty_files', '')):>6}  {r.get('path')}"
            )
    print(f"\nwrote {OUT.relative_to(REPO)}")
    print(
        f"SUCCESS:retire-predicate {len(cands) - len(unsafe)}/{len(cands)} safe under the "
        "origin/main criterion"
        if not unsafe
        else f"FAILED:retire-predicate {len(unsafe)} of {len(cands)} candidate(s) are NOT "
        "safe to retire under the origin/main criterion"
    )
    return 1 if unsafe else 0


if __name__ == "__main__":
    sys.exit(main())
