#!/usr/bin/env python3
"""Probe 1: verified-only denominator; unverified volume must not improve score.

Re-scores recorded telemetry via engine.score_run and requires the live
artifact to match. Independent of probe2's formula reimplementation.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

ART = E.REPO / E.OUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:RES-0193-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact-absent")
    text = ART.read_text(encoding="utf-8")
    if E.SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")

    telemetry = E.load_recorded_runs()
    live = E.score_telemetry(telemetry)
    art_rows = {
        r["id"]: r["efficiency"]
        for r in (doc.get("per_mode_efficiency") or [])
        if isinstance(r, dict)
    }
    if len(art_rows) != 12:
        return fail(f"mode-count={len(art_rows)}")

    for mode_id, scored in live["production_by_mode"].items():
        row = art_rows.get(mode_id)
        if not row:
            return fail(f"artifact-missing-mode:{mode_id}")
        for key in (
            "production_tokens",
            "independently_verified_new_claims",
            "tokens_per_verified_claim",
            "wall_ms_per_verified_claim",
            "status",
            "infinite",
            "below_default_set_threshold",
        ):
            if row.get(key) != scored.get(key):
                return fail(
                    f"drift {mode_id}.{key} artifact={row.get(key)} live={scored.get(key)}"
                )
        if scored.get("infinite") is True:
            return fail(f"infinite-serialized:{mode_id}")
        # Unverified must not be in the denominator: tokens/verified uses verified only.
        v = scored["independently_verified_new_claims"]
        u = scored["unverified_new_claims"]
        if v > 0 and u > 0:
            expected = scored["production_tokens"] / v
            if abs(expected - float(scored["tokens_per_verified_claim"])) > 1e-9:
                return fail(f"denominator-not-verified-only:{mode_id}")
            illegal = scored["production_tokens"] / (v + u)
            if illegal < expected:
                pass  # expected: illegal looks better
            else:
                return fail(f"illegal-metric-did-not-improve:{mode_id}")

    land_run = next(r for r in telemetry["runs"] if r["run_id"] == "RUN-broad_landscape_scan")
    legal = E.score_run(land_run)
    planted = E.score_run(E.plant_unverified_volume(land_run, extra=100))
    if legal["tokens_per_verified_claim"] != planted["tokens_per_verified_claim"]:
        return fail("unverified-volume-improved-legal-score")
    wrong_a = E.wrong_metric_count_unverified(land_run)
    wrong_b = E.wrong_metric_count_unverified(E.plant_unverified_volume(land_run, extra=100))
    if wrong_a is None or wrong_b is None or not (wrong_b < wrong_a):
        return fail("illegal-denominator-control-mute")

    nc = doc.get("negative_controls") or []
    vol = next((c for c in nc if c.get("id") == "NC-unverified-volume-cannot-improve-score"), None)
    if not vol or vol.get("score_unchanged") is not True:
        return fail("artifact-volume-control")

    below = doc.get("modes_below_default_set_threshold") or []
    if "broad_landscape_scan" not in below:
        return fail("landscape-not-below-threshold")
    if live["gate"]["below_default_set_threshold"] != below:
        return fail("gate-below-drift")

    print(
        json.dumps(
            {
                "probe": "probe1-verified-denominator",
                "modes": 12,
                "landscape_tokens_per_verified": legal["tokens_per_verified_claim"],
                "planted_unchanged": True,
                "below": below,
                "illegal_improves": True,
            },
            sort_keys=True,
        )
    )
    print(
        f"landscape_tpv={legal['tokens_per_verified_claim']} "
        f"below={below} mutant_unchanged=True"
    )
    print("SUCCESS:RES-0193-probe1 verified-only denominator and volume mutant")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
