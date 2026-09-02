#!/usr/bin/env python3
"""Dump catalog + probe surface for shard-05 IDs (Windows-safe, no G-1 measure)."""
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
WAVE = REPO / "command-center" / "p2-wave"
IDS = [
    ln.strip()
    for ln in (HERE / "shard-05.txt").read_text(encoding="utf-8").splitlines()
    if ln.strip()
]
CAT = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
BY = {u["id"]: u for u in CAT.get("work_units") or []}
IMPORT_RE = re.compile(r"^\s*(?:from|import)\s+([A-Za-z0-9_.]+)", re.M)
ASSERT_RE = re.compile(r"^\s*assert .+$", re.M)


def brief(uid: str) -> dict:
    u = BY.get(uid) or {}
    pdir = WAVE / "probes" / uid
    out_rel = str(u.get("output_path") or "").replace("\\", "/")
    out = REPO / out_rel if out_rel else None
    py_files = sorted(p.name for p in pdir.glob("*.py")) if pdir.is_dir() else []
    all_files = sorted(p.name for p in pdir.iterdir()) if pdir.is_dir() else []
    probes = []
    imports: list[str] = []
    asserts: list[str] = []
    if pdir.is_dir():
        for p in sorted(pdir.glob("probe*.py")) + sorted(pdir.glob("run_probes.py")):
            if not p.is_file():
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines()
            rec = {
                "name": p.name,
                "bytes": len(text.encode("utf-8", errors="replace")),
                "lines": len(lines),
                "head": lines[:50],
                "tail": lines[-40:] if len(lines) > 50 else [],
            }
            if len(lines) <= 160:
                rec["full"] = lines
            probes.append(rec)
            imports.extend(IMPORT_RE.findall(text))
            asserts.extend(m.group(0).strip() for m in list(ASSERT_RE.finditer(text))[:20])
    ret = pdir / "SUBAGENT-RETURN.json"
    man = pdir / "UNIT-ARTIFACT-MANIFEST.json"
    ret_doc = None
    man_doc = None
    if ret.is_file():
        try:
            ret_doc = json.loads(ret.read_text(encoding="utf-8"))
        except Exception as exc:
            ret_doc = {"_err": type(exc).__name__}
    if man.is_file():
        try:
            man_doc = json.loads(man.read_text(encoding="utf-8"))
        except Exception as exc:
            man_doc = {"_err": type(exc).__name__}
    cmds = []
    if isinstance(ret_doc, dict):
        for key in ("named_probes", "probes"):
            for item in ret_doc.get(key) or []:
                if isinstance(item, dict) and item.get("command"):
                    cmds.append(item["command"])
    rows = []
    if isinstance(man_doc, dict):
        for a in man_doc.get("artifacts") or []:
            if isinstance(a, dict) and a.get("unit_id") == uid:
                rows.append(
                    {
                        "path": a.get("path"),
                        "sha256": a.get("sha256"),
                        "present": a.get("present"),
                        "bytes": a.get("bytes"),
                    }
                )
    art = None
    if out and out.is_file():
        try:
            txt = out.read_text(encoding="utf-8")
            art = {
                "bytes": out.stat().st_size,
                "keys": [],
                "state": None,
                "has_sentinel": False,
            }
            try:
                doc = json.loads(txt)
                if isinstance(doc, dict):
                    art["state"] = doc.get("state") or doc.get("status") or doc.get("verdict")
                    art["keys"] = sorted(doc.keys())[:30]
                    art["sample"] = {k: doc[k] for k in list(doc)[:12] if not isinstance(doc[k], (dict, list))}
            except Exception as exc:
                art["parse"] = type(exc).__name__
            sent = str(u.get("completion_sentinel") or "")
            art["has_sentinel"] = bool(sent) and sent in txt
        except Exception as exc:
            art = {"err": type(exc).__name__}
    return {
        "id": uid,
        "title": (u.get("title") or u.get("name") or "")[:220],
        "output_path": out_rel,
        "output_exists": bool(out and out.is_file()),
        "output_bytes": out.stat().st_size if out and out.is_file() else 0,
        "sentinel": (u.get("completion_sentinel") or "")[:280],
        "probe_dir": pdir.is_dir(),
        "all_files": all_files,
        "py_files": py_files,
        "probe_count": len(probes),
        "probes": probes,
        "imports": sorted(set(imports)),
        "asserts": asserts[:24],
        "has_return": ret.is_file(),
        "has_manifest": man.is_file(),
        "return_status": (
            (ret_doc or {}).get("status") or (ret_doc or {}).get("state")
            if isinstance(ret_doc, dict)
            else None
        ),
        "named_cmds": cmds[:8],
        "manifest_rows": rows[:4],
        "artifact": art,
    }


def main() -> None:
    rows = [brief(uid) for uid in IDS]
    out = HERE / "_shard05_dump.json"
    out.write_text(json.dumps({"n": len(rows), "rows": rows}, indent=2), encoding="utf-8")
    print(f"wrote {out} n={len(rows)}")
    for r in rows:
        print(
            f"{r['id']:10} out={r['output_exists']} bytes={r['output_bytes']:6} "
            f"py={len(r['py_files'])} ret={r['has_return']} man={r['has_manifest']} "
            f"st={r['return_status']} sent={r['artifact']['has_sentinel'] if r['artifact'] else None} "
            f"imp={r['imports'][:6]}"
        )


if __name__ == "__main__":
    main()
