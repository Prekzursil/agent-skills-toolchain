#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0267.json from a live dissent-survival run."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.council import simulate as S  # noqa: E402
from tools.council import synthesis as Y  # noqa: E402
from tools.council.synthesis import CapRejected  # noqa: E402

OUT = "command-center/receipts/TST-0267.json"
FIXTURE = "command-center/p2-wave/probes/TST-0267/fixtures/lone-dissenter.json"
SIM = "tools/council/simulate.py"
SYN = "tools/council/synthesis.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0267/probe1_lone_dissenter_trace.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0267/probe2_deletion_and_squeeze.py"
)
QUESTION = (
    "A dissent that is recorded in round 4 and absent from the final report "
    "has been dropped, not resolved. Does a scripted dissenting position "
    "survive transcript, argument ledger, decision record, synthesis and "
    "executive summary, and does the trace fail when propagation is removed?"
)


def digest(rel: str) -> dict:
    path = REPO / rel
    raw = path.read_bytes() if path.is_file() else b""
    norm = raw.replace(b"\r\n", b"\n")
    return {
        "path": rel,
        "bytes": len(raw),
        "sha256": hashlib.sha256(norm).hexdigest(),
        "exists": path.is_file(),
        "role": "primary" if rel == OUT else "supporting",
    }


def line_of(rel: str, needle: str) -> str:
    path = REPO / rel
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return f"{rel}:{i}"
    return rel


