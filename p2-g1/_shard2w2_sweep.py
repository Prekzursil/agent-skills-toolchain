#!/usr/bin/env python3
"""Read-only static state sweep for shard-2 wave-2 units (resume-don't-rebuild)."""
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1").resolve()
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
PROBES = REPO / "command-center" / "p2-wave" / "probes"

MINE = [
    "ADV-0124", "ADV-0127", "ADV-0128",
    "ARC-0001", "ARC-0012", "ARC-0013", "ARC-0015",
    "ARC-0019", "ARC-0020", "ARC-0021",
    "ARC-0047", "ARC-0048",
]


def norm_sha(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    cat = json.loads(CATALOG.read_text(encoding="utf-8"))
    units = {u.get("id"): u for u in cat.get("work_units", []) if isinstance(u, dict)}
    missing_cat = [u for u in MINE if u not in units]
    if missing_cat:
        print("CATALOG-MISSING:", ",".join(missing_cat))
        return 2
    report = {}
    for uid in MINE:
        u = units[uid]
        out_rel = str(u.get("output_path") or "").replace("\\", "/")
        out = REPO / out_rel
        entry = {"output_path": out_rel}
        if not out.is_file():
            entry["artifact"] = "ABSENT"
        elif out.stat().st_size == 0:
            entry["artifact"] = "EMPTY"
        else:
            try:
                doc = json.loads(out.read_text(encoding="utf-8"))
                if isinstance(doc, dict):
                    entry["artifact"] = "ok"
                    entry["state"] = str(doc.get("state", "")) or "-"
                    entry["bytes"] = out.stat().st_size
                    sentinel = str(u.get("completion_sentinel") or "")
                    if sentinel:
                        entry["sentinel_present"] = sentinel in out.read_text(encoding="utf-8")
                else:
                    entry["artifact"] = "ok-non-dict"
            except Exception as exc:
                entry["artifact"] = f"UNPARSEABLE:{type(exc).__name__}"
        pd = PROBES / uid
        entry["probe_dir"] = pd.is_dir()
        if pd.is_dir():
            sr = pd / "SUBAGENT-RETURN.json"
            if sr.is_file():
                try:
                    r = json.loads(sr.read_text(encoding="utf-8"))
                    entry["return_status"] = str(r.get("status") or r.get("state") or "")
                    nps = r.get("named_probes") or r.get("probes") or []
                    entry["named_probes"] = len(nps)
                except Exception as exc:
                    entry["return_status"] = f"UNPARSEABLE:{type(exc).__name__}"
            else:
                entry["return_status"] = "ABSENT"
            man = pd / "UNIT-ARTIFACT-MANIFEST.json"
            if man.is_file():
                try:
                    m = json.loads(man.read_text(encoding="utf-8"))
                    rows = [
                        a
                        for a in (m.get("artifacts") or [])
                        if isinstance(a, dict) and a.get("unit_id") == uid
                    ]
                    entry["manifest_rows"] = len(rows)
                    if rows and isinstance(entry.get("artifact"), str) and entry["artifact"].startswith("ok"):
                        live = norm_sha(out)
                        match = [
                            a
                            for a in rows
                            if str(a.get("path") or "").replace("\\", "/") == out_rel
                            and str(a.get("sha256") or "") == live
                            and a.get("present") is True
                        ]
                        entry["manifest_sha_match"] = len(match)
                except Exception as exc:
                    entry["manifest_rows"] = f"UNPARSEABLE:{type(exc).__name__}"
            else:
                entry["manifest_rows"] = "ABSENT"
        report[uid] = entry
    out_path = REPO / "_shard2w2_static_state.json"
    out_path.write_text(json.dumps(report, indent=1), encoding="utf-8")
    for uid, e in report.items():
        print(f"=== {uid} ===")
        for k, v in e.items():
            print(f"  {k}: {v}")
    print("WROTE", out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
