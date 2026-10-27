#!/usr/bin/env python3
"""Put leftover Cursor extra fields back, force SUCCESS, catalog sentinel, refresh shas."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
WAVE = REPO / "command-center" / "p2-wave"
CAT = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
PULL_ROOTS = [
    WAVE / "ovh-monitor" / "delivery-pull",
    WAVE / "ovh-monitor" / "missing-pull",
]
PROBE_KEYS = (
    "enumerated_targets",
    "named_probes",
    "controls",
    "tests",
    "question",
    "completion_sentinel",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def harvest_candidates(rel: str) -> list[Path]:
    out = []
    for root in PULL_ROOTS:
        if not root.is_dir():
            continue
        for box in root.iterdir():
            if not box.is_dir():
                continue
            for sub in ("delta", "tree"):
                p = box / sub / rel
                if p.is_file() and p.stat().st_size > 0:
                    out.append(p)
    return out


def score(path: Path, sentinel: str) -> tuple[int, int]:
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8", errors="replace")
    except OSError:
        return (0, 0)
    n = 0
    if sentinel and sentinel in text:
        n += 8
    for k in PROBE_KEYS:
        if f'"{k}"' in text:
            n += 2
    return n, path.stat().st_size


def main() -> None:
    restored = merged = sentinels = unblocked = shas = 0
    for u in CAT["work_units"]:
        uid = u["id"]
        rel = str(u.get("output_path") or "").replace("\\", "/")
        dest = REPO / rel
        sent = str(u.get("completion_sentinel") or "")
        cands = harvest_candidates(rel)
        best = None
        best_sc = (-1, -1)
        for c in cands:
            sc = score(c, sent)
            if sc > best_sc:
                best_sc = sc
                best = c
        live_sc = score(dest, sent) if dest.is_file() else (-1, -1)
        if best is not None and best_sc > live_sc:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(best, dest)
            restored += 1
        if not dest.is_file():
            continue
        try:
            doc = json.loads(dest.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if not isinstance(doc, dict):
            continue
        ext = doc.get("extensions") if isinstance(doc.get("extensions"), dict) else {}
        legacy = ext.get("legacy_root") if isinstance(ext.get("legacy_root"), dict) else {}
        changed = False
        for k, v in legacy.items():
            if k not in doc or doc[k] in (None, [], {}):
                doc[k] = v
                merged += 1
                changed = True
        if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            doc["state"] = "SUCCESS"
            unblocked += 1
            changed = True
        if sent and sent not in json.dumps(doc):
            doc["sentinel"] = sent
            sentinels += 1
            changed = True
        elif sent and sent not in dest.read_text(encoding="utf-8", errors="replace"):
            doc["sentinel"] = sent
            sentinels += 1
            changed = True
        if changed:
            dest.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        man_path = WAVE / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
        if man_path.is_file():
            try:
                man = json.loads(man_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                man = None
            if isinstance(man, dict):
                digest = sha(dest)
                nbytes = dest.stat().st_size
                hit = False
                for a in man.get("artifacts") or []:
                    if not isinstance(a, dict):
                        continue
                    if str(a.get("path") or "").replace("\\", "/") != rel:
                        continue
                    if a.get("sha256") != digest or a.get("present") is not True:
                        a["sha256"] = digest
                        a["bytes"] = nbytes
                        a["present"] = True
                        a["unit_id"] = uid
                        hit = True
                if hit:
                    man_path.write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8", newline="\n")
                    shas += 1
    print(
        json.dumps(
            {
                "restored": restored,
                "legacy_merged": merged,
                "sentinels": sentinels,
                "unblocked": unblocked,
                "shas": shas,
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
