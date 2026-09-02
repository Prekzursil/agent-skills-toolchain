"""Red-proof: `apply_severed_resolution` must GO RED on each broken state, and only then
may its green on the real file be believed.

Rules/common/single-signal-verification.md sec.3b: before a probe's silence counts as
"fixed", run it against the KNOWN-BROKEN state and confirm it FIRES. This round's whole
subject is a check that passed while a number did not close, so the checks added to repair
it get the treatment first.

Every mutation is applied to a TEMP COPY. `population-classified.json` is never mutated by
this file -- the applier is pointed at the copy by rebinding its module-level OUT.
"""

from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path

import apply_severed_resolution as app

HERE = Path(__file__).resolve().parent
SRC = HERE / "population-classified.json"
OUTFILE = HERE / "redproof-severed.json"


def run_against(report: dict, tmpdir: Path) -> int:
    """Point the applier at a temp copy and return its exit code."""
    path = tmpdir / "population-classified.json"
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(report, fh, indent=2)
    saved = app.OUT
    try:
        app.OUT = path
        return app.main()
    finally:
        app.OUT = saved


def main() -> int:
    baseline = json.loads(SRC.read_text(encoding="utf-8"))
    results: list[dict] = []

    cases: list[tuple[str, str, int]] = []

    def case(name: str, mutate, expect: int, why: str) -> None:
        cases.append((name, why, expect))
        report = copy.deepcopy(baseline)
        mutate(report)
        with tempfile.TemporaryDirectory() as td:
            rc = run_against(report, Path(td))
        results.append(
            {
                "case": name,
                "expected_rc": expect,
                "actual_rc": rc,
                "fired_as_expected": rc == expect,
                "why": why,
            }
        )
        print(f"\n>>> {name}: expected rc={expect} got rc={rc}\n")

    # HEALTHY (the positive control). Without this the four reds below would prove only
    # that the applier can fail, not that it can distinguish.
    case("healthy", lambda r: None, 0, "unmutated copy must apply cleanly")

    def truncate(r: dict) -> None:
        r["rows"] = r["rows"][:5]

    case("floor-breached", truncate, 3, "5 rows is below the plausibility floor")

    def hide_disagreement(r: dict) -> None:
        for row in r["rows"]:
            if row.get("signals_agree") is False:
                row["signals_agree"] = True

    case(
        "no-disagreeing-row",
        hide_disagreement,
        1,
        "the defect it repairs is absent -> must not report success",
    )

    def move_invariant(r: dict) -> None:
        for row in r["rows"]:
            if row.get("kind") == "worktree":
                row["kind"] = "own-store"
                break

    case(
        "invariant-moved",
        move_invariant,
        3,
        "linked_worktrees no longer matches the file it was measured against",
    )

    def break_arithmetic(r: dict) -> None:
        ghost = copy.deepcopy(r["rows"][0])
        ghost["path"] = "C:/Users/Prekzursil/source/_redproof_ghost"
        ghost["kind"] = "bogus-kind"
        ghost["signals_agree"] = True
        r["rows"].append(ghost)

    case(
        "arithmetic-does-not-close",
        break_arithmetic,
        3,
        "a row in no bucket: sum < on_disk, exactly round 2's 177-vs-178 shape",
    )

    all_fired = all(r["fired_as_expected"] for r in results)
    with open(OUTFILE, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(
            {"source": str(SRC), "cases": results, "all_fired": all_fired}, fh, indent=2
        )

    print("=" * 72)
    for r in results:
        mark = "OK " if r["fired_as_expected"] else "MISS"
        print(
            f"  [{mark}] {r['case']:28s} expect={r['expected_rc']} got={r['actual_rc']}"
        )
    print(f"wrote {OUTFILE}")
    if not all_fired:
        print("FAILED:redproof-severed a check did not fire on its broken state")
        return 1
    print(f"SUCCESS:redproof-severed cases={len(results)} all fired")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
