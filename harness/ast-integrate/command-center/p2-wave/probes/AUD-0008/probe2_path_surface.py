#!/usr/bin/env python3
"""Probe 2: changed-path surface vs catalog unit ids. Author identity is ignored.

Cross-vendor Codex reviewer re-runs ONLY this probe.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402

OUT = REPO / "command-center/audit/AUD-0008-commit-authorship-integrity.json"
SENTINEL = E.SENTINEL


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0008-probe2 {msg}")
    return 1


def main() -> int:
    unit_ids = E.load_unit_ids()
    if "AUD-0008" not in unit_ids:
        return fail("catalog missing AUD-0008")
    ctl = E.build_path_fixture(unit_ids)
    if not ctl["pass"]:
        return fail(f"path fixture failed {json.dumps(ctl, sort_keys=True)}")
    agent = ctl["forged_agent_identity_commit"]
    owner = ctl["forged_owner_identity_commit"]
    if agent["path_class"] != "NO-UNIT-SURFACE":
        return fail("Claude-authored README commit must be NO-UNIT-SURFACE by paths")
    if owner["path_class"] != "UNIT-CORROBORATED":
        return fail("owner-authored AUD-0008 path must be UNIT-CORROBORATED by paths")
    if "AUD-0008" not in owner["catalog_unit_ids_on_paths"]:
        return fail("AUD-0008 not recovered from changed paths")
    if agent["author_name"] == "Claude" and owner["author_name"] == "Prekzursil":
        # Identity labels are opposite the path verdict. That is the point.
        pass
    else:
        return fail("fixture authors not as planted")

    live = E.census_live(unit_ids)

    if not OUT.is_file() or OUT.stat().st_size <= 0:
        return fail("artifact missing")
    text = OUT.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        return fail("catalog sentinel absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"artifact self-declared {doc.get('state')}")
    art_ctl = doc.get("probe2_control") or doc.get("probe2_control") or {}
    if art_ctl.get("pass") is not True:
        return fail("artifact probe2_control.pass is not true")
    if art_ctl.get("identity_ignored_for_verdict") is not True:
        return fail("artifact did not declare identity ignored for probe 2")
    instrument = str(doc.get("probe2_instrument") or doc.get("probe2_instrument") or "")
    if "name-only" not in instrument and "diff-tree" not in instrument:
        return fail("artifact did not record diff-tree/name-only as probe 2")

    payload = {
        "probe": "probe2-path-surface",
        "unit_id": "AUD-0008",
        "reviewer_id": "AUD-0008-probe2-codex-path-surface",
        "vendor": "openai",
        "instrument": "git diff-tree --name-only matched to catalog unit ids",
        "identity_ignored": True,
        "control_pass": True,
        "forged_claude_readme_class": agent["path_class"],
        "forged_owner_unit_path_class": owner["path_class"],
        "live_unit_corroborated_commits": sum(
            int(r.get("unit_corroborated_commit_count") or r.get("unit_corroborated_commit_count") or 0)
            for r in live["repos"]
        ),
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "SUCCESS:AUD-0008-probe2 path surface distinguishes unit work; "
        "author identity ignored"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
