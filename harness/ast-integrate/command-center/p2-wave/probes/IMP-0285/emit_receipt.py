#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0285.json from live jury runs and named probes."""
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
from load_jury import load_jury  # noqa: E402

UNIT = "IMP-0285"
OUT = "command-center/receipts/IMP-0285.json"
SCHEMA = (
    "command-center/schema/receipt.schema.json profile=council-topology-module"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0285/probe1_verdict_form.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0285/probe2_hung_and_support.py"
)
HUNG_FIX = "command-center/p2-wave/probes/IMP-0285/fixtures/hung-jury-outcome.json"
SUPPORT_FIX = (
    "command-center/p2-wave/probes/IMP-0285/fixtures/support-check-unsupported.json"
)
MODULE = "tools/council/topology/jury.py"


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": path.is_file(),
        "role": role,
        "eol": "LF",
    }


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
    return p.returncode, text


def probe(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:65000],
        "exit_code": exit_code,
        "fingerprint": hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32],
    }


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    mod = load_jury()
    hung = mod.run_jury(mod.hung_jury_fixture())
    uni = mod.run_jury(mod.unanimous_supported_fixture())
    planted = mod.plant_unsupported_verdict(uni, "PLANTED-WRONG")
    planted_report = mod.check_verdict_support(planted, uni.juror_records)
    form_ok = not mod.validate_verdict_form(hung.verdict)
    coerced = mod.coerce_plurality_finding(hung.verdict.ballot_tally)

    (HERE / "fixtures").mkdir(parents=True, exist_ok=True)
    hung_blob = {
        "fixture": "hung_jury_fixture",
        "decision_rule": hung.verdict.decision_rule,
        "panel_size": hung.verdict.panel_size,
        "threshold": hung.verdict.threshold,
        "ballot_tally": hung.verdict.ballot_tally,
        "outcome_kind": hung.verdict.outcome_kind,
        "finding": hung.verdict.finding,
        "hung_reason": hung.verdict.hung_reason,
        "plurality_finding_not_used": hung.verdict.plurality_finding,
        "coerce_plurality_finding_would_return": coerced,
        "excluded": hung.excluded,
        "admitted": hung.admitted,
        "form_valid": form_ok,
    }
    support_blob = {
        "fixture": "plant_unsupported_verdict",
        "planted_finding": "PLANTED-WRONG",
        "unanimous_support_ok": uni.support.ok,
        "unanimous_unsupported": uni.support.to_dict()["unsupported"],
        "planted_support_ok": planted_report.ok,
        "unsupported": planted_report.to_dict()["unsupported"],
    }
    (REPO / HUNG_FIX).write_text(
        json.dumps(hung_blob, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (REPO / SUPPORT_FIX).write_text(
        json.dumps(support_blob, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:{UNIT} named probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    if hung.verdict.outcome_kind != "NO-DECISION" or hung.verdict.finding is not None:
        print(f"FAILED:{UNIT} hung fixture did not produce NO-DECISION")
        return 1
    if planted_report.ok or not planted_report.unsupported:
        print(f"FAILED:{UNIT} planted verdict was not listed as unsupported")
        return 1

    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    module_art = art(MODULE, "implementation")
    hung_art = art(HUNG_FIX, "evidence")
    support_art = art(SUPPORT_FIX, "evidence")
    p1_art = art("command-center/p2-wave/probes/IMP-0285/probe1_verdict_form.py", "supporting")
    p2_art = art("command-center/p2-wave/probes/IMP-0285/probe2_hung_and_support.py", "supporting")
    artifact_paths = [
        MODULE,
        HUNG_FIX,
        SUPPORT_FIX,
        OUT,
        "command-center/p2-wave/probes/IMP-0285/probe1_verdict_form.py",
        "command-center/p2-wave/probes/IMP-0285/probe2_hung_and_support.py",
    ]
    hung_json = json.dumps(hung_blob, sort_keys=True)
    support_json = json.dumps(support_blob, sort_keys=True)
    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0285",
        "spec_anchor": (
            "WORK-UNIT-CATALOG.json:IMP-0285 "
            "tools/council/topology/jury.py; "
            "_USER-PROMPTS.md:10915-10946; "
            "P17 jury-with-allowed-hung"
        ),
        "output_schema": SCHEMA,
        "title": "Jury topology with jurors, judge and a typed verdict form",
        "artifact_paths": artifact_paths,
        "artifacts": [module_art, hung_art, support_art, p1_art, p2_art],
        "min_bytes_threshold": 128,
        "evidence": [
            {
                "claim": (
                    "A hung 3-2 panel under unanimity produces outcome_kind "
                    "NO-DECISION with finding=null; plurality CONVICT is recorded "
                    "but not promoted."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{HUNG_FIX}:outcome_kind",
                "confidence": "almost-certain",
                "probes": [
                    probe("source", "in-process", "run_jury(hung_jury_fixture())", hung_json, 0),
                    probe("verifier", "command", P2, t2, c2),
                ],
            },
            {
                "claim": (
                    "check_verdict_support lists unsupported verdicts: planting "
                    "PLANTED-WRONG on a unanimous CONVICT panel yields ok=false "
                    "and unsupported[].finding=PLANTED-WRONG."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{SUPPORT_FIX}:unsupported",
                "confidence": "almost-certain",
                "probes": [
                    probe(
                        "source",
                        "in-process",
                        "check_verdict_support(plant_unsupported_verdict(...))",
                        support_json,
                        0,
                    ),
                    probe("verifier", "command", P2, t2, c2),
                ],
            },
            {
                "claim": (
                    "validate_verdict_form accepts canonical DECISION and "
                    "NO-DECISION forms and rejects PASS-kind, missing finding, "
                    "coerced hung finding, and judge-as-juror."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/council/topology/jury.py:validate_verdict_form",
                "confidence": "almost-certain",
                "probes": [
                    probe("source", "command", P1, t1, c1),
                    probe("verifier", "command", P2, t2, c2),
                ],
            },
        ],
        "test_ids": [
            "unit:verdict-form-validation",
            "integration:hung-jury-no-decision",
            "negative:unsupported-verdict-fails-support-check",
        ],
        "negative_control_ids": [
            "nc-unsupported-verdict",
            "nc-coerced-majority-finding-on-hung",
            "nc-empty-reasoning-unanimous-ballots",
        ],
        "tests": [
            {"id": "unit:verdict-form-validation", "command": P1, "result": "PASS", "exit_code": c1},
            {
                "id": "integration:hung-jury-no-decision",
                "command": P2,
                "result": "PASS",
                "exit_code": c2,
            },
            {
                "id": "negative:unsupported-verdict-fails-support-check",
                "command": P2,
                "result": "PASS",
                "exit_code": c2,
            },
        ],
        "negative_controls": [
            {
                "id": "nc-unsupported-verdict",
                "kind": "planted-finding",
                "description": (
                    "Plant PLANTED-WRONG on a unanimous CONVICT panel. "
                    "Support check must FAIL and list the finding."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": support_json[:16000],
                "good_state_output": json.dumps(uni.support.to_dict(), sort_keys=True)[:16000],
            },
            {
                "id": "nc-coerced-majority-finding-on-hung",
                "kind": "plurality-coercion",
                "description": (
                    "3-2 CONVICT/ACQUIT under unanimity. coerce_plurality_finding "
                    "returns CONVICT; run_jury finding must stay null."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": f"coerce_plurality_finding={coerced}",
                "good_state_output": hung_json[:16000],
            },
        ],
        "reviewer_verdict": "PASS",
        "reviewer": {
            "reviewer_id": "IMP-0285-named-probes",
            "verdict": "PASS",
            "independent": False,
            "fresh_context": False,
            "note": (
                "Named probes start from the tests, not an author summary. "
                "They were authored in the same session as jury.py; a separate "
                "fresh-context adversarial reviewer is residual."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "An independent adversarial reviewer in a fresh context who "
                    "did not author tools/council/topology/jury.py has not signed."
                ),
                "settling_experiment": (
                    "Re-run probe1_verdict_form.py and probe2_hung_and_support.py "
                    "in a new session that is given the tests first, then record "
                    "reviewer.independent=true."
                ),
                "verdict": "NOT-CHECKED",
            },
            {
                "claim": (
                    "tools/council/kernel.py (IMP-0264) is absent. RecordingKernel "
                    "is a local event log; a live kernel call-graph check that no "
                    "topology writes participant output directly was not executed "
                    "against the IMP-0264 binary."
                ),
                "settling_experiment": "Re-run with IMP-0264 kernel.py on PYTHONPATH.",
                "verdict": "NOT-CHECKED",
            },
            {
                "claim": (
                    "tools/council/vote/bayes.py (IMP-0305) is absent. Hung vs "
                    "decision uses discrete ballot thresholds, not credence pooling."
                ),
                "settling_experiment": (
                    "If jurors emit credences, pool with IMP-0305 and confirm a "
                    "split panel still cannot be coerced into DECISION."
                ),
                "verdict": "NOT-CHECKED",
            },
        ],
        "retry": {"count": 0, "policy": "two strikes then pivot (AGENTS.md 4b)"},
        "timestamps": {"started_at": started, "ended_at": ended},
        "downstream_consumers": [
            {
                "artifact_path": OUT,
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "executed": False,
                "read_ok": False,
                "note": "Measure runs after this receipt and the per-unit manifest exist.",
            }
        ],
        "manifest_registration": {
            "manifest_path": "command-center/p2-wave/probes/IMP-0285/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2},
        ],
        "notes": (
            "G-1 IMP-0285: jury.py returns typed verdicts; hung fixture is "
            "NO-DECISION; unsupported planted finding fails the support check. "
            "Did not run global unit_manifest.py --write. No ADV rebuild."
        ),
    }
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    size = out.stat().st_size
    if size < 128:
        print(f"FAILED:{UNIT} receipt {size}B below floor")
        return 1
    text = out.read_text(encoding="utf-8")
    if "SUCCESS:IMP-0285" not in text:
        print(f"FAILED:{UNIT} sentinel absent after write")
        return 1
    if json.loads(text).get("state", "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:{UNIT} self-declared non-delivery")
        return 1
    print(f"wrote {OUT} ({size} B)")
    print("SUCCESS:IMP-0285")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
