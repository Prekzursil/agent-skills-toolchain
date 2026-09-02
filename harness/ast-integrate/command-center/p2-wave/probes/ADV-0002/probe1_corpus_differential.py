#!/usr/bin/env python3
"""Probe 1: re-run the 200-outcome corpus through every site's imported reducer.

Independent of the report narrative: rebuild the verdict matrix from disk and
require it to match the artifact byte-for-byte on matrix_sha256, class counts,
and per-target scientific verdicts.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

ART = REPO / "command-center/adversarial/ADV-0002-predicate-crosssite-differential.json"
SENTINEL = (
    "SUCCESS:ADV-0002 emitted ONLY when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, records BOTH named probes "
    "verbatim with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, "
    "and records the result of every listed control/negative test. Any missing "
    "control downgrades the unit's verdicts to NOT-CHECKED. Otherwise "
    "FAILED:ADV-0002 <reason>."
)
ALLOWED = {"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"}


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:ADV-0002-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:ADV-0002-probe1 unparseable {exc}")
        return 1
    if not isinstance(doc, dict):
        print("FAILED:ADV-0002-probe1 not an object")
        return 1
    if doc.get("unit_id") != "ADV-0002":
        print("FAILED:ADV-0002-probe1 unit_id", doc.get("unit_id"))
        return 1
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:ADV-0002-probe1 self-declared", st)
        return 1
    if SENTINEL not in text:
        print("FAILED:ADV-0002-probe1 catalog sentinel absent")
        return 1

    live = E.investigate()
    art_matrix = (doc.get("probe1") or {}).get("matrix") or doc.get("matrix") or {}
    live_sha = live["matrix"]["matrix_sha256"]
    art_sha = art_matrix.get("matrix_sha256")
    n = live["matrix"]["n_outcomes"]
    n_class = live["corpus"]["n_per_class"]
    payload = {
        "probe": "probe1-corpus-differential",
        "unit_id": "ADV-0002",
        "n_outcomes": n,
        "n_per_class": n_class,
        "n_disagreements": live["matrix"]["n_disagreements"],
        "n_byte_identical_rows": live["matrix"]["n_byte_identical_rows"],
        "by_site": live["matrix"]["by_site"],
        "matrix_sha256": live_sha,
        "artifact_matrix_sha256": art_sha,
        "sha_match": live_sha == art_sha,
        "overall_verdict": live["overall_verdict"],
        "artifact_overall": doc.get("overall_verdict"),
        "target_verdicts": [t["verdict"] for t in live["targets"]],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(
        f"n={n} disagreements={payload['n_disagreements']} "
        f"identical={payload['n_byte_identical_rows']} sha_match={payload['sha_match']}"
    )
    if n != 200:
        print("FAILED:ADV-0002-probe1 corpus is not 200 outcomes")
        return 1
    if any(n_class.get(c) != 40 for c in E.OUTCOME_CLASSES):
        print("FAILED:ADV-0002-probe1 class counts", n_class)
        return 1
    if live_sha != art_sha:
        print("FAILED:ADV-0002-probe1 matrix_sha256 drift")
        return 1
    if live["overall_verdict"] != doc.get("overall_verdict"):
        print("FAILED:ADV-0002-probe1 overall_verdict drift")
        return 1
    art_targets = doc.get("targets") or []
    if len(art_targets) != 7:
        print("FAILED:ADV-0002-probe1 expected 7 targets", len(art_targets))
        return 1
    live_by = {t["target_id"]: t for t in live["targets"]}
    seen = set()
    for row in art_targets:
        tid = row.get("target_id")
        v = row.get("verdict")
        if tid in seen or tid not in live_by:
            print("FAILED:ADV-0002-probe1 target id", tid)
            return 1
        if v not in ALLOWED:
            print("FAILED:ADV-0002-probe1 illegal verdict", tid, v)
            return 1
        if v != live_by[tid]["verdict"]:
            print("FAILED:ADV-0002-probe1 target verdict drift", tid, v, live_by[tid]["verdict"])
            return 1
        seen.add(tid)
    if seen != set(E.SITE_IDS):
        print("FAILED:ADV-0002-probe1 target set", sorted(seen))
        return 1
    if live["matrix"]["n_disagreements"] <= 0:
        print("FAILED:ADV-0002-probe1 expected cross-site disagreement on this tree")
        return 1
    print("SUCCESS:ADV-0002-probe1 corpus differential re-derived and matched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
