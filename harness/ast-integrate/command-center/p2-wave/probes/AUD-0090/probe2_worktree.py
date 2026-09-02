#!/usr/bin/env python3
"""Probe 2: same pinned tools against the Windows CRLF worktree analogue.

Records BOTH blob and worktree counts. Divergence on the planted
CRLF-sensitive file is required; identical counts everywhere means blob
extraction silently returned worktree bytes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402

ART = REPO / E.OUT_REL
UID = E.UID


def fail(msg: str) -> int:
    print(f"FAILED:{UID}-probe2 {msg}")
    return 1


def check_artifact(snap: dict) -> str | None:
    if not ART.is_file():
        return None
    text = ART.read_text(encoding="utf-8")
    if E.COMPLETION_SENTINEL not in text:
        return "artifact completion_sentinel absent"
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return f"artifact self-declared {doc.get('state')}"
    rec = ((doc.get("observations") or {}).get("control") or {})
    live = ((snap.get("comparable") or {}).get("control") or {})
    if rec.get("counts_differ") is not True or live.get("counts_differ") is not True:
        return "both-counts control did not record a divergence"
    rec_win = rec.get("counts_windows") or {}
    live_win = live.get("counts_windows") or {}
    if rec_win != live_win:
        return f"artifact windows counts {rec_win} != live {live_win}"
    rec_blob = rec.get("counts_blob") or {}
    if rec_blob == rec_win:
        return "artifact recorded identical blob and windows counts"
    per_rule = (doc.get("observations") or {}).get("per_rule") or {}
    live_rule = (snap.get("comparable") or {}).get("per_rule") or {}
    if per_rule.get("windows_worktree") != live_rule.get("windows_worktree"):
        return "artifact windows per_rule drifted from live analogue scan"
    if per_rule.get("blob") != live_rule.get("blob"):
        return "artifact blob per_rule drifted (probe 2 records BOTH counts)"
    return None


def main() -> int:
    comparable = E.comparable_scan()
    snap = {"comparable": comparable}
    ctl = comparable["control"]
    if ctl.get("used_git_archive") is True:
        return fail("git archive was used")
    if not ctl.get("windows_is_crlf"):
        return fail("windows analogue is not CRLF")
    if not ctl.get("blob_is_lf"):
        return fail("blob side is not LF")
    if not ctl.get("counts_differ"):
        return fail(
            "identical counts on the CRLF-sensitive file; blob extraction "
            f"may have returned worktree bytes blob={ctl.get('counts_blob')} "
            f"windows={ctl.get('counts_windows')}"
        )
    if not ctl.get("pass"):
        return fail("control did not pass")
    err = check_artifact(snap)
    if err:
        return fail(err)
    out = {
        "probe": "probe2-windows-worktree-analogue",
        "unit_id": UID,
        "method": "LF->CRLF analogue of git cat-file bytes (core.autocrlf=true)",
        "used_git_archive": False,
        "windows_is_crlf": ctl["windows_is_crlf"],
        "counts_blob": ctl["counts_blob"],
        "counts_windows": ctl["counts_windows"],
        "counts_differ": ctl["counts_differ"],
        "per_rule_blob": snap["comparable"]["per_rule"]["blob"],
        "per_rule_windows": snap["comparable"]["per_rule"]["windows_worktree"],
        "both_counts_recorded": True,
        "pins": {
            "ruff": E.RUFF_PIN,
            "semgrep": E.SEMGREP_PIN,
            "bandit": E.BANDIT_PIN,
        },
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"differ={ctl['counts_differ']} blob={ctl['counts_blob']} "
        f"windows={ctl['counts_windows']}"
    )
    print("SUCCESS:AUD-0090-probe2 both blob and Windows-analogue counts recorded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
