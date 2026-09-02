#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
WAVE = REPO / "command-center" / "p2-wave"
IDS = [
    ln.strip()
    for ln in (WAVE / "ovh-monitor" / "g1-shards" / "shard-01.txt")
    .read_text(encoding="utf-8")
    .splitlines()
    if ln.strip()
]
CAT = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
BY = {u["id"]: u for u in CAT["work_units"]}


def imports_of(text: str) -> list[str]:
    out = []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return ["<syntax-error>"]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                out.append(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.append(node.module.split(".")[0])
    return sorted(set(out))


def fail_strings(text: str) -> list[str]:
    found = []
    for m in re.finditer(r'fail\((?:f)?"([^"]{8,160})"', text):
        found.append(m.group(1)[:160])
    for m in re.finditer(r"fail\((?:f)?'([^']{8,160})'", text):
        found.append(m.group(1)[:160])
    for m in re.finditer(r'FAILED:[^"\n]{0,120}', text):
        found.append(m.group(0)[:160])
    return found[:12]


def main() -> None:
    rows = []
    for uid in IDS:
        u = BY.get(uid) or {}
        pdir = WAVE / "probes" / uid
        out_rel = str(u.get("output_path") or "").replace("\\", "/")
        out = REPO / out_rel if out_rel else None
        probes = []
        helpers = []
        if pdir.is_dir():
            for p in sorted(pdir.iterdir()):
                if not p.is_file():
                    continue
                rec = {
                    "name": p.name,
                    "bytes": p.stat().st_size,
                }
                if p.suffix == ".py":
                    text = p.read_text(encoding="utf-8", errors="replace")
                    rec["lines"] = text.count("\n") + 1
                    rec["imports"] = imports_of(text)
                    rec["fails"] = fail_strings(text)
                    rec["head"] = "\n".join(text.splitlines()[:18])
                    rec["tail"] = "\n".join(text.splitlines()[-25:])
                    rec["asserts"] = [
                        ln.strip()
                        for ln in text.splitlines()
                        if "assert " in ln or "raise " in ln or "fail(" in ln
                    ][:20]
                    if p.name.startswith("probe"):
                        probes.append(rec)
                    else:
                        helpers.append(rec)
                else:
                    if p.name in {"SUBAGENT-RETURN.json", "UNIT-ARTIFACT-MANIFEST.json"}:
                        try:
                            rec["json_ok"] = True
                            rec["keys"] = list(json.loads(p.read_text(encoding="utf-8")).keys())[:12]
                        except Exception as exc:
                            rec["json_ok"] = False
                            rec["err"] = type(exc).__name__
                    helpers.append(rec)
        art = None
        if out and out.is_file():
            try:
                doc = json.loads(out.read_text(encoding="utf-8"))
                art = {
                    "exists": True,
                    "bytes": out.stat().st_size,
                    "state": doc.get("state") if isinstance(doc, dict) else type(doc).__name__,
                    "keys": list(doc.keys())[:20] if isinstance(doc, dict) else [],
                }
            except Exception as exc:
                art = {"exists": True, "bytes": out.stat().st_size, "parse": type(exc).__name__}
        else:
            art = {"exists": False, "rel": out_rel}
        rows.append(
            {
                "id": uid,
                "title": (u.get("title") or "")[:180],
                "output_path": out_rel,
                "sentinel": (u.get("completion_sentinel") or "")[:180],
                "tests": (u.get("tests_required") or [])[:6],
                "artifact": art,
                "probe_dir": pdir.is_dir(),
                "probes": probes,
                "helpers": [{"name": h.get("name"), "bytes": h.get("bytes"), "imports": h.get("imports")} for h in helpers],
            }
        )
    dest = WAVE / "ovh-monitor" / "g1-shards" / "_diag_shard01.json"
    dest.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"wrote {dest} n={len(rows)}")
    for r in rows:
        pnames = [p["name"] for p in r["probes"]]
        print(f"{r['id']:10} art={r['artifact'].get('exists')} probes={pnames} out={r['output_path']}")


if __name__ == "__main__":
    main()
