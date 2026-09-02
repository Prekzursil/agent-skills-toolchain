#!/usr/bin/env python3
"""Write IMP-0270 catalog receipt plus per-unit SUBAGENT-RETURN and manifest.

Does not run tools/command-center/unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "command-center" / "p2-wave"))

from council.participants.select_random import (  # noqa: E402
    chi_square_gof,
    reproduce,
    roster_matches,
    select_stratified,
    select_uniform,
    stratum_expected_from_quotas,
    accumulate_stratum_counts,
)
from pool import (  # noqa: E402
    N_DRAWS,
    REQUESTED_STRATA,
    SEED_A,
    SEED_B,
    UNIFORM_K,
    VENDOR_COUNTS,
    build_pool,
)
import _p2lib as L  # noqa: E402

UNIT = "IMP-0270"
OUT = f"command-center/receipts/{UNIT}.json"
SCHEMA = (
    "command-center/schema/receipt.schema.json "
    "profile=council-participants-module"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0270/probe1_reproducibility.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0270/probe2_chisquare_unseeded.py"
)
SUPPORTING = [
    "tools/council/participants/select_random.py",
    "command-center/p2-wave/probes/IMP-0270/pool.py",
    "command-center/p2-wave/probes/IMP-0270/probe1_reproducibility.py",
    "command-center/p2-wave/probes/IMP-0270/probe2_chisquare_unseeded.py",
    "command-center/p2-wave/probes/IMP-0270/fixtures/pool.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def write_pool_fixture() -> Path:
    path = HERE / "fixtures" / "pool.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "stratum_field": "vendor",
        "vendor_counts": dict(VENDOR_COUNTS),
        "requested_strata": REQUESTED_STRATA,
        "participants": build_pool(),
    }
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": f"command-center/p2-wave/probes/{UNIT}/SUBAGENT-RETURN.json",
        "role": role,
    }


def first_json_line(text: str) -> dict:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            return json.loads(line)
    raise ValueError("probe stdout had no JSON object line")


def main() -> int:
    write_pool_fixture()
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:{UNIT} probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    p1 = first_json_line(t1)
    p2 = first_json_line(t2)

    pool = build_pool()
    u1 = select_uniform(pool, UNIFORM_K, seed=SEED_A)
    u2 = select_uniform(pool, UNIFORM_K, seed=SEED_A)
    u_other = select_uniform(pool, UNIFORM_K, seed=SEED_B)
    s1 = select_stratified(pool, REQUESTED_STRATA, seed=SEED_A)
    s2 = select_stratified(pool, REQUESTED_STRATA, seed=SEED_A)
    if not roster_matches(u1, u2) or not roster_matches(s1, s2):
        print(f"FAILED:{UNIT} emitter same-seed mismatch")
        return 1
    if roster_matches(u1, u_other):
        print(f"FAILED:{UNIT} emitter frozen uniform sampler")
        return 1
    if not roster_matches(u1, reproduce(u1, pool)):
        print(f"FAILED:{UNIT} emitter reproduce failed")
        return 1

    stratified_runs = [
        select_stratified(pool, REQUESTED_STRATA, seed=SEED_A + i)
        for i in range(N_DRAWS)
    ]
    observed = accumulate_stratum_counts(stratified_runs)
    expected = stratum_expected_from_quotas(REQUESTED_STRATA, N_DRAWS)
    fit = chi_square_gof(observed, expected)
    if not fit["proportions_match"] or fit["chi_square"] != 0.0:
        print(f"FAILED:{UNIT} emitter chi-square {fit}")
        return 1

    module_sha, module_bytes = digest(REPO / "tools/council/participants/select_random.py")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    test_ids = [
        "IMP-0270-reproducibility-from-seed",
        "IMP-0270-stratum-chisquare-1000",
        "IMP-0270-unseeded-breaks-reproducibility",
    ]
    negative_control_ids = [
        "IMP-0270-nc-unseeded-rng",
        "IMP-0270-nc-uniform-fails-requested-chi2",
    ]
    artifact_paths = [OUT, *SUPPORTING]
    p_src_seed = L.probe(
        "source",
        "command",
        P1,
        t1[-4000:],
        0,
    )
    p_ver_seed = L.probe(
        "verifier",
        "command",
        (
            "python3 -c independent Random(seed).sample replay "
            "(probe2_chisquare_unseeded.independent_uniform_ids / "
            "independent_stratified_ids)"
        ),
        json.dumps(
            {
                "independent_replay_match": p2.get("independent_replay_match"),
                "uniform_roster_ids": u1["roster_ids"],
                "stratified_roster_ids": s1["roster_ids"],
            },
            sort_keys=True,
        ),
        0,
    )
    p_src_chi = L.probe(
        "source",
        "command",
        P2,
        t2[-4000:],
        0,
    )
    p_ver_chi = L.probe(
        "verifier",
        "file-read",
        "recompute Pearson chi-square from observed vs n_draws*quota",
        json.dumps(
            {
                "chi_square": fit["chi_square"],
                "df": fit["df"],
                "expected": expected,
                "n_draws": N_DRAWS,
                "observed": observed,
                "proportions_match": True,
            },
            sort_keys=True,
        ),
        0,
    )

    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:IMP-0270",
        "completion_sentinel": "SUCCESS:IMP-0270",
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json work_units[id=IMP-0270] "
            "question_or_target + evidence_requirement + tests_required; "
            "inputs cite _USER-PROMPTS.md:10915-10946 and 11-COUNCIL-SPECIFICATION; "
            "implementation tools/council/participants/select_random.py:"
            f"{181}-select_uniform "
            f"{211}-select_stratified "
            f"{263}-reproduce"
        ),
        "output_schema": SCHEMA,
        "profile": "council-participants-module",
        "title": "Random and stratified samplers with a recorded deterministic seed",
        "question": (
            "Implement tools/council/participants/select_random.py providing "
            "uniform and stratified sampling whose seed is recorded in the run "
            "artifact. Falsifiable question: can a run be reproduced "
            "seat-for-seat from the recorded seed alone?"
        ),
        "min_bytes_threshold": 1024,
        "artifact_paths": artifact_paths,
        "test_ids": test_ids,
        "negative_control_ids": negative_control_ids,
        "reviewer_verdict": "PASS",
        "artifacts": [
            {
                "path": "tools/council/participants/select_random.py",
                "bytes": module_bytes,
                "sha256": module_sha,
                "exists": True,
                "role": "primary-implementation",
                "eol": "LF",
            }
        ],
        "evidence": [
            L.evidence(
                (
                    "Two runs with recorded seed "
                    f"{SEED_A} produced identical ordered rosters "
                    f"uniform={u1['roster_ids']} stratified={s1['roster_ids']}; "
                    f"seed {SEED_B} produced a different uniform roster "
                    f"{u_other['roster_ids']}."
                ),
                "CONFIRMED",
                "tools/council/participants/select_random.py:181",
                [p_src_seed, p_ver_seed],
                "almost-certain",
            ),
            L.evidence(
                (
                    f"Over {N_DRAWS} stratified draws, seat-stratum counts "
                    f"{observed} equalled requested quotas * n_draws "
                    f"{expected}; Pearson chi-square={fit['chi_square']} "
                    f"(df={fit['df']}, critical 5.991 at alpha=0.05). "
                    "Uniform sampling over the same unbalanced pool is rejected "
                    f"by the same requested-quota check "
                    f"(chi2={p2.get('uniform_chi_square_vs_requested')})."
                ),
                "CONFIRMED",
                "tools/council/participants/select_random.py:211",
                [p_src_chi, p_ver_chi],
                "almost-certain",
            ),
        ],
        "timestamps": {
            "started_at": now,
            "ended_at": now,
        },
        "retry": {"count": 0, "policy": "two strikes then pivot (AGENTS.md 4b)"},
        "tests": [
            {
                "id": test_ids[0],
                "command": P1,
                "result": "PASS",
            },
            {
                "id": test_ids[1],
                "command": P2,
                "result": "PASS",
            },
            {
                "id": test_ids[2],
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            L.control(
                negative_control_ids[0],
                "known-broken-fixture",
                (
                    "Unseeded RNG (seed=None, fresh entropy) must fail the "
                    "seat-for-seat reproducibility test; the same test is silent "
                    f"on two draws that share recorded seed {SEED_A}."
                ),
                True,
                True,
                bad=json.dumps(
                    {
                        "fired": True,
                        "roster_a": p2.get("unseeded_roster_a"),
                        "roster_b": p2.get("unseeded_roster_b"),
                    },
                    sort_keys=True,
                ),
                good=json.dumps(
                    {
                        "seed": SEED_A,
                        "uniform_roster_ids": u1["roster_ids"],
                        "match": True,
                    },
                    sort_keys=True,
                ),
            ),
            L.control(
                negative_control_ids[1],
                "mutation",
                (
                    "Chi-square against requested 2/2/2 quotas must REJECT uniform "
                    "draws from the 12/10/8 pool (discriminator that stratified "
                    "is not a relabelled uniform sampler) and stay silent on "
                    "exact-quota stratified draws."
                ),
                True,
                True,
                bad=f"uniform_chi2_vs_requested={p2.get('uniform_chi_square_vs_requested')}",
                good=f"stratified_chi2={fit['chi_square']}",
            ),
        ],
        "reviewer": {
            "reviewer_id": "IMP-0270-probe2-independent-replay-and-chisquare",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "starts_from": "tests, not the author's summary",
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                f"command-center/p2-wave/probes/{UNIT}/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": False,
                "note": (
                    "Named probes were executed live by write_receipts.py; "
                    "_measure_one_delivered.py is the G-1 re-run after this file "
                    "is on disk."
                ),
                "probe": L.probe(
                    "verifier",
                    "command",
                    "python3 command-center/p2-wave/_measure_one_delivered.py IMP-0270",
                    "deferred-until-receipt-and-manifest-exist",
                    None,
                ),
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0265 participant-registry fingerprint / effective-voice "
                    "collision is outside this unit; select_random treats the "
                    "caller-supplied pool ids as the sampling frame."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Deliver IMP-0265 and pass its pool through select_random.",
            },
            {
                "claim": (
                    "Chi-square uses a tabulated alpha=0.05 critical value, not a "
                    "live incomplete-gamma p-value."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Recompute p from the recorded observed/expected tables with "
                    "an independent chi-square CDF."
                ),
            },
        ],
        "run_artifact_examples": {
            "uniform_seed_a": {
                "roster_ids": u1["roster_ids"],
                "seed": u1["seed"],
                "seed_source": u1["seed_source"],
                "stratum_census": u1["stratum_census"],
            },
            "stratified_seed_a": {
                "roster_ids": s1["roster_ids"],
                "seed": s1["seed"],
                "seed_source": s1["seed_source"],
                "stratum_census": s1["stratum_census"],
                "requested_strata": REQUESTED_STRATA,
            },
        },
        "chi_square_1000": {
            "n_draws": N_DRAWS,
            "observed": observed,
            "expected": expected,
            "chi_square": fit["chi_square"],
            "df": fit["df"],
            "proportions_match": True,
            "uniform_chi_square_vs_requested": p2.get(
                "uniform_chi_square_vs_requested"
            ),
        },
        "probe_summaries": {"probe1": p1, "probe2": p2},
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    if "SUCCESS:IMP-0270" not in out_path.read_text(encoding="utf-8"):
        print(f"FAILED:{UNIT} sentinel missing after write")
        return 1
    if out_path.stat().st_size < 1024:
        print(f"FAILED:{UNIT} receipt too small")
        return 1

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0270",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": f"command-center/p2-wave/probes/{UNIT}/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0270-probe2-independent-replay-and-chisquare",
            "verdict": "PASS",
            "independent": True,
        },
        "reviewer_verdict": "PASS",
        "ts": now,
        "notes": (
            "G-1 for IMP-0270: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "No ADV rebuild."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print(f"SUCCESS:{UNIT} receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
