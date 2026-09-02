#!/usr/bin/env python3
"""Both-states control harness for health sub-checks.

A check is TRUSTED only when it is SUCCESS on the known-good install and
FAILED on that check's own seeded breakage. Same verdict in both states
is UNTRUSTWORTHY (silent-both or fire-both). A missing broken fixture is
UNTRUSTWORTHY, not skipped.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Callable

import health as H
import scenario as S

CheckFn = Callable[[Path], H.CheckResult]


def pair(
    fn: CheckFn,
    good_root: Path,
    broken_root: Path | None,
    check_id: str,
) -> dict[str, Any]:
    good = H.safe_run(check_id, fn, Path(good_root))
    if broken_root is None:
        return {
            "id": check_id,
            "good": good.as_dict(),
            "broken": None,
            "trusted": False,
            "trust": "UNTRUSTWORTHY",
            "reason": "missing-broken-fixture",
        }
    broken = H.safe_run(check_id, fn, Path(broken_root))
    trusted = good.verdict == H.SUCCESS and broken.verdict == H.FAILED
    if trusted:
        trust, reason = "TRUSTED", "silent-on-good-fires-on-broken"
    elif good.verdict == broken.verdict:
        trust, reason = "UNTRUSTWORTHY", "same-verdict-both-states"
    else:
        trust, reason = "UNTRUSTWORTHY", "did-not-discriminate"
    return {
        "id": check_id,
        "good": good.as_dict(),
        "broken": broken.as_dict(),
        "trusted": trusted,
        "trust": trust,
        "reason": reason,
    }


def specificity(report: dict[str, Any], target: str) -> dict[str, Any]:
    """On a tree broken only for `target`, only that sub-check may be FAILED."""
    failed = [
        cid
        for cid, row in (report.get("subchecks") or {}).items()
        if row.get("verdict") == H.FAILED
    ]
    others_green = [
        cid
        for cid in H.SUBCHECK_IDS
        if cid != target
        and (report.get("subchecks") or {}).get(cid, {}).get("verdict") == H.SUCCESS
    ]
    only_target = failed == [target]
    return {
        "target": target,
        "failed": failed,
        "others_green": others_green,
        "only_target_failed": only_target,
        "others_all_success": len(others_green) == len(H.SUBCHECK_IDS) - 1,
    }


def evaluate_live() -> dict[str, Any]:
    """Build disposable trees, run both-states + aggregate + inert rejection."""
    with tempfile.TemporaryDirectory(prefix="tst0075-") as td:
        base = Path(td)
        good = S.materialize_good(base / "good")
        good_report = H.run_health(good)

        pairs = []
        breakage_reports = []
        for cid in H.SUBCHECK_IDS:
            broken = S.clone_and_break(good, base / f"broken-{cid}", cid)
            row = pair(H.CHECKS[cid], good, broken, cid)
            br = H.run_health(broken)
            spec = specificity(br, cid)
            row["aggregate_on_breakage"] = br["aggregate"]
            row["breakage_green"] = br["green"]
            row["specificity"] = spec
            row["breakage_kind"] = S.BREAKAGE_KIND[cid]
            pairs.append(row)
            breakage_reports.append(
                {
                    "subcheck": cid,
                    "aggregate": br["aggregate"],
                    "green": br["green"],
                    "specificity": spec,
                }
            )

        inert = pair(H.always_ok, good, base / "broken-hooks_loaded", "always_ok")
        # always_ok must see the hooks-broken tree and still return SUCCESS.
        inert_broken_root = base / "broken-hooks_loaded"
        inert = pair(H.always_ok, good, inert_broken_root, "always_ok")
        fire_both = pair(H.always_failed, good, inert_broken_root, "always_failed")
        missing_fx = pair(H.CHECKS["hooks_loaded"], good, None, "hooks_loaded")

        blocked_results = {
            cid: H.safe_run(cid, H.CHECKS[cid], good) for cid in H.SUBCHECK_IDS
        }
        blocked_results["blocked_probe"] = H.blocked_probe(good)
        blocked_agg = H.aggregate(
            blocked_results, expected_ids=H.SUBCHECK_IDS + ("blocked_probe",)
        )

        unrun = {
            cid: H.safe_run(cid, H.CHECKS[cid], good)
            for cid in H.SUBCHECK_IDS
            if cid != "cache_valid"
        }
        unrun_agg = H.aggregate(unrun, expected_ids=H.SUBCHECK_IDS)

        def _boom(_root: Path) -> H.CheckResult:
            raise RuntimeError("injected-boom")

        throwing = H.safe_run("throws", _boom, good)

        return {
            "good_aggregate": good_report["aggregate"],
            "good_green": good_report["green"],
            "good_subchecks": good_report["subchecks"],
            "pairs": pairs,
            "breakage_reports": breakage_reports,
            "inert_always_ok": inert,
            "inert_always_failed": fire_both,
            "missing_broken_fixture": missing_fx,
            "blocked_aggregate": blocked_agg,
            "unrun_aggregate": unrun_agg,
            "throwing": throwing.as_dict(),
        }


def assertions(live: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if live.get("good_aggregate") != H.GREEN or not live.get("good_green"):
        errors.append(f"good install is not GREEN ({live.get('good_aggregate')})")
    for row in live.get("pairs") or []:
        cid = row.get("id")
        if not row.get("trusted"):
            errors.append(f"{cid} not trusted: {row.get('reason')}")
        if row.get("breakage_green"):
            errors.append(f"{cid} breakage still GREEN")
        spec = row.get("specificity") or {}
        if not spec.get("only_target_failed") or not spec.get("others_all_success"):
            errors.append(f"{cid} not specific: {spec}")
    inert = live.get("inert_always_ok") or {}
    if inert.get("trusted") or not (inert.get("good") or {}).get("verdict") == H.SUCCESS:
        errors.append(f"always_ok was not rejected as inert: {inert}")
    if inert.get("broken", {}).get("verdict") != H.SUCCESS:
        errors.append("always_ok did not stay SUCCESS on a broken tree")
    fire = live.get("inert_always_failed") or {}
    if fire.get("trusted"):
        errors.append("always_failed was trusted (fires in both states)")
    missing = live.get("missing_broken_fixture") or {}
    if missing.get("trusted") or missing.get("reason") != "missing-broken-fixture":
        errors.append(f"missing broken fixture was not UNTRUSTWORTHY: {missing}")
    if live.get("blocked_aggregate") == H.GREEN:
        errors.append("BLOCKED extra probe still produced GREEN aggregate")
    if live.get("unrun_aggregate") == H.GREEN:
        errors.append("unrun sub-check still produced GREEN aggregate")
    throwing = live.get("throwing") or {}
    if throwing.get("verdict") != H.FAILED:
        errors.append(f"thrown check was not FAILED: {throwing}")
    return errors
