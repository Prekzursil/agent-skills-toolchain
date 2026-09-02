#!/usr/bin/env python3
"""Probe 1: classify stored greens by volatility and re-execute live-query gates."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

ART = REPO / E.OUT_REL
SENTINEL = (
    "SUCCESS:ADV-0011 emitted ONLY when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, records BOTH named probes "
    "verbatim with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, "
    "and records the result of every listed control/negative test. Any missing "
    "control downgrades the unit's verdicts to NOT-CHECKED. Otherwise "
    "FAILED:ADV-0011 <reason>."
)
ALLOWED = {"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"}
NEED = {
    "live-query-vs-deterministic-classification",
    "stored-live-query-green-verdict-flip",
    "advisory-feed-diff-for-unrerunnable-gates",
    "deterministic-input-control-same-verdict",
}


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0011-probe1 {msg}")
    return 1


def main() -> int:
    live = E.investigate()
    payload = E.compact_probe1(live)
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(
        f"inventory={payload['counts']['inventory']} "
        f"live={payload['counts']['live_query']} "
        f"det={payload['counts']['deterministic_input']} "
        f"eol={payload['eol_policy']['today']} "
        f"known_bad={payload['known_bad']['today']} "
        f"known_clean={payload['known_clean']['today']} "
        f"frozen={payload['frozen_green']['today']}"
    )

    if payload["counts"]["live_query"] < 1:
        return fail("no-live-query-classified")
    if payload["counts"]["deterministic_input"] < 1:
        return fail("no-deterministic-classified")
    if payload["eol_policy"]["today"] != "GREEN" or payload["eol_policy"]["flipped"]:
        return fail("deterministic-control-changed")
    if not payload["hash_twice_match"]:
        return fail("hash-control-nondeterministic")
    if payload["known_bad"]["today"] != "RED" or not payload["known_bad"]["red_ids"]:
        return fail("known-bad-not-red")
    if payload["known_clean"]["today"] == "TOOL-FAILURE":
        return fail("known-clean-tool-failure")
    if payload["known_clean"]["today"] != "GREEN":
        return fail("known-clean-not-green")
    if payload["frozen_green"]["today"] == "TOOL-FAILURE":
        return fail("frozen-green-tool-failure")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact-missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"unparseable:{exc}")
    if not isinstance(doc, dict):
        return fail("not-object")
    if doc.get("unit_id") != "ADV-0011":
        return fail("unit_id")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")
    if SENTINEL not in text:
        return fail("catalog-sentinel-absent")
    targets = doc.get("enumerated_targets") or doc.get("targets") or []
    ids = [t.get("id") for t in targets if isinstance(t, dict)]
    if NEED - set(ids):
        return fail(f"targets-missing:{sorted(NEED - set(ids))}")
    for t in targets:
        if t.get("verdict") not in ALLOWED:
            return fail(f"bad-verdict:{t.get('id')}:{t.get('verdict')}")
    live_by = {t["id"]: t["verdict"] for t in live["targets"]}
    art_by = {t["id"]: t["verdict"] for t in targets if "id" in t}
    for tid in NEED:
        if live_by.get(tid) != art_by.get(tid):
            return fail(f"artifact-drift:{tid} live={live_by.get(tid)} art={art_by.get(tid)}")
    if doc.get("overall_verdict") != live["overall_verdict"]:
        return fail("overall-drift")
    probes = doc.get("named_probes") or []
    if len(probes) < 2:
        return fail("named-probes-missing")
    tests = doc.get("tests") or []
    if not tests:
        return fail("tests-missing")
    if not doc.get("negative_controls"):
        return fail("negative-controls-missing")
    print("SUCCESS:ADV-0011-probe1 classify+rerun matched artifact")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
