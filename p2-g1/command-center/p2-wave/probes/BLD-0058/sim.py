# Recreated 2026-10-25 (wave-2 shard 7) after the original probe tree was
# lost with the prior builder session; content follows the recorded role in
# the unit receipt (anchors re-resolve live). Prior reviewer closure kept.
"""Instrument for BLD-0058: the both-states schedule simulation invariants.
Re-derives the arrival-control identities the receipt records for the 10x
scaled fleet (burst vs stagger under a vendor RPM ceiling), and the 429/529
classification table whose two classes demand opposite scheduler responses."""
from __future__ import annotations

from typing import Any


def check_schedule(bs: dict[str, Any]) -> tuple[bool, str]:
    n = int(bs["n_10x"])
    ok = (
        int(bs["burst_200"]) + int(bs["burst_429"]) == n
        and int(bs["stagger_200"]) == n
        and int(bs["stagger_429"]) == 0
        and float(bs["admit_rpm"]) < float(bs["rpm"])
        and bs["vacuous"] is False
    )
    return ok, (
        "burst %s+%s=%s (n=%s), stagger %s/429=%s, admit_rpm %s < rpm %s, vacuous=%s"
        % (bs["burst_200"], bs["burst_429"], int(bs["burst_200"]) + int(bs["burst_429"]),
           n, bs["stagger_200"], bs["stagger_429"], bs["admit_rpm"], bs["rpm"], bs["vacuous"])
    )


def check_error_classes(rows: list[dict[str, Any]]) -> tuple[bool, str]:
    by = {int(r["http_status"]): r for r in rows}
    if set(by) != {429, 529}:
        return False, "expected exactly classes 429 and 529, got %s" % sorted(by)
    ours = by[429]["class"] == "OUR_ARRIVAL_RATE" and "stagger" in str(by[429]["scheduler_response"])
    vendor = (
        by[529]["class"] == "VENDOR_OVERLOAD"
        and "keep-concurrency" in str(by[529]["scheduler_response"])
        and "do-not-self-throttle" in str(by[529]["scheduler_response"])
        and by[529]["concurrency_after_correct"] == by[529]["concurrency_before"]
        and by[529]["concurrency_after_naive_control"] < by[529]["concurrency_before"]
    )
    return ours and vendor, (
        "429=%s/%s 529=%s keep-concurrency=%s naive-throttles=%s"
        % (by[429]["class"], by[429]["scheduler_response"], by[529]["class"],
           by[529]["concurrency_after_correct"] == by[529]["concurrency_before"],
           by[529]["concurrency_after_naive_control"] < by[529]["concurrency_before"])
    )


def binding_rpm(quotas: list[dict[str, Any]]) -> tuple[int | None, str]:
    """The binding ceiling is the min over RPM rows that are DOCUMENTED or
    MEASURED; NOT-CHECKED rows are excluded (absence of a number must not be
    read as no ceiling)."""
    eligible = [
        q for q in quotas
        if str(q.get("unit")) == "rpm" and str(q.get("status")) in {"DOCUMENTED", "MEASURED"}
        and isinstance(q.get("numeric_value"), int)
    ]
    if not eligible:
        return None, "no eligible rpm rows"
    b = min(eligible, key=lambda q: q["numeric_value"])
    return int(b["numeric_value"]), "binding=%s status=%s over %d eligible" % (
        b["numeric_value"], b["status"], len(eligible))
