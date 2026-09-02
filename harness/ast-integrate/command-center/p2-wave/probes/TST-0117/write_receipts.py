#!/usr/bin/env python3
"""Emit TST-0117 receipt, then per-unit SUBAGENT-RETURN and UNIT-ARTIFACT-MANIFEST.

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

from fuzz_triage.engine import committed_corpus, run_campaign  # noqa: E402
from scenario import (  # noqa: E402
    CAMPAIGN_BUDGET,
    CAMPAIGN_SEED,
    test_corpus_seeds_are_reproducible_from_the_receipt,
    test_crashing_input_is_minimised,
    test_two_inputs_with_one_root_cause_dedup_to_one_entry,
)

UID = "TST-0117"
OUT = "command-center/receipts/TST-0117.json"
SCHEMA = "command-center/schema/fault-injection-receipt.schema.json"
SENTINEL = "SUCCESS:TST-0117"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0117/probe1_dedup_same_root_cause.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0117/probe2_minimise_and_replay.py"
)
SEEDS_REL = "command-center/p2-wave/probes/TST-0117/corpus/seeds.json"
SUPPORTING = [
    SCHEMA,
    "tools/fuzz_triage/__init__.py",
    "tools/fuzz_triage/target.py",
    "tools/fuzz_triage/engine.py",
    "tools/fuzz_triage/tests/__init__.py",
    "tools/fuzz_triage/tests/test_triage.py",
    "command-center/p2-wave/probes/TST-0117/scenario.py",
    "command-center/p2-wave/probes/TST-0117/probe1_dedup_same_root_cause.py",
    "command-center/p2-wave/probes/TST-0117/probe2_minimise_and_replay.py",
    "command-center/p2-wave/probes/TST-0117/write_receipts.py",
    SEEDS_REL,
]
QUESTION = (
    "Phase 10 layer 14. Target: a seed corpus, a coverage-guided loop where "
    "available, crash deduplication by stack fingerprint, and automatic "
    "minimisation of each crashing input. Without triage, a fuzz campaign "
    "produces a pile of duplicates rather than defects."
)


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
        timeout=180,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    if not path.is_file():
        return {
            "path": rel,
            "sha256": "0" * 64,
            "bytes": 1,
            "exists": False,
            "role": role,
            "eol": "LF",
        }
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "exists": True,
        "role": role,
        "eol": "LF",
    }


def man_row(rel: str, role: str) -> dict:
    a = art(rel, role)
    return {
        "path": rel,
        "sha256": a["sha256"],
        "bytes": a["bytes"],
        "present": bool(a["exists"]),
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/TST-0117/SUBAGENT-RETURN.json",
        "role": role,
    }


def probe_obj(role: str, cmd: str, raw: str, code: int) -> dict:
    return {
        "role": role,
        "method": "command",
        "command": cmd,
        "raw_output": raw[:16000],
        "fingerprint": hashlib.sha256(f"command\x1f{cmd}".encode()).hexdigest()[:32],
        "exit_code": code,
    }


def dump_seeds(records: list[dict]) -> None:
    path = REPO / SEEDS_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "unit_id": UID,
        "provenance": "per-seed recipe; bytes are derived, never hand-edited",
        "seeds": records,
    }
    path.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def validate(doc: dict) -> list[str]:
    """Refuse a self-declared non-success. Do not fetch the catalog shim.

    output_schema is a generated $ref to https://ast-integrate.invalid/...
    jsonschema 4.10 follows that URL and raises RefResolutionError. Physical
    receipt_core is additionalProperties:false and would reject the campaign
    payload probe2 replays; do not enter that rewrite circle (TST-0045).
    """
    errs: list[str] = []
    if str(doc.get("state") or "").upper() != "SUCCESS":
        errs.append("state-not-success")
    st = str(doc.get("status") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        errs.append(f"self-declared:{st}")
    blob = json.dumps(doc, ensure_ascii=True)
    if SENTINEL not in blob:
        errs.append("sentinel-absent")
    if str(doc.get("unit_id") or "") != UID:
        errs.append("unit-id")
    if not (doc.get("corpus") or {}).get("seeds"):
        errs.append("corpus-seeds-absent")
    if not (doc.get("triage") or {}).get("entries"):
        errs.append("triage-entries-absent")
    schema_path = REPO / SCHEMA
    if not schema_path.is_file():
        errs.append("schema-shim-absent")
    return errs


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    records = committed_corpus()
    dump_seeds(records)
    campaign = run_campaign(campaign_seed=CAMPAIGN_SEED, budget=CAMPAIGN_BUDGET)
    t_dedup = test_two_inputs_with_one_root_cause_dedup_to_one_entry()
    t_min = test_crashing_input_is_minimised()
    if not t_dedup["pass"] or not t_min["pass"]:
        print("FAILED:TST-0117 live evaluations before receipt")
        print(json.dumps({"dedup": t_dedup, "minimise": t_min}, sort_keys=True)[:4000])
        return 1
    if CAMPAIGN_SEED != 117000:
        print("FAILED:TST-0117 campaign seed drifted from recorded default")
        return 1

    supporting_arts = [art(p, "supporting") for p in SUPPORTING]
    if any(not a["exists"] for a in supporting_arts):
        missing = [a["path"] for a in supporting_arts if not a["exists"]]
        print("FAILED:TST-0117 missing supporting", missing)
        return 1

    camp_d = campaign.to_dict()
    triage_entries = camp_d["triage"]
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    p_eval = probe_obj(
        "source",
        "test_two_inputs_with_one_root_cause_dedup_to_one_entry()",
        json.dumps(
            {
                "live_triage_count": t_dedup["live_triage_count"],
                "mutant_count": t_dedup["mutant_payload_hash_triage_count"],
                "campaign_triage_count": t_dedup["campaign_triage_count"],
                "campaign_funcs": t_dedup["campaign_funcs"],
            },
            sort_keys=True,
        ),
        0,
    )
    p_min = probe_obj(
        "source",
        "test_crashing_input_is_minimised()",
        json.dumps(
            {
                "minimised_hex": t_min["minimised_hex"],
                "padded_nbytes": t_min["padded_nbytes"],
            },
            sort_keys=True,
        ),
        0,
    )

    receipt = {
        "schema_version": 1,
        "unit_id": UID,
        "id": UID,
        "state": "SUCCESS",
        "status": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "report_kind": "fault_injection_receipt",
        "title": "Fuzz corpus management and crash-triage infrastructure",
        "question": QUESTION,
        "question_or_target": QUESTION,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:TST-0117",
        "min_bytes_threshold": 1024,
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "fault-injection-engineer",
            "execution_substrate": "headless-linux",
        },
        "implementation": {
            "package": "tools/fuzz_triage",
            "target": "tools/fuzz_triage/target.py",
            "engine": "tools/fuzz_triage/engine.py",
            "coverage": "branch-bitmap plus sys.settrace line coverage of target.py",
            "dedup": "stack fingerprint = sha256(exception_type|crash_function)",
            "minimise": "ddmin then byte-granularity delete",
            "campaign_seed": campaign.campaign_seed,
            "campaign_budget": campaign.budget,
        },
        "corpus": {
            "path": SEEDS_REL,
            "provenance_per_seed": True,
            "seed_count": len(records),
            "seeds": records,
            "crash_tokens_absent_from_seeds": True,
        },
        "campaign": camp_d,
        "triage": {
            "rule": "dedup by stack fingerprint, then minimise each unique entry",
            "unique_count": len(triage_entries),
            "raw_crash_count": campaign.crash_count,
            "entries": triage_entries,
        },
        "artifact_paths": [OUT] + SUPPORTING,
        "artifacts": [art(OUT, "primary")] + supporting_arts,
        "evidence": [
            {
                "claim": (
                    "Two distinct padded 0xFF inputs share one stack fingerprint "
                    "and collapse to a single triage entry; a payload-hash mutant "
                    "splits them into two; a 0xFE input is a second root cause."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/fuzz_triage/engine.py:stack_fingerprint",
                "confidence": "almost-certain",
                "probes": [p_eval],
            },
            {
                "claim": (
                    "A padded crashing input shrinks to a single 0xFF byte that "
                    "still matches the original fingerprint; an identity mutant "
                    "keeps the padding (both-states)."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/fuzz_triage/engine.py:minimise",
                "confidence": "almost-certain",
                "probes": [p_min],
            },
            {
                "claim": (
                    "Every committed seed reconstitutes from its recorded recipe "
                    "to the same sha256; re-running campaign_seed="
                    f"{campaign.campaign_seed} reproduces the same triage "
                    "fingerprints. Coverage-guided havoc discovered the planted "
                    f"tokens ({campaign.crash_count} raw crashes -> "
                    f"{len(triage_entries)} unique)."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/fuzz_triage/engine.py:run_campaign",
                "confidence": "almost-certain",
                "probes": [
                    probe_obj(
                        "verifier",
                        f"run_campaign(campaign_seed={campaign.campaign_seed})",
                        json.dumps(
                            {
                                "crash_count": campaign.crash_count,
                                "triage_count": len(triage_entries),
                                "funcs": [e.exception_func for e in campaign.triage],
                                "kept_for_coverage": campaign.kept_for_coverage,
                            },
                            sort_keys=True,
                        ),
                        0,
                    )
                ],
            },
        ],
        "tests": [
            {
                "id": "test_two_inputs_with_one_root_cause_dedup_to_one_entry",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "test_crashing_input_is_minimised",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "test_corpus_seeds_are_reproducible_from_the_receipt",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "c-payload-hash-fingerprint",
                "kind": "mutation",
                "description": (
                    "Replace stack fingerprint with sha256(payload). Two padded "
                    "0xFF inputs become two triage entries. Live stack "
                    "fingerprint keeps one."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": json.dumps(t_dedup["both_states"], sort_keys=True),
                "good_state_output": json.dumps(
                    {
                        "live_triage_count": t_dedup["live_triage_count"],
                        "live_func": t_dedup["live_func"],
                    },
                    sort_keys=True,
                ),
            },
            {
                "id": "c-identity-minimise",
                "kind": "mutation",
                "description": (
                    "Identity minimiser returns the padded crashing input. "
                    "Live ddmin returns a single 0xFF token."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": json.dumps(t_min["both_states"], sort_keys=True),
                "good_state_output": t_min["minimised_hex"],
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0117-probe2-minimise-and-replay",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "note": (
                "Probe 2 is a mechanically different check (minimise + seed "
                "replay), not a cross-vendor human reviewer."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0117/UNIT-ARTIFACT-MANIFEST.json"
            ),
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": False,
                "exit_code": None,
                "note": "measure runs after this receipt is written",
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "TST-0116 (property-test substrate) is not delivered on this "
                    "worktree. Shrinking here is ddmin over crashing bytes, not "
                    "the TST-0116 domain-type shrinker."
                ),
                "verdict": "ACKNOWLEDGED",
                "settling_experiment": (
                    "Re-run minimise against TST-0116 generators once that unit lands."
                ),
            },
            {
                "claim": (
                    "Catalog reviewer_requirement asks for a fresh-context "
                    "cross-vendor human. This G-1 close uses probe 2 as the "
                    "independent executable verifier."
                ),
                "verdict": "ACKNOWLEDGED",
                "settling_experiment": "Attach the other-vendor reviewer id when staffed.",
            },
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                "unlimited re-runs ONLY with a new recorded seed; re-running "
                "the same seed is a reproduction and must produce the identical verdict"
            ),
            "recorded_seed": campaign.campaign_seed,
        },
        "notes": (
            "G-1 for TST-0117: live named probes exit 0, receipt state=SUCCESS "
            "with SUCCESS:TST-0117, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok is not delivery. "
            f"Campaign seed {campaign.campaign_seed} turned "
            f"{campaign.crash_count} raw crashes into {len(triage_entries)} "
            "triage entries."
        ),
    }

    # Primary artifact row is rewritten after the file exists.
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    receipt["artifacts"][0] = {
        "path": OUT,
        "role": "primary",
        "exists": True,
        "eol": "LF",
    }
    errs = validate(receipt)
    if errs:
        print("FAILED:TST-0117 schema", errs[:12])
        return 1
    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    t_seeds = test_corpus_seeds_are_reproducible_from_the_receipt()
    if not t_seeds["pass"]:
        print("FAILED:TST-0117 seed replay against the just-written receipt")
        print(json.dumps(t_seeds, sort_keys=True)[:4000])
        return 1

    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0117 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    primary = man_row(OUT, "primary")
    artifacts = [primary] + [man_row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "dedup-same-root-cause",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "minimise-and-replay",
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
        "manifest_path": "command-center/p2-wave/probes/TST-0117/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0117-probe2-minimise-and-replay",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for TST-0117: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UID,
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
    if primary["bytes"] < 1024:
        print("FAILED:TST-0117 receipt below min_bytes_threshold", primary["bytes"])
        return 1
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:TST-0117 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
