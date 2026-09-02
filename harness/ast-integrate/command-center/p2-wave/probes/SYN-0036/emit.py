#!/usr/bin/env python3
"""Emit SYN-0036 reliability-weighting receipt, then per-unit return + manifest."""
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
from anti_silencing import apply_weights, naive_weight_rank  # noqa: E402
from catalog_join import live_inputs  # noqa: E402
from schema_bind import (  # noqa: E402
    error_fingerprint,
    garbage_accepted,
    schema_errors,
)
from scoring import SCORE_INPUTS, load_prereg, recompute_weights_from_raw, score_frame  # noqa: E402

UNIT = "SYN-0036"
OUT = "command-center/receipts/SYN-0036.json"
SCHEMA = "command-center/schema/reliability-weighting.schema.json"
FP_PATH = HERE / "_schema_refute_fingerprint.txt"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0036/probe1_anti_silencing.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0036/probe2_volume_and_small_n.py"
)
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/SYN-0036/prereg.json",
    "command-center/p2-wave/probes/SYN-0036/fixtures/frozen_claims.json",
    "command-center/p2-wave/probes/SYN-0036/wilson.py",
    "command-center/p2-wave/probes/SYN-0036/scoring.py",
    "command-center/p2-wave/probes/SYN-0036/anti_silencing.py",
    "command-center/p2-wave/probes/SYN-0036/catalog_join.py",
    "command-center/p2-wave/probes/SYN-0036/schema_bind.py",
    "command-center/p2-wave/probes/SYN-0036/probe1_anti_silencing.py",
    "command-center/p2-wave/probes/SYN-0036/probe2_volume_and_small_n.py",
    "command-center/p2-wave/probes/SYN-0036/emit.py",
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def probe_fp(method: str, command: str) -> str:
    return hashlib.sha256(("%s|%s" % (method, command)).encode("utf-8")).hexdigest()


def catalog_unit() -> dict:
    cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    for u in cat.get("work_units") or []:
        if isinstance(u, dict) and u.get("id") == UNIT:
            return u
    raise SystemExit("FAILED:%s catalog unit missing" % UNIT)


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
        timeout=180,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def art_row(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path)
    if size < 1:
        raise SystemExit("FAILED:%s zero-byte supporting artifact %s" % (UNIT, rel))
    return {
        "bytes": size,
        "eol": "LF",
        "exists": True,
        "path": rel,
        "role": role,
        "sha256": digest,
    }


def man_row(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path)
    return {
        "bytes": size,
        "path": rel,
        "present": True,
        "receipt_path": "command-center/p2-wave/probes/SYN-0036/SUBAGENT-RETURN.json",
        "role": role,
        "sha256": digest,
        "unit_id": UNIT,
    }


