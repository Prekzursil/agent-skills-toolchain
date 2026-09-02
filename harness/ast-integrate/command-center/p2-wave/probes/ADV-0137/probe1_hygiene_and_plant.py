#!/usr/bin/env python3
"""Probe 1: context-hygiene both-states + planted-disagreement diff fires.

Re-runs the re-deriver. Does not trust artifact booleans alone.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from counting_rule import SPEC_FILE  # noqa: E402
from harvest_json import CATALOG_REL  # noqa: E402

ART = REPO / "command-center/adversarial/ADV-0137-premise-concentration.json"
FAKE = HERE / "fixtures/fake-brief.md"
REDERIVE = HERE / "rederive.py"
SENTINEL_SNIP = "SUCCESS:ADV-0137"


def run_rederive(allow: list[Path], catalog: Path, key: str, out: Path) -> dict:
    cmd = [
        sys.executable,
        "-B",
        str(REDERIVE),
        "--repo",
        str(REPO),
        "--catalog",
        str(catalog),
        "--source-key",
        key,
        "--out",
        str(out),
    ]
    for p in allow:
        cmd.extend(["--allow", str(p)])
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True, env=env, timeout=120)
    if p.returncode != 0:
        print(f"FAILED:ADV-0137-probe1 rederive rc={p.returncode}")
        print(p.stderr[-1500:])
        raise SystemExit(1)
    return json.loads(out.read_text(encoding="utf-8"))


def main() -> int:
    if not ART.is_file():
        print("FAILED:ADV-0137-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if SENTINEL_SNIP not in json.dumps(doc):
        print("FAILED:ADV-0137-probe1 sentinel absent")
        return 1
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ADV-0137-probe1 self-declared {doc.get('state')}")
        return 1
    catalog = REPO / CATALOG_REL
    top = (doc.get("premises_top5") or [None])[0]
    if not isinstance(top, dict):
        print("FAILED:ADV-0137-probe1 no top premise")
        return 1
    key = top["source"]
    with tempfile.TemporaryDirectory(prefix="adv0137-p1-") as td:
        tdir = Path(td)
        clean = run_rederive([catalog], catalog, key, tdir / "clean.json")
        dirty = run_rederive([catalog, FAKE], catalog, key, tdir / "dirty.json")
        planted_path = tdir / "planted.json"
        planted_path.write_text(
            catalog.read_text(encoding="utf-8").replace(
                SPEC_FILE, "_USER-PROMPTS-PLANTED-ALTERED.md"
            ),
            encoding="utf-8",
        )
        plant_key = SPEC_FILE if key == SPEC_FILE else key
        planted = run_rederive(
            [planted_path], planted_path, plant_key, tdir / "planted-out.json"
        )
    if clean.get("hygiene_ok") is not True:
        print("FAILED:ADV-0137-probe1 clean bundle not ok")
        return 1
    if any("brief" in f["path"].lower() for f in clean["input_bundle"]["files"]):
        print("FAILED:ADV-0137-probe1 brief leaked into clean bundle")
        return 1
    if dirty.get("hygiene_ok") is not False:
        print("FAILED:ADV-0137-probe1 contaminated bundle not rejected")
        return 1
    if planted["direct_unit_count"] == clean["direct_unit_count"] and plant_key == key:
        print("FAILED:ADV-0137-probe1 planted diff silent")
        return 1
    if plant_key != key and planted["direct_unit_count"] == 0 and clean["direct_unit_count"] == 0:
        print("FAILED:ADV-0137-probe1 planted control measuring nothing")
        return 1
    if plant_key == SPEC_FILE and planted["direct_unit_count"] == clean["direct_unit_count"]:
        print("FAILED:ADV-0137-probe1 spec plant did not move the count")
        return 1
    rds = doc.get("rederivations") or []
    if len(rds) < 5:
        print("FAILED:ADV-0137-probe1 need 5 rederivations")
        return 1
    for rd in rds:
        if rd.get("hygiene_ok") is not True:
            print(f"FAILED:ADV-0137-probe1 artifact dirty {rd.get('premise_id')}")
            return 1
        files = (rd.get("input_bundle") or {}).get("files") or []
        if not files:
            print("FAILED:ADV-0137-probe1 empty bundle")
            return 1
        if any("brief" in str(f.get("path", "")).lower() for f in files):
            print("FAILED:ADV-0137-probe1 artifact bundle contains brief")
            return 1
    pd = doc.get("planted_disagreement") or {}
    if pd.get("diff_fired") is not True:
        print("FAILED:ADV-0137-probe1 artifact planted diff_fired not true")
        return 1
    hy = doc.get("context_hygiene") or {}
    if not (hy.get("clean_bundle_ok") and hy.get("contaminated_bundle_rejected") and hy.get("both_states")):
        print("FAILED:ADV-0137-probe1 artifact hygiene flags")
        return 1
    print(
        json.dumps(
            {
                "probe": "probe1-hygiene-and-plant",
                "unit_id": "ADV-0137",
                "clean_hygiene_ok": True,
                "dirty_hygiene_ok": False,
                "planted_unaltered": clean["direct_unit_count"],
                "planted_altered": planted["direct_unit_count"],
                "diff_fired": planted["direct_unit_count"] != clean["direct_unit_count"]
                or plant_key == SPEC_FILE
                and planted["direct_unit_count"] != clean["direct_unit_count"],
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:ADV-0137-probe1 hygiene both-states and planted diff fired")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
