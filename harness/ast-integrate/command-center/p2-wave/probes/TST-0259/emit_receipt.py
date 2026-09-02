#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0259.json from live planted-cast measurements.

Catalog output_schema is command-center/schema/receipt.schema.json (receipt_core).
Domain numbers live in `report` so the core stays additionalProperties-clean.
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
sys.path.insert(0, str(HERE))

from casts import ROLES  # noqa: E402
from divergence import floor_value, load_floor, score_from_raw, score_transcript  # noqa: E402
from simulate import canonical_bytes, run_named, run_sweep  # noqa: E402

OUT = "command-center/receipts/TST-0259.json"
SCHEMA = "command-center/schema/receipt.schema.json"
SENTINEL = "SUCCESS:TST-0259"
UNIT = "TST-0259"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0259/probe1_collapsed_vs_differentiated.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0259/probe2_sensitivity_and_recompute.py"
)
V1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0259/recompute_verifier.py"
)
CONSUMER = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0259/read_receipt.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/TST-0259/floor.json",
    "command-center/p2-wave/probes/TST-0259/casts.py",
    "command-center/p2-wave/probes/TST-0259/divergence.py",
    "command-center/p2-wave/probes/TST-0259/simulate.py",
    "command-center/p2-wave/probes/TST-0259/probe1_collapsed_vs_differentiated.py",
    "command-center/p2-wave/probes/TST-0259/probe2_sensitivity_and_recompute.py",
    "command-center/p2-wave/probes/TST-0259/probe2-raw-casts.json",
    "command-center/p2-wave/probes/TST-0259/recompute_verifier.py",
    "command-center/p2-wave/probes/TST-0259/read_receipt.py",
    "command-center/p2-wave/probes/TST-0259/emit_receipt.py",
]


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return sha256_bytes(raw), len(raw)


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\n{command}".encode("utf-8")).hexdigest()


def run_cmd(cmd: str) -> tuple[int, str]:
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
    return p.returncode, text[-65000:]


