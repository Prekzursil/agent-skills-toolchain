#!/usr/bin/env python3
"""Probe 1: re-apply the published rubric blind and check calibration counts.

Recomputes GEM verdicts from feature cards only. Requires:
  * 10 Tier-1 rows and 5 Tier-3 rows
  * disagreement count > 0 (perfect agreement is the suspicious case)
  * zero Tier-3 rows scored as GEM
  * published rubric sha256 matches the artifact
  * author scorer and independent scorer agree on every row
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import call_sheet as CS  # noqa: E402
import rubric as R  # noqa: E402
import score as S  # noqa: E402

ART = REPO / "command-center/research/RES-0108.json"
PUB = HERE / "fixtures/rubric.published.json"
SENTINEL = (
    "SUCCESS:RES-0108 in the receipt AND a pre-published rubric with a "
    "blind agreement count on Tier-1 rows and a Tier-3 negative control"
)


def fail(msg: str) -> int:
    print(f"FAILED:RES-0108-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact-absent")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")

    published = json.loads(PUB.read_text(encoding="utf-8"))
    live_sha = R.published_sha256(published)
    rec_sha = str((doc.get("rubric") or {}).get("published_sha256") or "")
    if live_sha != rec_sha:
        return fail(f"rubric-sha-mismatch live={live_sha} rec={rec_sha}")
    if live_sha != R.published_sha256(R.RUBRIC):
        return fail("published-file-diverged-from-module")

    t1, t3 = CS.TIER1, CS.TIER3
    if len(t1) != 10 or len(t3) != 5:
        return fail(f"row-counts t1={len(t1)} t3={len(t3)}")

    agree = disagree = 0
    t3_gem = 0
    by_id = {m["id"]: m for m in (doc.get("measurements") or []) if isinstance(m, dict)}
    for row in t1:
        a = S.apply(row)
        b = S.apply_independent(row)
        if a["gem"] != b["gem"]:
            return fail(f"scorer-split {row['id']} author={a['gem']} indep={b['gem']}")
        want_gem = S.expected_call_sheet_gem(row["call_sheet_grade"])
        # Agreement is "rubric GEM iff call-sheet TIER-1".
        if a["gem"] == want_gem:
            agree += 1
        else:
            disagree += 1
        rec = by_id.get(row["id"]) or {}
        if rec.get("gem") is not a["gem"] or rec.get("agree") is not (a["gem"] == want_gem):
            return fail(f"artifact-drift {row['id']}")
        print(
            f"{row['id']} gem={a['gem']} grade={row['call_sheet_grade']} "
            f"agree={a['gem'] == want_gem}"
        )

    for row in t3:
        a = S.apply(row)
        b = S.apply_independent(row)
        if a["gem"] != b["gem"]:
            return fail(f"scorer-split {row['id']}")
        if a["gem"]:
            t3_gem += 1
        rec = by_id.get(row["id"]) or {}
        if rec.get("gem") is not False:
            return fail(f"artifact-t3-gem {row['id']}")
        print(f"{row['id']} gem={a['gem']} grade={row['call_sheet_grade']}")

    cal = doc.get("calibration") or {}
    if cal.get("tier1_agree") != agree or cal.get("tier1_disagree") != disagree:
        return fail(f"count-drift agree={agree} disagree={disagree} cal={cal}")
    if cal.get("tier3_scored_as_gem") != t3_gem:
        return fail(f"t3-gem-drift {t3_gem}")
    if disagree < 1:
        return fail("perfect-tier1-agreement-suspicious")
    if t3_gem != 0:
        return fail(f"tier3-negative-control-failed gems={t3_gem}")
    if not doc.get("methodology", {}).get("published_before_application") is True:
        return fail("published-before-application-not-true")

    print(
        f"tier1 agree={agree} disagree={disagree} "
        f"tier3_gem={t3_gem} rubric_sha={live_sha}"
    )
    print("SUCCESS:RES-0108-probe1 blind agreement and Tier-3 negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
