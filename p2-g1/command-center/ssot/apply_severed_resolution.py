"""Land the third signal ON the machine-readable SSOT, without re-running the sweep.

WHY THIS FILE EXISTS. Round 3's write-up said the one `kind-signals-disagree` row "is now
resolved by a third signal". The PROSE was resolved; `population-classified.json` was not --
and `CLAUDE.md` points future agents at that JSON as the machine-readable SSOT. The round-3
verifier confirmed the gap: the blob at HEAD, at two earlier commits, and in the working tree
all still carry `kind_signals_disagree: list[1]` with no resolution field anywhere. A reader
who trusts the file over the prose gets an unclassified row and a kind arithmetic that does
not close (9 + 168 = 177, population 178).

WHY NOT JUST RE-RUN `classify_population.py`. It re-measures 178 live checkouts against a
tree that moved three times this evening -- every row's head/dirty/unpushed would churn, the
diff would be unreviewable, and the one field under repair would be buried in it. This applies
ONLY the resolution, to ONLY the rows whose two primary signals disagree, and refuses to write
if anything else about the file's shape has changed.

NO SECOND IMPLEMENTATION. `resolve_severed` is imported from `classify_population`, not
copied, so the applier and a future fresh sweep cannot drift apart.

Exit codes: 0 applied or already-applied - 1 nothing to do and nothing written - 3 a control
failed, a floor was breached, or an invariant moved.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from classify_population import KNOWN_WORKTREE, OUT, kind_buckets, resolve_severed

FABRICATED = "C:/Users/Prekzursil/source/this-path-does-not-exist-92f1a"
MIN_ROWS = 100  # plausibility floor: this population has been 170-178 all evening


def controls() -> bool:
    """Both states, plus the negative that makes the positive mean something."""
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / ".git").write_text(
            f"gitdir: {Path(td) / 'no-such-admin-dir'}\n", encoding="utf-8"
        )
        synth = resolve_severed(td) or {}
    live_wt = resolve_severed(KNOWN_WORKTREE) or {}
    fabricated = resolve_severed(FABRICATED)

    pos = synth.get("kind") == "severed-worktree"
    neg = live_wt.get("kind") == "worktree"
    none_case = fabricated is None
    print(
        f"CONTROL synthetic missing target -> {synth.get('kind')!r:22s} expect severed"
    )
    print(
        f"CONTROL live linked worktree     -> {live_wt.get('kind')!r:22s} expect worktree"
    )
    print(f"CONTROL fabricated path          -> {fabricated!r:22s} expect None")
    ok = pos and neg and none_case
    print(f"discriminates: {ok}")
    return ok


def main() -> int:
    if not controls():
        print("FAILED:apply-severed control did not discriminate")
        return 3

    report = json.loads(OUT.read_text(encoding="utf-8"))
    rows = report.get("rows") or []
    if len(rows) < MIN_ROWS:
        print(
            f"FAILED:apply-severed only {len(rows)} rows (floor {MIN_ROWS}) - wrong file?"
        )
        return 3

    live = [r for r in rows if r.get("exists")]
    targets = [r for r in live if r.get("signals_agree") is False]
    print(
        f"\nrows={len(rows)} on_disk={len(live)} primary-signal disagreements={len(targets)}"
    )
    if not targets:
        print(
            "FAILED:apply-severed no disagreeing row found - the defect it repairs is absent"
        )
        return 1

    changed = 0
    for row in targets:
        third = resolve_severed(row["path"])
        if not third:
            # Shape does not apply: leave it UNRESOLVED rather than invent a verdict.
            print(f"  UNRESOLVED (shape does not apply): {row['path']}")
            continue
        before = row.get("kind")
        if row.get("resolved_by") != third["resolved_by"] or before != third["kind"]:
            changed += 1
        row.update(third)
        print(f"  {before} -> {row['kind']}  via {row['resolved_by']}")
        print(f"      pointer: {row['gitdir_pointer']}")
        print(f"      target exists: {row['gitdir_target_exists']}")

    buckets = kind_buckets(live)
    worktrees, clones = buckets["worktrees"], buckets["clones"]
    severed, unresolved = buckets["severed"], buckets["unresolved"]

    # INVARIANT: this applier repairs ONE field. If the two headline kind counts moved, the
    # file is not the one this was measured against and it must not be written.
    for key, got in (
        ("linked_worktrees", len(worktrees)),
        ("independent_clones", len(clones)),
    ):
        was = report.get(key)
        if was != got:
            print(f"FAILED:apply-severed {key} moved {was} -> {got}; refusing to write")
            return 3

    print(
        f"\nkind arithmetic: {len(worktrees)} worktrees + {len(clones)} clones + "
        f"{len(severed)} severed + {len(unresolved)} unresolved = {buckets['sum']} "
        f"vs on_disk {buckets['on_disk']} -> closes={buckets['closes']}"
    )
    if not buckets["closes"]:
        print("FAILED:apply-severed kind arithmetic does not close; refusing to write")
        return 3

    report["severed_worktrees"] = [r["path"] for r in severed]
    report["kind_signals_disagree"] = [r["path"] for r in targets]
    report["kind_signals_disagree_unresolved"] = [r["path"] for r in unresolved]
    report["kind_arithmetic"] = {
        "linked_worktrees": len(worktrees),
        "independent_clones": len(clones),
        "severed_worktrees": len(severed),
        "unresolved": len(unresolved),
        "sum": buckets["sum"],
        "on_disk": buckets["on_disk"],
        "closes": buckets["closes"],
    }

    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(report, fh, indent=2)
    print(f"wrote {OUT}")
    print(
        f"SUCCESS:apply-severed resolved={len(severed)} unresolved={len(unresolved)} "
        f"rows_changed={changed} arithmetic_closes={buckets['closes']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
