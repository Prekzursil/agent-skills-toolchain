#!/usr/bin/env python3
"""Probe 2: process-level phase trace (install/resolve/import/execute).

Independent of probe 1's median table: one traced run with phase boundaries.
When the baseline artifact exists, try to falsify its headline numbers against
this live trace rather than re-reading them as truth.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import timing as T  # noqa: E402

RAW = HERE / "probe2-process-trace.raw.json"
ART = REPO / "command-center/audit/AUD-0087-startup-latency-baseline.json"


def _ratio(a: float, b: float) -> float:
    lo, hi = (a, b) if a <= b else (b, a)
    if lo <= 0:
        return float("inf")
    return hi / lo


def falsify_headline(trace: dict, doc: dict) -> list[str]:
    problems: list[str] = []
    headline = doc.get("headline") if isinstance(doc.get("headline"), dict) else {}
    pairs = (
        ("cold_install_median_ms", "cold_install_ms"),
        ("first_import_process_median_ms", "first_import_process_ms"),
        ("first_command_process_median_ms", "first_command_process_ms"),
    )
    for art_key, live_key in pairs:
        claimed = headline.get(art_key)
        live = float(trace.get(live_key) or 0.0)
        if not isinstance(claimed, (int, float)) or claimed <= 0:
            problems.append(f"{art_key} is not a positive number ({claimed!r})")
            continue
        if live <= 0:
            problems.append(f"live {live_key} is not positive")
            continue
        if _ratio(float(claimed), live) > 50:
            problems.append(
                f"{art_key}={claimed} vs live {live_key}={live} ratio>50"
            )
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        problems.append(f"artifact self-declared {doc.get('state')}")
    return problems


def main() -> int:
    control = T.both_states_contention_control()
    try:
        trace = T.run_one_sample(label="probe2-trace")
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": f"{type(exc).__name__}: {exc}"}, sort_keys=True))
        print("FAILED:AUD-0087-probe2 traced sample raised")
        return 1
    ok, why = T.phase_attribution_ok(trace)
    problems: list[str] = []
    if ART.is_file() and ART.stat().st_size > 0:
        try:
            doc = json.loads(ART.read_text(encoding="utf-8"))
            if isinstance(doc, dict):
                problems = falsify_headline(trace, doc)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            problems = [f"artifact unreadable: {type(exc).__name__}"]
    payload = {
        "probe": "probe2-process-trace",
        "unit_id": "AUD-0087",
        "method": "fresh-prefix-phase-timestamps",
        "phases": trace.get("phases"),
        "cold_install_ms": trace.get("cold_install_ms"),
        "resolve_ms": trace.get("resolve_ms"),
        "first_import_process_ms": trace.get("first_import_process_ms"),
        "first_import_statement_ms": trace.get("first_import_statement_ms"),
        "first_command_process_ms": trace.get("first_command_process_ms"),
        "source_match": trace.get("source_match"),
        "accepted": trace.get("accepted"),
        "discarded": trace.get("discarded"),
        "discard_reason": trace.get("discard_reason"),
        "load_before": trace.get("load_before"),
        "attribution_ok": ok,
        "attribution_why": why,
        "contention_control_pass": control["pass"],
        "headline_falsify_problems": problems,
        "artifact_present": ART.is_file(),
        "pip": T.pip_available(),
    }
    RAW.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))
    if not control["pass"]:
        print("FAILED:AUD-0087-probe2 contention control does not discriminate")
        return 1
    if not ok:
        print(f"FAILED:AUD-0087-probe2 phase attribution {why}")
        return 1
    if not trace.get("source_match"):
        print("FAILED:AUD-0087-probe2 installed bytes do not match current source")
        return 1
    if trace.get("discarded"):
        print(
            "FAILED:AUD-0087-probe2 traced run discarded: {0}".format(
                trace.get("discard_reason")
            )
        )
        return 1
    if problems:
        print("FAILED:AUD-0087-probe2 falsified artifact headline: " + "; ".join(problems))
        return 1
    print(
        "phases_ms resolve={0:.3f} install={1:.3f} import={2:.3f} execute={3:.3f} "
        "total={4:.3f} attribution={5}".format(
            float(trace["phases"]["resolve_ms"]),
            float(trace["phases"]["install_ms"]),
            float(trace["phases"]["import_process_ms"]),
            float(trace["phases"]["execute_ms"]),
            float(trace["phases"]["total_ms"]),
            why,
        )
    )
    print("SUCCESS:AUD-0087-probe2 process-level phase trace")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
