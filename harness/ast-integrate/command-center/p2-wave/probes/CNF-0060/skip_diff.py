"""Skip / xfail / deselect set-diff and the planted-skip detector control."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SUITE_SRC = HERE / "fixtures" / "suite"

from runner import PLANTED_REASON, PLANTED_TEST, plant_skip, run_suite  # noqa: E402

PASS_LIKE = frozenset({"passed", "xpassed"})
FAIL_LIKE = frozenset({"failed", "error"})


def _index(report: dict[str, Any]) -> dict[str, str]:
    return {str(m["id"]): str(m.get("outcome") or "") for m in report.get("members") or []}


def symmetric_difference(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    b = _index(before)
    a = _index(after)
    only_before = sorted(set(b) - set(a))
    only_after = sorted(set(a) - set(b))
    flipped: list[dict[str, str]] = []
    for tid in sorted(set(b) & set(a)):
        if b[tid] != a[tid]:
            flipped.append({"id": tid, "from": b[tid], "to": a[tid]})
    to_pass = sum(1 for f in flipped if f["from"] in FAIL_LIKE and f["to"] in PASS_LIKE)
    to_fail = sum(1 for f in flipped if f["from"] in PASS_LIKE and f["to"] in FAIL_LIKE)
    return {
        "only_in_before": only_before,
        "only_in_after": only_after,
        "flipped": flipped,
        "counts": {
            "before_only": len(only_before),
            "after_only": len(only_after),
            "flipped": len(flipped),
            "flipped_to_pass": to_pass,
            "flipped_to_fail": to_fail,
        },
    }


def skip_sets(report: dict[str, Any]) -> dict[str, Any]:
    skipped = [m for m in report["members"] if m.get("outcome") == "skipped"]
    by_kind: dict[str, list[str]] = {}
    for m in skipped:
        by_kind.setdefault(str(m.get("skip_kind") or "unspecified"), []).append(m["id"])
    for k in by_kind:
        by_kind[k].sort()
    return {
        "skipped_ids": sorted(m["id"] for m in skipped),
        "skipped_with_reasons": [
            {
                "id": m["id"],
                "reason": m.get("skip_reason") or m.get("diagnostic") or "",
                "skip_kind": m.get("skip_kind"),
            }
            for m in skipped
        ],
        "xfailed_ids": list(report.get("xfailed_ids") or []),
        "deselected_ids": list(report.get("deselected_ids") or []),
        "executed_ids": list(report.get("executed_ids") or []),
        "by_skip_kind": by_kind,
    }


def newly_disabled(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    b, a = skip_sets(before), skip_sets(after)
    newly_skipped = sorted(set(a["skipped_ids"]) - set(b["skipped_ids"]))
    newly_xfailed = sorted(set(a["xfailed_ids"]) - set(b["xfailed_ids"]))
    newly_deselected = sorted(set(a["deselected_ids"]) - set(b["deselected_ids"]))
    stopped = sorted(set(b["executed_ids"]) - set(a["executed_ids"]))
    reasons = {r["id"]: r for r in a["skipped_with_reasons"]}
    justifications = []
    for tid in stopped:
        row = reasons.get(tid)
        justifications.append(
            {
                "id": tid,
                "justification": (row or {}).get("reason") or "",
                "skip_kind": (row or {}).get("skip_kind"),
                "recorded": bool(row and (row.get("reason") or "").strip()),
            }
        )
    return {
        "newly_skipped": newly_skipped,
        "newly_xfailed": newly_xfailed,
        "newly_deselected": newly_deselected,
        "stopped_executing": stopped,
        "justifications": justifications,
        "executed_count_before": len(b["executed_ids"]),
        "executed_count_after": len(a["executed_ids"]),
        "passed_count_before": before["counts"]["passed"],
        "passed_count_after": after["counts"]["passed"],
        "passed_count_unchanged": before["counts"]["passed"] == after["counts"]["passed"],
        "executed_count_dropped": len(a["executed_ids"]) < len(b["executed_ids"]),
    }


def run_planted_skip_control(workdir: Path | None = None) -> dict[str, Any]:
    own = workdir is None
    root = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="cnf0060-"))
    suite = root / "suite"
    if suite.exists():
        shutil.rmtree(suite)
    shutil.copytree(SUITE_SRC, suite)
    before = run_suite(suite)
    planted_id = plant_skip(suite)
    after = run_suite(suite)
    diff = symmetric_difference(before, after)
    disabled = newly_disabled(before, after)
    before["label"] = "fixture-before-plant"
    after["label"] = "fixture-after-planted-skip"
    fired = (
        planted_id in disabled["newly_skipped"]
        and planted_id in disabled["stopped_executing"]
        and PLANTED_REASON
        in next(
            (j["justification"] for j in disabled["justifications"] if j["id"] == planted_id),
            "",
        )
        and disabled["executed_count_dropped"]
    )
    kinds_after = skip_sets(after)["by_skip_kind"]
    result = {
        "constructed": True,
        "fired": fired,
        "planted_id": planted_id,
        "planted_test": PLANTED_TEST,
        "planted_reason": PLANTED_REASON,
        "before": before,
        "after": after,
        "symmetric_difference": diff,
        "disabled": disabled,
        "unconditional_skips_after": kinds_after.get("unconditional") or [],
        "platform_conditional_skips_after": kinds_after.get("platform-conditional") or [],
        "kinds_distinct": bool(kinds_after.get("unconditional"))
        and bool(kinds_after.get("platform-conditional"))
        and set(kinds_after.get("unconditional") or []).isdisjoint(
            set(kinds_after.get("platform-conditional") or [])
        ),
        "workdir": str(root),
    }
    if own:
        shutil.rmtree(root, ignore_errors=True)
        result["workdir"] = None
    return result


def payload_from_receipt(doc: dict[str, Any]) -> dict[str, Any]:
    """Read skip-diff fields from a receipt (report.*) or a legacy top-level doc."""
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    before = report.get("before") if isinstance(report.get("before"), dict) else None
    if not before:
        before = doc.get("before") if isinstance(doc.get("before"), dict) else {}
    after = report.get("after") if isinstance(report.get("after"), dict) else None
    if not after:
        after = doc.get("after") if isinstance(doc.get("after"), dict) else {}
    controls = report.get("controls") if isinstance(report.get("controls"), dict) else None
    if not controls:
        controls = doc.get("controls") if isinstance(doc.get("controls"), dict) else {}
    planted = controls.get("planted_skip") if isinstance(controls.get("planted_skip"), dict) else {}
    return {
        "before": before,
        "after": after,
        "controls": controls,
        "planted_skip": planted,
        "executed_ids_before": list(
            report.get("executed_ids_before")
            or doc.get("executed_ids_before")
            or before.get("executed_ids")
            or []
        ),
        "executed_ids_after": list(
            report.get("executed_ids_after")
            or doc.get("executed_ids_after")
            or after.get("executed_ids")
            or []
        ),
    }


if __name__ == "__main__":
    import json
    import sys

    ctrl = run_planted_skip_control()
    print(
        json.dumps(
            {
                "fired": ctrl["fired"],
                "kinds_distinct": ctrl["kinds_distinct"],
                "planted_id": ctrl["planted_id"],
                "executed_before": ctrl["disabled"]["executed_count_before"],
                "executed_after": ctrl["disabled"]["executed_count_after"],
                "passed_unchanged": ctrl["disabled"]["passed_count_unchanged"],
            },
            sort_keys=True,
        )
    )
    raise SystemExit(0 if ctrl["fired"] and ctrl["kinds_distinct"] else 1)
