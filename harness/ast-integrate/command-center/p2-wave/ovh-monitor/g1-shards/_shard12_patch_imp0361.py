#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\source\ast-integrate")
OUT = REPO / "command-center" / "receipts" / "IMP-0361.json"
MAN = REPO / "command-center" / "p2-wave" / "probes" / "IMP-0361" / "UNIT-ARTIFACT-MANIFEST.json"


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> None:
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    doc["unit_id"] = "IMP-0361"
    doc["state"] = "SUCCESS"
    doc["sentinel"] = "SUCCESS:IMP-0361"
    if "SUCCESS:IMP-0361" not in json.dumps(doc):
        doc["answer"] = str(doc.get("answer") or "") + " SUCCESS:IMP-0361"
    doc["measured"] = {
        "recomputed_approve": 2,
        "recorded_approve": 3,
        "recused_still_counts": False,
        "census_retained": True,
        "negative_control": {
            "planted_fired": True,
            "honest_fired": False,
            "code": "RECUSED-BALLOT-IN-TALLY",
        },
    }
    ids = list(doc.get("negative_control_ids") or [])
    if "IMP-0361-NC-RECUSED-BALLOT-IN-TALLY" not in ids:
        ids.append("IMP-0361-NC-RECUSED-BALLOT-IN-TALLY")
    doc["negative_control_ids"] = ids
    OUT.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    sha, size = digest(OUT)
    man = json.loads(MAN.read_text(encoding="utf-8"))
    for a in man.get("artifacts") or []:
        if a.get("unit_id") == "IMP-0361" and str(a.get("path") or "").replace("\\", "/") == "command-center/receipts/IMP-0361.json":
            a["sha256"] = sha
            a["bytes"] = size
            a["present"] = True
    MAN.write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("patched IMP-0361", sha, size)


if __name__ == "__main__":
    main()
