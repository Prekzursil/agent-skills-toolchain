#!/usr/bin/env python3
"""Probe 1: predicted live-path set vs dry-run HOME listing (independent signals)."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "plugin"))
import projection_map as pm  # noqa: E402

ART = REPO / "command-center" / "receipts" / "IMP-0010.json"


def main() -> int:
    bundle = pm.load_bundle(REPO)
    with tempfile.TemporaryDirectory(prefix="imp0010-p1-") as tmp:
        home = Path(tmp)
        predicted = pm.predict(bundle, home)
        actual = pm.dry_run(bundle, home)
        delta = pm.diff_sets(predicted, actual)
        report = {
            "probe": "probe1-prediction-matches-dry-run",
            "unit_id": "IMP-0010",
            "predicted_count": len(predicted),
            "actual_count": len(actual),
            "predicted": predicted,
            "actual": actual,
            "diff": delta,
            "match": predicted == actual
            and not delta["predicted_absent"]
            and not delta["present_unpredicted"],
        }
        print(json.dumps({k: report[k] for k in report if k not in {"predicted", "actual"}}, sort_keys=True))
        if not report["match"]:
            print("FAILED:IMP-0010-probe1 predicted vs dry-run mismatch")
            print(json.dumps(delta, indent=2))
            return 1
        if len(predicted) < 6:
            print("FAILED:IMP-0010-probe1 expected >=6 live identities")
            return 1
        kinds = {
            "settings": sum(1 for p in predicted if "/settings.json#" in p),
            "hooks": sum(1 for p in predicted if "hooks/_dispatch/manifest.json" in p),
            "skills": sum(1 for p in predicted if p.endswith("/SKILL.md")),
        }
        if kinds["hooks"] < 1 or kinds["skills"] < 1 or kinds["settings"] < 1:
            print(f"FAILED:IMP-0010-probe1 missing kind coverage {kinds}")
            return 1
        if ART.is_file():
            text = ART.read_text(encoding="utf-8")
            if "SUCCESS:IMP-0010" not in text:
                print("FAILED:IMP-0010-probe1 receipt sentinel absent")
                return 1
            doc = json.loads(text)
            st = str(doc.get("state") or "").upper()
            if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
                print(f"FAILED:IMP-0010-probe1 receipt self-declared {st}")
                return 1
        print(
            f"match=True predicted={len(predicted)} "
            f"hooks={kinds['hooks']} skills={kinds['skills']} settings={kinds['settings']}"
        )
        print("SUCCESS:IMP-0010-probe1 prediction matches dry-run HOME listing")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
