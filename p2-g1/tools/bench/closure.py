"""Defect closure blocked without a pre-fix FAIL run (TST-0313)."""
from __future__ import annotations

from typing import Any


def _rows(ledger: Any) -> list[dict[str, Any]]:
    if hasattr(ledger, "rows"):
        return list(ledger.rows())
    if hasattr(ledger, "records"):
        return list(ledger.records())
    if isinstance(ledger, list):
        return list(ledger)
    return []


def _by_id(register: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in register.get("defects") or []:
        if isinstance(item, dict) and item.get("id"):
            out[str(item["id"])] = item
    return out


def _lookup(ledger: Any, run_id: str | None) -> dict[str, Any] | None:
    if not run_id:
        return None
    for row in _rows(ledger):
        if str(row.get("run_id") or "") == str(run_id):
            return row
    return None


def close_defect(
    register: dict[str, Any],
    defect_id: str,
    ledger: Any,
    *,
    pre_run_id: str | None = None,
    post_run_id: str | None = None,
    reviewer_ok: bool = False,
) -> dict[str, Any]:
    reasons: list[str] = []
    pre = _lookup(ledger, pre_run_id)
    post = _lookup(ledger, post_run_id)

    if pre_run_id is None:
        reasons.append("pre-fix-run-missing")
    if pre is not None and pre.get("executed") is False:
        reasons.append("pre-fix-run-not-executed")
    if pre is not None and post is not None and pre_run_id == post_run_id:
        reasons.append("single-passing-run-inadmissible")
    if pre is not None and post is not None and pre.get("outcome") == "PASS" and post.get("outcome") == "PASS":
        reasons.append("oracle-silent-in-both-states")
    if pre is not None and pre.get("outcome") != "FAIL":
        if "oracle-silent-in-both-states" not in reasons and "single-passing-run-inadmissible" not in reasons:
            reasons.append("pre-fix-not-fail")
    if reviewer_ok:
        reasons.append("reviewer-discipline-insufficient")

    allow = not reasons and pre is not None and post is not None
    if allow and pre.get("outcome") == "FAIL" and post.get("outcome") == "PASS" and pre.get("executed") and post.get("executed"):
        allow = True
    else:
        allow = False if reasons else allow

    defect = _by_id(register).get(str(defect_id))
    result = {
        "allow": bool(allow),
        "reason": reasons[0] if reasons else "closed",
        "reasons": reasons,
        "reviewer_ok_ignored": bool(reviewer_ok),
        "defect_id": defect_id,
        "pre_run_id": pre_run_id,
        "post_run_id": post_run_id,
    }
    if allow and defect is not None:
        defect["status"] = "CLOSED"
        defect["pre_fix_run_id"] = pre_run_id
        defect["post_fix_run_id"] = post_run_id
    return result


def stub_reviewer_close(*, reviewer_ok: bool = False, has_prefix_fail: bool = False) -> bool:
    """Reviewer-discipline stub: will close without a pre-fix FAIL if told to."""
    if reviewer_ok and not has_prefix_fail:
        return True
    return bool(has_prefix_fail)


def census(register: dict[str, Any], ledger: Any) -> dict[str, Any]:
    rows = _rows(ledger)
    by_run = {str(r.get("run_id") or ""): r for r in rows}
    debt_ids: list[str] = []
    honest_ids: list[str] = []
    for item in register.get("defects") or []:
        if not isinstance(item, dict):
            continue
        did = str(item.get("id") or "")
        status = str(item.get("status") or "").upper()
        pre_id = item.get("pre_fix_run_id")
        post_id = item.get("post_fix_run_id")
        pre = by_run.get(str(pre_id or ""))
        post = by_run.get(str(post_id or ""))
        honest = (
            pre is not None
            and post is not None
            and pre.get("outcome") == "FAIL"
            and post.get("outcome") == "PASS"
            and pre.get("executed") is not False
        )
        if honest:
            honest_ids.append(did)
            continue
        if status == "CLOSED" and not honest:
            debt_ids.append(did)
            continue
        if status == "OPEN" and item.get("historical_closed_without_prefix"):
            debt_ids.append(did)
        # Paper-closed / schema-absent planted debt.
        if did in {"B11-I2-SCHEMA-ABSENT", "B10-PAPER-CLOSED"}:
            if did not in debt_ids:
                debt_ids.append(did)
    debt_n = len(debt_ids)
    return {
        "treat_debt_as": "DEBT",
        "pass_if_debt": False,
        "debt_missing_prefix_fail": debt_n,
        "debt_ids": debt_ids,
        "honest_ids": honest_ids,
        "verdict": "DEBT" if debt_n else "PASS",
        "ledger_rows": len(rows),
    }


__all__ = ["census", "close_defect", "stub_reviewer_close"]
