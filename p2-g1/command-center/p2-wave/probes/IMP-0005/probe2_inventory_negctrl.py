#!/usr/bin/env python3
"""IMP-0005 probe2: inventory diff + negative controls + tautology review.

Rebuilt 2026-10-26 (shard-6 wave-4 resume): re-derives the receipt's claims
live. Controls:
  C1 added/removed/grown classification is exact on the inventory fixtures and
     the emitted inventory validates against payload-inventory.schema.json.
  C2 known-broken fixture (incompressible 512KiB blob) fires the derived
     max_bytes ceiling; the pristine previous release stays silent (both states).
  C3 tautology guard: raising the ceiling above the bloated fixture flips the
     verdict green -- proving the red came from the measurement, not from a
     ceiling copied from the artifact size.
  C4 detector control: a truncated zip must raise DetectorFailure.
  C5 the two required test files run green from the live tree.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))

import jsonschema  # noqa: E402

import fixtures as fx  # noqa: E402
from archive_census import DetectorFailure, census  # noqa: E402
from inventory_diff import diff_archives  # noqa: E402
from size_budget import Budget, check_archive, derive_budget  # noqa: E402

SCHEMA = json.loads(
    (PLUGIN / "schema" / "payload-inventory.schema.json").read_text(encoding="utf-8")
)


def main() -> int:
    facts: dict = {"unit_id": "IMP-0005", "probe": "probe2-inventory-negctrl"}
    checks: list[dict] = []

    def chk(name: str, ok: bool) -> bool:
        checks.append({"check": name, "ok": bool(ok)})
        return bool(ok)

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        # C1: inventory diff classification + schema validation.
        prev = fx.inventory_previous_zip(tmp / "inv-prev.zip")
        curr = fx.inventory_current_zip(tmp / "inv-curr.zip")
        inv = diff_archives(prev, curr)
        jsonschema.validate(inv, SCHEMA)
        added = {r["path"] for r in inv["added"]}
        removed = {r["path"] for r in inv["removed"]}
        grown = {r["path"] for r in inv["grown"]}
        chk("schema_validates_inventory", True)
        chk("added_exact", added == {"new/added.txt"})
        chk("removed_exact", removed == {"drop/gone.txt"})
        chk("grown_exact", grown == {"keep/grow.txt"})

        # C2: known-broken fixture fires max_bytes; good state silent.
        previous = fx.previous_zip(tmp / "prev.zip")
        bloated = fx.over_budget_zip(tmp / "over.zip")
        budget = derive_budget(previous)
        bad = check_archive(bloated, budget)
        good = check_archive(previous, budget)
        chk("bad_state_fires_max_bytes", (not bad["ok"]) and any(v.startswith("max_bytes:") for v in bad["violations"]))
        chk("good_state_silent", good["ok"])

        # C3: ceiling raised above the fixture -> verdict flips green (not tautological).
        raised = Budget(
            max_bytes=bloated.stat().st_size + 1,
            max_file_count=10_000,
            derivation={"mutated": "ceiling-raised-above-fixture"},
        )
        chk("raised_ceiling_flips_green", check_archive(bloated, raised)["ok"])
        chk("derivation_differs_from_current_size", budget.max_bytes != bloated.stat().st_size)

        # C4: truncated zip trips the detector (both-reader disagreement surface).
        truncated = tmp / "trunc.zip"
        truncated.write_bytes(previous.read_bytes()[:40])
        fired = False
        try:
            census(truncated)
        except DetectorFailure:
            fired = True
        chk("truncated_zip_detector_failure", fired)

        facts["inventory"] = {"added": sorted(added), "removed": sorted(removed), "grown": sorted(grown)}
        facts["over_budget_violations"] = bad["violations"]
        facts["derived_budget"] = {"max_bytes": budget.max_bytes, "max_file_count": budget.max_file_count}

    # C5: required test files green from the live tree. Child env is CLEAN
    # (no PYTHONPATH): the measure harness puts the repo's platform/lib on
    # PYTHONPATH, which shadows stdlib platform inside attrs/jsonschema in the
    # child. The tests are self-contained (they insert tools/plugin on
    # sys.path themselves), so a clean env is both correct and the stronger
    # isolation claim.
    child_env = {
        k: v
        for k, v in os.environ.items()
        if k in {"PATH", "SYSTEMROOT", "COMSPEC", "PATHEXT", "TEMP", "TMP", "SYSTEMDRIVE"}
    }
    child_env["PYTHONDONTWRITEBYTECODE"] = "1"
    for label, script in [
        ("test_size_budget", "tools/plugin/tests/test_size_budget.py"),
        ("test_inventory_diff", "tools/plugin/tests/test_inventory_diff.py"),
    ]:
        p = subprocess.run(
            [sys.executable, "-B", str(REPO / script)],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=300,
            env=child_env,
        )
        chk(f"{label}_exit0", p.returncode == 0 and "OK" in (p.stdout or ""))
        facts[f"{label}_tail"] = ((p.stdout or "") + (p.stderr or "")).strip()[-120:]

    facts["checks"] = checks
    facts["all_ok"] = all(c["ok"] for c in checks)
    print(json.dumps(facts, indent=1))
    if not facts["all_ok"]:
        print("FAILED:IMP-0005-probe2 inventory or negative-control check failed")
        return 1
    print("SUCCESS:IMP-0005-probe2 inventory diff exact; negative controls fire; tests green")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
