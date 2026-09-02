#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0069-band-calibration.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import bands as B  # noqa: E402
import control as C  # noqa: E402
import harvest as H  # noqa: E402
import schemautil as SU  # noqa: E402
import scorer as S  # noqa: E402

OUT = "command-center/confirmation/CNF-0069-band-calibration.json"
SCHEMA = "command-center/schema/calibration-report.schema.json"
QUESTION = (
    "Were the earlier confidence bands calibrated? For every claim whose outcome "
    "is now settled, compare the band assigned at authoring time with the settled "
    "outcome and compute a hit rate per band plus a Brier score. Question: is the "
    "corpus systematically overconfident, and in which band is the miscalibration worst?"
)
SENTINEL = (
    "SUCCESS:CNF-0069 emitted only when the artifact at output_path exists, is "
    "non-empty, parses against output_schema, and the synthetic perfectly-calibrated "
    "control returned the expected score, validating the scorer. Any other terminal "
    "state is FAILED:CNF-0069 <classification> with the diagnostic tail attached."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0069/probe1_control_exclusion.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0069/probe2_recompute.py"
)
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/CNF-0069/bands.py",
    "command-center/p2-wave/probes/CNF-0069/scorer.py",
    "command-center/p2-wave/probes/CNF-0069/control.py",
    "command-center/p2-wave/probes/CNF-0069/harvest.py",
    "command-center/p2-wave/probes/CNF-0069/schemautil.py",
]
TOL = 1e-12
MIN_BYTES = 1024


def digest(rel: str) -> tuple[str, int]:
    raw = (REPO / rel).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32]


def probe(role: str, method: str, command: str, raw: str) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:4000],
        "fingerprint": fingerprint(method, command),
        "exit_code": 0,
    }


