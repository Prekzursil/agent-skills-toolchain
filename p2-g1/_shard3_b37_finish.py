# -*- coding: utf-8 -*-
"""Shard-3 BLD-0037 finish: after probe1+probe2 go green, refresh the
per-unit manifest row for the freshly emitted receipt and print the sha."""
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent
RP = REPO / "command-center" / "receipts" / "BLD-0037.json"
MAN = REPO / "command-center" / "p2-wave" / "probes" / "BLD-0037" / "UNIT-ARTIFACT-MANIFEST.json"

final_sha = hashlib.sha256(RP.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
man = json.loads(MAN.read_text(encoding="utf-8"))
hit = False
for a in man.get("artifacts", []):
    if a.get("unit_id") == "BLD-0037" and a.get("path", "").endswith("receipts/BLD-0037.json"):
        a["sha256"] = final_sha
        a["bytes"] = RP.stat().st_size
        a["present"] = True
        a["role"] = "primary"
        hit = True
if not hit:
    man.setdefault("artifacts", []).append(
        {
            "unit_id": "BLD-0037",
            "path": "command-center/receipts/BLD-0037.json",
            "sha256": final_sha,
            "bytes": RP.stat().st_size,
            "present": True,
            "role": "primary",
            "receipt_path": "command-center/p2-wave/probes/BLD-0037/SUBAGENT-RETURN.json",
        }
    )
MAN.write_text(json.dumps(man, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
print("BLD-0037 manifest refreshed; sha:", final_sha)
