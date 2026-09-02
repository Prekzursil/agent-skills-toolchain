#!/usr/bin/env python3
"""Probe 2: observed-class vs declared-class, plus hermetic never-expires.

Independent classifier in independent_classify.py does not import
tools/bench/classify.py. A case that declares hermetic but urlopens NVD
must be advisory-db. A true hermetic result aged 10 years must still
cite as current.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

import independent_classify as IC  # noqa: E402
from bench.classify import classify_calls  # noqa: E402
from bench.expire import cite_as_current, gate_accepts  # noqa: E402
from bench.observe import NetworkObserver  # noqa: E402
from bench.oracles import (  # noqa: E402
    case_by_id,
    execute_case,
    oracle_advisory,
    oracle_hermetic,
)
from bench.ttl import ttl_for  # noqa: E402

NOW = datetime(2026, 8, 24, 18, 0, 0, tzinfo=timezone.utc)


def _observe(fn) -> list[dict]:
    with NetworkObserver() as obs:
        fn("probe2")
        return list(obs.calls)


def main() -> int:
    hermetic_calls = _observe(oracle_hermetic)
    nvd_calls = _observe(oracle_advisory)
    ind_h = IC.independent_class(hermetic_calls)
    ind_n = IC.independent_class(nvd_calls)
    plat_h = classify_calls(hermetic_calls)
    plat_n = classify_calls(nvd_calls)

    lie = execute_case(
        case_by_id("lie-hermetic-hits-nvd"), captured_at=NOW, result_id="lie"
    )
    true_h = execute_case(
        case_by_id("hermetic-digest"),
        captured_at=NOW - timedelta(days=3650),
        result_id="ancient-hermetic",
    )
    ttl = ttl_for("advisory-db")
    if ttl is None:
        print("FAILED:TST-0303-probe2 advisory TTL missing")
        return 1
    lie_old = execute_case(
        case_by_id("lie-hermetic-hits-nvd"),
        captured_at=NOW - timedelta(seconds=ttl + 1),
        result_id="lie-expired",
    )
    lie_old.verdict = "PASS"
    true_h.verdict = "PASS"

    hermetic_still_current = gate_accepts(true_h, NOW)
    lie_expired = gate_accepts(lie_old, NOW)
    lie_cite = cite_as_current(lie_old, NOW)

    payload = {
        "declared_lie": lie.declared_class,
        "independent_hermetic": ind_h,
        "independent_nvd": ind_n,
        "lie_expired_accepted": lie_expired["accepted"],
        "lie_expired_as": lie_expired["as"],
        "lie_observed": lie.observed_class,
        "platform_hermetic": plat_h,
        "platform_nvd": plat_n,
        "true_hermetic_accepted": hermetic_still_current["accepted"],
        "true_hermetic_age_days": 3650,
        "true_hermetic_observed": true_h.observed_class,
        "pass": (
            ind_h == "hermetic"
            and plat_h == "hermetic"
            and ind_n == "advisory-db"
            and plat_n == "advisory-db"
            and lie.declared_class == "hermetic"
            and lie.observed_class == "advisory-db"
            and hermetic_still_current["accepted"] is True
            and hermetic_still_current["as"] == "PASS"
            and lie_expired["accepted"] is False
            and lie_expired["as"] == "NOT-CHECKED"
            and lie_cite.status == "EXPIRED-NOT-CHECKED"
        ),
        "probe": "probe2-observed-class-and-hermetic",
        "unit_id": "TST-0303",
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"lie_declared={lie.declared_class} lie_observed={lie.observed_class} "
        f"hermetic_still={hermetic_still_current['accepted']} "
        f"lie_expired_as={lie_expired['as']}"
    )
    if not payload["pass"]:
        print("FAILED:TST-0303-probe2 classification or hermetic TTL")
        return 1
    print(
        "SUCCESS:TST-0303-probe2 observed class beats declared; hermetic never expires"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
