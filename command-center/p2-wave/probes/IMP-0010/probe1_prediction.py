#!/usr/bin/env python3
"""IMP-0010 probe1: prediction measurement (signal 1)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "plugin"))
import projection_map as P  # noqa: E402

PROBE = Path(__file__).resolve().parent
EVIDENCE = (
    "TWO independent signals: (1) the projection map's predicted live-path set "
    "for the current manifest; (2) an actual dry-run deploy into a throwaway HOME "
    "whose resulting file listing is diffed against the prediction."
)


def main() -> int:
    home = Path("/tmp/imp0010-probe1-predict-home")
    doc = P.build_projection_map(REPO)
    errs = P.validate_projection_map(doc, REPO)
    predicted = P.predict_live_paths(REPO, home=home)
    consumes = P.consumes_generators(REPO)
    skill_paths = [
        p for p in predicted if "/skills/" in p.replace("\\", "/") and p.endswith("SKILL.md")
    ]
    confirmed = (
        not errs
        and len(predicted) >= 4
        and len(skill_paths) >= 1
        and any(p.endswith("settings.json") for p in predicted)
        and any("_dispatch/manifest.json" in p.replace("\\", "/") for p in predicted)
        and consumes["emit_callable"]
        and consumes["gen_callable"]
    )
    meas = {
        "probe": "probe1-prediction",
        "probe_1_confirmed": confirmed,
        "ok": confirmed,
        "predicted_count": len(predicted),
        "skill_path_count": len(skill_paths),
        "schema_errors": errs,
        "consumes_generators": consumes,
        "plugin": doc.get("plugin"),
        "version": doc.get("version"),
        "target_count": len(doc.get("targets") or []),
        "entrypoint_count": len(doc.get("entrypoints") or []),
        "sample_predicted": sorted(predicted)[:8],
    }
    (PROBE / "probe1-measurement.json").write_text(
        json.dumps(meas, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    lines = [
        "NAMED PROBE 1: PROJECTION PREDICTION MEASUREMENT",
        "PROBE-1-BEGIN:IMP-0010",
        "stage=p2-deliver",
        f"evidence_requirement_verbatim={EVIDENCE}",
        f"plugin={doc.get('plugin')} version={doc.get('version')}",
        f"predicted_count={len(predicted)}",
        f"skill_path_count={len(skill_paths)}",
        f"schema_errors={errs}",
        f"emit_callable={consumes['emit_callable']}",
        f"gen_callable={consumes['gen_callable']}",
        f"probe_1_confirmed={confirmed}",
        "PROBE-1-COMPLETE:IMP-0010",
        "SUCCESS:IMP-0010-probe1" if confirmed else "FAILED:IMP-0010-probe1",
    ]
    raw = "\n".join(lines) + "\n"
    (PROBE / "probe1-prediction.raw.txt").write_text(raw, encoding="utf-8")
    print(raw, end="")
    return 0 if confirmed else 1


if __name__ == "__main__":
    raise SystemExit(main())
