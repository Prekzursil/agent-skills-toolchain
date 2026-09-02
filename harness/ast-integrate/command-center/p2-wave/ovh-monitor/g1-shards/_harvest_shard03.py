#!/usr/bin/env python3
"""Harvest shard-03 unit state from catalog, probes, and prior measure jsonl."""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
WAVE = REPO / "command-center" / "p2-wave"
SHARD = WAVE / "ovh-monitor" / "g1-shards" / "shard-03.txt"
JSONL = WAVE / "ovh-monitor" / "g1-shards" / "class-other.measure.jsonl"
CAT = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
BY = {u["id"]: u for u in CAT["work_units"]}

IDS = [ln.strip() for ln in SHARD.read_text(encoding="utf-8").splitlines() if ln.strip()]

prior = {}
if JSONL.is_file():
    for ln in JSONL.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        rec = json.loads(ln)
        prior[rec["id"]] = rec


def probe_failed_lines(text: str) -> list[str]:
    out = []
    for ln in text.splitlines():
        s = ln.strip()
        if s.startswith("FAILED:") or "assert " in s[:80]:
            out.append(s[:240])
    return out[:12]


def main() -> None:
    rows = []
    for uid in IDS:
        u = BY.get(uid) or {}
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
        fail_lines = []
        for p in (pdir.glob("probe*.py") if pdir.is_dir() else []):
            fail_lines.extend(probe_failed_lines(p.read_text(encoding="utf-8", errors="replace")))
        rec = prior.get(uid) or {}
        tail = rec.get("tail") or rec.get("line") or ""
        tail_fail = ""
        for ln in str(tail).splitlines():
            if "FAILED:" in ln or "Error:" in ln or "Error " in ln or "ModuleNotFound" in ln or "FileNotFound" in ln:
                tail_fail = ln.strip()[:300]
                break
        if not tail_fail and tail:
            tail_fail = str(tail)[-400:]
        out_rel = str(u.get("output_path") or "").replace("\\", "/")
        out = REPO / out_rel if out_rel else None
        rows.append(
            {
                "id": uid,
                "cls": rec.get("cls"),
                "ok_prior": rec.get("ok"),
                "line": rec.get("line"),
                "tail_fail": tail_fail,
                "title": (u.get("title") or u.get("name") or "")[:140],
                "output": out_rel,
                "output_exists": bool(out and out.is_file() and out.stat().st_size > 0),
                "output_bytes": out.stat().st_size if out and out.is_file() else 0,
                "sentinel_in_art": bool(
                    out
                    and out.is_file()
                    and (u.get("completion_sentinel") or "")
                    and (u.get("completion_sentinel") in out.read_text(encoding="utf-8", errors="replace"))
                ),
                "probe_dir": pdir.is_dir(),
                "probes": probes,
                "helpers": helpers,
                "has_emit": (pdir / "emit_artifact.py").is_file() if pdir.is_dir() else False,
                "has_ret": (pdir / "SUBAGENT-RETURN.json").is_file() if pdir.is_dir() else False,
                "has_man": (pdir / "UNIT-ARTIFACT-MANIFEST.json").is_file() if pdir.is_dir() else False,
                "probe_fail_lines": fail_lines[:8],
            }
        )
    dest = WAVE / "ovh-monitor" / "g1-shards" / "_shard03_harvest.json"
    dest.write_text(json.dumps({"n": len(rows), "rows": rows}, indent=2), encoding="utf-8")
    print(f"wrote {dest} n={len(rows)}")
    from collections import Counter

    print("cls", Counter(r["cls"] for r in rows))
    print("has_emit", sum(1 for r in rows if r["has_emit"]))
    print("output_exists", sum(1 for r in rows if r["output_exists"]))
    print("sentinel_in_art", sum(1 for r in rows if r["sentinel_in_art"]))
    missing_probes = [r["id"] for r in rows if not r["probes"]]
    print("no probes", missing_probes)
    for r in rows:
        print(
            f"{r['id']:10} {str(r['cls']):22} emit={int(r['has_emit'])} "
            f"out={int(r['output_exists'])} sent={int(r['sentinel_in_art'])} "
            f"probes={len(r['probes'])} {r['tail_fail'][:120]!r}"
        )


if __name__ == "__main__":
    main()
