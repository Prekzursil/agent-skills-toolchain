#!/usr/bin/env python3
"""Where catalog output_path files are vs probe manifests vs harvest extracts."""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
CATALOG = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
PROBES = REPO / "command-center" / "p2-wave" / "probes"
EXTRACT = REPO / "command-center" / "p2-wave" / "ovh-monitor" / "error-pull" / "extracted"
DELTA = REPO / "command-center" / "p2-wave" / "ovh-monitor" / "error-pull" / "extracted-delta"
OUT = REPO / "command-center" / "p2-wave" / "ovh-monitor" / "output-path-census.json"


def main() -> None:
    units = CATALOG.get("work_units") or []
    present = missing = no_path = 0
    missing_ids = []
    probe_has_primary = 0
    for u in units:
        uid = u.get("id")
        rel = str(u.get("output_path") or "").replace("\\", "/")
        if not rel:
            no_path += 1
            continue
        if (REPO / rel).is_file():
            present += 1
            continue
        missing += 1
        if len(missing_ids) < 8:
            missing_ids.append({"id": uid, "path": rel})
        man = PROBES / str(uid) / "UNIT-ARTIFACT-MANIFEST.json"
        if man.is_file():
            try:
                arts = json.loads(man.read_text(encoding="utf-8")).get("artifacts") or []
            except Exception:
                arts = []
            for a in arts:
                if str(a.get("path") or "").replace("\\", "/") == rel:
                    # primary registered; file still absent
                    probe_has_primary += 1
                    break
    print(f"units={len(units)} output_present={present} output_missing={missing} no_path={no_path}")
    print(f"missing_but_manifest_names_path={probe_has_primary}")
    print("sample missing", missing_ids)
    OUT.write_text(
        json.dumps(
            {
                "units": len(units),
                "output_present": present,
                "output_missing": missing,
                "no_path": no_path,
                "missing_but_manifest_names_path": probe_has_primary,
                "sample_missing": missing_ids,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
