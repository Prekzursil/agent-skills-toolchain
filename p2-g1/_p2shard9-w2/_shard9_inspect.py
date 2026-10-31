#!/usr/bin/env python3
"""Shard-9 wave-2 inspector: per-unit state vs delivery contract."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
PROBES = REPO / "command-center" / "p2-wave" / "probes"
UNITS = [
    "CNF-0169", "CNF-0171", "CNF-0172", "CNF-0177",
    "CNF-0184", "CNF-0188", "CNF-0191", "CNL-0078",
    "IMP-0002", "IMP-0006", "IMP-0022", "IMP-0031",
]
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"__error__": f"{type(exc).__name__}: {exc}"}


def digest_file(path: Path):
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    cat = load(CATALOG)
    index = {}
    for u in cat.get("work_units") or []:
        if isinstance(u, dict) and u.get("id") in UNITS:
            index[u["id"]] = u
    for uid in UNITS:
        print(f"===== {uid} =====")
        unit = index.get(uid)
        if unit is None:
            print("  CATALOG: MISSING ENTRY")
            continue
        out_rel = str(unit.get("output_path") or "").replace("\\", "/")
        print(f"  catalog.out={out_rel}")
        print(f"  catalog.schema={unit.get('output_schema')}")
        print(f"  catalog.dep={unit.get('dependencies')}")
        print(f"  catalog.sentinel={unit.get('completion_sentinel')!r}")
        print(f"  catalog.probes={json.dumps(unit.get('probes'))[:220]}")
        print(f"  catalog.desc={str(unit.get('description'))[:360]}")
        # artifact
        art = REPO / out_rel if out_rel else None
        if art is None or not art.is_file():
            print(f"  ARTIFACT: ABSENT ({art})")
        else:
            doc = load(art)
            if "__error__" in doc:
                print(f"  ARTIFACT: size={art.stat().st_size} UNPARSEABLE {doc['__error__']}")
            else:
                st = str(doc.get("state") or "").upper()
                rev = doc.get("reviewer") or {}
                print(f"  ARTIFACT: size={art.stat().st_size} state={st!r}")
                print(f"  reviewer: verdict={rev.get('verdict')!r} independent={rev.get('independent')!r} id={rev.get('reviewer_id')!r}")
                fail_ = doc.get("failure") or {}
                print(f"  failure: {json.dumps(fail_)[:240]}")
                nts = str(doc.get("notes") or "")[:220]
                print(f"  notes: {nts}")
                sentinel = str(unit.get("completion_sentinel") or "")
                if sentinel:
                    text = art.read_text(encoding="utf-8", errors="replace")
                    print(f"  sentinel-present={sentinel in text}")
        # probe dir
        pd = PROBES / uid
        files = sorted(p.name for p in pd.iterdir()) if pd.is_dir() else []
        print(f"  PROBES: files={files}")
        ret = load(pd / "SUBAGENT-RETURN.json") if (pd / "SUBAGENT-RETURN.json").is_file() else None
        if isinstance(ret, dict):
            st_ret = str(ret.get("status") or ret.get("state") or "").upper()
            print(f"  RETURN: status={st_ret!r} reviewer={json.dumps(ret.get('reviewer'))[:160]}")
        man = load(pd / "UNIT-ARTIFACT-MANIFEST.json") if (pd / "UNIT-ARTIFACT-MANIFEST.json").is_file() else None
        if isinstance(man, dict):
            rows = [a for a in (man.get("artifacts") or []) if isinstance(a, dict) and a.get("unit_id") == uid]
            for a in rows:
                p_match = str(a.get("path") or "").replace("\\", "/") == out_rel
                live = None
                if art is not None and art.is_file():
                    live, _ = digest_file(art)
                sha_match = str(a.get("sha256") or "") == live
                print(f"  MANIFEST row: path-match={p_match} sha-match={sha_match} present={a.get('present')} manifest-sha={str(a.get('sha256'))[:12]}.. live-sha={str(live)[:12]}..")
            if not rows:
                print("  MANIFEST: NO ROW FOR THIS UNIT")
        else:
            print("  MANIFEST: ABSENT/UNPARSEABLE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
