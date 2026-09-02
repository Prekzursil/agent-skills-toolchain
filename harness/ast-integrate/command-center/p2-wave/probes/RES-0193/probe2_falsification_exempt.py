#!/usr/bin/env python3
"""Probe 2: independent refuter. Falsification-only must not be infinite.

Does not call engine.score_run. Re-reads recorded telemetry, re-hashes
lineage bytes, reimplements the exemption and keep-rule, and defaults to
REFUTED when evidence is missing.
"""
from __future__ import annotations

import hashlib
import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ART = REPO / (
    "command-center/research/deep-research-design/"
    "RES-0193-tokens-per-verified-claim-efficiency.json"
)
RECORDED = HERE / "fixtures" / "recorded-runs.json"
SENTINEL = "SUCCESS:RES-0193"
TOKEN_FLOOR = 500.0
WALL_FLOOR_MS = 5.0
THRESHOLD_MULT = 10.0


def fail(msg: str) -> int:
    print(f"FAILED:RES-0193-probe2 {msg}")
    return 1


def digest_file(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def verified_new(run: dict) -> int:
    n = 0
    for claim in run.get("claims") or []:
        if claim.get("kind") != "new_finding":
            continue
        if claim.get("independently_verified") is True:
            n += 1
    return n


def independent_score(run: dict) -> dict:
    prod = int((run.get("tokens") or {}).get("production") or 0)
    verified = verified_new(run)
    prod_wall = float(run.get("wall_clock_ms_production") or 0.0)
    if prod == 0 and verified == 0:
        return {
            "status": "EXEMPT_FALSIFICATION",
            "infinite": False,
            "tokens_per_verified_claim": None,
            "wall_ms_per_verified_claim": None,
            "verified": verified,
            "production_tokens": prod,
        }
    if verified == 0:
        return {
            "status": "ZERO_VERIFIED_YIELD",
            "infinite": False,
            "tokens_per_verified_claim": None,
            "wall_ms_per_verified_claim": None,
            "verified": verified,
            "production_tokens": prod,
        }
    return {
        "status": "SCORED",
        "infinite": False,
        "tokens_per_verified_claim": prod / verified,
        "wall_ms_per_verified_claim": prod_wall / verified,
        "verified": verified,
        "production_tokens": prod,
    }


def main() -> int:
    if not ART.is_file():
        return fail("artifact-absent")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")
    if not RECORDED.is_file():
        return fail("telemetry-absent")

    telemetry = json.loads(RECORDED.read_text(encoding="utf-8"))
    live_sha = digest_file(RECORDED)
    art_sha = (doc.get("telemetry") or {}).get("sha256")
    if art_sha != live_sha:
        return fail(f"telemetry-sha artifact={art_sha} live={live_sha}")

    nc_run = next(
        (r for r in telemetry.get("runs") or [] if r.get("run_id") == "NC-refutation-only"),
        None,
    )
    if nc_run is None:
        return fail("control-run-absent")
    nc = independent_score(nc_run)
    if nc["status"] != "EXEMPT_FALSIFICATION":
        return fail(f"control-status:{nc['status']}")
    if nc["infinite"] is True:
        return fail("control-marked-infinite")
    if nc["tokens_per_verified_claim"] is not None:
        return fail("control-has-ratio")
    # Numeric JSON Infinity is illegal; the word in a caveat is not a score.
    if "infinite\": true" in text.replace(" ", "") or doc.get("infinite") is True:
        return fail("infinite-true-on-artifact")
    for row in doc.get("per_mode_efficiency") or []:
        eff = row.get("efficiency") or {}
        if eff.get("infinite") is True:
            return fail(f"mode-infinite:{row.get('id')}")
        tpv = eff.get("tokens_per_verified_claim")
        if isinstance(tpv, float) and tpv == float("inf"):
            return fail(f"mode-inf-ratio:{row.get('id')}")

    art_nc = None
    for row in doc.get("negative_controls") or []:
        if row.get("id") == "NC-refutation-only-zero-new-claims":
            art_nc = row.get("result") or {}
    if not art_nc:
        return fail("artifact-missing-nc")
    if art_nc.get("status") != "EXEMPT_FALSIFICATION" or art_nc.get("infinite") is True:
        return fail("artifact-nc-not-exempt")

    scored = []
    for run in telemetry.get("runs") or []:
        if run.get("control"):
            continue
        scored.append((run.get("mode_id"), independent_score(run)))
    tok_vals = [
        s["tokens_per_verified_claim"]
        for _, s in scored
        if s["status"] == "SCORED" and s["tokens_per_verified_claim"] is not None
    ]
    wall_vals = [
        s["wall_ms_per_verified_claim"]
        for _, s in scored
        if s["status"] == "SCORED" and s["wall_ms_per_verified_claim"] is not None
    ]
    tok_ceil = max(TOKEN_FLOOR, THRESHOLD_MULT * float(statistics.median(tok_vals)))
    wall_ceil = max(WALL_FLOOR_MS, THRESHOLD_MULT * float(statistics.median(wall_vals)))
    below = []
    for mode_id, s in scored:
        if s["status"] != "SCORED":
            below.append(mode_id)
            continue
        if s["tokens_per_verified_claim"] > tok_ceil or s["wall_ms_per_verified_claim"] > wall_ceil:
            below.append(mode_id)
    art_below = doc.get("modes_below_default_set_threshold") or []
    if sorted(below) != sorted(art_below):
        return fail(f"below-mismatch live={below} artifact={art_below}")
    if "broad_landscape_scan" not in below:
        return fail("landscape-survived-default-set")

    # Lineage: every CONFIRMED claim needs URL + timestamp + sha256 + two signals.
    for claim in doc.get("claims") or []:
        if claim.get("verdict") == "CONFIRMED":
            if len(claim.get("signals") or []) < 2:
                return fail(f"{claim.get('claim_id')}:single-signal")
            if not claim.get("confidence_band") and not (claim.get("sherman_kent") or {}).get("band"):
                return fail(f"{claim.get('claim_id')}:no-sherman-kent")
            if not claim.get("independent_verification_path"):
                return fail(f"{claim.get('claim_id')}:no-verification-path")
            lin = claim.get("source_lineage") or []
            if not lin:
                return fail(f"{claim.get('claim_id')}:no-lineage")
            for row in lin:
                if not row.get("resolved_url") or not row.get("sha256") or not row.get("fetch_timestamp"):
                    return fail(f"{claim.get('claim_id')}:incomplete-lineage")
                snap = row.get("snapshot_path")
                if snap:
                    path = REPO / str(snap)
                    if path.is_file() and digest_file(path) != row.get("sha256"):
                        return fail(f"{claim.get('claim_id')}:lineage-sha-drift:{snap}")

    metric = doc.get("metric") or {}
    forbidden = set(metric.get("not_inputs") or [])
    if "output_bytes" not in forbidden or "agent_id" not in forbidden:
        return fail("volume-or-agent-still-in-score-inputs")
    for row in doc.get("per_mode_efficiency") or []:
        if "agent_id" in (row.get("efficiency") or {}):
            return fail("agent-id-in-score")

    print(
        json.dumps(
            {
                "probe": "probe2-falsification-exempt",
                "nc_status": nc["status"],
                "infinite": False,
                "below": below,
                "telemetry_sha256": live_sha,
                "claims": len(doc.get("claims") or []),
            },
            sort_keys=True,
        )
    )
    print(
        f"nc={nc['status']} infinite=False below={below} "
        f"sources_hashed={len(doc.get('source_lineage') or [])}"
    )
    print("SUCCESS:RES-0193-probe2 falsification exemption and lineage")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
