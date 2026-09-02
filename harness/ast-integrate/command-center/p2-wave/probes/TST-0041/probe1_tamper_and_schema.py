#!/usr/bin/env python3
"""Probe 1: live schema + monotonic seq + unit_id + tamper both-states."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from paths import CATALOG_SENTINEL, OUT_REL, REPO, UNIT  # noqa: E402
from schema_val import schema_errors  # noqa: E402
from suite import both_states, live_log, tamper_control  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    art = REPO / OUT_REL
    if not art.is_file() or art.stat().st_size <= 0:
        return fail("artifact missing")
    text = art.read_text(encoding="utf-8")
    if CATALOG_SENTINEL not in text:
        return fail("catalog sentinel absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    if doc.get("unit_id") != UNIT:
        return fail("unit_id mismatch")

    errs = schema_errors(doc)
    if errs:
        return fail(f"schema {errs[0]}")
    if not schema_errors({"totally": "unrelated"}):
        return fail("schema accepted garbage")

    report = doc.get("report") or {}
    if report.get("kind") != "conformance-report":
        return fail("report.kind is not conformance-report")

    live = live_log()
    if not live.get("present"):
        return fail(f"live log absent {live}")
    if live.get("ok"):
        if not live.get("seq") or any(s is None for s in live["seq"]):
            return fail("live seq missing")
        if not live.get("unit_ids") or any(not u for u in live["unit_ids"]):
            return fail("live unit_id missing")
    elif not live.get("detector_fired"):
        return fail("live log non-conforming but verifier was silent")

    tamper = tamper_control()
    if not tamper.get("pass"):
        return fail(f"tamper control {tamper}")
    if not tamper.get("fired_on_bad") or not tamper.get("silent_on_good"):
        return fail("tamper both-states failed")
    if not tamper.get("prefix_changed"):
        return fail("tamper did not change prefix digest")

    both = both_states()
    if not both.get("all_pass"):
        failed = [r["id"] for r in both.get("rows") or [] if not r.get("pass")]
        return fail(f"both-states failed {failed}")

    required_mutants = {
        "missing-unit-id",
        "missing-seq",
        "ts-without-timezone",
        "tamper-earlier-line",
        "seq-decrease",
    }
    have = {r["id"] for r in both.get("rows") or [] if r.get("pass")}
    missing = required_mutants - have
    if missing:
        return fail(f"missing mutant coverage {sorted(missing)}")

    evidence = doc.get("evidence") or []
    if not any(
        e.get("verdict") == "CONFIRMED" and "tamper" in str(e.get("claim") or "").lower()
        for e in evidence
        if isinstance(e, dict)
    ):
        return fail("receipt missing CONFIRMED tamper evidence")
    if not any(
        e.get("verdict") == "CONFIRMED" and "unit" in str(e.get("claim") or "").lower()
        for e in evidence
        if isinstance(e, dict)
    ):
        return fail("receipt missing CONFIRMED unit_id evidence")

    ncs = doc.get("negative_controls") or []
    if not any(
        x.get("id") == "tamper-earlier-line" and x.get("fired_on_bad_state") for x in ncs
    ):
        return fail("receipt missing tamper negative control")
    if not any(x.get("fired_on_bad_state") and x.get("silent_on_good_state") for x in ncs):
        return fail("receipt negative controls not both-states")

    rev = doc.get("reviewer") or {}
    if rev.get("independent") is not True or rev.get("verdict") != "PASS":
        return fail("reviewer not independent PASS")

    out = {
        "probe": "probe1-tamper-and-schema",
        "unit_id": UNIT,
        "live_ok": bool(live.get("ok")),
        "live_detector_fired": bool(live.get("detector_fired")),
        "tamper_pass": True,
        "both_states_pass": True,
        "mutants": len(both.get("rows") or []),
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"live_ok={live.get('ok')} detector_fired={live.get('detector_fired')} "
        f"tamper_fired={tamper['fired_on_bad']} silent={tamper['silent_on_good']} "
        f"mutants={len(both.get('rows') or [])}"
    )
    print(f"SUCCESS:{UNIT}-probe1 tamper+schema both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
