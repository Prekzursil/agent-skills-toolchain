#!/usr/bin/env python3
"""Lift ADV-0131 report domain fields to top-level so probe2 can see them."""
from __future__ import annotations

import json
from pathlib import Path

import importlib.util

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("s12_sha", HERE / "_s12_sha.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

REPO = mod.REPO
ART = REPO / "command-center/adversarial/ADV-0131-cross-artifact-contradictions.json"

doc = json.loads(ART.read_text(encoding="utf-8"))
report = doc.get("report") or {}
lift = ("known_live_instance", "pairs", "false_positive_control", "pair_count", "matching_rule")
for k in lift:
    if k in report and k not in doc:
        doc[k] = report[k]
    elif k in report:
        # keep top-level if already present; only fill if missing
        pass

# probe2 also iterates doc.get("pairs") for anchors
if not doc.get("pairs") and report.get("pairs"):
    doc["pairs"] = report["pairs"]
if "known_live_instance" not in doc and report.get("known_live_instance"):
    doc["known_live_instance"] = report["known_live_instance"]
if "false_positive_control" not in doc and report.get("false_positive_control"):
    doc["false_positive_control"] = report["false_positive_control"]

ART.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8", newline="\n")
print("lifted", {k: k in doc for k in lift})
print("known_found", (doc.get("known_live_instance") or {}).get("found"))
print("pairs", len(doc.get("pairs") or []))
mod.refresh_manifest("ADV-0131", ["command-center/adversarial/ADV-0131-cross-artifact-contradictions.json"])
