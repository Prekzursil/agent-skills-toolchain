#!/usr/bin/env python3
"""Probe 2: live two-platform digest pair and two independent packer counts.

Does not trust emit.py's copied digests: re-runs measure() and checks the
stored-struct packer independently.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from measure import AXES, definition_sha256, measure  # noqa: E402

REPO = HERE.parents[3]
ART = (
    REPO
    / "command-center"
    / "research"
    / "supply-chain"
    / "RES-0134-reproducible-build-for-asset-packages.json"
)
SENTINEL = "SUCCESS:RES-0134"


def fail(msg: str) -> int:
    print(f"FAILED:RES-0134-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        return fail("sentinel absent")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")

    live = measure()
    tp = live["two_platform"]
    tpass = live["two_pass"]
    if tpass["relative_delta"] > 0.10:
        return fail(
            f"two-pass delta {tpass['relative_delta']} exceeds 10% "
            f"(a={tpass['pass_a_count']} b={tpass['pass_b_count']})"
        )
    if not tpass["within_10_percent"]:
        return fail("within_10_percent flag is false")
    art_tp = doc.get("two_pass") or {}
    if art_tp.get("pass_a_count") != tpass["pass_a_count"] or art_tp.get(
        "pass_b_count"
    ) != tpass["pass_b_count"]:
        return fail("artifact two-pass counts drifted from live re-count")
    if live["definition_sha256"] != (doc.get("definition") or {}).get("sha256"):
        return fail("live definition hash drifted from artifact")
    if live["definition_sha256"] != definition_sha256():
        return fail("measure() definition hash drifted from disk")

    if not tp["recipe_on_zipfile_equal"] or not tp["recipe_on_stored_equal"]:
        return fail("live two-platform recipe-on pair diverged")
    if not tp["recipe_off_digests_differ"]:
        return fail("live two-platform recipe-off pair collided")
    art_plat = doc.get("two_platform") or {}
    for key in (
        "linux_recipe_on_sha256",
        "windows_recipe_on_sha256",
        "linux_recipe_on_stored_sha256",
        "windows_recipe_on_stored_sha256",
        "linux_recipe_off_sha256",
        "windows_recipe_off_sha256",
    ):
        if art_plat.get(key) != tp.get(key):
            return fail(f"artifact two_platform.{key} drifted from live re-pack")

    live_breaks = live["per_packer_breaks"]
    for packer in ("zipfile-deflate", "stored-struct"):
        got = list(live_breaks.get(packer) or [])
        if got != list(AXES):
            return fail(f"{packer} break set {got} != {list(AXES)}")

    art_counts = {
        r["vendor_id"]: r["count"]
        for r in (doc.get("per_vendor_counts") or doc.get("per_vendor_counts") or [])
    }
    if len(art_counts) < 5:
        return fail("artifact per_vendor_counts has fewer than 5 axes")
    for row in live["axes"]:
        n = sum(1 for it in row["items"] if it["broke_identity"])
        if art_counts.get(row["vendor_id"]) != n:
            return fail(f"axis {row['vendor_id']} count drifted")
        if n < 1:
            return fail(f"axis {row['vendor_id']} did not break on either packer")

    reviewer = doc.get("reviewer") or {}
    if reviewer.get("independent") is not True:
        return fail("reviewer.independent is not true")
    if str(reviewer.get("verdict") or "").upper() != "PASS":
        return fail(f"reviewer.verdict {reviewer.get('verdict')}")

    payload = {
        "probe": "probe2-two-platform-and-two-packer",
        "unit_id": "RES-0134",
        "pass_a_count": tpass["pass_a_count"],
        "pass_b_count": tpass["pass_b_count"],
        "relative_delta": tpass["relative_delta"],
        "within_10_percent": True,
        "linux_on": tp["linux_recipe_on_sha256"],
        "windows_on": tp["windows_recipe_on_sha256"],
        "linux_on_stored": tp["linux_recipe_on_stored_sha256"],
        "windows_on_stored": tp["windows_recipe_on_stored_sha256"],
        "live_matches_artifact": True,
        "pass": True,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(
        "SUCCESS:RES-0134-probe2 two-platform digest pair recorded; "
        "two-packer counts agree within 10%"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
