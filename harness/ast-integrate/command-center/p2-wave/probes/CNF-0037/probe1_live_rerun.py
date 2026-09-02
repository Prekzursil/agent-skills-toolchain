#!/usr/bin/env python3
"""Probe 1: re-extract the live corpus and re-run fixture commands against the artifact."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import extract as X  # noqa: E402
import runner as R  # noqa: E402
import schema_check as S  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0037-doc-command-conformance.json"
SENTINEL_PREFIX = "SUCCESS:CNF-0037"


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0037-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL_PREFIX not in text:
        return fail("sentinel absent")
    errs = S.error_list(doc)
    if errs:
        return fail(f"schema {errs[0]}")
    for g in S.GARBAGE:
        if not S.error_list(g):
            return fail("schema accepted garbage")
    extracted = X.extract_corpus(REPO, include_fixtures=True)
    recorded = X.recorded_commands(doc)
    omitted = X.silently_omitted(extracted, recorded)
    if omitted:
        return fail(f"silently omitted {omitted!r}")
    if len(extracted) != len(recorded):
        return fail(f"count extracted={len(extracted)} recorded={len(recorded)}")
    live_keys = {X.command_key(e) for e in extracted}
    rec_keys = {
        X.command_key(
            {
                "source_path": r.get("source_path"),
                "source_line": r.get("source_line"),
                "invocation": r.get("verbatim_invocation"),
            }
        )
        for r in recorded
    }
    if live_keys != rec_keys:
        return fail(
            f"key mismatch extra={sorted(rec_keys - live_keys)[:3]} "
            f"missing={sorted(live_keys - rec_keys)[:3]}"
        )
    fixtures = [
        r
        for r in extracted
        if str(r.get("source_path") or "").startswith(
            "command-center/p2-wave/probes/CNF-0037/fixtures/"
        )
    ]
    rerun = R.execute_all(fixtures, REPO, timeout=20)
    by_id = {r["id"]: r for r in recorded}
    for live in rerun:
        rec = by_id.get(live["id"])
        if rec is None:
            return fail(f"fixture {live['id']} absent from artifact")
        if rec.get("outcome") != live.get("outcome"):
            return fail(
                f"outcome drift {live['id']} artifact={rec.get('outcome')} live={live.get('outcome')}"
            )
        if live.get("outcome") == "DIFF":
            recomputed = R.output_diff(
                live.get("documented_output") or "", live.get("actual_output") or ""
            )
            if recomputed != (live.get("diff") or ""):
                return fail(f"diff not recomputable {live['id']}")
            art_diff = rec.get("diff") or ""
            if recomputed != art_diff:
                return fail(f"artifact diff != live diff {live['id']}")
    view = S.report_view(doc)
    cov = view.get("coverage") or doc.get("coverage") or {}
    if int(cov.get("silently_omitted", 1)) != 0:
        return fail("coverage.silently_omitted != 0")
    ans = view.get("answer") or doc.get("answer") or {}
    print(
        json.dumps(
            {
                "extracted": len(extracted),
                "recorded": len(recorded),
                "fixture_rerun": len(rerun),
                "omitted": 0,
                "do_not_exist_or_fail_or_differ": ans.get("do_not_exist_or_fail_or_differ"),
                "python_on_path": (view.get("environment") or {}).get("python_on_path"),
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:CNF-0037-probe1 live re-extract and fixture re-run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
