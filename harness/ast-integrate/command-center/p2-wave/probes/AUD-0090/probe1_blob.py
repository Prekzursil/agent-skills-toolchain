#!/usr/bin/env python3
"""Probe 1: ruff/semgrep/bandit at pinned versions against git cat-file blob bytes.

Does not convert LF to CRLF and does not treat worktree bytes as the blob.
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
    print(f"FAILED:{UID}-probe1 {msg}")
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
    if str(doc.get("report_kind") or "") != "audit-metric-baseline":
        return "artifact report_kind is not audit-metric-baseline"
    rec = ((doc.get("observations") or {}).get("control") or {})
    live = ((snap.get("comparable") or {}).get("control") or {})
    if rec.get("counts_differ") is not True:
        return "artifact control.counts_differ is not true"
    if live.get("pass") is not True:
        return "live control did not pass"
    rec_blob = rec.get("counts_blob") or {}
    live_blob = live.get("counts_blob") or {}
    if rec_blob != live_blob:
        return f"artifact blob counts {rec_blob} != live {live_blob}"
    per_rule = ((doc.get("observations") or {}).get("per_rule") or {}).get("blob") or {}
    live_rule = ((snap.get("comparable") or {}).get("per_rule") or {}).get("blob") or {}
    if per_rule != live_rule:
        return "artifact blob per_rule drifted from live cat-file scan"
    return None


def main() -> int:
    comparable = E.comparable_scan()
    snap = {"comparable": comparable}
    ctl = comparable["control"]
    blob = comparable["blob"]
    trees = comparable["trees"]
    if any(trees.get(k) for k in ("used_git_add", "used_git_commit", "used_git_archive")):
        return fail("fixture git used a forbidden command")
    if ctl.get("used_git_archive") is True:
        return fail("git archive was used")
    if not ctl.get("blob_is_lf"):
        return fail("cat-file blob is not LF")
    if cr := ctl.get("blob_cr"):
        return fail(f"cat-file blob has CR count {cr}")
    if not ctl.get("pass"):
        return fail(f"control failed blob={ctl.get('counts_blob')} win={ctl.get('counts_windows')}")
    err = check_artifact(snap)
    if err:
        return fail(err)
    out = {
        "probe": "probe1-blob-cat-file",
        "unit_id": UID,
        "method": "git cat-file -p HEAD:<path>",
        "used_git_archive": False,
        "blob_is_lf": ctl["blob_is_lf"],
        "counts_blob": ctl["counts_blob"],
        "per_rule_blob": snap["comparable"]["per_rule"]["blob"],
        "ruff_parse_ok": blob["ruff"]["parse_ok"],
        "semgrep_parse_ok": blob["semgrep"]["parse_ok"],
        "bandit_parse_ok": blob["bandit"]["parse_ok"],
        "pins": {
            "ruff": E.RUFF_PIN,
            "semgrep": E.SEMGREP_PIN,
            "bandit": E.BANDIT_PIN,
        },
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"blob_lf={ctl['blob_is_lf']} counts={ctl['counts_blob']} "
        f"per_rule={snap['comparable']['per_rule']['blob']}"
    )
    print("SUCCESS:AUD-0090-probe1 pinned tools against git cat-file blob bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
