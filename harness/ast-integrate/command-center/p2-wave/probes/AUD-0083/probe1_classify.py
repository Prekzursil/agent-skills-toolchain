#!/usr/bin/env python3
"""Probe 1: shebang + extension classification and explicit interpreter at call sites."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

ART = E.REPO / "command-center/audit/AUD-0083-script-interpreter-audit.json"
SENTINEL = (
    "SUCCESS:AUD-0083 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)


def main() -> int:
    data = E.census()
    scripts = data["scripts"]
    sites = data["call_sites"]
    sh = [s for s in scripts if s["extension"] == ".sh"]
    marker = next(
        (s for s in scripts if s["path"].endswith("TST-0068/fixtures/scripts/marker.sh")),
        None,
    )
    ctrl = next(
        (s for s in scripts if s["path"].endswith("fixtures/control/with-shebang.sh")),
        None,
    )
    estate_hazards = [
        h
        for h in data["hazards"]
        if "TST-0068/fixtures/estate" in h["file"]
    ]
    gold_bare = [
        s
        for s in sites
        if "TST-0068/fixtures/gold" in s["file"] and s["bare"]
    ]

    print(
        json.dumps(
            {
                "script_count": data["script_count"],
                "by_extension": data["by_extension"],
                "call_site_count": data["call_site_count"],
                "bare_windows_hazard_count": data["bare_windows_hazard_count"],
                "sh_files": [s["path"] for s in sh],
                "marker_shebang": None if marker is None else marker.get("shebang"),
                "marker_windows_bare": None
                if marker is None
                else marker["windows_pwsh7_bare"]["outcome"],
                "estate_hazard_count": len(estate_hazards),
                "gold_bare_count": len(gold_bare),
            },
            sort_keys=True,
        )
    )

    if data["script_count"] < 1:
        print("FAILED:AUD-0083-probe1 zero scripts classified")
        return 1
    if marker is None:
        print("FAILED:AUD-0083-probe1 TST-0068 marker.sh missing from census")
        return 1
    if not (marker.get("shebang") or "").startswith("#!"):
        print("FAILED:AUD-0083-probe1 marker.sh shebang not classified")
        return 1
    if marker.get("shebang_interpreter") != "bash":
        print(
            "FAILED:AUD-0083-probe1 marker shebang_interpreter="
            f"{marker.get('shebang_interpreter')}"
        )
        return 1
    if marker["windows_pwsh7_bare"]["outcome"] != "FAILURE":
        print("FAILED:AUD-0083-probe1 marker bare Windows was not FAILURE")
        return 1
    if marker["windows_pwsh7_bare"].get("reads_shebang"):
        print("FAILED:AUD-0083-probe1 classifier leaked shebang into Windows bare")
        return 1
    if ctrl is None or ctrl["windows_pwsh7_bare"]["outcome"] != "FAILURE":
        print("FAILED:AUD-0083-probe1 control fixture not FAILURE on Windows bare")
        return 1
    if len(estate_hazards) < 2:
        print(f"FAILED:AUD-0083-probe1 estate bare hazards={len(estate_hazards)}")
        return 1
    if gold_bare:
        print(f"FAILED:AUD-0083-probe1 gold fixtures still have bare sites {gold_bare}")
        return 1

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            print(f"FAILED:AUD-0083-probe1 artifact state={doc.get('state')}")
            return 1
        if SENTINEL not in text:
            print("FAILED:AUD-0083-probe1 completion sentinel absent")
            return 1
        print(f"artifact_state={doc.get('state')} bytes={ART.stat().st_size}")

    print(
        f"classified={data['script_count']} sites={data['call_site_count']} "
        f"hazards={data['bare_windows_hazard_count']} "
        f"estate_hazards={len(estate_hazards)}"
    )
    print("SUCCESS:AUD-0083-probe1 shebang-and-call-site classification")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
