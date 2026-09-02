#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
WAVE = REPO / "command-center" / "p2-wave"
IDS = [
    ln.strip()
    for ln in (WAVE / "ovh-monitor" / "g1-shards" / "class-probe-missing.txt")
    .read_text(encoding="utf-8")
    .splitlines()
    if ln.strip()
][:12]
CAT = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
UNITS = {u["id"]: u for u in CAT["work_units"]}


def sha(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def exists(rel: str) -> dict:
    p = REPO / rel
    return {"rel": rel, "exists": p.is_file(), "size": p.stat().st_size if p.is_file() else 0}


EXTRA = [
    "blueprints/workflows/wf.research.archival.json",
    "blueprints/workflows/wf.research.contradiction-negative-result.json",
    "blueprints/workflows/wf.research.watchlist.json",
    "tools/workflow_foundry/license_extract.py",
    "tools/marketplace/license.py",
    "tools/marketplace/name_grammar.py",
    "tools/marketplace/fixtures/planted_collisions.json",
    "command-center/wrong_recipe_gate.py",
    "tools/plugin/blob.py",
    "tools/plugin/drift.py",
    "tools/plugin/data/error-taxonomy.json",
    "tools/plugin/tests/test_argv_only.py",
    "tools/plugin/tests/test_drift_classifier.py",
    "tools/plugin/tests/test_deployed_copy_guard.py",
    "tools/plugin/tests/test_compat_diagnostics.py",
    "tools/plugin/tests/test_exit_codes.py",
    "tools/plugin/tests/test_doctor_coverage.py",
    "tools/plugin/doctor/coverage.py",
    "tools/plugin/doctor/io.py",
    "tools/plugin/doctor/__init__.py",
    "tools/glob-argv-guard/glob_argv_guard.py",
    "tools/plugin/argv.py",
    "command-center/receipts/CNF-0183.json",
    "command-center/receipts/IMP-0019.json",
    "command-center/receipts/IMP-0034.json",
    "command-center/receipts/IMP-0037.json",
    "command-center/receipts/IMP-0045.json",
    "command-center/receipts/IMP-0046.json",
    "command-center/receipts/IMP-0050.json",
    "command-center/receipts/IMP-0055.json",
    "command-center/receipts/IMP-0069.json",
    "command-center/receipts/CC-0006.json",
    "command-center/audit/AUD-0024-license-inventory.json",
    "command-center/phase4/contracts/ARC-0082.json",
]


def main() -> None:
    rows = []
    for uid in IDS:
        unit = UNITS[uid]
        out_rel = unit["output_path"].replace("\\", "/")
        out = REPO / out_rel
        man_path = WAVE / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
        ret_path = WAVE / "probes" / uid / "SUBAGENT-RETURN.json"
        man = json.loads(man_path.read_text(encoding="utf-8")) if man_path.is_file() else None
        live_sha = sha(out) if out.is_file() else None
        rows_m = []
        if isinstance(man, dict):
            for a in man.get("artifacts") or []:
                if a.get("unit_id") == uid:
                    rows_m.append(a)
        match = any(
            str(a.get("path") or "").replace("\\", "/") == out_rel
            and a.get("sha256") == live_sha
            and a.get("present") is True
            for a in rows_m
        )
        rec = {
            "id": uid,
            "output": out_rel,
            "out_exists": out.is_file(),
            "out_size": out.stat().st_size if out.is_file() else 0,
            "live_sha": live_sha,
            "man_match": match,
            "man_shas": [a.get("sha256") for a in rows_m],
            "man_paths": [a.get("path") for a in rows_m],
            "sentinel": unit.get("completion_sentinel"),
            "sentinel_in": bool(unit.get("completion_sentinel") and out.is_file() and unit["completion_sentinel"] in out.read_text(encoding="utf-8", errors="replace")),
            "ret": ret_path.is_file(),
            "man": man_path.is_file(),
        }
        rows.append(rec)
        print(json.dumps(rec))
    extras = [exists(r) for r in EXTRA]
    missing = [e for e in extras if not e["exists"]]
    print("MISSING_EXTRA", json.dumps(missing))
    print("EXTRA_OK", len(extras) - len(missing), "/", len(extras))
    outp = WAVE / "ovh-monitor" / "g1-shards" / "_first12_prep.json"
    outp.write_text(json.dumps({"units": rows, "extras": extras}, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
