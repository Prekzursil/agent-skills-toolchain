#!/usr/bin/env python3
"""AUD-0042 probe1 -- runner exit-code per CI test step (live, fail-closed).

Re-derives the CI-gap step census from the artifact's recorded rows: the 32
gap steps classify coherently (tests-ran / target-absent / collected-zero /
isolation-ran), the per-row success rule is `exit_code == 0 and collected > 0
and classification == tests-ran`, pytest's no-tests-collected exit code 5 is
recorded on collected-zero rows, and the headline totals recompute from the
rows. Both-states control: a synthetic zero-collect/exit-0 row must NOT count
as test-success; a one-test row must.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
OUT = REPO / "command-center/audit/AUD-0042-close-baseline-ci-gap.json"
UNIT = "AUD-0042"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def main() -> int:
    fails: list[str] = []
    notes: list[str] = []
    try:
        text = OUT.read_text(encoding="utf-8")
        doc = json.loads(text)
    except Exception as exc:
        print(f"FAILED:{UNIT}-probe1 artifact unreadable: {type(exc).__name__}")
        return 1

    def check(ok: bool, label: str, detail: str = "") -> None:
        if not ok:
            fails.append(f"{label}{': ' + detail if detail else ''}")

    # structural predicate
    check(isinstance(doc, dict), "artifact not a JSON object")
    check(doc.get("unit_id") == UNIT, "unit_id mismatch", str(doc.get("unit_id")))
    check(
        str(doc.get("state", "")).upper() not in NOT_DELIVERING,
        "self-declared non-delivery",
        str(doc.get("state")),
    )
    check(OUT.stat().st_size > 0, "artifact empty")
    sent = str(doc.get("completion_sentinel") or doc.get("sentinel") or "")
    check(bool(sent) and sent in text, "completion sentinel absent")

    def counts_success(row: dict) -> bool:
        """The recorded success rule: exit 0 AND collected > 0 AND tests actually ran."""
        return (
            row.get("exit_code") == 0
            and int(row.get("collected") or 0) > 0
            and row.get("classification") == "tests-ran"
        )

    gap = doc.get("gap_steps") or []
    check(len(gap) == 32, "gap_steps != 32 rows", str(len(gap)))
    classes = Counter(str(r.get("classification")) for r in gap)
    check(classes.get("tests-ran") == 18 and classes.get("target-absent") == 10
          and classes.get("collected-zero") == 3 and classes.get("isolation-ran") == 1,
          "gap step classification mix drifted", json.dumps(dict(classes)))
    for r in gap:
        idx = r.get("index")
        check(isinstance(r.get("exit_code"), int), "exit_code not an int", str(idx))
        counted = r.get("counted_as_test_success") is True
        check(counted == counts_success(r),
              "row counted_as_test_success violates the exit+collected rule",
              f"row {idx}: counted={counted} rule={counts_success(r)}")
        if r.get("classification") == "tests-ran":
            # skipped tests make the sum strict; it can never exceed collected
            check(int(r.get("passed") or 0) + int(r.get("failed") or 0)
                  + int(r.get("errored") or 0) <= int(r.get("collected") or 0),
                  "passed+failed+errored exceeds collected", f"row {idx}")
            if r.get("failed") == 0 and r.get("errored") == 0:
                check(r.get("exit_code") == 0, "clean summary with non-zero exit", f"row {idx}")
        if r.get("classification") == "collected-zero":
            check(int(r.get("collected") or 0) == 0, "collected-zero row with collected > 0",
                  f"row {idx}")
            check(r.get("counted_as_test_success") is False,
                  "zero-collect row counted as test-success", f"row {idx}")
        if r.get("classification") == "isolation-ran":
            check(r.get("counted_as_test_success") is False,
                  "isolation run counted as test-success", f"row {idx}")

    # headline totals recompute from rows
    head = doc.get("headline") or {}
    n_present = sum(1 for r in gap if r.get("present_paths"))
    n_counted = sum(1 for r in gap if r.get("counted_as_test_success") is True)
    n_collected = sum(int(r.get("collected") or 0) for r in gap)
    check(head.get("gap_steps_recorded") == len(gap), "headline gap_steps_recorded drift")
    check(head.get("gap_targets_present") == n_present, "headline gap_targets_present drift",
          f"{head.get('gap_targets_present')} vs {n_present}")
    check(head.get("gap_counted_as_test_success") == n_counted,
          "headline gap_counted_as_test_success drift",
          f"{head.get('gap_counted_as_test_success')} vs {n_counted}")
    check(head.get("gap_collected_total") == n_collected, "headline gap_collected_total drift",
          f"{head.get('gap_collected_total')} vs {n_collected}")

    ws = doc.get("worktree_never_ci_steps") or []
    check(len(ws) == 10, "worktree_never_ci_steps != 10 rows", str(len(ws)))
    for r in ws:
        check(isinstance(r.get("exit_code"), int), "ws exit_code not int", str(r.get("name")))
        check((r.get("counted_as_test_success") is True) == counts_success(r),
              "ws row counted_as_test_success violates the rule", str(r.get("name")))

    # both-states control on the recorded rule
    zero_collect = {"exit_code": 0, "collected": 0, "classification": "tests-ran"}
    one_test = {"exit_code": 0, "collected": 1, "classification": "tests-ran"}
    check(not counts_success(zero_collect),
          "zero-collect exit-0 row counts as success (control cannot fire)")
    check(counts_success(one_test), "one-test exit-0 row does not count (over-strict rule)")

    # honesty: raw per-step logs instrument-absent on this worktree (drift note)
    raw_dir = REPO / "command-center/p2-wave/probes/AUD-0042/runs/raw"
    if not raw_dir.is_dir():
        notes.append(
            "instrument-absent: the raw per-step logs (command-center/p2-wave/probes/"
            "AUD-0042/runs/raw/*.txt referenced by gap_steps rows) were lost with the prior "
            "builder's tree; this probe re-derives the recorded summaries' internal "
            "arithmetic and the recorded exit/collected success rule instead"
        )

    report = {
        "probe": "probe1-runner-exit-code-per-step",
        "unit_id": UNIT,
        "gap_rows": len(gap),
        "classifications": dict(classes),
        "recomputed": {"targets_present": n_present, "counted_success": n_counted,
                       "collected_total": n_collected},
        "notes": notes,
        "fails": fails,
    }
    print(json.dumps(report, indent=1, ensure_ascii=False))
    if fails:
        print(f"FAILED:{UNIT}-probe1 " + "; ".join(fails))
        return 1
    print(f"SUCCESS:{UNIT}-probe1 exit-code census re-derived (32 rows: "
          f"{n_present} targets present, {n_counted} counted success, {n_collected} collected); "
          "zero-collect control fires, one-test control counts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
