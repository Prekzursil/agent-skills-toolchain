#!/usr/bin/env python3
"""Probe 2: known-gated suite joins to the gated side (control + both-states)."""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from join import (  # noqa: E402
    CWD_GATED,
    KNOWN_GATED,
    KNOWN_UNGATED,
    REPO,
    assert_every_suite_classified,
    assert_known_gated_joined,
    assert_ungated_listed_by_path,
    census,
    control_census,
)

ART = REPO / "command-center" / "receipts" / "TST-0124.json"
SENTINEL = "SUCCESS:TST-0124"
MUTANT_QUALITY = """name: quality
on:
  push:
jobs:
  tests:
    name: gate-known-gated-suite
    runs-on: ubuntu-latest
    steps:
      - name: run known gated suite
        run: echo no-pytest-here
"""


def fail(msg: str) -> int:
    print(f"FAILED:TST-0124-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    ctrl = control_census()
    try:
        assert_every_suite_classified(ctrl)
        assert_ungated_listed_by_path(ctrl)
        assert_known_gated_joined(ctrl)
    except AssertionError as exc:
        return fail(str(exc))

    by = {r["suite"]: r for r in ctrl["join"]}
    if KNOWN_GATED not in by or by[KNOWN_GATED]["classification"] != "GATED":
        return fail("known gated suite not on gated side")
    if not any(
        g["workflow"].endswith("quality.yml") for g in by[KNOWN_GATED]["gates"]
    ):
        return fail("known gated suite not joined through quality.yml")

    with tempfile.TemporaryDirectory(prefix="tst0124-mutant-") as tmp:
        mutant_root = Path(tmp) / "estate"
        shutil.copytree(HERE / "fixtures" / "control-estate", mutant_root)
        q = mutant_root / ".github" / "workflows" / "quality.yml"
        q.write_text(MUTANT_QUALITY, encoding="utf-8")
        broken = census(mutant_root)
        bmap = {r["suite"]: r for r in broken["join"]}
        if KNOWN_GATED not in bmap:
            return fail("mutant lost known gated suite")
        if bmap[KNOWN_GATED]["classification"] != "UNGATED":
            return fail(
                "mutant still GATED after pytest removed from quality.yml "
                f"{bmap[KNOWN_GATED]}"
            )
        if CWD_GATED in bmap and bmap[CWD_GATED]["classification"] != "UNGATED":
            return fail("cwd gated suite still GATED after quality.yml stripped")
        if bmap[KNOWN_UNGATED]["classification"] != "UNGATED":
            return fail("ungated control flipped on mutant")

    art_ctrl = doc.get("known_gated_control") or {}
    if art_ctrl.get("known_gated_classification") != "GATED":
        return fail("receipt control missing GATED known suite")
    if art_ctrl.get("known_ungated_classification") != "UNGATED":
        return fail("receipt control missing UNGATED orphan")

    summary = {
        "probe": "probe2-known-gated-join",
        "unit_id": "TST-0124",
        "known_gated_suite": KNOWN_GATED,
        "known_gated_classification": "GATED",
        "known_gated_gates": by[KNOWN_GATED]["gates"],
        "cwd_gated_classification": by.get(CWD_GATED, {}).get("classification"),
        "known_ungated_classification": by[KNOWN_UNGATED]["classification"],
        "mutant_quality_without_pytest_ungates": True,
        "pass": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"known_gated={KNOWN_GATED}:GATED cwd={CWD_GATED}:"
        f"{by.get(CWD_GATED, {}).get('classification')} "
        f"orphan={KNOWN_UNGATED}:UNGATED mutant_ungates=True"
    )
    print("SUCCESS:TST-0124-probe2 known-gated suite joined; mutant ungates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
