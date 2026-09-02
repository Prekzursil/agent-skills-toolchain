#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\source\ast-integrate")
WAVE = REPO / "command-center" / "p2-wave"
CAT = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
BY = {u["id"]: u for u in CAT["work_units"]}
IDS = [
    ln.strip()
    for ln in (WAVE / "ovh-monitor" / "g1-shards" / "shard-02.txt").read_text(encoding="utf-8").splitlines()
    if ln.strip()
]


def tail_asserts(text: str, n: int = 40) -> list[str]:
    lines = text.splitlines()
    hits = [ln for ln in lines if "assert" in ln or "raise " in ln or "FAILED" in ln]
    return hits[-n:]


def main() -> None:
    rows = []
    for uid in IDS:
        u = BY.get(uid) or {}
        pdir = WAVE / "probes" / uid
        out_rel = str(u.get("output_path") or "").replace("\\", "/")
        out = REPO / out_rel if out_rel else None
        probes = sorted(p.name for p in pdir.glob("probe*.py")) if pdir.is_dir() else []
        helpers = (
            sorted(p.name for p in pdir.iterdir() if p.suffix == ".py" and not p.name.startswith("probe"))
            if pdir.is_dir()
            else []
        )
        ret = {}
        ret_path = pdir / "SUBAGENT-RETURN.json"
        if ret_path.is_file():
            try:
                ret = json.loads(ret_path.read_text(encoding="utf-8"))
            except Exception as exc:
                ret = {"_err": type(exc).__name__}
        man = {}
        man_path = pdir / "UNIT-ARTIFACT-MANIFEST.json"
        if man_path.is_file():
            try:
                man = json.loads(man_path.read_text(encoding="utf-8"))
            except Exception as exc:
                man = {"_err": type(exc).__name__}
        probe_asserts = {}
        for name in probes:
            text = (pdir / name).read_text(encoding="utf-8", errors="replace")
            probe_asserts[name] = {
                "lines": text.count("\n") + 1,
                "imports": [ln.strip() for ln in text.splitlines() if ln.startswith(("import ", "from "))],
                "asserts": tail_asserts(text, 50),
            }
        art = None
        if out and out.is_file():
            try:
                raw = out.read_text(encoding="utf-8")
                art = {
                    "bytes": out.stat().st_size,
                    "keys": list(json.loads(raw).keys())[:30] if raw.strip().startswith("{") else None,
                    "head": raw[:400],
                }
            except Exception as exc:
                art = {"err": type(exc).__name__, "bytes": out.stat().st_size}
        rows.append(
            {
                "id": uid,
                "title": (u.get("title") or u.get("name") or "")[:200],
                "output_path": out_rel,
                "sentinel": u.get("completion_sentinel"),
                "out_exists": bool(out and out.is_file() and out.stat().st_size > 0),
                "probe_dir": pdir.is_dir(),
                "probes": probes,
                "helpers": helpers,
                "ret_status": (ret.get("status") or ret.get("state") if isinstance(ret, dict) else None),
                "named_probes": (ret.get("named_probes") or ret.get("probes") if isinstance(ret, dict) else None),
                "man_rows": (man.get("artifacts") if isinstance(man, dict) else None),
                "artifact": art,
                "probe_asserts": probe_asserts,
            }
        )
    dest = WAVE / "ovh-monitor" / "g1-shards" / "_shard02_dump.json"
    dest.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"wrote {dest} n={len(rows)}")


if __name__ == "__main__":
    main()
