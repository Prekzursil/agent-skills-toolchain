#!/usr/bin/env python3
"""shard-07 repair helpers: JSON load/save with LF, normalized sha256, manifest refresh."""
import hashlib
import json
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\source\ast-integrate")


def load(rel: str):
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def save(rel: str, doc, sort_keys: bool = True) -> None:
    text = json.dumps(doc, indent=2, sort_keys=sort_keys, ensure_ascii=False) + "\n"
    (REPO / rel).write_text(text, encoding="utf-8", newline="\n")


def sha_norm(rel: str) -> tuple[str, int]:
    raw = (REPO / rel).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def refresh_manifest(unit: str, touched_rels: list[str]) -> None:
    """Recompute sha256/bytes rows in the unit's UNIT-ARTIFACT-MANIFEST.json for touched paths."""
    man_rel = f"command-center/p2-wave/probes/{unit}/UNIT-ARTIFACT-MANIFEST.json"
    man = load(man_rel)
    touched = {t.replace("\\", "/") for t in touched_rels}
    for row in man.get("artifacts", []):
        p = str(row.get("path") or "").replace("\\", "/")
        if p in touched:
            sha, n = sha_norm(p)
            row["sha256"] = sha
            row["bytes"] = n
            row["present"] = True
    save(man_rel, man)
    for t in touched:
        sha, n = sha_norm(t)
        print(f"  refreshed {t} sha256={sha} bytes={n}")
