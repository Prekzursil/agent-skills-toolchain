#!/usr/bin/env python3
"""Named probe 1: re-run the 21 live predicates and check the on-disk artifact.

A reviewer who only re-reads SYN-0043.stopping-verdict.json has verified nothing.
"""
from __future__ import annotations

import json
import sys
import sysconfig
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
_STDLIB = sysconfig.get_paths()["stdlib"]
if _STDLIB not in sys.path:
    sys.path.insert(0, _STDLIB)

sys.path.insert(0, str(HERE))
from evaluate import live_bundle  # noqa: E402
import schema_util as SU  # noqa: E402

ART = REPO / "command-center/synthesis/SYN-0043.stopping-verdict.json"
SCHEMA = REPO / "command-center/schema/stopping-verdict.schema.json"
SENTINEL = (
    "SUCCESS:SYN-0043 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and all 21 rows carry a "
    "verdict and a probe, and the overall verdict follows the stated rule. "
    "Any other terminal state is FAILED:SYN-0043 <classification> with the "
    "diagnostic tail attached."
)


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:SYN-0043-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:SYN-0043-probe1 unparseable {exc}")
        return 1
    if not isinstance(doc, dict):
        print("FAILED:SYN-0043-probe1 not an object")
        return 1
    if doc.get("unit_id") != "SYN-0043":
        print("FAILED:SYN-0043-probe1 unit_id", doc.get("unit_id"))
        return 1
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:SYN-0043-probe1 self-declared", st)
        return 1
    if SENTINEL not in text:
        print("FAILED:SYN-0043-probe1 catalog sentinel absent")
        return 1

    schema_errs = SU.iter_errors(doc)
    if schema_errs:
        print("FAILED:SYN-0043-probe1 schema")
        for e in schema_errs[:10]:
            print(" ", e)
        return 1

    bundle = live_bundle()
    live_rows = bundle["rows"]
    live_adj = bundle["adjudication"]
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    art_rows = report.get("rows") or doc.get("rows") or []
    if len(art_rows) != 21 or len(live_rows) != 21:
        print(f"FAILED:SYN-0043-probe1 row counts art={len(art_rows)} live={len(live_rows)}")
        return 1
    mismatches = []
    for live, art in zip(live_rows, art_rows):
        if live["condition_id"] != art.get("condition_id"):
            mismatches.append(("id", live["condition_id"], art.get("condition_id")))
        if live["verdict"] != art.get("verdict"):
            mismatches.append(
                ("verdict", live["condition_id"], live["verdict"], art.get("verdict"))
            )
        if not art.get("condition_text"):
            mismatches.append(("text", live["condition_id"]))
        probe = art.get("probe") or {}
        if not probe.get("command") or not probe.get("output_tail"):
            mismatches.append(("probe", live["condition_id"]))
        if not art.get("timestamp"):
            mismatches.append(("timestamp", live["condition_id"]))
    if mismatches:
        print("FAILED:SYN-0043-probe1 live/artifact mismatch")
        print(json.dumps(mismatches[:12], sort_keys=True))
        return 1
    overall = report.get("overall_verdict") or doc.get("overall_verdict")
    named_missing = report.get("named_missing_probe") or doc.get("named_missing_probe") or ""
    c13_res = report.get("condition_13_resolution") or doc.get("condition_13_resolution") or {}
    if overall != live_adj["overall_verdict"]:
        print(
            "FAILED:SYN-0043-probe1 overall mismatch "
            f"art={overall} live={live_adj['overall_verdict']}"
        )
        return 1
    if live_adj["overall_verdict"] == "PROGRAM-COMPLETE":
        if any(r["verdict"] != "TRUE" for r in live_rows):
            print("FAILED:SYN-0043-probe1 COMPLETE with a non-TRUE row")
            return 1
    if live_adj["blocking_class"] == "NOT-CHECKED":
        if " --condition " not in named_missing:
            print("FAILED:SYN-0043-probe1 NOT-CHECKED without named missing probe")
            return 1
    c13 = next(r for r in art_rows if r.get("condition_id") == 13)
    res = c13_res
    if res.get("skipped") is True:
        print("FAILED:SYN-0043-probe1 condition 13 was skipped")
        return 1
    if c13.get("verdict") not in {"TRUE", "FALSE", "NOT-CHECKED", "DECORATIVE"}:
        print("FAILED:SYN-0043-probe1 condition 13 missing verdict")
        return 1

    payload = {
        "adjudicated": True,
        "live_overall": live_adj["overall_verdict"],
        "live_class": live_adj["blocking_class"],
        "live_counts": live_adj.get("counts"),
        "artifact_overall": overall,
        "rows": 21,
        "c13_verdict": c13.get("verdict"),
        "c13_skipped": res.get("skipped"),
        "pass": True,
        "probe": "probe1-live-rows",
        "unit_id": "SYN-0043",
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"live_overall={live_adj['overall_verdict']} "
        f"class={live_adj['blocking_class']} rows=21 c13={c13.get('verdict')}"
    )
    print("SUCCESS:SYN-0043-probe1 live 21-row re-evaluation matches artifact")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