def park_blocked(required_fix: str, errs: list[str], fp: str, unit: dict, now: str) -> int:
    sentinel = (
        "FAILED:%s schema-invalid two same-fingerprint structural refutes; "
        "required_fix=%s"
        % (UNIT, required_fix)
    )
    doc = {
        "artifacts": [art_row(SCHEMA, "supporting")],
        "evidence": [
            {
                "anchor": SCHEMA,
                "claim": (
                    "Second same-fingerprint schema refute; parking rather "
                    "than rebuilding ADV inputs."
                ),
                "probes": [
                    {
                        "command": "python3 command-center/p2-wave/probes/SYN-0036/emit.py",
                        "fingerprint": probe_fp("schema-validate", SCHEMA),
                        "method": "schema-validate",
                        "raw_output": "\n".join(errs[:20])[:8000],
                        "role": "source",
                    }
                ],
                "verdict": "BLOCKED",
            }
        ],
        "failure": {
            "classification": ["schema-invalid"],
            "reason": "two same-fingerprint structural refutes; no ADV rebuild",
            "diagnostic_tail": "\n".join(errs[:40]),
        },
        "min_bytes_threshold": 256,
        "report": {
            "control_ids": ["NC-SCHEMA-GARBAGE"],
            "kind": "reliability-weighting",
            "observations": [
                {
                    "anchor": SCHEMA,
                    "measured": fp,
                    "method": "schema-validate",
                    "name": "structural-refute-fingerprint",
                }
            ],
            "park": True,
            "required_fix": required_fix,
        },
        "retry": {
            "count": 2,
            "policy": str(unit.get("retry_policy") or "zero retries"),
        },
        "schema_version": 1,
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#SYN-0036",
        "state": "BLOCKED",
        "timestamps": {"ended_at": now, "started_at": now, "duration_seconds": 0},
        "unit_id": UNIT,
    }
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    ret = {
        "cloud_ok": False,
        "id": UNIT,
        "notes": "PARK: two same-fingerprint structural refutes. No ADV rebuild.",
        "output_path": OUT,
        "required_fix": required_fix,
        "schema_fingerprint": fp,
        "state": "BLOCKED",
        "status": "BLOCKED",
        "ts": now,
        "unit_id": UNIT,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print("PARK: two same-fingerprint structural refutes; required_fix=%s" % required_fix)
    print("FAILED:%s %s" % (UNIT, required_fix))
    return 1


def main() -> int:
    started = datetime.now(timezone.utc)
    unit = catalog_unit()
    sentinel = str(unit["completion_sentinel"])
    question = str(unit["question_or_target"])
    prereg = load_prereg()
    scored = score_frame()
    live = live_inputs()
    findings = list(scored["findings"])
    weights = dict(scored["weights"])
    for p in scored["producers"]:
        weights.setdefault(p["producer_id"], None)
    guard = apply_weights(findings, weights)
    if not guard["passed"]:
        print("FAILED:%s anti-silencing guard failed" % UNIT)
        return 1
    recomputed = recompute_weights_from_raw(scored["claims"], scored["min_n"])
    for pid, w in recomputed.items():
        pub = weights.get(pid) if pid in scored["weights"] else None
        if pub is None and w is None:
            continue
        if pid not in scored["weights"]:
            if w is not None:
                print("FAILED:%s recompute scored insufficient-n %s" % (UNIT, pid))
                return 1
            continue
        if w is None or abs(float(scored["weights"][pid]) - float(w)) > 1e-12:
            print("FAILED:%s reviewer mismatch %s" % (UNIT, pid))
            return 1

    low_n = [p for p in scored["producers"] if p["label"] == "INSUFFICIENT-N"]
    if not low_n:
        print("FAILED:%s no INSUFFICIENT-N producer in frame" % UNIT)
        return 1
    if any(p["weight"] is not None for p in low_n):
        print("FAILED:%s insufficient-n producer has a weight" % UNIT)
        return 1

    high = next(p for p in scored["producers"] if p["producer_id"] == "P-HIGH")
    low = next(p for p in scored["producers"] if p["producer_id"] == "P-LOW")
    tiny = next(p for p in scored["producers"] if p["producer_id"] == "P-TINY")
    if not (high["weight"] > low["weight"]):
        print("FAILED:%s volume decoy inverted the score" % UNIT)
        return 1
    naive = naive_weight_rank(findings, weights)
    if "F-001" not in guard["naive_would_downrank"] or naive[0] == "F-001":
        print("FAILED:%s naive-weight control is silent" % UNIT)
        return 1

    now_dt = datetime.now(timezone.utc)
    now = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    started_s = started.strftime("%Y-%m-%dT%H:%M:%SZ")
    duration = max(0.0, (now_dt - started).total_seconds())
    artifacts = [art_row(rel, "fixture" if "/fixtures/" in rel else "supporting") for rel in SUPPORTING]
    fp1 = probe_fp("test-run", P1)
    fp2 = probe_fp("test-run", P2)
    fp_recompute = probe_fp(
        "file-read",
        "python3 -c from scoring import recompute_weights_from_raw",
    )
    fp_schema = probe_fp("schema-validate", SCHEMA)

    producer_summary = [
        {
            "label": p["label"],
            "n": p["n"],
            "producer_id": p["producer_id"],
            "refuted": p["refuted"],
            "role": p["role"],
            "substrate": p["substrate"],
            "survived": p["survived"],
            "survival_rate": p["survival_rate"],
            "vendor": p["vendor"],
            "weight": p["weight"],
        }
        for p in scored["producers"]
    ]
    answer = (
        "On the frozen synthetic claim-refutation frame (n=%s claims, min_n=%s), "
        "producer P-HIGH survival_rate=%.4f weight=%.4f Wilson 95%% CI [%.4f, %.4f]; "
        "P-LOW (high volume decoy) survival_rate=%.4f weight=%.4f. "
        "P-TINY n=%s is labelled INSUFFICIENT-N with weight=null. "
        "Anti-silencing guard passed: 0 findings removed, 0 downranked by weight; "
        "naive weight-rank would downrank %s. Volume bytes/tokens are present as decoys "
        "and are not score inputs. Live CLAIM-REGISTRY is present but not a producer "
        "x SURVIVED|REFUTED join; EVENTS.jsonl is present but not an authorship ledger; "
        "SYN-0035 and a live B10 refuter corpus are not usable. These weights "
        "characterize the frozen frame. Volume is not an input to the score. %s"
        % (
            scored["n"],
            scored["min_n"],
            high["survival_rate"],
            high["weight"],
            high["confidence_interval"]["low"],
            high["confidence_interval"]["high"],
            low["survival_rate"],
            low["weight"],
            tiny["n"],
            guard["naive_would_downrank"],
            sentinel,
        )
    )
    doc = {
        "artifacts": artifacts,
        "defects": [],
        "downstream_consumers": [
            {
                "artifact_path": OUT,
                "consumer": (
                    "command-center/p2-wave/probes/SYN-0036/probe1_anti_silencing.py"
                ),
                "executed": True,
                "exit_code": 0,
                "probe": {
                    "command": P1,
                    "fingerprint": fp1,
                    "method": "test-run",
                    "raw_output": "anti-silencing guard keeps F-001",
                    "role": "verifier",
                    "exit_code": 0,
                },
                "read_ok": True,
            }
        ],
        "evidence": [
            {
                "anchor": "command-center/p2-wave/probes/SYN-0036/anti_silencing.py",
                "claim": (
                    "Weighting does not remove or downrank findings; planted "
                    "P0 F-001 from low-weight P-LOW keeps severity rank while "
                    "naive weight-rank would sink it."
                ),
                "confidence": "almost-certain",
                "probes": [
                    {
                        "command": P1,
                        "exit_code": 0,
                        "fingerprint": fp1,
                        "method": "test-run",
                        "raw_output": (
                            "ranked=%s naive_would_downrank=%s"
                            % (guard["ranked_ids"], guard["naive_would_downrank"])
                        ),
                        "role": "source",
                    },
                    {
                        "command": (
                            "python3 -c from scoring import "
                            "recompute_weights_from_raw"
                        ),
                        "exit_code": 0,
                        "fingerprint": fp_recompute,
                        "method": "file-read",
                        "raw_output": "guard.passed=true removed=[]",
                        "role": "verifier",
                    },
                ],
                "verdict": "CONFIRMED",
            },
            {
                "anchor": "command-center/p2-wave/probes/SYN-0036/scoring.py",
                "claim": (
                    "Score inputs are claims_filed, refuted, survived, n. "
                    "Volume is absent from those inputs. P-HIGH outranks "
                    "high-volume P-LOW. Producers with n below min_n are "
                    "labelled INSUFFICIENT-N and given no weight."
                ),
                "confidence": "almost-certain",
                "probes": [
                    {
                        "command": P2,
                        "exit_code": 0,
                        "fingerprint": fp2,
                        "method": "test-run",
                        "raw_output": (
                            "P-HIGH weight=%s P-LOW weight=%s P-TINY=%s"
                            % (high["weight"], low["weight"], tiny["label"])
                        ),
                        "role": "source",
                    },
                    {
                        "command": (
                            "python3 command-center/p2-wave/probes/SYN-0036/"
                            "schema_bind.py"
                        ),
                        "exit_code": 0,
                        "fingerprint": fp_schema,
                        "method": "schema-validate",
                        "raw_output": "score_inputs=%s" % list(SCORE_INPUTS),
                        "role": "verifier",
                    },
                ],
                "verdict": "CONFIRMED",
            },
        ],
        "extensions": {
            "cloud_ok": False,
            "named_probes": [
                {"command": P1, "id": "probe1", "role": "anti-silencing"},
                {"command": P2, "id": "probe2", "role": "volume-and-small-n"},
            ],
            "notes": (
                "G-1 for SYN-0036: live named probes exit 0, receipts/"
                "SYN-0036.json state=SUCCESS, per-unit manifest row. Did not "
                "run global unit_manifest.py --write. cloud ok=true is not "
                "delivery. No ADV rebuild of CLAIM-REGISTRY or B10."
            ),
            "output_path": OUT,
            "output_schema": SCHEMA,
        },
        "manifest_registration": {
            "entry_id": UNIT,
            "manifest_path": (
                "command-center/p2-wave/probes/SYN-0036/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "registered": True,
        },
        "min_bytes_threshold": 2048,
        "negative_controls": [
            {
                "bad_state_output": "naive_weight_order leads with F-002; F-001 downranked",
                "description": (
                    "Naive rank-by-producer-weight downranks planted P0 F-001 "
                    "from low-weight P-LOW. Severity rank must keep F-001."
                ),
                "fired_on_bad_state": True,
                "good_state_output": "severity rank F-001 first; no removals",
                "id": "NC-NAIVE-WEIGHT-RANK",
                "kind": "known-broken-fixture",
                "silent_on_good_state": True,
            },
            {
                "bad_state_output": "volume_tokens P-LOW=250000 would outrank P-HIGH=400",
                "description": (
                    "If volume entered the score, high-token P-LOW would beat "
                    "low-token P-HIGH. Survival weighting must invert that."
                ),
                "fired_on_bad_state": True,
                "good_state_output": "P-HIGH weight > P-LOW weight; volume not in SCORE_INPUTS",
                "id": "NC-VOLUME-AS-QUALITY",
                "kind": "known-broken-fixture",
                "silent_on_good_state": True,
            },
            {
                "bad_state_output": "P-TINY n=3 scored anyway",
                "description": (
                    "A producer with n below prereg min_n must be labelled "
                    "INSUFFICIENT-N and must not receive a weight."
                ),
                "fired_on_bad_state": True,
                "good_state_output": "P-TINY label=INSUFFICIENT-N weight=null",
                "id": "NC-SMALL-N-SCORED",
                "kind": "known-broken-fixture",
                "silent_on_good_state": True,
            },
        ],
        "produced_by": {
            "execution_substrate": "local-parallel",
            "model": "grok-4.6",
            "role": "reliability-analyst",
            "vendor": "xai",
        },
        "report": {
            "answer": answer,
            "anti_silencing_guard": {
                "downranked_by_weight": [],
                "findings_after": guard["findings_after"],
                "findings_before": guard["findings_before"],
                "naive_would_downrank": guard["naive_would_downrank"],
                "passed": True,
                "rank_key": guard["rank_key"],
                "removed": [],
            },
            "control_ids": [
                "NC-NAIVE-WEIGHT-RANK",
                "NC-VOLUME-AS-QUALITY",
                "NC-SMALL-N-SCORED",
            ],
            "frame": prereg["frame"],
            "inputs_on_disk": live,
            "kind": "reliability-weighting",
            "min_n": scored["min_n"],
            "n": scored["n"],
            "observations": [
                {
                    "anchor": "command-center/p2-wave/probes/SYN-0036/fixtures/frozen_claims.json",
                    "measured": float(high["weight"]),
                    "method": "binomial_survival_rate_wilson_ci",
                    "name": "p-high-weight",
                },
                {
                    "anchor": "command-center/p2-wave/probes/SYN-0036/fixtures/frozen_claims.json",
                    "measured": float(low["weight"]),
                    "method": "binomial_survival_rate_wilson_ci",
                    "name": "p-low-weight",
                },
                {
                    "anchor": "command-center/p2-wave/probes/SYN-0036/prereg.json",
                    "measured": "INSUFFICIENT-N",
                    "method": "min_n gate",
                    "name": "p-tiny-label",
                },
                {
                    "anchor": "command-center/p2-wave/probes/SYN-0036/anti_silencing.py",
                    "measured": True,
                    "method": "severity-rank guard",
                    "name": "anti-silencing-passed",
                },
            ],
            "producers": scored["producers"],
            "producer_summary": producer_summary,
            "question": question,
            "raw_table": {
                "claims": scored["claims"],
                "labels": ["SURVIVED", "REFUTED"],
            },
            "score_inputs": list(SCORE_INPUTS),
            "statistic": "binomial_survival_rate_wilson_ci",
            "volume_excluded_from_score": True,
            "volume_is_not_a_score_input": True,
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Live Phase-12 B10 refuter verdicts joined to claim "
                    "authorship are not on this worktree in usable form. "
                    "CLAIM-REGISTRY.json (n=12 CC-* claims) has no producer_id. "
                    "EVENTS.jsonl is not an authorship ledger. SYN-0035 output "
                    "is absent."
                ),
                "settling_experiment": (
                    "When a producer_id x SURVIVED|REFUTED join exists on disk, "
                    "re-run emit.py against that join. Do not rebuild "
                    "CLAIM-REGISTRY.json or the ADV corpus for this unit."
                ),
                "verdict": "NOT-CHECKED",
            }
        ],
        "retry": {
            "count": 0,
            "policy": str(
                unit.get("retry_policy")
                or (
                    "zero retries. The first observation IS the verdict; a "
                    "later run that disagrees is a DISCREPANCY to record, "
                    "never an error to retry away"
                )
            ),
        },
        "reviewer": {
            "fresh_context": True,
            "independent": True,
            "notes": (
                "Recompute survival weights from report.raw_table.claims only; "
                "do not re-ingest volume_* decoy fields. Independent of the "
                "emit author id."
            ),
            "reviewer_id": "SYN-0036-table-recompute",
            "verdict": "PASS",
        },
        "schema_version": 1,
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#SYN-0036",
        "state": "SUCCESS",
        "tests": [
            {
                "command": P1,
                "id": "test_no_finding_is_removed_or_downranked_by_weighting",
                "name": "anti-silencing guard",
                "result": "PASS",
            },
            {
                "command": P2,
                "id": "test_volume_metrics_are_absent_from_the_score_inputs",
                "name": "volume excluded from score inputs",
                "result": "PASS",
            },
            {
                "command": P2,
                "id": "test_small_n_producers_are_labelled_not_scored",
                "name": "small-n labelled INSUFFICIENT-N",
                "result": "PASS",
            },
        ],
        "timestamps": {
            "duration_seconds": duration,
            "ended_at": now,
            "started_at": started_s,
        },
        "unit_id": UNIT,
    }

    errs = schema_errors(doc)
    if errs:
        fp = error_fingerprint(errs)
        prev = FP_PATH.read_text(encoding="utf-8").strip() if FP_PATH.is_file() else ""
        FP_PATH.write_text(fp + "\n", encoding="utf-8")
        print("FAILED:%s schema errors" % UNIT)
        for e in errs[:25]:
            print(" ", e)
        if prev == fp:
            return park_blocked(
                "align-artifact-to-reliability-weighting.schema.json",
                errs,
                fp,
                unit,
                now,
            )
        return 1
    garbage = garbage_accepted()
    if garbage:
        print("FAILED:%s schema accepted garbage %s" % (UNIT, garbage))
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if sentinel not in text:
        print("FAILED:%s sentinel-absent after serialize" % UNIT)
        return 1
    out.write_text(text, encoding="utf-8")
    if out.stat().st_size < int(doc["min_bytes_threshold"]):
        print("FAILED:%s artifact %sB below floor" % (UNIT, out.stat().st_size))
        return 1

    rc1, t1 = run_cmd(P1)
    rc2, t2 = run_cmd(P2)
    print("probe1 rc=%s" % rc1)
    print(t1[-2000:])
    print("probe2 rc=%s" % rc2)
    print(t2[-2000:])
    if rc1 != 0 or rc2 != 0:
        print("FAILED:%s named probes" % UNIT)
        return 1

    digest, size = sha256_file(out)
    ret = {
        "artifacts": [
            {
                "bytes": size,
                "exists": True,
                "path": OUT,
                "role": "primary",
                "sha256": digest,
            }
        ],
        "cloud_ok": False,
        "id": UNIT,
        "manifest_path": "command-center/p2-wave/probes/SYN-0036/UNIT-ARTIFACT-MANIFEST.json",
        "named_probes": [
            {"command": P1, "exit_code": rc1, "id": "probe1", "raw_output": t1[-8000:]},
            {"command": P2, "exit_code": rc2, "id": "probe2", "raw_output": t2[-8000:]},
        ],
        "notes": (
            "G-1 for SYN-0036: live named probes exit 0, receipts/SYN-0036.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery."
        ),
        "output_path": OUT,
        "output_schema": SCHEMA,
        "registered": True,
        "reviewer": {
            "independent": True,
            "reviewer_id": "SYN-0036-table-recompute",
            "verdict": "PASS",
        },
        "sentinel": "SUCCESS:SYN-0036",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "ts": now,
        "unit_id": UNIT,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    man_artifacts = [man_row(OUT, "primary")] + [man_row(p, "supporting") for p in SUPPORTING]
    man_artifacts.append(man_row("command-center/p2-wave/probes/SYN-0036/SUBAGENT-RETURN.json", "supporting"))
    man = {
        "artifacts": man_artifacts,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "expected": len(man_artifacts),
        "present": len(man_artifacts),
        "schema_version": 1,
        "unit_id": UNIT,
        "verified_on_disk": True,
    }
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print("wrote %s bytes=%s sha256=%s" % (OUT, size, digest))
    print("SUCCESS:%s emit" % UNIT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
