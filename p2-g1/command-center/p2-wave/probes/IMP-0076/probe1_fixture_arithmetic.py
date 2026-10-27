#!/usr/bin/env python3
"""IMP-0076 probe1 (source): trust levels equal hand-derived millipoint arithmetic.

Computes trust for every fixture publisher via the real implementation and
requires level + per-component millipoints to equal the hand-derived values
frozen in the fixture file.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W / "tools"))

from marketplace.trust_levels import compute_publisher_trust, component_map  # noqa: E402

FIX = json.loads((W / "tools/marketplace/fixtures/trust_publishers.json").read_text(encoding="utf-8"))
RESULTS = {"probe": "probe1-fixture-arithmetic", "unit_id": "IMP-0076", "rows": []}
FAILS = []


def record(cid, ok, detail=""):
    RESULTS["rows"].append({"id": cid, "ok": bool(ok), "detail": str(detail)[:200]})
    if not ok:
        FAILS.append(cid + " " + str(detail)[:120])


MP_FIELDS = {
    "signed_mp": "signed_releases",
    "conformance_mp": "conformance_pass_rate",
    "advisory_mp": "advisory_response_time",
    "provenance_mp": "provenance_completeness",
}

for pub in FIX["publishers"]:
    got = compute_publisher_trust(pub["record"])
    hand = pub["hand_derived"]
    cid = pub["id"]
    record(cid + "-level", got.level == hand["level"],
           f"got {got.level} want {hand['level']}")
    if hand["score_millipoints"] is None:
        record(cid + "-score-null", got.score_millipoints is None, str(got.score_millipoints))
    else:
        record(cid + "-score", got.score_millipoints == hand["score_millipoints"],
               f"got {got.score_millipoints} want {hand['score_millipoints']}")
    comps = component_map(got)
    for hf, comp_name in MP_FIELDS.items():
        want = hand.get(hf)
        got_mp = comps[comp_name].millipoints
        if want is None:
            record(f"{cid}-{hf}-null", got_mp is None, f"{comp_name}={got_mp}")
        else:
            record(f"{cid}-{hf}", got_mp == want, f"{comp_name} got {got_mp} want {want}")
    # scoring_input_sha256 covers ONLY the scoring keys (canonical json, sorted).
    import hashlib
    payload = {k: pub["record"].get(k) for k in (
        "releases_signed", "releases_unsigned", "published_version_count",
        "conformance_passes", "conformance_runs", "advisory_count",
        "advisory_median_response_hours", "provenance_complete_versions")}
    payload["formula_version"] = "tl-v1-millipoints-10000"
    want_sha = hashlib.sha256(json.dumps(
        payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    record(cid + "-sha", got.scoring_input_sha256 == want_sha,
           f"{got.scoring_input_sha256[:12]} vs {want_sha[:12]}")

RESULTS.update({"n": len(RESULTS["rows"]), "ok": sum(r["ok"] for r in RESULTS["rows"]),
                "pass": not FAILS, "failures": FAILS})
print("RESULT:" + json.dumps(RESULTS, sort_keys=True))
if FAILS:
    print("FAILED:IMP-0076-probe1 " + "; ".join(FAILS[:6]))
    raise SystemExit(1)
print("SUCCESS:IMP-0076-probe1 fixture arithmetic matches hand-derived millipoints")
