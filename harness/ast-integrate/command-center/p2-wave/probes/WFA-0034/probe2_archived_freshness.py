#!/usr/bin/env python3
"""Probe 2: archived disposition flag, prose diffs, API-vs-git freshness.

Re-reads git ref HEAD (signal B) and API archived/push fields (signal A)
independently of probe 1's NOT-CHECKED path.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import git_refs as G  # noqa: E402
import scenario as S  # noqa: E402
from engine import (  # noqa: E402
    archived_adopt_risk_present,
    live_active_not_flagged,
)
from git_refs import normalize_iso  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0034-extract-maintenance-state.json"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0034-probe2 {msg}")
    return 1


def load_api(name: str) -> dict:
    path = HERE / "fixtures" / "api" / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:WFA-0034" not in json.dumps(doc):
        return fail("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")

    live = S.run_extraction()
    if not live.get("pass"):
        return fail("live extraction did not pass")
    if not archived_adopt_risk_present(live):
        return fail("archived ADOPT-AS-IS not flagged")
    if not live_active_not_flagged(live):
        return fail("live-active incorrectly flagged")

    by_id = {r["candidate_id"]: r for r in live["rows"]}

    git_stale = G.read_head(HERE / "fixtures" / "git-repos" / "stale-api")
    if not git_stale:
        return fail("git HEAD unreadable for stale-api")
    git_day = normalize_iso(git_stale["committer_iso"])[:10]
    api_stale = load_api("stale-api")
    api_day = normalize_iso(str(api_stale["pushed_at"]))[:10]
    if git_day == api_day:
        return fail("planted API/git divergence missing")
    stale_row = by_id["wf-ext-stale-api"]
    finding = stale_row.get("freshness_finding") or {}
    if finding.get("kind") != "api-stale-vs-git-head":
        return fail(f"freshness kind={finding.get('kind')}")
    if (stale_row.get("measured") or {}).get("git_head_date", "")[:10] != git_day:
        return fail("artifact/live git_head_date != git ref")
    if (stale_row.get("measured") or {}).get("api_last_push", "")[:10] != api_day:
        return fail("live api_last_push != API JSON")

    api_arch = load_api("archived-adopt")
    if api_arch.get("archived") is not True:
        return fail("API fixture archived-adopt not archived")
    git_arch = G.read_head(HERE / "fixtures" / "git-repos" / "archived-adopt")
    if not git_arch:
        return fail("git HEAD unreadable for archived-adopt")

    api_live = load_api("live-active")
    if api_live.get("archived") is not False:
        return fail("API fixture live-active is archived")

    cons = live.get("contradictions") or []
    kinds = {(c.get("candidate_id"), c.get("kind")) for c in cons}
    if ("wf-ext-archived-adopt", "archived-vs-active-prose") not in kinds:
        return fail("missing archived-vs-active-prose contradiction")
    if ("wf-ext-prose-archived-wrong", "prose-archived-vs-measured-live") not in kinds:
        return fail("missing prose-archived-vs-measured-live contradiction")
    if not any(c.get("candidate_id") == "wf-ext-stale-api" for c in cons):
        return fail("stale-api prose date mismatch not listed")

    recs = {r.get("candidate_id"): r for r in (doc.get("records") or [])}
    art_arch = recs.get("wf-ext-archived-adopt") or {}
    if (art_arch.get("disposition_flag") or {}).get("adopt_as_is_risk") is not True:
        return fail("artifact missing archived ADOPT-AS-IS risk flag")
    art_active = recs.get("wf-ext-live-active") or {}
    if art_active.get("disposition_flag") is not None:
        return fail("artifact flagged live-active")
    art_stale = recs.get("wf-ext-stale-api") or {}
    if (art_stale.get("freshness_finding") or {}).get("kind") != "api-stale-vs-git-head":
        return fail("artifact missing API freshness finding")

    art_cons = doc.get("contradictions") or []
    if len(art_cons) != len(cons):
        return fail(f"artifact contradictions {len(art_cons)} != live {len(cons)}")

    both = doc.get("both_states") or {}
    if both.get("archived_adopt_flagged") is not True:
        return fail("artifact both_states archived not flagged")
    if both.get("live_active_not_flagged") is not True:
        return fail("artifact both_states live-active flagged")

    if (doc.get("reviewer") or {}).get("independent") is not True:
        return fail("reviewer not independent")
    if (doc.get("reviewer") or {}).get("verdict") != "PASS":
        return fail("reviewer verdict not PASS")

    out = {
        "probe": "probe2-archived-freshness",
        "unit_id": "WFA-0034",
        "archived_adopt_risk": True,
        "live_active_not_flagged": True,
        "api_vs_git_divergence": True,
        "git_head_date": git_stale["committer_iso"],
        "api_last_push": api_stale["pushed_at"],
        "contradictions": len(cons),
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"archived_flagged=True live_not_flagged=True "
        f"freshness=api-stale-vs-git-head contradictions={len(cons)}"
    )
    print("SUCCESS:WFA-0034-probe2 archived disposition and API vs git HEAD")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
