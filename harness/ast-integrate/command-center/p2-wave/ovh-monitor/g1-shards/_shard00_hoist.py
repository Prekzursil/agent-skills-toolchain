#!/usr/bin/env python3
"""Hoist report.* fields to artifact root so live probes can read them."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
WAVE = REPO / "command-center" / "p2-wave"
IDS = [
    ln.strip()
    for ln in (WAVE / "ovh-monitor" / "g1-shards" / "shard-00.txt")
    .read_text(encoding="utf-8")
    .splitlines()
    if ln.strip()
]
CAT = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
BY = {u["id"]: u for u in CAT["work_units"]}


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def dump(path: Path, doc: object) -> None:
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def refresh_manifest(uid: str, rel: str, out: Path) -> None:
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


def main() -> None:
    n = 0
    for uid in IDS:
        rel = str((BY.get(uid) or {}).get("output_path") or "").replace("\\", "/")
        if not rel:
            continue
        out = REPO / rel
        if not out.is_file():
            continue
        try:
            doc = json.loads(out.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if not isinstance(doc, dict):
            continue
        report = doc.get("report")
        if not isinstance(report, dict):
            continue
        changed = False
        for k, v in report.items():
            if k not in doc:
                doc[k] = v
                changed = True
        if changed:
            dump(out, doc)
            refresh_manifest(uid, rel, out)
            n += 1
            print("hoist", uid)
    print("HOISTED", n)


if __name__ == "__main__":
    main()
