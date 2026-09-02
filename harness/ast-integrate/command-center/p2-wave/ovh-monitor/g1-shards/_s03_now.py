#!/usr/bin/env python3
"""Compact harvest for the current leftover shard-03 IDs."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CAT = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
BY = {u["id"]: u for u in CAT["work_units"]}
IDS = [ln.strip() for ln in (HERE / "shard-03.txt").read_text(encoding="utf-8").splitlines() if ln.strip()]
PROBES = REPO / "command-center" / "p2-wave" / "probes"
FAIL_RE = re.compile(r"FAILED:|assert |raise SystemExit|ModuleNotFound|FileNotFound")


def digest(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def fail_lines(text: str) -> list[str]:
    out = []
    for ln in text.splitlines():
        s = ln.strip()
        if FAIL_RE.search(s) and len(s) < 240:
            out.append(s[:220])
    return out[:10]


def main() -> None:
    rows = []
    for uid in IDS:
        u = BY.get(uid) or {}
        pdir = PROBES / uid
        out_rel = str(u.get("output_path") or "").replace("\\", "/")
        out = REPO / out_rel if out_rel else None
        ret = {}
        man = {}
        if (pdir / "SUBAGENT-RETURN.json").is_file():
            try:
                ret = json.loads((pdir / "SUBAGENT-RETURN.json").read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                ret = {"_unparseable": True}
        if (pdir / "UNIT-ARTIFACT-MANIFEST.json").is_file():
            try:
                man = json.loads((pdir / "UNIT-ARTIFACT-MANIFEST.json").read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                man = {"_unparseable": True}
        py = sorted(p.name for p in pdir.glob("*.py")) if pdir.is_dir() else []
        pfail = []
        for p in (pdir.glob("probe*.py") if pdir.is_dir() else []):
            pfail.extend(fail_lines(p.read_text(encoding="utf-8", errors="replace")))
        art_sha = digest(out) if out and out.is_file() else ""
        man_rows = [
            a
            for a in (man.get("artifacts") or [])
            if isinstance(a, dict) and a.get("unit_id") == uid
        ]
        man_sha = ""
        if man_rows:
            for a in man_rows:
                if str(a.get("path") or "").replace("\\", "/") == out_rel:
                    man_sha = str(a.get("sha256") or "")
        rows.append(
            {
                "id": uid,
                "title": (u.get("title") or u.get("name") or "")[:160],
                "output": out_rel,
                "sentinel": (u.get("completion_sentinel") or "")[:80],
                "out_exists": bool(out and out.is_file() and out.stat().st_size > 0),
                "out_bytes": out.stat().st_size if out and out.is_file() else 0,
                "art_sha8": art_sha[:8],
                "man_sha8": man_sha[:8],
                "sha_match": bool(art_sha and man_sha and art_sha == man_sha),
                "ret_status": str(ret.get("status") or ret.get("state") or ""),
                "py": py,
                "cmds": [
                    (x.get("command") or "")
                    for x in (ret.get("named_probes") or ret.get("probes") or [])
                    if isinstance(x, dict)
                ],
                "probe_fail_lines": pfail[:8],
                "pdir": pdir.is_dir(),
                "has_ret": (pdir / "SUBAGENT-RETURN.json").is_file() if pdir.is_dir() else False,
                "has_man": (pdir / "UNIT-ARTIFACT-MANIFEST.json").is_file() if pdir.is_dir() else False,
            }
        )
    dest = HERE / "_s03_now.json"
    dest.write_text(json.dumps({"n": len(rows), "rows": rows}, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {dest} n={len(rows)}")
    for r in rows:
        print(
            f"{r['id']:10} out={int(r['out_exists']):d} sha={int(r['sha_match']):d} "
            f"ret={r['ret_status'][:12]:12} py={len(r['py']):2d} {r['output'][-50:]}"
        )


if __name__ == "__main__":
    main()
