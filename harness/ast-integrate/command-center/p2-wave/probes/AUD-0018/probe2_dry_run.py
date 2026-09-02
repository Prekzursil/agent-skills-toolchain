#!/usr/bin/env python3
"""Probe 2: dry-run against a scratch fixture pair.

Proves the interpreter is non-destructive (byte-identical fixture before/after)
before trusting the would-touch file list. The line-read is the claim; this
dry-run is the receipt. Never executes scripts/sync-from-live.ps1.
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


def fail(msg: str) -> int:
    print(f"FAILED:{E.UNIT}-probe2 {msg}")
    return 1


def check_artifact(bundle: dict, ctl: dict) -> str | None:
    if not ART.is_file():
        return None
    text = ART.read_text(encoding="utf-8")
    if E.COMPLETION not in text:
        return "artifact completion_sentinel absent"
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return f"artifact self-declared {doc.get('state')}"
    rec = doc.get("dry_run") or {}
    if rec.get("fixture_byte_identical") is not True:
        return "artifact dry_run.fixture_byte_identical is not true"
    rec_ok = "rules/ok.md" in (
        ((rec.get("planted_plans") or {}).get("copy-item-force-verbatim.ps1") or {}).get(
            "would_touch"
        )
        or []
    )
    live_ok = "rules/ok.md" in (
        ((bundle.get("planted_plans") or {}).get("copy-item-force-verbatim.ps1") or {}).get(
            "would_touch"
        )
        or []
    )
    if rec_ok != live_ok:
        return "would_touch rules/ok.md drift vs artifact"
    if not (doc.get("dry_control") or {}).get("pass"):
        return "artifact dry_control.pass is not true"
    _ = ctl
    return None


def main() -> int:
    bundle = E.dry_run_bundle()
    ctl = E.control_dry_run(bundle)
    if not ctl.get("pass"):
        return fail(f"dry-run controls failed {ctl.get('failed')}")
    if not bundle.get("fixture_byte_identical"):
        return fail("fixture mutated during dry-run")
    err = check_artifact(bundle, ctl)
    if err:
        return fail(err)
    vplan = (bundle.get("planted_plans") or {}).get("copy-item-force-verbatim.ps1") or {}
    payload = {
        "probe": "probe2-dry-run",
        "unit_id": E.UNIT,
        "method": "interpreted WhatIf over fixtures/trees; isolated clone for destructive mutant",
        "command": E.P2,
        "fixture_byte_identical": bundle["fixture_byte_identical"],
        "would_touch_verbatim": vplan.get("would_touch"),
        "would_touch_count": vplan.get("would_touch_count"),
        "skipped_by_guards": bundle.get("skipped_by_guards"),
        "nested_repo_skipped": bundle.get("nested_repo_skipped"),
        "vendored_skipped": bundle.get("vendored_skipped"),
        "repo_owned_skipped": bundle.get("repo_owned_skipped"),
        "destructive_mutant": bundle.get("destructive_mutant"),
        "never_executed_live_sync_from_live": bundle.get(
            "never_executed_live_sync_from_live"
        ),
        "control": ctl["checks"],
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"byte_identical={bundle['fixture_byte_identical']} "
        f"would_touch={vplan.get('would_touch_count')} "
        f"skipped={len(bundle.get('skipped_by_guards') or [])} "
        f"mutant_changed={((bundle.get('destructive_mutant') or {}).get('dest_rules_ok_changed'))}"
    )
    print("SUCCESS:AUD-0018-probe2 dry-run non-destructive would-touch receipt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
