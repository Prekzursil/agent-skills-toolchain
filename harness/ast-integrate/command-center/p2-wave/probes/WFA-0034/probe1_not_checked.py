#!/usr/bin/env python3
"""Probe 1: unreachable metadata is NOT-CHECKED and never inferred from prose.

Mechanically independent of probe 2 (archived flag / API-vs-git freshness).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import scenario as S  # noqa: E402
from engine import mutant_infer_unreachable, prose_leaked_into_measured  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0034-extract-maintenance-state.json"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0034-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "WFA-0034":
        return fail(f"unit_id {doc.get('unit_id')}")
    text = json.dumps(doc)
    if "SUCCESS:WFA-0034" not in text:
        return fail("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")

    live = S.run_extraction()
    if not live.get("pass"):
        return fail("live extraction did not pass")
    controls = S.negative_controls()
    if not controls.get("pass"):
        return fail("negative controls did not fire")

    by_id = {r["candidate_id"]: r for r in live["rows"]}
    unr = by_id.get("wf-ext-unreachable") or {}
    if unr.get("status") != "NOT-CHECKED":
        return fail(f"unreachable status={unr.get('status')}")
    if unr.get("inferred_from_prose") is True:
        return fail("unreachable inferred_from_prose true")
    if unr.get("last_commit_date") is not None:
        return fail("unreachable last_commit_date copied")
    if unr.get("archived") is not None:
        return fail("unreachable archived copied")
    if unr.get("open_issue_velocity") is not None:
        return fail("unreachable velocity copied")
    if unr.get("latest_release") is not None:
        return fail("unreachable release copied")
    if prose_leaked_into_measured(unr):
        return fail("prose leaked into NOT-CHECKED measured fields")
    prose = str(unr.get("discovery_prose") or "")
    if "2024-12-01" not in prose:
        return fail("fixture prose missing 2024-12-01 (control needle)")
    if "2024-12-01" in json.dumps(unr.get("measured") or {}):
        return fail("prose date present in measured object")

    local = by_id.get("wf-local-only") or {}
    if local.get("status") != "SKIPPED-LOCAL":
        return fail(f"local-only status={local.get('status')}")

    inferred = mutant_infer_unreachable(*_candidates_transport())
    leaked_row = next(
        r for r in inferred["rows"] if r["candidate_id"] == "wf-ext-unreachable"
    )
    if not prose_leaked_into_measured(leaked_row):
        return fail("infer-from-prose mutant was not detected")
    if leaked_row.get("last_commit_date") is None:
        return fail("mutant did not plant a prose date")

    recs = {r.get("candidate_id"): r for r in (doc.get("records") or [])}
    art_unr = recs.get("wf-ext-unreachable") or {}
    if art_unr.get("status") != "NOT-CHECKED":
        return fail("artifact unreachable not NOT-CHECKED")
    if art_unr.get("last_commit_date") is not None:
        return fail("artifact copied prose last_commit_date")
    if art_unr.get("inferred_from_prose") is True:
        return fail("artifact inferred_from_prose")

    src = doc.get("source_probe") or {}
    ver = doc.get("verifier_probe") or {}
    if not src or not ver:
        return fail("empty source_probe or verifier_probe")
    if json.dumps(src, sort_keys=True) == json.dumps(ver, sort_keys=True):
        return fail("source_probe identical to verifier_probe")

    out = {
        "probe": "probe1-not-checked",
        "unit_id": "WFA-0034",
        "unreachable_status": "NOT-CHECKED",
        "inferred_from_prose": False,
        "prose_leak": False,
        "mutant_detected": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "unreachable=NOT-CHECKED inferred=False local=SKIPPED-LOCAL "
        "infer-mutant-fired=True"
    )
    print("SUCCESS:WFA-0034-probe1 unreachable NOT-CHECKED never inferred from prose")
    return 0


def _candidates_transport():
    cands, _meta = S.load_candidates()
    from transport import FixtureTransport

    return cands, FixtureTransport(HERE)


if __name__ == "__main__":
    raise SystemExit(main())
