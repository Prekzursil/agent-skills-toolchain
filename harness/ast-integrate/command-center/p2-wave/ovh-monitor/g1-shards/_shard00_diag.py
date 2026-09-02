#!/usr/bin/env python3
"""Diagnose shard-00 IDs from census + probe files + catalog."""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
WAVE = REPO / "command-center" / "p2-wave"
SHARD = WAVE / "ovh-monitor" / "g1-shards" / "shard-00.txt"
CAT = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
BY = {u["id"]: u for u in CAT["work_units"]}
IDS = [ln.strip() for ln in SHARD.read_text(encoding="utf-8").splitlines() if ln.strip()]


def main() -> None:
    found: dict[str, dict] = {}
    jsonl = WAVE / "ovh-monitor" / "g1-local-full.jsonl"
    if jsonl.is_file():
        with jsonl.open(encoding="utf-8") as f:
            for ln in f:
                rec = json.loads(ln)
                if rec.get("id") in set(IDS):
                    found[rec["id"]] = rec
    rows = []
    for uid in IDS:
        u = BY.get(uid) or {}
        rec = found.get(uid) or {}
        pdir = WAVE / "probes" / uid
        probes = sorted(p.name for p in pdir.glob("probe*.py")) if pdir.is_dir() else []
        helpers = (
            sorted(
                p.name
                for p in pdir.iterdir()
                if p.suffix == ".py" and not p.name.startswith("probe")
            )
            if pdir.is_dir()
            else []
        )
        out_rel = str(u.get("output_path") or "").replace("\\", "/")
        out = REPO / out_rel if out_rel else None
        ret = pdir / "SUBAGENT-RETURN.json"
        man = pdir / "UNIT-ARTIFACT-MANIFEST.json"
        row = {
            "id": uid,
            "title": (u.get("title") or u.get("name") or "")[:180],
            "output": out_rel,
            "out_exists": bool(out and out.is_file()),
            "out_size": out.stat().st_size if out and out.is_file() else 0,
            "probe_dir": pdir.is_dir(),
            "probes": probes,
            "helpers": helpers,
            "ret": ret.is_file(),
            "man": man.is_file(),
            "cls": rec.get("cls"),
            "ok": rec.get("ok"),
            "reason": rec.get("reason") or rec.get("fail") or rec.get("cls"),
            "tail_last": (rec.get("tail") or rec.get("line") or "")[-1200:],
        }
        rows.append(row)
        print("=" * 72)
        print(uid, "cls=", row["cls"], "ok=", row["ok"], "out=", row["out_exists"], row["out_size"])
        print("title:", row["title"])
        print("output:", row["output"])
        print("probes:", probes, "helpers:", helpers)
        print("TAIL:")
        print(row["tail_last"][-600:])
    outp = WAVE / "ovh-monitor" / "g1-shards" / "_shard00_diag.json"
    outp.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    print("WROTE", outp, "n=", len(rows), "census_hits=", len(found))


if __name__ == "__main__":
    main()
