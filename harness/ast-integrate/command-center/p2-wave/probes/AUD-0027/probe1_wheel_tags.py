#!/usr/bin/env python3
"""Probe 1: live published wheel-tag matrix for every declared direct dependency."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

ART = H.REPO / H.OUT_REL


def main() -> int:
    census = H.build_census()
    n = census["declared_count"]
    findings = census["finding_count"]
    plat = census["platform_wheel_names"]
    sdist = census["sdist_only_names"]
    runtime = census["runtime_hint_names"]
    fail_linux = census["fail_declared_linux_x86_64"]
    errors = [r for r in census["rows"] if not r.get("ok")]
    print(f"declared={n} findings={findings}")
    print(f"platform_wheel={len(plat)} {plat}")
    print(f"sdist_only={len(sdist)} {sdist}")
    print(f"runtime_hints={len(runtime)} {runtime}")
    print(f"fail_declared_linux_x86_64={fail_linux}")
    print(f"fetch_errors={len(errors)}")
    if errors:
        print("FAILED:AUD-0027-probe1 pypi fetch errors", errors)
        return 1
    if n < 1:
        print("FAILED:AUD-0027-probe1 empty declared set")
        return 1
    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        if doc.get("unit_id") != H.UNIT:
            print("FAILED:AUD-0027-probe1 unit_id", doc.get("unit_id"))
            return 1
        if H.SENTINEL not in ART.read_text(encoding="utf-8"):
            print("FAILED:AUD-0027-probe1 sentinel absent")
            return 1
        live_plat = set(plat)
        art_plat = set(doc.get("headline", {}).get("platform_wheel_names") or [])
        if live_plat != art_plat:
            print("FAILED:AUD-0027-probe1 platform-wheel set drifted")
            print("live", sorted(live_plat))
            print("artifact", sorted(art_plat))
            return 1
        if doc.get("headline", {}).get("finding_count") != findings:
            print(
                "FAILED:AUD-0027-probe1 finding_count",
                doc.get("headline", {}).get("finding_count"),
                "live",
                findings,
            )
            return 1
        print("artifact_matches_live_matrix=true")
    print("SUCCESS:AUD-0027-probe1 live wheel-tag matrix")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
