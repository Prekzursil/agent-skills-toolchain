#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

IDS = [
    "ADV-0139",
    "ARC-0005",
    "ARC-0004",
    "ARC-0049",
    "ARC-0089",
    "AUD-0074",
    "BLD-0036",
    "CNF-0045",
    "CNF-0101",
    "IMP-0025",
    "IMP-0036",
    "RES-0010",
    "RES-0015",
    "RES-0102",
    "RES-0177",
    "TST-0072",
    "WFA-0018",
    "WFA-0039",
    "WFA-0044",
    "WFA-0045",
    "WFA-0133",
    "WFA-0141",
]
REPO = Path(__file__).resolve().parents[4]
PROBES = REPO / "command-center" / "p2-wave" / "probes"
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"


def main() -> None:
    cat = json.loads(CATALOG.read_text(encoding="utf-8"))
    by = {u["id"]: u for u in cat.get("work_units") or []}
    for uid in IDS:
        d = PROBES / uid
        print("====", uid)
        unit = by.get(uid) or {}
        out_rel = str(unit.get("output_path") or "").replace("\\", "/")
        out = REPO / out_rel
        print("  output:", out_rel, "exists" if out.is_file() else "MISSING", "size", out.stat().st_size if out.is_file() else 0)
        ret = d / "SUBAGENT-RETURN.json"
        man = d / "UNIT-ARTIFACT-MANIFEST.json"
        print("  return", ret.is_file(), "manifest", man.is_file())
        if ret.is_file():
            try:
                data = json.loads(ret.read_text(encoding="utf-8"))
                print("  return.status", data.get("status") or data.get("state"), "named_probes", len(data.get("named_probes") or []), "probes", len(data.get("probes") or []))
            except Exception as exc:
                print("  return unparseable", type(exc).__name__)
        if man.is_file():
            try:
                data = json.loads(man.read_text(encoding="utf-8"))
                arts = [a for a in (data.get("artifacts") or []) if isinstance(a, dict) and a.get("unit_id") == uid]
                print("  manifest rows", len(arts))
                for a in arts[:3]:
                    print("   ", a.get("path"), "present", a.get("present"), "sha", str(a.get("sha256") or "")[:16])
            except Exception as exc:
                print("  manifest unparseable", type(exc).__name__)
        # remaining /root
        for p in sorted(d.rglob("*")):
            if not p.is_file():
                continue
            if p.suffix.lower() not in {".py", ".json", ".md", ".txt", ".js", ".sh"}:
                continue
            txt = p.read_text(encoding="utf-8", errors="replace")
            if "/root" in txt:
                print("  /root in", p.relative_to(d))
                for i, line in enumerate(txt.splitlines(), 1):
                    if "/root" in line:
                        print(f"    {i}: {line.strip()[:220]}")


if __name__ == "__main__":
    main()
