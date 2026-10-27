#!/usr/bin/env python3
"""Check each artifact records the unit's named probes with verbatim output."""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
MY = ["AUD-0044", "AUD-0047", "AUD-0053", "AUD-0055", "AUD-0057",
      "AUD-0064", "AUD-0066", "AUD-0069", "AUD-0071", "AUD-0072",
      "AUD-0075", "AUD-0080"]

cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
byid = {e["id"]: e for e in cat["work_units"]}

for uid in MY:
    e = byid[uid]
    art = json.loads((REPO / e["output_path"]).read_text(encoding="utf-8"))
    probes = art.get("probes")
    n = 0
    names = []
    if isinstance(probes, list):
        n = len(probes)
        for p in probes:
            if isinstance(p, dict):
                nm = p.get("name") or p.get("id") or p.get("probe") or ""
                has_raw = ("raw_output" in p) or ("output" in p) or ("stdout" in p)
                names.append(f"{nm}({'raw' if has_raw else 'NO-RAW'})")
    elif isinstance(probes, dict):
        names = list(probes.keys())
        n = len(names)
    named_scripts = sorted(x.name for x in
                           (REPO / f"command-center/p2-wave/probes/{uid}").glob("probe*.py"))
    print(f"{uid}: artifact.probes={n} {names} | scripts on disk: {named_scripts}")