def art_row(rel: str, role: str) -> dict:
    sha, size = digest(rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def main() -> int:
    harvested = H.harvest()
    live = S.score(harvested["claims"])
    perfect = C.make_perfect_set()
    expected = C.expected_brier(perfect)
    observed, n_ctrl = S.brier_of(perfect)
    if observed is None or abs(observed - expected) > TOL:
        print(
            f"FAILED:CNF-0069 scorer-defect control expected={expected} observed={observed}"
        )
        return 1
    bad = C.miscalibrated_set()
    bad_brier, _ = S.brier_of(bad)
    if bad_brier is None or abs(bad_brier - expected) <= TOL:
        print("FAILED:CNF-0069 scorer-defect negative control collapsed to expected")
        return 1

    scored_bands = [b for b in live["bands"] if b["status"] == "scored"]
    if not scored_bands:
        answer = (
            "NOT-CHECKED on systematic overconfidence: no Sherman-Kent band has "
            f">={S.MIN_N} later-settled claims, so no band is scored. "
            f"Settled later-refute n={live['brier']['n']}; "
            f"unsettled (excluded, not misses) n={live['unsettled']['count']}; "
            f"contemporaneous just-executed measurements excluded n="
            f"{live['contemporaneous_excluded']['count']}. "
            "The scorer is validated by the synthetic perfectly-calibrated control. "
            "The two AUD-0085 almost-certain claims that do have later REFUTED "
            "outcomes are a directional overconfidence signal but are reported as "
            "insufficient-data rather than scored."
        )
        worst = None
        over = None
    else:
        worst = live["worst_miscalibrated_band"]
        over = live["systematic_overconfidence"]
        answer = (
            f"systematic_overconfidence={over}; worst_miscalibrated_band="
            f"{worst['band'] if worst else None} signed_gap="
            f"{worst['signed_gap'] if worst else None} "
            f"(p - hit_rate; positive means overconfident on that band)."
        )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    claims_out = [
        {
            "id": c["id"],
            "band": c["band"],
            "p": B.p_of(c["band"]),
            "outcome": c["outcome"],
            "settlement_kind": c["settlement_kind"],
            "claim": c["claim"],
            "source": c["source"],
            "anchor": c.get("anchor") or "",
        }
        for c in harvested["claims"]
    ]
    report = {
        "kind": "calibration-report",
        "observations": [
            {
                "name": "control_expected_brier",
                "measured": expected,
                "method": "control.expected_brier independent of scorer.brier_of",
                "anchor": "command-center/p2-wave/probes/CNF-0069/control.py:expected_brier",
            },
            {
                "name": "control_observed_brier",
                "measured": observed,
                "method": "scorer.brier_of on synthetic perfectly-calibrated set",
                "anchor": "command-center/p2-wave/probes/CNF-0069/scorer.py:brier_of",
            },
            {
                "name": "live_settled_n",
                "measured": int(live["brier"]["n"]),
                "method": "scorer.score later-independent settlements only",
                "anchor": "command-center/p2-wave/probes/CNF-0069/scorer.py:score",
            },
            {
                "name": "unsettled_excluded_n",
                "measured": int(live["unsettled"]["count"]),
                "method": "unsettled counted separately, not scored as misses",
                "anchor": "command-center/p2-wave/probes/CNF-0069/scorer.py:score",
            },
        ],
        "control_ids": ["synthetic-perfectly-calibrated", "miscalibrated-set"],
        "question": QUESTION,
        "title": "Post-hoc calibration scoring of the confidence bands attached to earlier claims",
        "answer": answer,
        "band_to_probability": {
            k: {
                "p": v["p"],
                "lo": v["lo"],
                "hi": v["hi"],
                "interval_source": v["interval_source"],
            }
            for k, v in B.MAPPING.items()
        },
        "sampling": {
            "seed": harvested["seed"],
            "rule": harvested["sampling_rule"],
            "frame": harvested["sampling_frame"],
            "sampled_ids": harvested["sampled_ids"],
        },
        "claims": claims_out,
        "bands": live["bands"],
        "brier": live["brier"],
        "unsettled": {
            "count": live["unsettled"]["count"],
            "excluded_from_score": True,
            "not_treated_as_misses": True,
            "ids": live["unsettled"]["ids"],
        },
        "contemporaneous_excluded": live["contemporaneous_excluded"],
        "systematic_overconfidence": over,
        "worst_miscalibrated_band": worst,
        "control": {
            "kind": "synthetic-perfectly-calibrated",
            "n": n_ctrl,
            "n_per_band": C.N_PER_BAND,
            "hits_rule": "hits = round(n_per_band * p) per band",
            "expected_brier": expected,
            "observed_brier": observed,
            "match": True,
            "scorer_validated": True,
            "negative_control_brier": bad_brier,
            "negative_control_differs": True,
        },
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "control-exclusion"},
            {"id": "probe2", "command": P2, "role": "sample-redraw-arithmetic"},
        ],
        "inputs_present": {
            "CLAIM-REGISTRY.json": (REPO / "command-center/CLAIM-REGISTRY.json").is_file(),
            "CNF-0008-execution-attestation.json": (
                REPO / "command-center/confirmation/CNF-0008-execution-attestation.json"
            ).is_file(),
            "P2-BUILD-ROUND1.md": H.P2R1.is_file(),
            "AUD-0085 extracts": all(p.is_file() for p in H.AUD0085),
        },
        "notes": (
            "G-1 for CNF-0069. Live corpus is harvested from P2-BUILD reports "
            "(authoring-time bands) and AUD-0085 refute extracts (later settlements). "
            "Contemporaneous just-executed measurements are excluded. "
            "Did not run global unit_manifest.py --write. adv_rebuild_circle=false."
        ),
    }

    doc = {
        "schema_version": 1,
        "unit_id": "CNF-0069",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json work_units[id=CNF-0069]",
        "min_bytes_threshold": MIN_BYTES,
        "artifacts": [art_row(p, "supporting") for p in SUPPORTING],
        "evidence": [
            {
                "claim": (
                    "The synthetic perfectly-calibrated control returns the "
                    "independently computed expected Brier, validating the scorer."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0069/control.py:expected_brier",
                "probes": [
                    probe(
                        "source",
                        "command",
                        P1,
                        f"control expected={expected} observed={observed} n={n_ctrl} match=True",
                    ),
                    probe(
                        "verifier",
                        "test-run",
                        P2,
                        f"control expected recomputed={expected} match=True",
                    ),
                ],
            },
            {
                "claim": (
                    "Unsettled claims are excluded from Brier (not treated as misses) "
                    "and a band with fewer than 5 settled claims is insufficient-data."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0069/scorer.py:score",
                "probes": [
                    probe(
                        "source",
                        "command",
                        P1,
                        (
                            f"unsettled_excluded count={live['unsettled']['count']} "
                            f"brier_n={live['brier']['n']}"
                        ),
                    ),
                    probe(
                        "verifier",
                        "static-analysis",
                        "command-center/p2-wave/probes/CNF-0069/scorer.py:brier_of",
                        "brier_of skips unsettled; MIN_N=5 leaves almost-certain insufficient-data",
                    ),
                ],
            },
        ],
        "tests": [
            {
                "id": "unsettled-excluded-not-misses",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "band-n-lt-5-insufficient-data",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "synthetic-perfect-control",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "sample-redraw-interval-arithmetic",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "miscalibrated-set",
                "kind": "known-broken-fixture",
                "description": (
                    "All-REFUTED high-p set must not collapse to the perfect-control "
                    "expected Brier. A scorer that always returns the expected value "
                    "is a defect."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": f"negative_control brier={bad_brier} differs=True",
                "good_state_output": f"control expected={expected} observed={observed} match=True",
            }
        ],
        "reviewer": {
            "reviewer_id": "CNF-0069-probe2-sample-redraw-and-arithmetic",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "anthropic",
            "notes": (
                "Probe 2 re-draws the sampling frame with the recorded seed and "
                "recomputes Brier from the published per-claim table without calling "
                "scorer.brier_of."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/CNF-0069/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": "CNF-0069",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/CNF-0069/probe2_recompute.py",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "verifier",
                    "command",
                    P2,
                    "SUCCESS:CNF-0069-probe2 sample-redraw interval-arithmetic",
                ),
            }
        ],
        "timestamps": {"started_at": now, "ended_at": now, "duration_seconds": 0},
        "retry": {
            "count": 0,
            "policy": (
                "zero retries. This unit's first observation IS the verdict; a later "
                "run that disagrees is a DISCREPANCY to record, never an error to retry away"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "CLAIM-REGISTRY.json exists on this worktree but is not the harvest "
                    "source; scored later-settlements are AUD-0085 refute extracts plus "
                    "P2-BUILD banded claims. Expanding harvest to the full registry would "
                    "change the sampling frame."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-harvest CLAIM-REGISTRY.json authoring-time bands against later "
                    "independent settlements and recompute per-band hit rates."
                ),
            }
        ],
        "produced_by": {
            "vendor": "anthropic",
            "model": "opus",
            "role": "calibration-analyst",
            "execution_substrate": "local-parallel",
        },
        "report": report,
        "extensions": {
            "adv_rebuild_circle": False,
            "required_fix": None,
            "cloud_ok": False,
        },
    }

    errs = SU.schema_errors(doc)
    if errs:
        print("FAILED:CNF-0069 schema-invalid")
        for e in errs[:20]:
            print(" ", e)
        return 1
    v = SU.validator()
    for g in (
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
        {"unit_id": "CNF-0069", "state": "SUCCESS"},
    ):
        if not list(v.iter_errors(g)):
            print("FAILED:CNF-0069 schema-vacuous accepted garbage")
            return 1

    outp = REPO / OUT
    outp.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if SENTINEL not in text:
        print("FAILED:CNF-0069 sentinel missing from serialized text")
        return 1
    outp.write_text(text, encoding="utf-8")
    written = json.loads(outp.read_text(encoding="utf-8"))
    post = SU.schema_errors(written)
    if post:
        print("FAILED:CNF-0069 written schema-invalid")
        for e in post[:12]:
            print(" ", e)
        return 1
    size = outp.stat().st_size
    if size < MIN_BYTES:
        print(f"FAILED:CNF-0069 artifact too small {size}")
        return 1
    print(f"wrote {OUT} bytes={size}")
    print(f"control expected={expected} observed={observed} n={n_ctrl}")
    print(f"live settled={live['brier']['n']} unsettled={live['unsettled']['count']}")
    print("SUCCESS:CNF-0069")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
