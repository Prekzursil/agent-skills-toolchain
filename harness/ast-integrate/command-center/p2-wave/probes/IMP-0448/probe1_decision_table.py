#!/usr/bin/env python3
"""Probe 1: one live grind per taxonomy class; observed attempts must match policy.

Mechanically different from probe 2 (two-strikes / text-matching mutant):
this probe uses DISTINCT fingerprints so two-strikes does not fire, isolating
the class-driven cap. A class whose observed count differs from its policy
is a defect. Decoy error strings are recorded and never passed to decide().
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import retry_engine as R  # noqa: E402

CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"

# Shared decoy: would fool a text-matcher into treating every class as transient.
DECOY = "timeout: connection reset; HTTP 429; schema looks invalid"


def catalog_parse_sample() -> dict:
    samples = {
        "max-2-backoff": "max 2 attempts, backoff 30s/120s",
        "zero-retries": (
            "zero retries. This unit's first observation IS the verdict; "
            "a later run that disagrees is a DISCREPANCY to record"
        ),
        "no-automatic": (
            "No automatic retry: a failure here is a finding, not a transient."
        ),
        "transients-only": "max 3 attempts for provider transients only",
        "two-strikes": (
            "two strikes then pivot - after the second failure on the same "
            "error fingerprint, enumerate >=2 alternative approaches"
        ),
        "imp-0448": (
            "max 2 attempts to implement; the engine must not be able to "
            "retry its own failure indefinitely"
        ),
    }
    parsed = {}
    for name, raw in samples.items():
        pol = R.parse_retry_policy(raw)
        parsed[name] = {
            "raw": raw,
            "max_attempts": pol.max_attempts,
            "backoff_seconds": list(pol.backoff_seconds),
            "two_strikes_pivot": pol.two_strikes_pivot,
            "transient_only": pol.transient_only,
        }
    live = {}
    if CATALOG.is_file():
        data = json.loads(CATALOG.read_text(encoding="utf-8"))
        for unit in data.get("work_units") or []:
            if isinstance(unit, dict) and unit.get("id") == "IMP-0448":
                pol = R.parse_retry_policy(str(unit.get("retry_policy") or ""))
                live["IMP-0448"] = {
                    "max_attempts": pol.max_attempts,
                    "backoff_seconds": list(pol.backoff_seconds),
                    "transient_only": pol.transient_only,
                }
                break
    return {"fixtures": parsed, "catalog_imp_0448": live}


def main() -> int:
    policy = R.RetryPolicy(
        max_attempts=3,
        backoff_seconds=(30, 120),
        two_strikes_pivot=True,
        raw="max 3 attempts, backoff 30s/120s",
    )
    rows = R.decision_table(policy, distinct_fingerprints=True)
    errors = R.table_is_sound(rows)
    parsed = catalog_parse_sample()
    fixtures = parsed["fixtures"]

    parse_ok = (
        fixtures["max-2-backoff"]["max_attempts"] == 2
        and fixtures["max-2-backoff"]["backoff_seconds"][:2] == [30, 120]
        and fixtures["zero-retries"]["max_attempts"] == 1
        and fixtures["no-automatic"]["max_attempts"] == 1
        and fixtures["transients-only"]["max_attempts"] == 3
        and fixtures["transients-only"]["transient_only"] is True
        and fixtures["two-strikes"]["two_strikes_pivot"] is True
        and fixtures["two-strikes"]["max_attempts"] == 3
        and fixtures["imp-0448"]["max_attempts"] == 2
    )

    # Transient-only: schema-invalid still 1; severed-stream uses the cap.
    t_only = R.parse_retry_policy("max 3 attempts for provider transients only")
    inv = R.observe_attempts("schema-invalid", t_only, distinct_fingerprints=True)
    sev = R.observe_attempts("severed-stream", t_only, distinct_fingerprints=True)

    # Decoy text is recorded only here. decide() never receives it.
    decoy = R.class_overrides_decoy_text()

    expected_never = {
        "schema-invalid",
        "blocked",
        "win-arg-limit",
        "degraded",
        "UNCLASSIFIED",
    }
    expected_transient = {"severed-stream", "adapter-exit-n", "timeout"}
    by_cls = {r["failure_class"]: r for r in rows}

    class_ok = True
    class_errors: list[str] = []
    for cls in expected_never:
        row = by_cls.get(cls) or {}
        if row.get("observed_attempt_count") != 1 or row.get("match") is not True:
            class_ok = False
            class_errors.append(f"never {cls} {row}")
    for cls in expected_transient:
        row = by_cls.get(cls) or {}
        if row.get("observed_attempt_count") != 3 or row.get("match") is not True:
            class_ok = False
            class_errors.append(f"transient {cls} {row}")
    partial = by_cls.get("partial-artifact") or {}
    if partial.get("observed_attempt_count") != 2 or partial.get("match") is not True:
        class_ok = False
        class_errors.append(f"limited partial-artifact {partial}")

    transients_only_ok = (
        inv.observed_attempt_count == 1
        and sev.observed_attempt_count == 3
        and inv.terminal_action == "STOP"
        and sev.terminal_action == "STOP"
    )

    report = {
        "probe": "probe1-decision-table",
        "unit_id": "IMP-0448",
        "decoy_text": DECOY,
        "decoy_not_passed_to_decide": decoy["decoy_text_not_passed_to_decide"],
        "rows": rows,
        "table_errors": errors,
        "parse": parsed,
        "parse_ok": parse_ok,
        "class_ok": class_ok,
        "class_errors": class_errors,
        "transients_only_ok": transients_only_ok,
        "schema_invalid_zero_retries": by_cls.get("schema-invalid", {}).get(
            "observed_attempt_count"
        )
        == 1,
        "decoy_pair_diverged": decoy["diverged"],
        "pass": bool(
            not errors
            and parse_ok
            and class_ok
            and transients_only_ok
            and decoy["diverged"]
            and decoy["schema_invalid_is_stop"]
            and decoy["severed_stream_is_retry"]
        ),
    }
    print(json.dumps(report, indent=1, sort_keys=True))
    print(
        f"rows={len(rows)} errors={errors} parse_ok={parse_ok} "
        f"class_ok={class_ok} transients_only_ok={transients_only_ok} "
        f"decoy_diverged={decoy['diverged']}"
    )
    if not report["pass"]:
        print("FAILED:IMP-0448-probe1 decision table")
        if class_errors:
            print("class_errors", class_errors)
        return 1
    print(
        "SUCCESS:IMP-0448-probe1 per-class attempt counts match policy; "
        "schema-invalid retried ZERO times; decoy text ignored"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
