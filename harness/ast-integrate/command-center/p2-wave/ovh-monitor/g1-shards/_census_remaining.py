#!/usr/bin/env python3
"""Census remaining class-probe-missing IDs: probes, harvest, imports."""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
WAVE = REPO / "command-center" / "p2-wave"
SHARD = WAVE / "ovh-monitor" / "g1-shards" / "class-probe-missing.txt"
CAT = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
UNITS = {u["id"]: u for u in CAT["work_units"]}
PULL = [
    WAVE / "ovh-monitor" / "delivery-pull",
    WAVE / "ovh-monitor" / "missing-pull",
    WAVE / "ovh-monitor" / "error-pull",
]
SUBS = ("tree", "delta", "extracted", "extracted-delta")
DONE = {
    "ARC-0082", "AUD-0024", "CC-0006", "CNF-0183", "IMP-0019", "IMP-0034",
    "IMP-0037", "IMP-0045", "IMP-0050", "IMP-0046", "IMP-0055", "IMP-0069",
}
IMP_RE = re.compile(r"^(?:from|import)\s+([a-zA-Z0-9_.]+)", re.M)


def named_py(ret: dict) -> list[str]:
    out: list[str] = []
    for item in (ret.get("named_probes") or []) + (ret.get("probes") or []):
        if not isinstance(item, dict):
            continue
        cmd = item.get("command")
        if not isinstance(cmd, str):
            continue
        for tok in cmd.split():
            t = tok.replace("\\", "/")
            if t.endswith(".py") and "probes/" in t:
                out.append(t)
    return out


def harvest(rel: str) -> list[str]:
    hits: list[str] = []
    for root in PULL:
        if not root.is_dir():
            continue
        for box in root.iterdir():
            if not box.is_dir():
                continue
            for sub in SUBS:
                cand = box / sub / rel
                if cand.is_file() and cand.stat().st_size > 0:
                    hits.append(str(cand.relative_to(WAVE)))
                alt = box / sub / Path(rel).name
                if alt.is_file() and alt.stat().st_size > 0:
                    hits.append(str(alt.relative_to(WAVE)))
    return hits


def imports_of(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return []
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                names.append(a.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


def main() -> None:
    ids = [ln.strip() for ln in SHARD.read_text(encoding="utf-8").splitlines() if ln.strip()]
    rows = []
    for uid in ids:
        unit = UNITS.get(uid) or {}
        pdir = WAVE / "probes" / uid
        ret_path = pdir / "SUBAGENT-RETURN.json"
        man_path = pdir / "UNIT-ARTIFACT-MANIFEST.json"
        out_rel = str(unit.get("output_path") or "").replace("\\", "/")
        out = REPO / out_rel if out_rel else None
        ret = None
        if ret_path.is_file():
            try:
                ret = json.loads(ret_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                ret = {"_unparseable": True}
        cmds = []
        if isinstance(ret, dict):
            for item in (ret.get("named_probes") or []) + (ret.get("probes") or []):
                if isinstance(item, dict) and isinstance(item.get("command"), str):
                    cmds.append(item["command"].strip())
        pys = named_py(ret) if isinstance(ret, dict) else []
        pfiles = sorted(p.name for p in pdir.glob("*.py")) if pdir.is_dir() else []
        missing = [p for p in pys if not (REPO / p).is_file()]
        present_pys = [p for p in pys if (REPO / p).is_file()]
        imps: list[str] = []
        for p in present_pys:
            imps.extend(imports_of(REPO / p))
        for p in pdir.glob("probe*.py") if pdir.is_dir() else []:
            imps.extend(imports_of(p))
        rec = {
            "id": uid,
            "done_prev": uid in DONE,
            "title": (unit.get("title") or unit.get("name") or "")[:120],
            "output": out_rel,
            "out_exists": bool(out and out.is_file() and out.stat().st_size > 0),
            "out_size": out.stat().st_size if out and out.is_file() else 0,
            "ret": ret_path.is_file(),
            "man": man_path.is_file(),
            "pdir": pdir.is_dir(),
            "py_files": pfiles,
            "cmds": cmds,
            "named_py": pys,
            "missing_py": missing,
            "harvest_missing": {m: harvest(m)[:3] for m in missing},
            "imports": sorted(set(imps)),
            "ret_status": (ret or {}).get("status") or (ret or {}).get("state") if isinstance(ret, dict) else None,
        }
        rows.append(rec)
        print(
            f"{uid} out={rec['out_exists']} ret={rec['ret']} man={rec['man']} "
            f"py={pfiles} missing={missing} cmds={len(cmds)}"
        )
    outp = WAVE / "ovh-monitor" / "g1-shards" / "_census_remaining.json"
    outp.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    missing_all = [r["id"] for r in rows if r["missing_py"]]
    no_py = [r["id"] for r in rows if not r["py_files"]]
    print("N", len(rows), "MISSING_NAMED", missing_all, "NO_PY_FILES", no_py)


if __name__ == "__main__":
    main()
