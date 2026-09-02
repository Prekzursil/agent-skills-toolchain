#!/usr/bin/env python3
"""Probe 1: live YAML keys are not silently coerced (listing is complete).

Re-runs the live corpus scan. Catalog input quality.yml must be scanned and its
unquoted `on:` key must appear in the hazard listing when the file exists.
Planted fixtures belong to probe 2.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

ART = REPO / "command-center" / "receipts" / "TST-0059.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0059-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    blob = json.dumps(doc)
    if "SUCCESS:TST-0059" not in blob:
        return fail("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")

    live = E.run_suite()
    t1 = live["test_no_key_is_silently_coerced"]
    if not t1["pass"]:
        return fail(
            "live scan silent or incomplete "
            f"quality_scanned={t1.get('quality_yml_scanned')} "
            f"quality_on={t1.get('quality_on_key_listed')} "
            f"hazard_count={t1['live_hazard_count']}"
        )
    rec = doc.get("tests") or []
    rec_t1 = next(
        (
            t
            for t in rec
            if isinstance(t, dict)
            and t.get("id") in {"test_no_key_is_silently_coerced", "t1"}
        ),
        None,
    )
    if not rec_t1 or rec_t1.get("result") != "PASS":
        return fail("artifact test_no_key_is_silently_coerced is not PASS")
    probe = doc.get("report") or doc.get("probe") or {}
    rec_live = int(probe.get("live_hazard_count", -1))
    if rec_live != live["live_hazard_count"]:
        return fail(
            f"artifact live_hazard_count={rec_live} != live {live['live_hazard_count']}"
        )
    rec_files = int(probe.get("live_file_count", -1))
    if rec_files != live["live_file_count"]:
        return fail(
            f"artifact live_file_count={rec_files} != live {live['live_file_count']}"
        )
    if live["live_file_count"] < 1:
        return fail("live corpus empty")
    quality = REPO / E.QUALITY_REL
    if quality.is_file():
        sources = [d["source"] for d in live["live_yaml_files"]]
        if E.QUALITY_REL not in sources:
            return fail("catalog input quality.yml not in live corpus")
        if not E.quality_on_key_listed(live["live_hazards"]):
            return fail("quality.yml on: key missing from hazard listing")

    out = {
        "probe": "probe1-no-silent-coercion",
        "unit_id": "TST-0059",
        "live_file_count": live["live_file_count"],
        "live_hazard_count": live["live_hazard_count"],
        "quality_yml_scanned": t1.get("quality_yml_scanned"),
        "quality_on_key_listed": t1.get("quality_on_key_listed"),
        "pass": True,
        "files": [d["source"] for d in live["live_yaml_files"] if d.get("hazard_count")],
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"live files={live['live_file_count']} hazards={live['live_hazard_count']} "
        f"quality_on={t1.get('quality_on_key_listed')}"
    )
    print("SUCCESS:TST-0059-probe1 no live key is silently coerced")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
