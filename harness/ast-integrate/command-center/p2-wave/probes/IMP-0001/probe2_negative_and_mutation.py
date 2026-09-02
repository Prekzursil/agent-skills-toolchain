#!/usr/bin/env python3
"""Probe 2: planted .git/config + 40MB log must be named and refused;
widening one include glob to ** must turn the live checks red.
Independent reviewer: re-derive payload from Claude plugin layout dirs.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))

import payload_allowlist as pa  # noqa: E402

ART = REPO / "command-center" / "receipts" / "IMP-0001.json"
PACK = PLUGIN / "pack.py"


def main() -> int:
    doc = pa.load_allowlist()
    derived = pa.independent_plugin_layout_paths(REPO)
    source, census = pa.listed_paths(REPO)
    authored = pa.expand(census, doc, matcher="a")
    if derived != authored:
        print(
            json.dumps(
                {
                    "only_authored": sorted(set(authored) - set(derived)),
                    "only_derived": sorted(set(derived) - set(authored)),
                },
                indent=2,
            )
        )
        print("FAILED:IMP-0001-probe2 independent layout derivation disagrees")
        return 1

    mutant = deepcopy(doc)
    mutant["include"][0]["glob"] = "**"
    mutation_red = bool(pa.unbounded_include_globs(mutant)) and any(
        p.startswith("command-center/")
        for p in census
        if pa.matches_any_a(p, pa.include_globs(mutant))
    )
    live_unbounded = pa.unbounded_include_globs(doc)
    if live_unbounded or not mutation_red:
        print(
            json.dumps(
                {"live_unbounded": live_unbounded, "mutation_red": mutation_red},
                sort_keys=True,
            )
        )
        print("FAILED:IMP-0001-probe2 mutation control")
        return 1

    with tempfile.TemporaryDirectory(prefix="imp0001-p2-") as tmp:
        staging = Path(tmp) / "staging"
        staging.mkdir()
        for rel, src in pa.select_pairs(REPO, doc):
            dest = staging / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
        pa.plant_negative_staging(staging)
        archive = Path(tmp) / "nope.tar"
        proc = subprocess.run(
            [
                sys.executable,
                "-B",
                str(PACK),
                "--staging",
                str(staging),
                "--output",
                str(archive),
            ],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        text = ((proc.stdout or "") + (proc.stderr or "")).strip()
        named_git = ".git/config" in text
        named_log = "planted-40mb.log" in text
        refused = proc.returncode != 0
        wrote = archive.is_file() and archive.stat().st_size > 0
        if not (refused and named_git and named_log and not wrote):
            print(text[-2000:])
            print("FAILED:IMP-0001-probe2 packer did not refuse naming both planted paths")
            return 1

        clean = Path(tmp) / "clean"
        clean.mkdir()
        for rel, src in pa.select_pairs(REPO, doc):
            dest = clean / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
        good = Path(tmp) / "ok.tar"
        proc2 = subprocess.run(
            [
                sys.executable,
                "-B",
                str(PACK),
                "--staging",
                str(clean),
                "--output",
                str(good),
            ],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        if proc2.returncode != 0:
            print(proc2.stdout, proc2.stderr)
            print("FAILED:IMP-0001-probe2 clean staging was refused")
            return 1

    if ART.is_file():
        body_text = ART.read_text(encoding="utf-8")
        if "SUCCESS:IMP-0001" not in body_text:
            print("FAILED:IMP-0001-probe2 receipt sentinel absent")
            return 1
        body = json.loads(body_text)
        if str(body.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            print("FAILED:IMP-0001-probe2 receipt blocked")
            return 1

    print(
        json.dumps(
            {
                "probe": "probe2-negative-and-mutation",
                "unit_id": "IMP-0001",
                "census_source": source,
                "named_git_config": named_git,
                "named_40mb_log": named_log,
                "packer_refused": refused,
                "did_not_emit": not wrote,
                "clean_staging_packed": proc2.returncode == 0,
                "mutation_widen_starstar_goes_red": mutation_red,
                "live_include_unbounded": False,
                "independent_layout_match": True,
                "derived_count": len(derived),
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:IMP-0001-probe2 packer named both planted paths; mutation goes red")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