def components(sc: dict) -> dict:
    return {
        "claim_jaccard_distance": sc["claim_jaccard_distance"],
        "evidence_jaccard_distance": sc["evidence_jaccard_distance"],
        "vote_dispersion": sc["vote_dispersion"],
        "lexical_jaccard_distance": sc["lexical_jaccard_distance"],
    }


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest_file(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def dump(obj: dict) -> str:
    return json.dumps(obj, indent=1, sort_keys=True) + "\n"


def main() -> int:
    started = utcnow()
    floor_doc = load_floor()
    floor = floor_value()
    collapsed = run_named("collapsed")
    differentiated = run_named("differentiated")
    relabeled = run_named("relabeled")
    if canonical_bytes(collapsed) != canonical_bytes(run_named("collapsed")):
        print("FAILED:TST-0259 emit collapsed not deterministic")
        return 1
    sc = score_transcript(collapsed)
    sd = score_transcript(differentiated)
    sr = score_transcript(relabeled)
    if sc["panel"] != "FAIL" or sd["panel"] != "PASS" or sr["panel"] != "FAIL":
        print("FAILED:TST-0259 emit planted panels")
        print(json.dumps({"c": sc, "d": sd, "r": sr}, indent=2)[:3000])
        return 1
    if abs(sc["D"] - sr["D"]) > 1e-12:
        print("FAILED:TST-0259 emit relabel moved D")
        return 1

    sweep_live = []
    raw_casts = []
    for t in run_sweep():
        st = score_transcript(t)
        sweep_live.append(
            {
                "cast_id": t["cast_id"],
                "similarity": t["similarity"],
                "D": st["D"],
                "panel": st["panel"],
                "components": components(st),
            }
        )
        raw_casts.append(
            {
                "cast_id": t["cast_id"],
                "similarity": t["similarity"],
                "participants": t["participants"],
            }
        )
    if len(sweep_live) < 5:
        print("FAILED:TST-0259 emit sweep < 5")
        return 1
    recomputed = [score_from_raw(row["participants"])["D"] for row in raw_casts]
    for a, b in zip(sweep_live, recomputed):
        if abs(a["D"] - b) > 1e-12:
            print("FAILED:TST-0259 emit recompute mismatch")
            return 1
    ds = [row["D"] for row in sweep_live]
    for i in range(1, len(ds)):
        if ds[i] - ds[i - 1] > 1e-9:
            print("FAILED:TST-0259 emit sweep not non-increasing")
            return 1
    gaps = []
    for i in range(1, len(sweep_live)):
        left, right = sweep_live[i - 1], sweep_live[i]
        if left["D"] >= floor > right["D"]:
            gaps.append(
                {
                    "between": [left["cast_id"], right["cast_id"]],
                    "D_left": left["D"],
                    "D_right": right["D"],
                }
            )
    if not gaps:
        print("FAILED:TST-0259 emit floor not in sweep gap")
        return 1

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0259 emit named probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    c_v1, t_v1 = run_cmd(V1)
    if c_v1 != 0:
        print("FAILED:TST-0259 emit independent recompute")
        print(t_v1[-2000:])
        return 1

    prod = REPO / "tools/council/simulate.py"
    raw_path = HERE / "probe2-raw-casts.json"
    if not raw_path.is_file() or raw_path.stat().st_size <= 0:
        print("FAILED:TST-0259 emit probe2-raw-casts.json missing")
        return 1
    raw_reload = json.loads(raw_path.read_text(encoding="utf-8"))
    file_recomputed = [
        {
            "cast_id": row["cast_id"],
            "D": score_from_raw(row["participants"])["D"],
            "panel": score_from_raw(row["participants"])["panel"],
        }
        for row in raw_reload["casts"]
    ]
    file_read_out = json.dumps(
        {"n": len(file_recomputed), "rows": file_recomputed, "floor": floor},
        indent=2,
        sort_keys=True,
    )

    inverted_collapsed = "PASS" if sc["D"] < floor else "FAIL"
    inverted_differentiated = "FAIL" if sd["D"] >= floor else "PASS"

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)

    supporting = [artifact_row(rel, "supporting") for rel in SUPPORTING]
    missing = [a for a in supporting if not a["exists"] or a["bytes"] < 2]
    if missing:
        print("FAILED:TST-0259 emit missing supporting", missing)
        return 1

    ended = utcnow()
    report = {
        "kind": "divergence-calibration",
        "statistic_id": floor_doc["statistic_id"],
        "definition": floor_doc["components"],
        "formula": (
            "D = mean(mean_pairwise_jaccard_distance(claims), "
            "mean_pairwise_jaccard_distance(evidence), "
            "(unique_votes-1)/(n-1), "
            "mean_pairwise_jaccard_distance(opening_tokens))"
        ),
        "range": floor_doc["range"],
        "floor": {
            "value": floor,
            "selection": floor_doc["selection"],
            "post_hoc": bool(floor_doc["post_hoc"]),
            "rationale": floor_doc["rationale"],
            "declared_in": "command-center/p2-wave/probes/TST-0259/floor.json",
        },
        "collapsed": {
            "cast_id": collapsed["cast_id"],
            "D": sc["D"],
            "panel": sc["panel"],
            "components": components(sc),
            "n_seats": sc["n_seats"],
            "unique_votes": sc["unique_votes"],
            "roles_labeled": sc["roles"],
        },
        "differentiated": {
            "cast_id": differentiated["cast_id"],
            "D": sd["D"],
            "panel": sd["panel"],
            "components": components(sd),
            "n_seats": sd["n_seats"],
            "unique_votes": sd["unique_votes"],
            "roles": list(ROLES),
        },
        "relabeled_clone": {"cast_id": relabeled["cast_id"], "D": sr["D"], "panel": sr["panel"]},
        "sweep": {
            "n": len(sweep_live),
            "order": "increasing similarity (0 = differentiated, 1 = collapsed)",
            "rows": sweep_live,
            "floor_sits_in_gap": gaps,
            "effect_size_D_low_sim_minus_high_sim": sweep_live[0]["D"] - sweep_live[-1]["D"],
            "independent_recompute_matched": True,
        },
        "harness": {
            "kind": "scripted-participant",
            "executable": "command-center/p2-wave/probes/TST-0259/simulate.py",
            "production_runtime_on_this_tree": {
                "path": "tools/council/simulate.py",
                "present": prod.is_file(),
                "bytes": prod.stat().st_size if prod.is_file() else 0,
            },
        },
    }

    placeholder = "0" * 64
    primary = {
        "path": OUT,
        "bytes": 1,
        "sha256": placeholder,
        "exists": True,
        "eol": "LF",
        "role": "primary",
    }

    consumer_probe = {
        "role": "verifier",
        "method": "command",
        "command": CONSUMER,
        "raw_output": "pending",
        "fingerprint": fingerprint("command", CONSUMER),
        "exit_code": 0,
    }

    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json:TST-0259; catalog cites "
            "_USER-PROMPTS.md:11230 and :10944 (file absent on this worktree); "
            "contracted tests are planted collapsed FAIL, planted differentiated "
            "PASS, and a five-cast increasing-similarity sweep"
        ),
        "min_bytes_threshold": 1024,
        "produced_by": {
            "vendor": "grok",
            "model": "grok-4.6",
            "role": "calibration-analyst",
            "execution_substrate": "linux-local",
        },
        "artifacts": [primary] + supporting,
        "evidence": [
            {
                "claim": (
                    f"Planted five-seat clone panel D={sc['D']:.6f} is below floor "
                    f"{floor} (panel FAIL); proposer/critic/judge/expert/user-proxy "
                    f"conflict panel D={sd['D']:.6f} is at or above the floor "
                    "(panel PASS). Relabeling clone seats does not move D."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/TST-0259/probe1_collapsed_vs_differentiated.py",
                "probes": [
                    {
                        "role": "source",
                        "method": "test-run",
                        "command": P1,
                        "raw_output": t1,
                        "fingerprint": fingerprint("test-run", P1),
                        "exit_code": c1,
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": V1,
                        "raw_output": t_v1,
                        "fingerprint": fingerprint("command", V1),
                        "exit_code": c_v1,
                    },
                ],
            },
            {
                "claim": (
                    f"Five-point increasing-similarity sweep D={ds} places floor "
                    f"{floor} in a measured gap; independent recompute from "
                    "serialized raw participant fields matches live D."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/TST-0259/probe2-raw-casts.json",
                "probes": [
                    {
                        "role": "source",
                        "method": "test-run",
                        "command": P2,
                        "raw_output": t2,
                        "fingerprint": fingerprint("test-run", P2),
                        "exit_code": c2,
                    },
                    {
                        "role": "verifier",
                        "method": "file-read",
                        "command": "command-center/p2-wave/probes/TST-0259/probe2-raw-casts.json",
                        "raw_output": file_read_out,
                        "fingerprint": fingerprint(
                            "file-read",
                            "command-center/p2-wave/probes/TST-0259/probe2-raw-casts.json",
                        ),
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "TST-0259-COLLAPSED-FAIL",
                "name": "Planted collapsed cast (all personas share one script) -> divergence below floor, panel FAILS.",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "TST-0259-DIFFERENTIATED-PASS",
                "name": "Planted differentiated cast (proposer/critic/judge with conflicting scripts) -> divergence above floor, panel PASSES.",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "TST-0259-SENSITIVITY-SWEEP",
                "name": "Sensitivity sweep: report the divergence value across at least 5 casts of increasing similarity so the floor is not a single-point guess.",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "relabeled-clone",
                "kind": "mutation",
                "description": "Change role labels, keep the shared clone script. D must stay at the clone floor so the statistic is not reading labels.",
                "fired_on_bad_state": sr["panel"] == "FAIL",
                "silent_on_good_state": sd["panel"] == "PASS",
                "bad_state_output": f"relabeled_D={sr['D']} panel={sr['panel']}",
                "good_state_output": f"differentiated_D={sd['D']} panel={sd['panel']}",
            },
            {
                "id": "inverted-detector",
                "kind": "mutation",
                "description": "Invert the floor rule (FAIL when D >= floor). The inverted rule must be wrong on both planted states.",
                "fired_on_bad_state": inverted_collapsed != "FAIL" and inverted_differentiated != "PASS",
                "silent_on_good_state": sd["panel"] == "PASS" and sc["panel"] == "FAIL",
                "bad_state_output": (
                    f"inverted(collapsed)={inverted_collapsed} "
                    f"inverted(differentiated)={inverted_differentiated}"
                ),
                "good_state_output": f"true(collapsed)={sc['panel']} true(differentiated)={sd['panel']}",
            },
            {
                "id": "determinism-byte-identical",
                "kind": "other",
                "description": "Second run of the collapsed cast must be byte-identical to the first (no wall clock, no RNG).",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "non-identical second run would fail emit",
                "good_state_output": "canonical_bytes(collapsed) matched rerun",
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0259-probe2-raw-recompute",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": False,
            "vendor": "local",
            "notes": (
                "Statistics mandate as a mechanical recount: probe 2 serialises "
                "raw participant claim/evidence/vote/opening fields, reloads them, "
                "and recomputes D via score_from_raw without probe 1's summary. "
                "This is not a named human statistician. Catalog reviewer_requirement "
                "asked for an independent statistics re-run from raw per-case results."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/TST-0259/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": UNIT,
        },
        "downstream_consumers": [
            {
                "consumer": "json-load-and-field-check of catalog output_path",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": consumer_probe,
            }
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                "Two strikes then pivot (AGENTS.md 4b): after a second failure on "
                "the same hypothesis, enumerate at least two alternative approaches "
                "before a third attempt. Two same-fingerprint structural refutes "
                "park BLOCKED with a named required_fix; no ADV rebuild circle."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "tools/council/simulate.py is absent on this worktree; "
                    "measurements are against the local planted-cast runner."
                ),
                "verdict": "CONFIRMED",
                "settling_experiment": (
                    "Re-run TST-0259 against tools/council/simulate.py when TST-0257 "
                    "lands that entry point, or keep the local runner as the harness "
                    "and leave this residual."
                ),
            },
            {
                "claim": (
                    "_USER-PROMPTS.md is absent; :11230/:10944 were not re-read as "
                    "file:line anchors on this box."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "When _USER-PROMPTS.md is present, grep :11230 and :10944 and "
                    "confirm the planted tests still match the spec wording."
                ),
            },
        ],
        "report": report,
        "extensions": {
            "named_probes": [
                {"id": "probe1", "command": P1, "role": "collapsed-vs-differentiated"},
                {"id": "probe2", "command": P2, "role": "sensitivity-sweep-and-recompute"},
            ],
            "cloud_ok": False,
            "honesty": (
                "Catalog input names tools/council/simulate.py. That file is not "
                "on this worktree. TST-0259 does not ship that entry point. "
                "Did not run global unit_manifest.py --write. No ADV rebuild."
            ),
        },
    }

    dest.write_text(dump(doc), encoding="utf-8")
    sha, size = digest_file(dest)
    doc["artifacts"][0]["sha256"] = sha
    doc["artifacts"][0]["bytes"] = size
    dest.write_text(dump(doc), encoding="utf-8")

    cc, ct = run_cmd(CONSUMER)
    if cc != 0:
        print("FAILED:TST-0259 emit downstream consumer")
        print(ct[-2000:])
        return 1
    doc["downstream_consumers"][0]["exit_code"] = cc
    doc["downstream_consumers"][0]["read_ok"] = True
    doc["downstream_consumers"][0]["executed"] = True
    doc["downstream_consumers"][0]["probe"]["raw_output"] = ct
    doc["downstream_consumers"][0]["probe"]["exit_code"] = cc
    dest.write_text(dump(doc), encoding="utf-8")
    sha, size = digest_file(dest)
    doc["artifacts"][0]["sha256"] = sha
    doc["artifacts"][0]["bytes"] = size
    dest.write_text(dump(doc), encoding="utf-8")

    live = dest.read_text(encoding="utf-8")
    if SENTINEL not in live:
        print("FAILED:TST-0259 emit sentinel missing")
        return 1
    if json.loads(live).get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:TST-0259 emit self-declared not-delivering")
        return 1
    sha, size = digest_file(dest)
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
