#!/usr/bin/env python3
"""IMP-0076 probe2 (verifier): gaming strategy against the trust formula.

Reviewer obligation (catalog): propose one gaming strategy against the
formula and report whether it works. Strategy under test: popularity
inflation (downloads/stars/ratings/followers planted at absurd levels) must
not move level, millipoints, component vector, or scoring_input_sha256.
Mechanically different from probe1: this instrument recomputes the weighted
average with an independent interpreter (no trust_levels import) and runs the
attack + the live-detector control.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W / "tools"))

from marketplace.trust_levels import compute_publisher_trust, component_map  # noqa: E402

FIX = json.loads((W / "tools/marketplace/fixtures/trust_publishers.json").read_text(encoding="utf-8"))
PUBS = {p["id"]: p for p in FIX["publishers"]}
RESULTS = {"probe": "probe2-gaming-attack", "unit_id": "IMP-0076"}
FAILS = []


def record(cid, ok, detail=""):
    RESULTS[cid] = {"ok": bool(ok), "detail": str(detail)[:200]}
    if not ok:
        FAILS.append(cid + " " + str(detail)[:120])


def independent_score(record):
    """Interpreter recomputation from the published formula spec."""
    signed = int(record.get("releases_signed") or 0)
    unsigned = int(record.get("releases_unsigned") or 0)
    published = int(record.get("published_version_count") or 0)
    passes = int(record.get("conformance_passes") or 0)
    runs = int(record.get("conformance_runs") or 0)
    adv = int(record.get("advisory_count") or 0)
    median = record.get("advisory_median_response_hours")
    complete = int(record.get("provenance_complete_versions") or 0)
    if published <= 0:
        return None
    total = signed + unsigned
    ratio = (signed * 10000) // total if total else 0
    volume = min(10000, (signed * 10000) // 5) if total else 0
    signed_mp = (ratio * volume) // 10000 if total else 0
    conf_mp = (passes * 10000) // runs if runs > 0 else 0
    if adv <= 0:
        parts = [(30, signed_mp), (30, conf_mp), (20, (complete * 10000) // published)]
    else:
        adv_mp = 0 if median is None else max(0, 10000 - (int(median) * 10000) // 720)
        parts = [(30, signed_mp), (30, conf_mp), (20, adv_mp), (20, (complete * 10000) // published)]
    wsum = sum(w for w, _ in parts)
    return sum(w * s for w, s in parts) // wsum


def level_of(score):
    return "LOW" if score < 4000 else ("MEDIUM" if score < 7000 else "HIGH")


alice = PUBS["alice"]["record"]
baseline = compute_publisher_trust(alice)

# THE ATTACK: absurd popularity inflation.
attacked_record = copy.deepcopy(alice)
attacked_record.update({
    "downloads": 99_999_999, "stars": 1_000_000, "ratings": 5.0,
    "followers": 500_000, "github_stars": 999_999, "weekly_downloads": 10**8,
    "default_trusted": True, "trust_level": "HIGH",
})
attacked = compute_publisher_trust(attacked_record)
record("popularity-inflation-no-effect",
       (attacked.level, attacked.score_millipoints, attacked.scoring_input_sha256)
       == (baseline.level, baseline.score_millipoints, baseline.scoring_input_sha256),
       f"{baseline.level}/{baseline.score_millipoints} -> {attacked.level}/{attacked.score_millipoints}")
record("component-vector-unchanged",
       [c.as_dict() for c in attacked.components] == [c.as_dict() for c in baseline.components])
record("popularity-fields-ignored",
       len(attacked.ignored_popularity_fields) >= 8 and
       all(k.split(".")[-1] in ("downloads", "stars", "ratings", "followers",
                                "github_stars", "weekly_downloads",
                                "default_trusted", "trust_level")
           for k in attacked.ignored_popularity_fields),
       str(attacked.ignored_popularity_fields))

# Independent interpreter agrees on alice and on the attacked twin.
ind_base = independent_score(alice)
ind_attacked = independent_score(attacked_record)
record("independent-interpreter-agrees",
       ind_base == baseline.score_millipoints and ind_attacked == attacked.score_millipoints,
       f"ind {ind_base}/{ind_attacked} impl {baseline.score_millipoints}/{attacked.score_millipoints}")

# LIVE-DETECTOR CONTROL: a REAL conformance drop must move the level.
near_high = copy.deepcopy(alice)
near_high["advisory_median_response_hours"] = 240   # 6666 mp, not perfect
near_high["provenance_complete_versions"] = 2       # 4000 mp on 5 published
near = compute_publisher_trust(near_high)
record("near-high-is-high", near.level == "HIGH", str(near.level) + "/" + str(near.score_millipoints))
dropped_rec = copy.deepcopy(near_high)
dropped_rec["conformance_passes"] = 3               # 30% pass rate
dropped = compute_publisher_trust(dropped_rec)
record("real-signal-moves-level",
       near.level == "HIGH" and dropped.level == "MEDIUM"
       and dropped.score_millipoints < near.score_millipoints,
       f"{near.level}({near.score_millipoints}) -> {dropped.level}({dropped.score_millipoints})")

# UNRATED never DEFAULT-TRUSTED.
unrated = compute_publisher_trust(PUBS["unrated-empty"]["record"])
record("unrated-empty-stays-unrated", unrated.level == "UNRATED" and unrated.score_millipoints is None,
       str(unrated.level))

RESULTS.update({"pass": not FAILS, "failures": FAILS,
                "gaming_strategy_verdict": "DEFETED - popularity inflation changes nothing "
                                           "while a real conformance drop moves the level"})
print("RESULT:" + json.dumps(RESULTS, sort_keys=True))
if FAILS:
    print("FAILED:IMP-0076-probe2 " + "; ".join(FAILS[:6]))
    raise SystemExit(1)
print("SUCCESS:IMP-0076-probe2 gaming strategy defeated; independent interpreter agrees")
