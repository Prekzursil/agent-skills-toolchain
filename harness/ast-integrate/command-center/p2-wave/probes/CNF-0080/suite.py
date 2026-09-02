#!/usr/bin/env python3
"""CNF-0080 live suite: dry-run plan vs filesystem-census trace.

Controls:
  extra-write  — apply writes sneak.txt; census must see it; plan must not.
  lying-delete — dry-run omits victim.txt delete; apply still deletes; detector fires.
  honest-parity — shared plan matches census.
  dry-run-zero  — dry-run census is empty.
  close.py      — production dry-run vs real --note on a disposable catalog.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import close_subject as C  # noqa: E402
import fs_tracer as T  # noqa: E402
import mutator as O  # noqa: E402

SNEAK = O.SNEAK
VICTIM = O.VICTIM


def report_field(doc: dict[str, Any], name: str, default: Any = None) -> Any:
    """Read a probe-facing field from a receipt-shaped or legacy artifact.

    Domain payload lives under report (receipt_core additionalProperties is
    false). Legacy top-level keys are still accepted so older artifacts work.
    """
    if not isinstance(doc, dict):
        return default
    if name in doc and doc[name] is not None:
        return doc[name]
    report = doc.get("report")
    if isinstance(report, dict) and name in report and report[name] is not None:
        return report[name]
    ext = doc.get("extensions")
    if isinstance(ext, dict) and name in ext and ext[name] is not None:
        return ext[name]
    return default


def _keys(actions: list[dict[str, Any]]) -> set[tuple[str, str]]:
    return set(T.keyset(actions))


def _omitted_destructive(predicted: list[dict[str, Any]], traced: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pred = _keys(predicted)
    out = []
    for a in traced:
        if a.get("op") == "delete" and (a.get("op"), a.get("path")) not in pred:
            out.append(a)
    return out


def extra_write_control() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="cnf0080-extra-") as tmp:
        root = Path(tmp) / "target"
        O.seed(root)
        predicted = O.dry_run()
        before = T.census(root)
        O.apply_extra_write(root)
        traced = T.diff_census(before, T.census(root))
    sneak_traced = any(a.get("path") == SNEAK for a in traced)
    sneak_predicted = any(a.get("path") == SNEAK for a in predicted)
    captured = sneak_traced and not sneak_predicted
    return {
        "id": "extra-write-control",
        "predicted_actions": predicted,
        "traced_actions": traced,
        "sneak_path": SNEAK,
        "sneak_in_trace": sneak_traced,
        "sneak_in_plan": sneak_predicted,
        "captured_by_tracer": captured,
        "pass": captured,
        "method": "before/after sha256 census of the disposable target; not a log of intentions",
    }


def honest_parity() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="cnf0080-honest-") as tmp:
        root = Path(tmp) / "target"
        O.seed(root)
        predicted = O.dry_run()
        before_dry = T.census(root)
        _ = O.dry_run()
        dry_actions = T.diff_census(before_dry, T.census(root))
        before = T.census(root)
        O.apply(root)
        traced = T.diff_census(before, T.census(root))
    omitted = _omitted_destructive(predicted, traced)
    match = _keys(predicted) == _keys(traced)
    return {
        "id": "honest-shared-plan-parity",
        "predicted_actions": predicted,
        "traced_actions": traced,
        "dry_run_wrote": dry_actions,
        "dry_run_zero_writes": dry_actions == [],
        "keys_match": match,
        "omitted_destructive": omitted,
        "pass": match and dry_actions == [] and omitted == [],
    }


def lying_detector() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="cnf0080-lie-") as tmp:
        root = Path(tmp) / "target"
        O.seed(root)
        predicted = O.lying_plan()
        before = T.census(root)
        O.apply_lying(root)
        traced = T.diff_census(before, T.census(root))
    omitted = _omitted_destructive(predicted, traced)
    fired = any(a.get("path") == VICTIM for a in omitted)
    return {
        "id": "known-broken-omitted-delete",
        "predicted_actions": predicted,
        "traced_actions": traced,
        "omitted_destructive": omitted,
        "p0_filed": fired,
        "classification": "dryrun-understates" if fired else None,
        "pass": fired,
        "note": "A delete present in the real run and absent from the dry-run plan is P0.",
    }


def run_suite() -> dict[str, Any]:
    extra = extra_write_control()
    honest = honest_parity()
    lying = lying_detector()
    with tempfile.TemporaryDirectory(prefix="cnf0080-close-") as tmp:
        close = C.measure(Path(tmp))
    close_ok = (
        close["dry_exit"] == 0
        and close["real_exit"] == 0
        and close["dry_run_zero_writes"] is True
        and len(close["traced_actions"]) >= 1
    )
    return {
        "pass": extra["pass"] and honest["pass"] and lying["pass"] and close_ok,
        "extra_write": extra,
        "honest_parity": honest,
        "lying_detector": lying,
        "close_py": close,
        "close_ok": close_ok,
        "both_lists_attached": True,
    }


def main() -> int:
    report = run_suite()
    print(json.dumps(
        {
            "pass": report["pass"],
            "extra_captured": report["extra_write"]["captured_by_tracer"],
            "honest_match": report["honest_parity"]["keys_match"],
            "detector_fired": report["lying_detector"]["p0_filed"],
            "close_understates": report["close_py"]["understates"],
            "close_traced": report["close_py"]["traced_actions"],
            "close_dry_zero": report["close_py"]["dry_run_zero_writes"],
            "close_dry_exit": report["close_py"]["dry_exit"],
            "close_real_exit": report["close_py"]["real_exit"],
            "close_dry_stdout": report["close_py"]["dry_stdout"][:240],
            "close_real_stderr": report["close_py"]["real_stderr"][:240],
        },
        indent=2,
        sort_keys=True,
        default=str,
    ))
    if not report["pass"]:
        print("FAILED:CNF-0080-suite")
        return 1
    print("SUCCESS:CNF-0080-suite")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
