#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
WAVE = REPO / "command-center" / "p2-wave"
diag = json.loads((WAVE / "ovh-monitor" / "g1-shards" / "_shard00_diag.json").read_text(encoding="utf-8"))


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def dump(path: Path, doc: object) -> None:
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    for row in diag:
        uid = row["id"]
        rel = str(row.get("output") or "").replace("\\", "/")
        out = REPO / rel
        if not rel or not out.is_file():
            print(uid, "skip")
            continue
        man_path = WAVE / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
        sha, nbytes = digest(out)
        man = json.loads(man_path.read_text(encoding="utf-8")) if man_path.is_file() else {}
        if not isinstance(man, dict):
            man = {}
        man.setdefault("schema_version", 1)
        man["unit_id"] = uid
        rows = man.get("artifacts")
        if not isinstance(rows, list):
            rows = []
            man["artifacts"] = rows
        hit = False
        for a in rows:
            if isinstance(a, dict) and str(a.get("path") or "").replace("\\", "/") == rel:
                a["sha256"] = sha
                a["bytes"] = nbytes
                a["present"] = True
                a["unit_id"] = uid
                hit = True
        if not hit:
            rows.insert(0, {"path": rel, "sha256": sha, "bytes": nbytes, "present": True, "unit_id": uid, "role": "primary"})
        dump(man_path, man)
        print(uid, sha[:12], nbytes)


if __name__ == "__main__":
    main()
