#!/usr/bin/env python3
"""Named probe 2: ceiling warnings + CI vs declared set (independent of emit prose)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import measure as M  # noqa: E402

ART = M.REPO / M.OUT_REL


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 2048:
        print("FAILED:BLD-0011-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:BLD-0011" not in json.dumps(doc):
        print("FAILED:BLD-0011-probe2 sentinel absent")
        return 1

    raw = M.run_campaign()
    if not raw.get("ceil_pass"):
        print("FAILED:BLD-0011-probe2 ceiling subset did not pass")
        print((raw.get("ceiling") or {}).get("output", "")[-1500:])
        return 1
    if raw.get("suppressed"):
        print("FAILED:BLD-0011-probe2 deprecation warnings were suppressed")
        return 1
    ceil_doc = doc.get("ceiling_run") or {}
    if ceil_doc.get("warnings_suppressed") is True:
        print("FAILED:BLD-0011-probe2 artifact claims warnings_suppressed")
        return 1

    live_same = raw.get("same_set")
    live_sym = raw.get("symmetric_difference") or []
    art_cmp = doc.get("ci_vs_declared") or {}
    if art_cmp.get("same_set") is True and live_same is False:
        print("FAILED:BLD-0011-probe2 artifact claims same_set but live check differs")
        return 1
    if live_same is False and not live_sym:
        print("FAILED:BLD-0011-probe2 sets differ but symmetric_difference empty")
        return 1
    reviewer = doc.get("reviewer") or {}
    if reviewer.get("independent") is not True or reviewer.get("verdict") != "PASS":
        print("FAILED:BLD-0011-probe2 reviewer gate")
        return 1
    if reviewer.get("scope_not_agreement") is not True:
        print("FAILED:BLD-0011-probe2 reviewer is agreement-not-scope")
        return 1
    never = doc.get("never_executed") or []
    if not never:
        print("FAILED:BLD-0011-probe2 never_executed empty")
        return 1
    print(
        json.dumps(
            {
                "probe": "probe2-ceiling-reviewer",
                "unit_id": "BLD-0011",
                "pass": True,
                "ceil_pass": raw.get("ceil_pass"),
                "warn_n": len(raw.get("warn_lines") or []),
                "same_set": live_same,
                "symmetric_difference": live_sym,
                "never_n": len(never),
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:BLD-0011-probe2 ceiling warnings and CI-vs-declared set")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
