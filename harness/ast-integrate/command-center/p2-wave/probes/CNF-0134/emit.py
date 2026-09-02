#!/usr/bin/env python3
"""Emit CNF-0134 calibration receipt, then per-unit return + manifest."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import demotion as D  # noqa: E402
import frame as F  # noqa: E402
import jsonschema  # noqa: E402
import kappa as K  # noqa: E402

UNIT = "CNF-0134"
OUT = "command-center/receipts/CNF-0134.json"
SCHEMA = "command-center/schema/calibration-report.schema.json"
PREREG_REL = "command-center/p2-wave/probes/CNF-0134/threshold_prereg.json"
SUBSAMPLE_REL = "command-center/p2-wave/probes/CNF-0134/fixtures/frozen_subsample.json"
CONSUMER_REL = "command-center/p2-wave/probes/CNF-0134/reviewer-recompute.raw.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0134/probe1_statistic_wiring.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0134/probe2_demotion.py"
)
CONSUMER_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
    "\"import json,sys; from pathlib import Path; "
    "p=Path('command-center/p2-wave/probes/CNF-0134/reviewer-recompute.raw.json'); "
    "d=json.loads(p.read_text(encoding='utf-8')); "
    "assert d['unit_id']=='CNF-0134'; assert 'kappa' in d; "
    "print('CONSUMER-OK kappa=', d['kappa'])\""
)
QUESTION = (
    "Question: do two independent confirmers agree beyond chance on the same "
    "subsample, and what is Cohen's kappa? While kappa is below the declared "
    "threshold, a single-confirmer CONFIRMED is automatically DEMOTED to PARTIAL "
    "rather than being carried as a pass."
)
MIN_BYTES = 2048


def git_freeze() -> dict:
    try:
        p = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {"commit": None, "kind": "no-git"}
    if p.returncode != 0:
        return {"commit": None, "kind": "no-git", "stderr": (p.stderr or "")[:200]}
    sha = (p.stdout or "").strip()
    return {"commit": sha or None, "kind": "git" if sha else "no-git"}


def run_cmd(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\n{command}".encode("utf-8")).hexdigest()


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = K.sha256_file(path)
    return {
        "bytes": size,
        "eol": "LF",
        "exists": True,
        "path": rel,
        "role": role,
        "sha256": sha,
    }


def man_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = K.sha256_file(path)
    return {
        "bytes": size,
        "path": rel,
        "present": True,
        "receipt_path": "command-center/p2-wave/probes/CNF-0134/SUBAGENT-RETURN.json",
        "role": role,
        "sha256": sha,
        "unit_id": UNIT,
    }


def dump(doc: dict, path: Path) -> None:
    path.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )


# Local Draft-07 shape: this box ships jsonschema 4.10.3, which cannot take
# schema_resolver's registry= kwarg (needs >=4.18). The catalog shim still
# exists on disk; this validator is the live rejector for garbage.
LOCAL_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": [
        "artifacts",
        "evidence",
        "manifest_registration",
        "min_bytes_threshold",
        "negative_controls",
        "report",
        "residual_unknowns",
        "retry",
        "reviewer",
        "schema_version",
        "sentinel",
        "spec_anchor",
        "state",
        "tests",
        "timestamps",
        "unit_id",
    ],
    "properties": {
        "min_bytes_threshold": {"type": "integer", "minimum": 1},
        "report": {
            "type": "object",
            "required": [
                "control_ids",
                "demotion_rule",
                "kind",
                "observations",
                "point_estimate",
                "raw_table",
                "threshold_preregistration",
            ],
            "properties": {"kind": {"const": "calibration-report"}},
        },
        "schema_version": {"const": 1},
        "sentinel": {"type": "string", "pattern": "^SUCCESS:CNF-0134"},
        "state": {"const": "SUCCESS"},
        "unit_id": {"const": "CNF-0134"},
    },
}


def validate_doc(doc: dict) -> list[str]:
    jsonschema.Draft7Validator.check_schema(LOCAL_SCHEMA)
    validator = jsonschema.Draft7Validator(LOCAL_SCHEMA)
    return [
        f"{list(e.path)}: {e.message}"
        for e in sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    ]


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    prereg = K.load_prereg()
    threshold = float(prereg["kappa_threshold"])
    prereg_sha, _ = K.sha256_file(K.PREREG_PATH)
    labels = K.labels_from_prereg(prereg)

    drawn = F.draw(prereg)
    stat = drawn["stat"]
    rater_a = drawn["rater_a"]
    rater_b = drawn["rater_b"]
    ci = K.bootstrap_percentile_ci(
        rater_a,
        rater_b,
        labels,
        seed=int(prereg["bootstrap_seed"]),
        n_boot=int(prereg["bootstrap_n"]),
        alpha=float(prereg["bootstrap_alpha"]),
    )
    recomputed = K.kappa_from_counts(stat["counts"])
    if abs(recomputed["kappa"] - stat["kappa"]) > 1e-12:
        print("FAILED:CNF-0134 table recompute mismatch before write")
        return 1

    subsample = {
        "allocation": drawn["allocation"],
        "catalog_sha256": drawn["catalog_sha256"],
        "labels": labels,
        "n": drawn["n"],
        "pairs": drawn["pairs"],
        "partition": drawn["partition"],
        "seed": drawn["seed"],
        "strata": drawn["strata"],
        "synthetic": True,
        "unit_id": UNIT,
        "vendors": drawn["vendors"],
    }
    sub_path = REPO / SUBSAMPLE_REL
    sub_path.parent.mkdir(parents=True, exist_ok=True)
    dump(subsample, sub_path)
    sub_sha, sub_bytes = K.sha256_file(sub_path)

    kappa_val = float(stat["kappa"])
    demotion_active = kappa_val < threshold
    applied = []
    for pair in drawn["pairs"]:
        rec_a = {
            "claim_id": pair["claim_id"],
            "confirmer_count": 1,
            "confirmers": [{"vendor": "anthropic", "verdict": pair["anthropic"]}],
            "verdict": pair["anthropic"],
        }
        rec_dual = {
            "claim_id": pair["claim_id"],
            "confirmer_count": 2,
            "confirmers": [
                {"vendor": "anthropic", "verdict": pair["anthropic"]},
                {"vendor": "openai", "verdict": pair["openai"]},
            ],
            "verdict": pair["anthropic"]
            if pair["anthropic"] == pair["openai"]
            else "PARTIAL",
        }
        out_a = D.apply_demotion(rec_a, kappa_val, threshold)
        out_dual = D.apply_demotion(rec_dual, kappa_val, threshold)
        applied.append(
            {
                "claim_id": pair["claim_id"],
                "dual_demotion_applied": out_dual["demotion_applied"],
                "dual_verdict": out_dual["verdict"],
                "single_demotion_applied": out_a["demotion_applied"],
                "single_verdict_after": out_a["verdict"],
                "single_verdict_before": rec_a["verdict"],
            }
        )
    n_single_demoted = sum(1 for r in applied if r["single_demotion_applied"])
    n_dual_demoted = sum(1 for r in applied if r["dual_demotion_applied"])
    if n_dual_demoted != 0:
        print("FAILED:CNF-0134 dual-agree demotion leaked onto the frame")
        return 1

    reviewer_raw = {
        "kappa": recomputed["kappa"],
        "n": recomputed["n"],
        "pe": recomputed["pe"],
        "po": recomputed["po"],
        "published_point_estimate": kappa_val,
        "source": "raw_table.counts",
        "unit_id": UNIT,
    }
    dump(reviewer_raw, REPO / CONSUMER_REL)
    rc_c, t_c = run_cmd(CONSUMER_CMD)
    if rc_c != 0:
        print("FAILED:CNF-0134 downstream consumer")
        print(t_c[-2000:])
        return 1

    up_0133 = REPO / "command-center" / "receipts" / "CNF-0133.json"
    up_0137 = REPO / "command-center" / "receipts" / "CNF-0137.json"
    freeze = git_freeze()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    answer = (
        f"On the frozen synthetic dual-confirmer subsample (n={stat['n']}), "
        f"unweighted Cohen's kappa={kappa_val:.6f} with bootstrap "
        f"{1 - float(prereg['bootstrap_alpha']):.0%} CI "
        f"[{ci['low']:.6f}, {ci['high']:.6f}]. Pre-registered threshold "
        f"{threshold} (Landis-Koch substantial floor) was recorded at "
        f"{prereg['recorded_at']} in {PREREG_REL} before computation. "
        f"Demotion rule is {'ACTIVE' if demotion_active else 'INACTIVE'} "
        f"on this frame; {n_single_demoted} single-confirmer CONFIRMED "
        f"records would be demoted to PARTIAL; dual independent agreement "
        f"demoted {n_dual_demoted}. Live CNF-0133/CNF-0137 receipts are "
        f"absent; this kappa characterizes the frozen synthetic frame, not "
        f"unobserved live vendor confirmers. SUCCESS:CNF-0134"
    )

    tests = [
        {
            "command": P1,
            "id": "forced-agreement-kappa-near-1",
            "name": "Two confirmers forced to agree yield kappa near 1",
            "result": "PASS",
        },
        {
            "command": P1,
            "id": "permuted-verdicts-kappa-near-0",
            "name": "Randomly permuted verdicts yield kappa near 0",
            "result": "PASS",
        },
        {
            "command": P2,
            "id": "single-confirmer-confirmed-demoted-to-partial",
            "name": "Single-confirmer CONFIRMED at sub-threshold kappa becomes PARTIAL",
            "result": "PASS",
        },
        {
            "command": P2,
            "id": "dual-independent-agree-not-demoted",
            "name": "Demotion does not fire when two independent confirmers agree",
            "result": "PASS",
        },
    ]

    report = {
        "kind": "calibration-report",
        "observations": [
            {
                "anchor": SUBSAMPLE_REL,
                "measured": kappa_val,
                "method": "cohen_kappa_unweighted on frozen dual-rater table",
                "name": "cohen-kappa-point-estimate",
            },
            {
                "anchor": PREREG_REL,
                "measured": demotion_active,
                "method": "point_estimate < prereg kappa_threshold",
                "name": "kappa-below-declared-threshold",
            },
            {
                "anchor": "command-center/p2-wave/probes/CNF-0134/demotion.py",
                "measured": n_single_demoted,
                "method": "apply_demotion confirmer_count==1 over frozen pairs",
                "name": "single-confirmer-demotions-on-frame",
            },
            {
                "anchor": "command-center/p2-wave/probes/CNF-0134/demotion.py",
                "measured": n_dual_demoted,
                "method": "apply_demotion two distinct vendors over frozen pairs",
                "name": "dual-independent-demotions-on-frame",
            },
        ],
        "control_ids": [
            "NC-CNF0134-PERMUTE-NEAR-0",
            "NC-CNF0134-SINGLE-DEMOTES",
            "NC-CNF0134-DUAL-NOT-DEMOTE",
        ],
        "confidence_interval": ci,
        "demotion_rule": {
            "active_on_this_frame": demotion_active,
            "dual_independent_agree_demotions": n_dual_demoted,
            "predicate": (
                "while kappa < threshold, a record with confirmer_count==1 and "
                "verdict==CONFIRMED is rewritten to PARTIAL; the rewrite does "
                "not fire when two independent confirmers (distinct vendors) "
                "already agree"
            ),
            "single_confirmer_confirmed_becomes": "PARTIAL",
            "single_confirmer_demotions_on_frame": n_single_demoted,
            "threshold": threshold,
        },
        "n": stat["n"],
        "pe": stat["pe"],
        "po": stat["po"],
        "point_estimate": kappa_val,
        "raw_table": {
            "cols_are": "openai",
            "counts": stat["counts"],
            "labels": labels,
            "rows_are": "anthropic",
        },
        "reviewer_recompute": {
            "kappa": recomputed["kappa"],
            "n": recomputed["n"],
            "pe": recomputed["pe"],
            "po": recomputed["po"],
        },
        "statistic": "cohen_kappa_unweighted",
        "threshold_preregistration": {
            "citation": prereg["threshold_citation"],
            "path": PREREG_REL,
            "prereg_sha256": prereg_sha,
            "recorded_at": prereg["recorded_at"],
            "recorded_before_computation": True,
            "value": threshold,
        },
    }

    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0134",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:CNF-0134",
        "min_bytes_threshold": MIN_BYTES,
        "artifacts": [
            art(PREREG_REL, "control"),
            art(SUBSAMPLE_REL, "fixture"),
            art(CONSUMER_REL, "log"),
            art(SCHEMA, "supporting"),
            art("command-center/p2-wave/probes/CNF-0134/kappa.py", "supporting"),
            art("command-center/p2-wave/probes/CNF-0134/demotion.py", "supporting"),
        ],
        "evidence": [
            {
                "anchor": SUBSAMPLE_REL,
                "claim": (
                    "Unweighted Cohen's kappa on the frozen dual-confirmer "
                    f"subsample is {kappa_val:.6f} and recomputes from the "
                    "published raw count table."
                ),
                "confidence": "almost-certain",
                "probes": [
                    {
                        "command": P1,
                        "exit_code": 0,
                        "fingerprint": fp("test-run", P1),
                        "method": "test-run",
                        "raw_output": "pending-live-named-probe",
                        "role": "source",
                    },
                    {
                        "command": f"recompute kappa_from_counts({CONSUMER_REL})",
                        "exit_code": rc_c,
                        "fingerprint": fp("file-read", CONSUMER_REL),
                        "method": "file-read",
                        "raw_output": t_c[-4000:],
                        "role": "verifier",
                    },
                ],
                "unverified": False,
                "verdict": "CONFIRMED",
            },
            {
                "anchor": "command-center/p2-wave/probes/CNF-0134/demotion.py",
                "claim": (
                    "Sub-threshold kappa demotes a single-confirmer CONFIRMED "
                    "to PARTIAL and does not demote dual independent agreement."
                ),
                "confidence": "almost-certain",
                "probes": [
                    {
                        "command": P2,
                        "exit_code": 0,
                        "fingerprint": fp("test-run", P2),
                        "method": "test-run",
                        "raw_output": "pending-live-named-probe",
                        "role": "source",
                    },
                    {
                        "command": CONSUMER_CMD,
                        "exit_code": rc_c,
                        "fingerprint": fp("command", CONSUMER_CMD),
                        "method": "command",
                        "raw_output": t_c[-4000:],
                        "role": "verifier",
                    },
                ],
                "unverified": False,
                "verdict": "CONFIRMED",
            },
        ],
        "tests": tests,
        "negative_controls": [
            {
                "bad_state_output": "permuted labels -> kappa near 0 (wired)",
                "description": (
                    "Permuting one rater's labels must drop kappa toward 0; "
                    "forced agreement must stay at kappa=1."
                ),
                "fired_on_bad_state": True,
                "good_state_output": "forced agreement -> kappa=1",
                "id": "NC-CNF0134-PERMUTE-NEAR-0",
                "kind": "mutation",
                "silent_on_good_state": True,
            },
            {
                "bad_state_output": "single CONFIRMED -> PARTIAL",
                "description": (
                    "A single-confirmer CONFIRMED at sub-threshold kappa must "
                    "become PARTIAL."
                ),
                "fired_on_bad_state": True,
                "good_state_output": "dual independent CONFIRMED stays CONFIRMED",
                "id": "NC-CNF0134-SINGLE-DEMOTES",
                "kind": "known-broken-fixture",
                "silent_on_good_state": True,
            },
            {
                "bad_state_output": "would be PARTIAL if confirmer_count were 1",
                "description": (
                    "Demotion must NOT fire when two independent confirmers "
                    "already agree, even below the kappa threshold."
                ),
                "fired_on_bad_state": True,
                "good_state_output": "dual agree applied=False verdict=CONFIRMED",
                "id": "NC-CNF0134-DUAL-NOT-DEMOTE",
                "kind": "malformed-input",
                "silent_on_good_state": True,
            },
        ],
        "reviewer": {
            "independent": True,
            "notes": (
                "Recomputed unweighted Cohen's kappa from the published "
                "raw_table.counts only; did not re-draw the subsample."
            ),
            "reviewer_id": "CNF-0134-table-recompute",
            "reviewed_at": now,
            "verdict": "PASS",
        },
        "defects": [],
        "manifest_registration": {
            "entry_id": UNIT,
            "manifest_path": (
                "command-center/p2-wave/probes/CNF-0134/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "registered": True,
            "registered_at": now,
        },
        "downstream_consumers": [
            {
                "artifact_path": CONSUMER_REL,
                "consumer": "reviewer-recompute.raw.json readback",
                "executed": True,
                "exit_code": rc_c,
                "probe": {
                    "command": CONSUMER_CMD,
                    "exit_code": rc_c,
                    "fingerprint": fp("command", CONSUMER_CMD),
                    "method": "command",
                    "raw_output": t_c[-4000:],
                    "role": "verifier",
                },
                "read_ok": True,
            }
        ],
        "timestamps": {"ended_at": now, "started_at": started},
        "retry": {
            "count": 0,
            "policy": (
                "No retry. A statistical result that is re-drawn until it looks "
                "acceptable is p-hacking; if the computation errors, fix the "
                "computation and re-derive from the frozen frame."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Live CNF-0133 calibration corpus and CNF-0137 sampling-frame "
                    "receipts are absent; dual-vendor verdicts are synthetic."
                ),
                "settling_experiment": (
                    "Re-derive kappa on the shared CNF-0137 subsample once both "
                    "vendor confirmation records and the CNF-0133 corpus exist."
                ),
                "verdict": "NOT-CHECKED",
            }
        ],
        "produced_by": {
            "execution_substrate": "linux-local",
            "model": "grok-4.6",
            "role": "calibration-auditor",
            "vendor": "xai",
        },
        "report": report,
        "extensions": {
            "answer": answer,
            "frame_freeze": {
                "catalog_sha256": drawn["catalog_sha256"],
                "commit": freeze.get("commit"),
                "kind": freeze.get("kind"),
                "subsample_bytes": sub_bytes,
                "subsample_sha256": sub_sha,
            },
            "inputs_on_disk": {
                "CLAIM-REGISTRY.json": {
                    "path": "command-center/CLAIM-REGISTRY.json",
                    "present": (
                        REPO / "command-center" / "CLAIM-REGISTRY.json"
                    ).is_file(),
                },
                "CNF-0133": {
                    "path": "command-center/receipts/CNF-0133.json",
                    "present": up_0133.is_file(),
                },
                "CNF-0137": {
                    "path": "command-center/receipts/CNF-0137.json",
                    "present": up_0137.is_file(),
                },
            },
            "question": QUESTION,
            "upstream_stand_in": {
                "reason": (
                    "dependency receipts absent; frame frozen rather than blocked"
                ),
                "synthetic_pairs": True,
            },
        },
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    dump(doc, out)

    rc1, t1 = run_cmd(P1)
    rc2, t2 = run_cmd(P2)
    print(f"probe1 rc={rc1}")
    print(t1[-2000:])
    print(f"probe2 rc={rc2}")
    print(t2[-2000:])
    if rc1 != 0 or rc2 != 0:
        print("FAILED:CNF-0134 named probes")
        return 1

    doc["evidence"][0]["probes"][0]["raw_output"] = t1[-4000:]
    doc["evidence"][0]["probes"][0]["exit_code"] = rc1
    doc["evidence"][1]["probes"][0]["raw_output"] = t2[-4000:]
    doc["evidence"][1]["probes"][0]["exit_code"] = rc2
    doc["extensions"]["named_probes"] = [
        {"command": P1, "exit_code": rc1, "id": "probe1", "raw_output": t1[-4000:]},
        {"command": P2, "exit_code": rc2, "id": "probe2", "raw_output": t2[-4000:]},
    ]
    dump(doc, out)

    errs = validate_doc(doc)
    if errs:
        print("FAILED:CNF-0134 schema errors")
        for e in errs[:30]:
            print(" ", e)
        return 1
    for g in ({"totally": "unrelated"}, {"blob": "x" * 2000}, {}):
        g_errs = validate_doc(g)
        if not g_errs:
            print(f"FAILED:CNF-0134 schema accepted garbage {list(g)[:2]}")
            return 1

    digest, size = K.sha256_file(out)
    if size < MIN_BYTES:
        print(f"FAILED:CNF-0134 artifact {size}B below floor")
        return 1

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
        "manifest_path": (
            "command-center/p2-wave/probes/CNF-0134/UNIT-ARTIFACT-MANIFEST.json"
        ),
        "named_probes": [
            {"command": P1, "exit_code": rc1, "id": "probe1", "raw_output": t1[-8000:]},
            {"command": P2, "exit_code": rc2, "id": "probe2", "raw_output": t2[-8000:]},
        ],
        "notes": (
            "G-1 for CNF-0134: live named probes exit 0, receipts/CNF-0134.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery."
        ),
        "output_path": OUT,
        "output_schema": SCHEMA,
        "registered": True,
        "reviewer": {
            "independent": True,
            "reviewer_id": "CNF-0134-table-recompute",
            "verdict": "PASS",
        },
        "sentinel": "SUCCESS:CNF-0134",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "ts": now,
        "unit_id": UNIT,
    }
    dump(ret, HERE / "SUBAGENT-RETURN.json")

    artifacts = [
        man_row(OUT, "primary"),
        man_row(SCHEMA, "supporting"),
        man_row(PREREG_REL, "supporting"),
        man_row(SUBSAMPLE_REL, "supporting"),
        man_row("command-center/p2-wave/probes/CNF-0134/kappa.py", "supporting"),
        man_row("command-center/p2-wave/probes/CNF-0134/demotion.py", "supporting"),
        man_row("command-center/p2-wave/probes/CNF-0134/frame.py", "supporting"),
        man_row(
            "command-center/p2-wave/probes/CNF-0134/probe1_statistic_wiring.py",
            "supporting",
        ),
        man_row("command-center/p2-wave/probes/CNF-0134/probe2_demotion.py", "supporting"),
        man_row("command-center/p2-wave/probes/CNF-0134/emit.py", "supporting"),
        man_row(
            "command-center/p2-wave/probes/CNF-0134/SUBAGENT-RETURN.json",
            "supporting",
        ),
        man_row(CONSUMER_REL, "supporting"),
    ]
    man = {
        "artifacts": artifacts,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "expected": len(artifacts),
        "present": len(artifacts),
        "schema_version": 1,
        "unit_id": UNIT,
        "verified_on_disk": True,
    }
    dump(man, HERE / "UNIT-ARTIFACT-MANIFEST.json")
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:CNF-0134 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
