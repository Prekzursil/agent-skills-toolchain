#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
WAVE = REPO / "command-center" / "p2-wave"
CAT = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
BY = {u["id"]: u for u in CAT["work_units"]}
IDS = [
    ln.strip()
    for ln in (WAVE / "ovh-monitor" / "g1-shards" / "shard-06.txt")
    .read_text(encoding="utf-8")
    .splitlines()
    if ln.strip()
]


def last_asserts(text: str, n: int = 40) -> list[str]:
    lines = text.splitlines()
    hits = [
        f"{i}:{ln}"
        for i, ln in enumerate(lines, 1)
        if "assert " in ln or ln.strip().startswith("raise ") or "FAILED:" in ln
    ]
    if hits:
        return hits[-n:]
    return [f"{i}:{ln}" for i, ln in enumerate(lines[-n:], max(1, len(lines) - n + 1))]


def imports_and_attrs(text: str) -> dict:
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return {"syntax_error": str(exc)}
    names: dict[str, list[str]] = {}
    froms: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                names.setdefault(a.asname or a.name.split(".")[0], [])
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            froms.append(mod)
            root = (mod.split(".")[0] if mod else ".")
            for a in node.names:
                names.setdefault(root, []).append(a.name)
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            names.setdefault(node.value.id, []).append(node.attr)
    # unique
    for k, v in list(names.items()):
        names[k] = sorted(set(v))
    return {"froms": sorted(set(froms)), "names": names}


def main() -> None:
    rows = []
    for uid in IDS:
        u = BY.get(uid) or {}
        pdir = WAVE / "probes" / uid
        out_rel = str(u.get("output_path") or "").replace("\\", "/")
        out = REPO / out_rel if out_rel else None
        rec = {
            "id": uid,
            "title": (u.get("title") or u.get("name") or "")[:180],
            "output_path": out_rel,
            "sentinel": u.get("completion_sentinel"),
            "catalog_present": bool(u),
            "artifact_exists": bool(out and out.is_file() and out.stat().st_size > 0),
            "artifact_bytes": (out.stat().st_size if out and out.is_file() else 0),
            "probe_dir": pdir.is_dir(),
            "probe_files": [],
            "helpers": [],
            "ret": None,
            "man_ok": False,
            "man_row": None,
        }
        if pdir.is_dir():
            rec["probe_files"] = sorted(p.name for p in pdir.glob("probe*.py"))
            rec["helpers"] = sorted(
                p.name
                for p in pdir.iterdir()
                if p.suffix == ".py" and not p.name.startswith("probe")
            )
            rec["all_files"] = sorted(p.name for p in pdir.iterdir() if p.is_file())[:40]
            retp = pdir / "SUBAGENT-RETURN.json"
            manp = pdir / "UNIT-ARTIFACT-MANIFEST.json"
            rec["has_return"] = retp.is_file()
            rec["has_manifest"] = manp.is_file()
            if retp.is_file():
                try:
                    ret = json.loads(retp.read_text(encoding="utf-8"))
                    rec["ret_status"] = ret.get("status") or ret.get("state")
                    rec["named_probes"] = [
                        (item.get("command") if isinstance(item, dict) else None)
                        for item in (ret.get("named_probes") or [])
                    ]
                    rec["probes"] = [
                        (item.get("command") if isinstance(item, dict) else None)
                        for item in (ret.get("probes") or [])
                    ]
                except Exception as exc:
                    rec["ret"] = f"unparseable:{exc}"
            if manp.is_file():
                try:
                    man = json.loads(manp.read_text(encoding="utf-8"))
                    rows_m = [
                        a
                        for a in (man.get("artifacts") or [])
                        if isinstance(a, dict) and a.get("unit_id") == uid
                    ]
                    rec["man_ok"] = True
                    rec["man_row"] = rows_m[0] if rows_m else None
                except Exception as exc:
                    rec["man_ok"] = False
                    rec["man_err"] = str(exc)
            rec["probe_detail"] = {}
            for p in sorted(pdir.glob("*.py")):
                text = p.read_text(encoding="utf-8", errors="replace")
                rec["probe_detail"][p.name] = {
                    "bytes": len(text),
                    "lines": text.count("\n") + 1,
                    "asserts": last_asserts(text, 50),
                    "imports": imports_and_attrs(text),
                    "head": text.splitlines()[:25],
                }
        rows.append(rec)
    outp = WAVE / "ovh-monitor" / "g1-shards" / "_shard06_diag.json"
    outp.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"wrote {outp} n={len(rows)}")


if __name__ == "__main__":
    main()
