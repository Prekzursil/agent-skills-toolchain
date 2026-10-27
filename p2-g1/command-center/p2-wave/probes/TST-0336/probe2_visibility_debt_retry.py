#!/usr/bin/env python3
"""Probe 2: quarantine visibility, debt (owner+age), retry-absorption DEFECT.

Signal b. Does not re-score the N=20 ranked list (probe 1). It mutates the
report lane and the retry policy and requires the detector to fire on the
bad state and stay silent on the good state.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import ledger as L  # noqa: E402
from suite import FIXED_NOW, REGISTRY, TESTS, commit_sha  # noqa: E402

ART = REPO / "command-center/receipts/TST-0336.json"
N = 20
UID = "TST-0336"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0336-probe2 {msg}")
    return 1


def check_artifact() -> str | None:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return "receipt missing"
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:TST-0336" not in text:
        return "sentinel absent"
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return f"self-declared {st}"
    return None


def main() -> int:
    err = check_artifact()
    if err:
        return fail(err)

    sha = commit_sha()
    honest = L.measure_suite(
        TESTS, N, sha, max_attempts=1, now=FIXED_NOW, registry=REGISTRY
    )
    ranked = honest["ranked"]

    visible = L.render_report(ranked, hide_quarantined=False)
    hidden = L.render_report(ranked, hide_quarantined=True)
    vis_ids = [r["test_id"] for r in visible]
    hid_ids = [r["test_id"] for r in hidden]
    if "coin_flip" not in vis_ids:
        return fail("visible lane dropped coin_flip")
    coin_vis = next(r for r in visible if r["test_id"] == "coin_flip")
    if coin_vis.get("status") != "QUARANTINED":
        return fail(f"visible coin_flip status={coin_vis.get('status')}")
    if "coin_flip" in hid_ids:
        return fail("hiding lane still lists coin_flip")
    if L.quarantine_hidden(visible, hidden) is not True:
        return fail("hiding detector did not fire on hide_quarantined=True")
    if L.quarantine_hidden(visible, visible) is not False:
        return fail("hiding detector fired on the visible (good) lane")

    # Debt: every quarantined row has owner and age; stripping owner fails.
    quarantined = [r for r in ranked if r["quarantined"]]
    if not quarantined:
        return fail("no quarantined rows")
    for row in quarantined:
        if not row.get("owner"):
            return fail(f"{row['test_id']} quarantined without owner")
        if row.get("age_days") is None or row["age_days"] < 0:
            return fail(f"{row['test_id']} missing/negative age")
        if row.get("open") is not True:
            return fail(f"{row['test_id']} debt not open")
        debt = L.Debt(
            owner=row["owner"],
            opened_at=row["quarantine_opened_at"],
            deadline=row.get("deadline"),
            age_days=row["age_days"],
            is_open=True,
        )
        if not debt.complete():
            return fail(f"{row['test_id']} debt incomplete on good state")
        stripped = L.Debt(
            owner=None,
            opened_at=row["quarantine_opened_at"],
            deadline=row.get("deadline"),
            age_days=row["age_days"],
            is_open=True,
        )
        if stripped.complete():
            return fail(f"{row['test_id']} owner-stripped debt still complete")

    coin = next(r for r in ranked if r["test_id"] == "coin_flip")
    if coin["owner"] != "test-governance":
        return fail(f"coin_flip owner={coin['owner']}")
    if coin["age_days"] <= 0:
        return fail(f"coin_flip age_days={coin['age_days']}")

    # Retry absorption: 3-attempt finals hide coin_flip and retry_bait.
    defects = L.retry_defects(
        TESTS, N, sha, retry_attempts=3, now=FIXED_NOW, registry=REGISTRY
    )
    reasons = {d["test_id"]: d for d in defects if d["reason"] == "retry-absorbed-flake"}
    if "coin_flip" not in reasons:
        return fail(f"coin_flip retry absorption not filed: {defects}")
    if "retry_bait" not in reasons:
        return fail("retry_bait retry absorption not filed")
    if reasons["coin_flip"]["retry_final_fail_rate"] != 0.0:
        return fail("retry finals for coin_flip were not all-pass")
    if reasons["coin_flip"]["first_attempt_flake_rate"] <= L.THRESHOLD:
        return fail("retry defect did not keep first-attempt flake rate")

    # Good-state retry (max_attempts=1) must not file absorption.
    no_retry = L.retry_defects(
        TESTS, N, sha, retry_attempts=1, now=FIXED_NOW, registry=REGISTRY
    )
    if no_retry:
        return fail(f"max_attempts=1 still filed retry defects: {no_retry}")

    # Quarantined flake cannot block; BROKEN still can.
    if "coin_flip" in honest["suite_blockers"]:
        return fail("quarantined coin_flip blocked the suite")
    if "just_above" in honest["suite_blockers"]:
        return fail("quarantined just_above blocked the suite")
    if "broken_always" not in honest["suite_blockers"]:
        return fail("BROKEN did not block")

    doc = json.loads(ART.read_text(encoding="utf-8"))
    vis = doc.get("visibility_control") or {}
    if vis.get("fired_on_bad_state") is not True or vis.get("silent_on_good_state") is not True:
        return fail("artifact visibility_control both-states missing")
    debt_art = doc.get("debt_accounting") or {}
    if debt_art.get("all_quarantined_have_owner_and_age") is not True:
        return fail("artifact debt_accounting incomplete")

    out = {
        "probe": "probe2-visibility-debt-retry",
        "unit_id": UID,
        "both_states": True,
        "visible_includes_coin_flip": True,
        "hidden_drops_coin_flip": True,
        "hiding_fires_on_bad": True,
        "hiding_silent_on_good": True,
        "debt_owner": coin["owner"],
        "debt_age_days": coin["age_days"],
        "debt_complete_good": True,
        "debt_incomplete_without_owner": True,
        "retry_absorbed_coin_flip": True,
        "retry_absorbed_retry_bait": True,
        "retry_silent_when_max_attempts_1": True,
        "quarantine_cannot_block": True,
        "broken_still_blocks": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "visible=True hidden_drops=True debt_owner_age=True "
        "retry_absorbed=True quarantine_cannot_block=True broken_blocks=True"
    )
    print("SUCCESS:TST-0336-probe2 visibility debt retry both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
