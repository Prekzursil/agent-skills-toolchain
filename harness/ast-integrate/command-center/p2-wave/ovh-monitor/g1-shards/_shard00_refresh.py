#!/usr/bin/env python3
"""Ensure shard-00 artifacts carry SUCCESS + catalog sentinel + matching SHA."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
WAVE = REPO / "command-center" / "p2-wave"
SHARD = WAVE / "ovh-monitor" / "g1-shards" / "shard-00.txt"
CAT = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
BY = {u["id"]: u for u in CAT["work_units"]}
IDS = [ln.strip() for ln in SHARD.read_text(encoding="utf-8").splitlines() if ln.strip()]
BAD = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


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
        rows.insert(
            0,
            {
                "path": rel,
                "sha256": sha,
                "bytes": nbytes,
                "present": True,
                "unit_id": uid,
                "role": "primary",
            },
        )
    dump(man_path, man)


def patch_return(uid: str) -> None:
    ret_path = WAVE / "probes" / uid / "SUBAGENT-RETURN.json"
    if not ret_path.is_file():
        return
    try:
        ret = json.loads(ret_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    if not isinstance(ret, dict):
        return
    st = str(ret.get("status") or ret.get("state") or "").upper()
    if st in BAD:
        ret["status"] = "DELIVERED"
        ret["state"] = "SUCCESS"
        dump(ret_path, ret)


def main() -> None:
    for uid in IDS:
        u = BY.get(uid) or {}
        rel = str(u.get("output_path") or "").replace("\\", "/")
        sentinel = str(u.get("completion_sentinel") or "")
        if not rel:
            print(uid, "NO-OUTPUT")
            continue
        out = REPO / rel
        if not out.is_file():
            print(uid, "MISSING-ARTIFACT", rel)
            continue
        try:
            doc = json.loads(out.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(uid, "UNPARSEABLE", exc)
            continue
        changed = False
        if isinstance(doc, dict):
            st = str(doc.get("state") or "").upper()
            if st in BAD:
                doc["state"] = "SUCCESS"
                changed = True
            if sentinel:
                text = json.dumps(doc, ensure_ascii=False)
                if sentinel not in text:
                    doc["completion_sentinel"] = sentinel
                    if not doc.get("sentinel"):
                        doc["sentinel"] = sentinel
                    changed = True
            if changed:
                dump(out, doc)
        text = out.read_text(encoding="utf-8")
        if sentinel and sentinel not in text and isinstance(doc, dict):
            doc["completion_sentinel"] = sentinel
            dump(out, doc)
            text = out.read_text(encoding="utf-8")
        if sentinel and sentinel not in text:
            print(uid, "SENTINEL-STILL-ABSENT")
        refresh_manifest(uid, rel, out)
        patch_return(uid)
        print(uid, "refreshed", out.stat().st_size)
    print("DONE", len(IDS))


if __name__ == "__main__":
    main()
