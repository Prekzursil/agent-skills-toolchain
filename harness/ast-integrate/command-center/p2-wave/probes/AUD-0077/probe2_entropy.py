#!/usr/bin/env python3
"""Named probe 2: independent entropy/pattern scan plus planted-token control."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from control import run_control  # noqa: E402
from entropy_scan import scan_tree  # noqa: E402
from helpers import OUT_REL, REPO, SENTINEL, UNIT  # noqa: E402

ART = REPO / OUT_REL


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:AUD-0077-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != UNIT:
        print("FAILED:AUD-0077-probe2 unit_id", doc.get("unit_id"))
        return 1
    if SENTINEL not in text:
        print("FAILED:AUD-0077-probe2 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:AUD-0077-probe2 self-declared", doc.get("state"))
        return 1
    if not (doc.get("entropy") or {}).get("independent_of_gitleaks"):
        print("FAILED:AUD-0077-probe2 entropy pass not marked independent")
        return 1

    live = scan_tree(REPO)
    recorded = list((doc.get("entropy") or {}).get("fingerprints") or [])
    if live["fingerprints"] != recorded:
        print("FAILED:AUD-0077-probe2 fingerprint mismatch")
        print(json.dumps({"live_n": live["hit_count"], "recorded_n": len(recorded)}, sort_keys=True))
        return 1

    ctrl = run_control()
    if not ctrl.get("entropy_found") or not ctrl.get("both_found"):
        print("FAILED:AUD-0077-probe2 planted token not found by entropy/both")
        return 1

    # Report text must not contain typical leaked gitleaks value keys as finding fields.
    for row in doc.get("findings") or []:
        for bad in ("value", "secret", "Secret", "Match", "raw"):
            if bad in row:
                print("FAILED:AUD-0077-probe2 finding contains", bad)
                return 1

    summary = {
        "probe": "probe2-entropy",
        "unit_id": UNIT,
        "pass": True,
        "hit_count": live["hit_count"],
        "files_scanned": live["files_scanned"],
        "rule_counts": live["rule_counts"],
        "independent_of_gitleaks": True,
        "control_entropy_found": True,
        "control_both_found": True,
        "secret_values_printed": False,
    }
    print(json.dumps(summary, sort_keys=True))
    print("SUCCESS:AUD-0077-probe2 entropy-plus-pattern metadata-only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
