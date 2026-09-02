#!/usr/bin/env python3
"""Extract census tails + compact probe/receipt surface for leftover shard-09 IDs."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
WAVE = REPO / "command-center" / "p2-wave"
IDS = [
    ln.strip()
    for ln in (HERE / "shard-09.txt").read_text(encoding="utf-8").splitlines()
    if ln.strip()
]
WANT = set(IDS)
JSONL = WAVE / "ovh-monitor" / "g1-local-full.jsonl"
CAT = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
BY = {u["id"]: u for u in CAT.get("work_units") or []}


def last_fail_lines(text: str, n: int = 18) -> list[str]:
    hits = []
    for ln in text.splitlines():
        s = ln.strip()
        if (
            s.startswith("FAILED:")
            or s.startswith("AssertionError")
            or s.startswith("ModuleNotFound")
            or s.startswith("ImportError")
            or s.startswith("AttributeError")
            or s.startswith("TypeError")
            or s.startswith("KeyError")
            or s.startswith("RuntimeError")
            or s.startswith("FileNotFound")
            or s.startswith("PermissionError")
            or "Error:" in s
            or s.startswith("assert ")
        ):
            hits.append(s[:300])
    return hits[-n:] if hits else [ln.strip()[:300] for ln in text.splitlines()[-8:] if ln.strip()]


def main() -> None:
    latest: dict[str, dict] = {}
    if JSONL.is_file():
        with JSONL.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if not line.strip():
                    continue
                if not any(uid in line[:160] for uid in WANT):
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                uid = rec.get("id")
                if uid in WANT:
                    latest[uid] = rec

    rows = []
    for uid in IDS:
        u = BY.get(uid) or {}
        rec = latest.get(uid) or {}
        tail = str(rec.get("tail") or rec.get("evidence") or "")
        pdir = WAVE / "probes" / uid
        out_rel = str(u.get("output_path") or "").replace("\\", "/")
        out = REPO / out_rel if out_rel else None
        art: dict = {}
        if out and out.is_file():
            try:
                doc = json.loads(out.read_text(encoding="utf-8"))
            except Exception as exc:
                art = {"parse_error": type(exc).__name__}
            else:
                if isinstance(doc, dict):
                    art = {
                        "keys": sorted(doc.keys())[:40],
                        "state": doc.get("state") or doc.get("status"),
                        "kind": doc.get("kind") or doc.get("report_kind") or (doc.get("report") or {}).get("kind")
                        if isinstance(doc.get("report"), dict)
                        else doc.get("kind"),
                        "unit_id": doc.get("unit_id") or doc.get("id"),
                    }
                else:
                    art = {"type": type(doc).__name__}
        asserts = []
        for p in sorted(pdir.glob("probe*.py")):
            text = p.read_text(encoding="utf-8", errors="replace")
            hits = [
                f"{i}:{ln.strip()[:220]}"
                for i, ln in enumerate(text.splitlines(), 1)
                if "assert " in ln or ln.strip().startswith("raise ") or "FAILED:" in ln
            ]
            asserts.append({"file": p.name, "n": len(hits), "last": hits[-12:]})
        rows.append(
            {
                "id": uid,
                "title": (u.get("title") or u.get("name") or "")[:160],
                "output_path": out_rel,
                "sentinel": u.get("completion_sentinel"),
                "census_ok": rec.get("ok"),
                "census_cls": rec.get("cls"),
                "census_line": rec.get("line"),
                "census_fails": last_fail_lines(tail),
                "artifact": art,
                "asserts": asserts,
            }
        )
    dest = HERE / "_s09_leftover_surface.json"
    dest.write_text(
        json.dumps({"n": len(rows), "found_census": len(latest), "rows": rows}, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print("wrote", dest, "census", len(latest), "of", len(IDS))
    print("census_ok", [r["id"] for r in rows if r.get("census_ok") is True])
    print("census_missing", [r["id"] for r in rows if r.get("census_ok") is None])


if __name__ == "__main__":
    main()
