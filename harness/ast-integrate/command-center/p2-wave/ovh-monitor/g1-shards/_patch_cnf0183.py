#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
ART = REPO / "command-center" / "receipts" / "CNF-0183.json"
MAN = (
    REPO
    / "command-center"
    / "p2-wave"
    / "probes"
    / "CNF-0183"
    / "UNIT-ARTIFACT-MANIFEST.json"
)


def sha(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> None:
    doc = json.loads(ART.read_text(encoding="utf-8"))
    rep = doc.get("report") or {}
    if not isinstance(rep, dict):
        raise SystemExit("no report")
    doc["rehearsals"] = list(rep.get("rehearsals") or [])
    doc["verdict_split"] = dict(rep.get("verdict_split") or {})
    doc["isolation"] = dict(rep.get("isolation") or {})
    ART.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha(ART)
    man = json.loads(MAN.read_text(encoding="utf-8"))
    for row in man.get("artifacts") or []:
        if row.get("unit_id") == "CNF-0183" and row.get("path") == "command-center/receipts/CNF-0183.json":
            row["sha256"] = digest
            row["bytes"] = size
            row["present"] = True
    MAN.write_text(json.dumps(man, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"bytes": size, "sha256": digest}))


if __name__ == "__main__":
    main()