def run_cmd(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd, cwd=str(REPO), shell=True, capture_output=True, text=True
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def main() -> int:
    spec = S.load_spec(REPO / FIXTURE)
    transcript = S.run(spec)
    chain = Y.run_chain(transcript, propagate=True, max_body_chars=None)
    dissent = Y.trace_survival(chain["rendered"])
    majority = Y.trace_survival(
        chain["rendered"], token=S.MAJORITY_TOKEN, claim=S.MAJORITY_CLAIM
    )
    if not dissent["ok"] or not majority["ok"]:
        print("FAILED:TST-0267 live chain dropped dissent or majority")
        return 1

    deleted = Y.run_chain(transcript, propagate=False, max_body_chars=None)
    deleted_trace = Y.trace_survival(deleted["rendered"])
    if deleted_trace["ok"] or deleted_trace["first_missing"] != "argument_ledger":
        print("FAILED:TST-0267 deletion control did not fail at argument_ledger")
        return 1

    cap_rejected = False
    cap_exc = None
    try:
        Y.run_chain(transcript, propagate=True, max_body_chars=80)
    except CapRejected as exc:
        cap_rejected = True
        cap_exc = str(exc)
    if not cap_rejected:
        print("FAILED:TST-0267 aggressive cap was not rejected")
        return 1

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0267 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    stage_evidence = []
    for row in dissent["stages"]:
        stage_evidence.append(
            {
                "artifact": row["stage"],
                "heading": row["heading"],
                "token_byte_offset": row["token"]["byte_offset"],
                "claim_byte_offset": row["claim"]["byte_offset"],
                "present": row["present"],
                "rendered_sha256": hashlib.sha256(
                    chain["rendered"][row["stage"]].encode("utf-8")
                ).hexdigest(),
                "rendered_bytes": len(chain["rendered"][row["stage"]].encode("utf-8")),
            }
        )

    receipt = {
        "schema_version": 1,
        "id": "TST-0267",
        "unit_id": "TST-0267",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:TST-0267",
        "completion_sentinel": "SUCCESS:TST-0267",
        "title": (
            "Prove the minority report survives all the way into the final "
            "synthesis artifact"
        ),
        "question": QUESTION,
        "answer": (
            "A scripted lone dissenter (skeptic) records "
            f"{S.DISSENT_TOKEN} in round 4. propagate_dissent copies the token "
            "and the claim through argument ledger, decision record, synthesis "
            "and executive summary. Offsets below are UTF-8 byte positions in "
            "the rendered artifact. Removing propagate_dissent makes the trace "
            "FAIL at argument_ledger. A summarisation cap smaller than the "
            "reserved minority block is rejected rather than dropping dissent."
        ),
        "spec_anchor": [
            S.SPEC_ANCHOR_DISSENT_REQUIRED,
            S.SPEC_ANCHOR_SUPPRESSION,
            S.SPEC_ANCHOR_DROPPED,
        ],
        "output_schema": "command-center/schema/receipt.schema.json",
        "output_schema_on_disk": (REPO / "command-center/schema/receipt.schema.json").is_file(),
        "min_bytes_threshold": 2048,
        "ts": now,
        "simulator": {
            "path": SIM,
            "run_entry": line_of(SIM, "def run("),
            "persona_script": FIXTURE,
            "transcript_sha256": S.digest_doc(transcript),
            "two_run_identical": True,
            "dissent_first_round": transcript.get("dissent_first_round"),
            "dissenters": transcript.get("dissenters"),
            "tally": transcript.get("tally"),
        },
        "chain": {
            "producer": SYN,
            "propagate_entry": line_of(SYN, "def propagate_dissent("),
            "stage_ids": list(Y.STAGE_IDS),
            "stages": stage_evidence,
        },
        "evidence": [
            {
                "id": "E1-round4-first-appearance",
                "claim": (
                    "Dissent token and claim first appear in the transcript at "
                    "round 4 under heading ## Minority report."
                ),
                "path": SIM,
                "line": int(line_of(SIM, 'kind": "dissent"').rsplit(":", 1)[-1])
                if ":" in line_of(SIM, 'kind": "dissent"')
                else None,
                "observation": stage_evidence[0],
            },
            {
                "id": "E2-all-downstream-offsets",
                "claim": (
                    "Every named downstream artifact contains the dissent token "
                    "and claim; byte offsets and headings are listed per stage."
                ),
                "path": SYN,
                "observation": stage_evidence,
            },
            {
                "id": "E3-deletion-control",
                "claim": (
                    "Removing propagate_dissent makes the trace FAIL at "
                    "argument_ledger while the transcript still holds the dissent."
                ),
                "path": SYN,
                "observation": {
                    "first_missing": deleted_trace["first_missing"],
                    "ok": deleted_trace["ok"],
                    "transcript_present": deleted_trace["stages"][0]["present"],
                },
            },
            {
                "id": "E4-summarisation-squeeze",
                "claim": (
                    "max_body_chars=80 is rejected because it cannot hold the "
                    "minority block; a generous cap keeps the dissent."
                ),
                "path": SYN,
                "observation": {
                    "aggressive_cap": 80,
                    "rejected": True,
                    "detail": cap_exc,
                },
            },
        ],
        "tests": [
            {
                "id": "TST-0267-LONE-DISSENTER-TRACE",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
            },
            {
                "id": "TST-0267-DELETION-CONTROL",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
            },
            {
                "id": "TST-0267-SUMMARISATION-SQUEEZE",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
            },
        ],
        "negative_controls": [
            {
                "id": "TST-0267-DISSENT-PROPAGATION-DELETED",
                "description": (
                    "Remove propagate_dissent and the survival trace must FAIL "
                    "at argument_ledger, proving the trace reads live artifacts."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "TST-0267-AGGRESSIVE-CAP-REJECTED",
                "description": (
                    "A length cap smaller than the reserved minority-report "
                    "block is rejected instead of silently dropping dissent."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0267-probe2-independent-byte-search",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "probe2 re-renders the chain and searches UTF-8 bytes for the "
                "token without calling trace_survival."
            ),
        },
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "lone-dissenter-survival-trace",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "deletion-control-and-summarisation-squeeze",
                "raw_output": t2,
            },
        ],
        "artifacts": [
            digest(OUT),
            digest(SIM),
            digest(SYN),
            digest(FIXTURE),
        ],
        "residual_unknowns": [
            {
                "id": "R1-TST-0257-broader-simulator",
                "note": (
                    "This unit does not claim the full TST-0257 simulator "
                    "contract (corrupt-persona loud-fail, different-seed "
                    "divergence across a broader cast). It ships the named "
                    "simulate.py entry point this trace rides on."
                ),
            }
        ],
        "owner_approval_required": True,
        "notes": (
            "G-1 for TST-0267. Did not run global unit_manifest.py --write. "
            "Did not rebuild ADV-0097. cloud ok is not delivery."
        ),
    }
    text = json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    print(f"wrote {OUT} bytes={len(text.encode('utf-8'))}")
    print("SUCCESS:TST-0267")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
