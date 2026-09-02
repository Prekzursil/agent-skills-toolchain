#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "probes" / "ADV-0067"))
import probe_common as C  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
art = REPO / C.ART_REL if hasattr(C, "ART_REL") else C.ART
live = C.compare_packages()
doc = json.loads(art.read_text(encoding="utf-8"))
rec = doc.setdefault("probe1_comparison", {})
rec["genuine_total"] = live["genuine"]["total"]
rec["gamed_total"] = live["gamed"]["total"]
rec["empty_total"] = live["empty"]["total"]
rec["named_inversion_term"] = live["named_inversion_term"]
sens = doc.setdefault("probe2_sensitivity", {})
if not sens.get("rows"):
    # copy live sensitivity if present
    if hasattr(C, "sensitivity"):
        pass
art.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print("patched", art, "genuine", rec["genuine_total"])
