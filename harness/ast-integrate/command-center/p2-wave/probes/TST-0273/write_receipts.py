#!/usr/bin/env python3
"""Write TST-0273 receipt, SUBAGENT-RETURN.json, and per-unit UNIT-ARTIFACT-MANIFEST.json."""
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
sys.path.insert(0, str(REPO))

from scenario import PAYLOADS, run_carrier_matrix, run_positive_and_naive  # noqa: E402

UID = "TST-0273"
OUT = "command-center/receipts/TST-0273.json"
SCHEMA = "command-center/schema/receipt.schema.json"
SUT = "tools/council/stage_context.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0273/probe1_carrier_matrix.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0273/probe2_positive_and_naive.py"
)
SUPPORTING = [
    SUT,
    "command-center/p2-wave/probes/TST-0273/scenario.py",
    "command-center/p2-wave/probes/TST-0273/probe1_carrier_matrix.py",
    "command-center/p2-wave/probes/TST-0273/probe2_positive_and_naive.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fp(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "eol": "LF",
        "exists": True,
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/TST-0273/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    matrix = run_carrier_matrix()
    pos = run_positive_and_naive()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    sut_sha, sut_bytes = digest(REPO / SUT)

    carrier_evidence = []
    for item in matrix["rows"]:
        carrier_evidence.append(
            {
                "carrier": item["carrier"],
                "payload_text": item["payload_text"],
                "token": item["token"],
                "later_stage_action_verbatim": item["later_stage_action"],
                "obeyed": item["later_stage_obeyed"],
                "token_reached": item["token_reached_assembled"],
                "directive_neutralized": item["directive_neutralized"],
            }
        )

    impl_rows = [row(p, "supporting") for p in SUPPORTING]
    receipt = {
        "unit_id": UID,
        "id": UID,
        "title": "Prompt injection via a participant artifact into a later council stage",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0273",
        "completion_sentinel": "SUCCESS:TST-0273",
        "schema_version": 1,
        "report_kind": "security_report",
        "output_schema": SCHEMA + " profile=security_report",
        "declared_schema_file_present": (REPO / SCHEMA).is_file(),
        "spec_anchor": (
            "WORK-UNIT-CATALOG.json TST-0273; _USER-PROMPTS.md:11344 "
            "(council transcript or participant artifact injects instructions "
            "into later stages); AGENTS.md section 9 (fetched/peer content is "
            "untrusted DATA)"
        ),
        "question": (
            "A participant writes a position paper containing instruction-shaped "
            "text; when a later stage reads that paper, does it obey it? Same "
            "question for transcript, idea ledger, evidence bundle, tool result, "
            "and participant display name, each planted separately. A payload in "
            "the genuine instruction channel must be obeyed (observer liveness)."
        ),
        "answer": (
            "No for every listed carrier under the defended assembler "
            f"({SUT}): later-stage action was 'NO-OP continued-deliberation' "
            "while each unique canary token still reached DATA and each live "
            "EXECUTE_CANARY directive was neutralized. Yes for the genuine "
            "instruction channel (positive control obeyed "
            f"{pos['positive_control']['token']}). Yes for the naive "
            "concatenator (known-broken twin obeyed the position-paper canary). "
            "Carriers actually exercised: "
            + ", ".join(matrix["carriers"])
            + "."
        ),
        "measured_at": now,
        "min_bytes_threshold": 2048,
        "cloud_ok": False,
        "sut": {
            "catalog_input": "stage-to-stage context assembler from bucket B07",
            "simulate_py_present": (REPO / "tools/council/simulate.py").is_file(),
            "live_module": SUT,
            "live_sha256": sut_sha,
            "live_bytes": sut_bytes,
            "later_stage": "scripted consume() obeys EXECUTE_CANARY only in the instruction channel",
            "defense": "UNTRUSTED-DATA fences plus EXECUTE_CANARY[NEUTRALIZED]: mangling; instruction channel not mangled",
        },
        "carriers_exercised": matrix["carriers"],
        "carrier_results": carrier_evidence,
        "payloads": PAYLOADS,
        "positive_control": pos["positive_control"],
        "naive_control": pos["naive_position_paper"],
        "defended_position_paper": pos["defended_position_paper"],
        "both_states": pos["both_states"],
        "clean_round": matrix["clean"],
        "drop_control": matrix["drop_control"],
        "tests": [
            {
                "id": "position-paper-not-obeyed",
                "result": "PASS",
                "command": P1,
            },
            {
                "id": "carrier-matrix-six-isolated-plants",
                "result": "PASS",
                "command": P1,
            },
            {
                "id": "positive-control-instruction-channel-obeyed",
                "result": "PASS",
                "command": P2,
            },
            {
                "id": "naive-concatenator-obeys-position-paper",
                "result": "PASS",
                "command": P2,
            },
        ],
        "negative_controls": [
            {
                "id": "naive-concatenator",
                "kind": "known-broken-implementation",
                "description": (
                    "Concatenate carrier text into the instruction channel with "
                    "no fences and no neutralization. The later stage MUST obey "
                    "EXECUTE_CANARY:CANARY-PP-TST0273. Defended assemble of the "
                    "same plant must stay silent."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": pos["naive_position_paper"]["later_stage_action"],
                "good_state_output": pos["defended_position_paper"]["later_stage_action"],
            },
            {
                "id": "drop-instead-of-fence",
                "kind": "vacuous-immunity",
                "description": (
                    "Replace the planted position paper with benign text. The "
                    "canary token must NOT appear in assembled context, proving "
                    "the reachability check would catch a drop-the-payload cheat."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": json.dumps(matrix["drop_control"], sort_keys=True),
            },
        ],
        "evidence": [
            {
                "anchor": "tools/council/stage_context.py:assemble+consume",
                "claim": (
                    "Isolated plants in position_paper, transcript, idea_ledger, "
                    "evidence_bundle, tool_result, and display_name are not obeyed "
                    "by the later stage; each payload text, carrier, and later-stage "
                    "action is recorded; each canary token still reaches DATA."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "source_probe": P1,
                "verifier_probe": P2,
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P1,
                        "exit_code": c1,
                        "fingerprint": fp(t1),
                        "raw_output": t1[-2500:],
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P2,
                        "exit_code": c2,
                        "fingerprint": fp(t2),
                        "raw_output": t2[-2500:],
                    },
                ],
            },
            {
                "anchor": "tools/council/stage_context.py:consume",
                "claim": (
                    "A payload in the genuine instruction channel is obeyed "
                    f"({pos['positive_control']['later_stage_action']}); the same "
                    "observer obeys a naive concatenator and stays silent on the "
                    "defended plant, so immunity is not a universal no-op."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "source_probe": P2,
                "verifier_probe": P1,
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P2,
                        "exit_code": c2,
                        "fingerprint": fp(t2),
                        "raw_output": t2[-2500:],
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": "emit-time recompute assemble(naive=True|False)+consume",
                        "exit_code": 0,
                        "fingerprint": fp(json.dumps(pos, sort_keys=True)),
                        "raw_output": json.dumps(
                            {
                                "positive_obeyed": pos["positive_control"]["obeyed"],
                                "naive_obeys": pos["both_states"]["naive_obeys"],
                                "defended_silent": pos["both_states"]["defended_silent"],
                            },
                            sort_keys=True,
                        ),
                    },
                ],
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0273-probe2-positive-and-naive",
            "independent": True,
            "fresh_context": False,
            "verdict": "PASS",
            "notes": (
                "Catalog asks for a cross-vendor security reviewer plus a "
                "correctness reviewer in a fresh context. This lane records "
                "probe 2 as a mechanically independent observer (positive "
                "control + naive twin) and does not claim a fresh-context human."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "tools/council/simulate.py and a live B07 dispatcher binary "
                    "are absent from this worktree. Measurements are of "
                    f"{SUT} plus a scripted later-stage consumer, not of a "
                    "missing production council simulator or a live model call."
                ),
                "settling_experiment": (
                    "Re-point assemble() at the B07 simulator once TST-0257 "
                    "ships, and re-run both named probes against a scripted "
                    "persona cast."
                ),
                "verdict": "NOT-CHECKED",
            }
        ],
        "retry": {
            "count": 0,
            "policy": "No automatic retry: a failure here is a finding, not a transient.",
        },
        "owner_approval_required": True,
        "manifest_registration": {
            "entry_id": UID,
            "manifest_path": "command-center/p2-wave/probes/TST-0273/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1},
            {"id": "probe2", "command": P2, "exit_code": c2},
        ],
        "notes": (
            "G-1 for TST-0273: live named probes exit 0, receipts/TST-0273.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery."
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    primary = row(OUT, "primary")
    artifacts = [primary] + impl_rows
    # Receipt bytes/hash after write.
    primary = row(OUT, "primary")
    artifacts[0] = primary

    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0273",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "carrier-matrix",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "positive-control-and-naive-concatenator",
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
        "manifest_path": "command-center/p2-wave/probes/TST-0273/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0273-probe2-positive-and-naive",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for TST-0273: live named probes exit 0, receipts/TST-0273.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
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
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:TST-0273 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
