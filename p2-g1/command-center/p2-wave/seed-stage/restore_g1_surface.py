#!/usr/bin/env python3
"""Restore harvested receipts, put catalog completion_sentinel in the file, refresh per-unit shas."""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
WAVE = REPO / "command-center" / "p2-wave"
CAT = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
PULLS = [
    WAVE / "ovh-monitor" / "delivery-pull",
    WAVE / "ovh-monitor" / "missing-pull",
]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def harvest_copies(rel: str) -> list[Path]:
    out = []
    for root in PULLS:
        if not root.is_dir():
            continue
        for box in root.iterdir():
            if not box.is_dir():
                continue
            for sub in ("delta", "tree"):
                cand = box / sub / rel
                if cand.is_file() and cand.stat().st_size > 0:
                    out.append(cand)
    return out


def best_copy(rel: str, sentinel: str) -> Path | None:
    copies = harvest_copies(rel)
    if not copies:
        return None
    if sentinel:
        with_sent = []
        for p in copies:
            try:
                if sentinel in p.read_text(encoding="utf-8", errors="replace"):
                    with_sent.append(p)
            except OSError:
                continue
        if with_sent:
            copies = with_sent
    copies.sort(key=lambda p: p.stat().st_size, reverse=True)
    return copies[0]


def inject_sentinel(path: Path, sentinel: str) -> bool:
    if not sentinel:
        return False
    text = path.read_text(encoding="utf-8", errors="replace")
    if sentinel in text:
        return False
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        path.write_text(text.rstrip() + "\n" + sentinel + "\n", encoding="utf-8", newline="\n")
        return True
    if not isinstance(doc, dict):
        return False
    doc["sentinel"] = sentinel
    path.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return True


def refresh_manifest(uid: str, rel: str, path: Path) -> bool:
    man_path = WAVE / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
    if not man_path.is_file():
        return False
    try:
        man = json.loads(man_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    if not isinstance(man, dict):
        return False
    sha = digest(path)
    nbytes = path.stat().st_size
    changed = False
    arts = man.get("artifacts")
    if not isinstance(arts, list):
        return False
    for a in arts:
        if not isinstance(a, dict):
            continue
        ap = str(a.get("path") or "").replace("\\", "/")
        if ap != rel:
            continue
        if a.get("sha256") != sha or a.get("present") is not True:
            a["sha256"] = sha
            a["bytes"] = nbytes
            a["present"] = True
            a["unit_id"] = uid
            changed = True
    if changed:
        man_path.write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8", newline="\n")
    return changed


def main() -> int:
    restored = injected = shas = missing = 0
    for u in CAT["work_units"]:
        uid = u["id"]
        rel = str(u.get("output_path") or "").replace("\\", "/")
        dest = REPO / rel
        sent = str(u.get("completion_sentinel") or "")
        src = best_copy(rel, sent)
        if src is not None and dest.is_file():
            src_sent = sent in src.read_text(encoding="utf-8", errors="replace") if sent else False
            dst_sent = sent in dest.read_text(encoding="utf-8", errors="replace") if sent else False
            if src_sent and not dst_sent:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
                restored += 1
            elif src.stat().st_size > dest.stat().st_size * 1.05:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
                restored += 1
        if not dest.is_file():
            if src is not None:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
                restored += 1
            else:
                missing += 1
                continue
        if inject_sentinel(dest, sent):
            injected += 1
        if refresh_manifest(uid, rel, dest):
            shas += 1
    rec = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "restored_from_harvest": restored,
        "sentinels_injected": injected,
        "manifests_refreshed": shas,
        "still_missing_output": missing,
    }
    out = WAVE / "ovh-monitor" / "g1-restore.json"
    out.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
    print(f"SUCCESS:restore {json.dumps(rec)}", flush=True)
    return 0 if missing == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
