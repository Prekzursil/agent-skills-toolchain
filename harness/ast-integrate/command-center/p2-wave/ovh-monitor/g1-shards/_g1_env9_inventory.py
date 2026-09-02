#!/usr/bin/env python3
"""Inventory the 9 assigned envelope IDs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\source\ast-integrate")
CAT = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
BY = {u["id"]: u for u in CAT["work_units"] if isinstance(u, dict) and u.get("id")}
PROBES = REPO / "command-center/p2-wave/probes"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})
IDS = [
    "ARC-0052",
    "ARC-0059",
    "CC-0002",
    "CNF-0140",
    "CNF-0158",
    "ARC-0024",
    "CNF-0001",
    "CNF-0063",
    "ARC-0058",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    rows = []
    for uid in IDS:
        unit = BY.get(uid) or {}
        rel = str(unit.get("output_path") or "").replace("\\", "/")
        sent = str(unit.get("completion_sentinel") or "")
        out = REPO / rel if rel else None
        probe = PROBES / uid
        rec = {
            "id": uid,
            "rel": rel,
            "sent_prefix": sent[:40],
            "out_exists": bool(out and out.is_file()),
            "out_bytes": out.stat().st_size if out and out.is_file() else 0,
            "probe_dir": probe.is_dir(),
            "p1": [p.name for p in sorted(probe.glob("probe1*.py"))],
            "p2": [p.name for p in sorted(probe.glob("probe2*.py"))],
            "emit": [p.name for p in sorted(probe.glob("emit*.py"))],
            "ret": (probe / "SUBAGENT-RETURN.json").is_file(),
            "man": (probe / "UNIT-ARTIFACT-MANIFEST.json").is_file(),
        }
        if out and out.is_file():
            try:
                text = out.read_text(encoding="utf-8")
                doc = json.loads(text)
                rec["parse"] = "ok"
                rec["state"] = doc.get("state") if isinstance(doc, dict) else type(doc).__name__
                rec["keys"] = sorted(doc.keys())[:30] if isinstance(doc, dict) else []
                rec["sentinel_in"] = sent[:20] in text if sent else None
                rec["sent_full_in"] = sent in text if sent else None
            except Exception as exc:  # noqa: BLE001
                rec["parse"] = type(exc).__name__
            sha, nbytes = digest(out)
            rec["live_sha16"] = sha[:16]
            rec["live_nbytes"] = nbytes
            man_path = probe / "UNIT-ARTIFACT-MANIFEST.json"
            if man_path.is_file():
                man = json.loads(man_path.read_text(encoding="utf-8"))
                hits = [
                    a
                    for a in (man.get("artifacts") or [])
                    if isinstance(a, dict)
                    and a.get("unit_id") == uid
                    and str(a.get("path") or "").replace("\\", "/") == rel
                ]
                rec["man_rows"] = len(hits)
                rec["man_sha16"] = (hits[0].get("sha256") or "")[:16] if hits else ""
                rec["sha_match"] = bool(hits and hits[0].get("sha256") == sha and hits[0].get("present") is True)
        ret_path = probe / "SUBAGENT-RETURN.json"
        if ret_path.is_file():
            try:
                ret = json.loads(ret_path.read_text(encoding="utf-8"))
                rec["ret_status"] = ret.get("status") or ret.get("state")
                rec["named"] = len(ret.get("named_probes") or [])
            except Exception as exc:  # noqa: BLE001
                rec["ret_status"] = type(exc).__name__
        rows.append(rec)
        print(json.dumps(rec, ensure_ascii=False))
    (Path(__file__).parent / "_g1_env9_inventory.json").write_text(
        json.dumps(rows, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
