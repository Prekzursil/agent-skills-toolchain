#!/usr/bin/env python3
"""Refresh per-unit UNIT-ARTIFACT-MANIFEST sha256 to live artifacts. No global write."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

REPO = Path(os.environ.get("AST_INTEGRATE_ROOT") or Path(__file__).resolve().parents[3])
CATALOG = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
BY_ID = {u["id"]: u for u in CATALOG.get("work_units") or [] if isinstance(u, dict) and "id" in u}
PROBES = REPO / "command-center" / "p2-wave" / "probes"
WIN = Path("/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards")


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def ids() -> list[str]:
    failp = WIN / "class-other.fail-ids.txt"
    if failp.is_file():
        rows = [ln.strip() for ln in failp.read_text(encoding="utf-8").splitlines() if ln.strip()]
        if rows:
            return rows
    summary = WIN / "class-envelope.measure.json"
    if summary.is_file():
        doc = json.loads(summary.read_text(encoding="utf-8"))
        return [str(x) for x in (doc.get("fail_ids") or [])]
    return []


def main() -> int:
    n = 0
    for uid in ids():
        unit = BY_ID.get(uid) or {}
        rel = str(unit.get("output_path") or "").replace("\\", "/")
        if not rel:
            continue
        out = REPO / rel
        if not out.is_file():
            continue
        sha, nbytes = digest_file(out)
        man_path = PROBES / uid / "UNIT-ARTIFACT-MANIFEST.json"
        man = {}
        if man_path.is_file():
            try:
                man = json.loads(man_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                man = {}
        if not isinstance(man, dict):
            man = {}
        arts = man.get("artifacts")
        if not isinstance(arts, list):
            arts = []
            man["artifacts"] = arts
        hit = False
        for a in arts:
            if not isinstance(a, dict):
                continue
            if str(a.get("path") or "").replace("\\", "/") != rel:
                continue
            a["sha256"] = sha
            a["bytes"] = nbytes
            a["present"] = True
            a["unit_id"] = uid
            hit = True
        if not hit:
            arts.insert(
                0,
                {"path": rel, "sha256": sha, "bytes": nbytes, "present": True, "unit_id": uid, "role": "primary"},
            )
        man["unit_id"] = uid
        man_path.parent.mkdir(parents=True, exist_ok=True)
        man_path.write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8", newline="\n")
        n += 1
    print(f"REFRESHED {n}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
