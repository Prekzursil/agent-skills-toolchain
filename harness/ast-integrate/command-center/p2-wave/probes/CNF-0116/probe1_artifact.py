#!/usr/bin/env python3
"""Probe 1: artifact surface via zip namelist, independent of git plumbing.

Enumerates from the archive, never from include-rules. Known-present control
must be found. A polluted zip that include-rules would omit must still flag
the planted credential-shaped filename. Does not read file contents.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402
from inventory import KNOWN_PRESENT_LIVE, KNOWN_PRESENT_REL  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0116-credential-exclusion.json"


def _sid(run: dict, sid: str) -> dict:
    for row in run["surfaces"]:
        if row["id"] == sid:
            return row
    raise KeyError(sid)


def _art_surfaces(doc: dict) -> list:
    if isinstance(doc.get("surfaces"), list) and doc["surfaces"]:
        return doc["surfaces"]
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    if isinstance(report.get("surfaces"), list):
        return report["surfaces"]
    return []


def main() -> int:
    run = S.run_scenario()
    clean = _sid(run, "artifact-clean-control")
    dirty = _sid(run, "artifact-polluted-control")
    live = _sid(run, "artifact-live-tree-archive")
    print(
        json.dumps(
            {
                "clean_count": clean["entry_count"],
                "dirty_count": dirty["entry_count"],
                "live_count": live["entry_count"],
                "clean_hits": [h["path"] for h in clean["credential_hits"]],
                "dirty_hits": [h["path"] for h in dirty["credential_hits"]],
                "live_hits": [h["path"] for h in live["credential_hits"]],
                "known_present_clean": clean["known_present_found"],
                "known_present_dirty": dirty["known_present_found"],
                "known_present_live": live["known_present_found"],
                "include_rules_missed_planted": dirty.get("include_rules_missed_planted"),
                "method": dirty["method"],
            },
            sort_keys=True,
        )
    )
    if not run.get("pass"):
        print("FAILED:CNF-0116-probe1 scenario controls failed")
        return 1
    if not dirty["known_present_found"] or dirty.get("known_present") != KNOWN_PRESENT_REL:
        print("FAILED:CNF-0116-probe1 known-present missing on artifact fixture")
        return 1
    if not live["known_present_found"] or live.get("known_present") != KNOWN_PRESENT_LIVE:
        print("FAILED:CNF-0116-probe1 known-present missing on live archive")
        return 1
    if not dirty.get("include_rules_missed_planted"):
        print("FAILED:CNF-0116-probe1 include-rules listing was treated as the artifact")
        return 1
    if not dirty["credential_hits"]:
        print("FAILED:CNF-0116-probe1 polluted zip produced zero filename hits")
        return 1
    if clean["credential_hits"]:
        print("FAILED:CNF-0116-probe1 clean zip was not clean")
        return 1
    if "include-rules" in dirty["method"].lower() and "not include-rules" not in dirty["method"]:
        print("FAILED:CNF-0116-probe1 method names include-rules as the enumerator")
        return 1
    if not ART.is_file():
        print("FAILED:CNF-0116-probe1 confirmation artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0116-probe1 self-declared {doc.get('state')}")
        return 1
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:CNF-0116" not in text:
        print("FAILED:CNF-0116-probe1 sentinel absent")
        return 1
    if "CNF-0116-filename-only-fixture" in text:
        print("FAILED:CNF-0116-probe1 artifact stores fixture body")
        return 1
    rec = {s["id"]: s for s in _art_surfaces(doc)}
    if not rec.get("artifact-polluted-control", {}).get("known_present_found"):
        print("FAILED:CNF-0116-probe1 artifact did not record known-present")
        return 1
    if rec.get("artifact-polluted-control", {}).get("include_rules_missed_planted") is not True:
        print("FAILED:CNF-0116-probe1 artifact omitted include-rules miss")
        return 1
    live_art_hits = [h["path"] for h in rec.get("artifact-live-tree-archive", {}).get("credential_hits") or []]
    live_now = [h["path"] for h in live["credential_hits"]]
    if sorted(live_art_hits) != sorted(live_now):
        print("FAILED:CNF-0116-probe1 live archive hits drifted from artifact")
        print("artifact", live_art_hits)
        print("live", live_now)
        return 1
    print("SUCCESS:CNF-0116-probe1 artifact zip namelist both-states known-present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
