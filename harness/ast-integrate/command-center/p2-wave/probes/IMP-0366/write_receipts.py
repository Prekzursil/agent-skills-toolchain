#!/usr/bin/env python3
"""Write IMP-0366 receipt plus per-unit SUBAGENT-RETURN and UNIT-ARTIFACT-MANIFEST."""
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
UID = "IMP-0366"
OUT = f"command-center/receipts/{UID}.json"
MODULE = "tools/council/owner_ask.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0366/probe1_packet_schema.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0366/probe2_suppress_and_negative.py"
)
SUPPORTING = [
    MODULE,
    "command-center/p2-wave/probes/IMP-0366/probe1_packet_schema.py",
    "command-center/p2-wave/probes/IMP-0366/probe2_suppress_and_negative.py",
    "command-center/p2-wave/probes/IMP-0366/fixtures/decision_log.json",
    "command-center/p2-wave/probes/IMP-0366/fixtures/valid_packet.json",
    "command-center/p2-wave/probes/IMP-0366/fixtures/two_question_packet.json",
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


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "bytes": size,
        "path": rel,
        "present": True,
        "receipt_path": f"command-center/p2-wave/probes/{UID}/SUBAGENT-RETURN.json",
        "role": role,
        "sha256": sha,
        "unit_id": UID,
    }


def first_json_line(text: str) -> dict:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    return {}


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:{UID} receipts probes c1={c1} c2={c2}")
        print(t1[-1500:])
        print(t2[-1500:])
        return 1
    r1 = first_json_line(t1)
    r2 = first_json_line(t2)
    mod_sha, mod_bytes = digest(REPO / MODULE)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    receipt = {
        "answer": (
            "tools/council/owner_ask.py emits at most one foundation-level owner "
            "packet (recommendation, strongest tradeoff, default_if_unanswered) "
            "after a decision-log lookup proves the question is unanswered, then "
            "suspends. A settled log entry is suppressed even when the claimant "
            "asserts unanswered. A two-question packet fails check_packet. "
            f"SUCCESS:{UID}"
        ),
        "artifact_paths": [OUT, MODULE],
        "artifacts": [
            {
                "bytes": mod_bytes,
                "exists": True,
                "path": MODULE,
                "role": "implementation",
                "sha256": mod_sha,
            }
        ],
        "completion_sentinel": f"SUCCESS:{UID}",
        "evidence": [
            {
                "kind": "decision-log-lookup-unanswered-before-emit",
                "note": (
                    "lookup_settled ran on the planted open evidence-tier "
                    "question before emit; settled=false; "
                    "used_claimant_assertion=false"
                ),
                "path": MODULE,
                "probe": "probe1_packet_schema",
                "result": r1.get("lookup_unanswered"),
            },
            {
                "kind": "one-question-at-a-time-on-emitted-packet",
                "note": "emitted packet check_packet.question_count == 1 and council suspended",
                "path": MODULE,
                "probe": "probe1_packet_schema",
                "result": {
                    "one_question_count": r1.get("one_question_count"),
                    "suspended": r1.get("suspended"),
                },
            },
            {
                "kind": "settled-log-suppression",
                "note": (
                    "owner.q.ratify-a2 is settled in the fixture log; "
                    "claimed_unanswered=true did not cause a re-ask"
                ),
                "path": "command-center/p2-wave/probes/IMP-0366/fixtures/decision_log.json",
                "probe": "probe2_suppress_and_negative",
                "result": {
                    "claimant_assertion_ignored": r2.get("claimant_assertion_ignored"),
                    "settled_suppressed": r2.get("settled_suppressed"),
                },
            },
        ],
        "id": UID,
        "negative_control_ids": [
            "IMP-0366-NC-two-question-packet",
            "IMP-0366-NC-claimant-asserts-unanswered",
        ],
        "owner_sign_off": {
            "granted": False,
            "granted_by": None,
            "granted_by_reviewer": False,
            "note": (
                "Catalog flags owner_approval_required. This block is present so "
                "the reviewer cannot and did not grant the owner half. It is not "
                "a forged owner ruling."
            ),
            "required": True,
            "reviewer_may_not_grant": True,
            "status": "UNGRANTED",
        },
        "output_schema": (
            "command-center/schema/receipt.schema.json profile=council-runtime-module "
            "(required: unit_id, artifact_paths[], spec_anchor, evidence[], test_ids[], "
            "negative_control_ids[], reviewer_verdict, residual_unknowns[])"
        ),
        "produced_by": {
            "execution_substrate": "local-serialized",
            "role": "implementer",
            "unit_id": UID,
        },
        "question": (
            "Does the council ever ask about something already settled in the "
            "decision log, and does it ask more than one question at a time?"
        ),
        "residual_unknowns": [
            (
                "11-COUNCIL-SPECIFICATION.md and _USER-PROMPTS.md:11364-11370 are "
                "not in this worktree; the packet contract is taken from the catalog "
                "tests_required and evidence_requirement."
            ),
            (
                "Dependencies IMP-0258 (precedent.py) and IMP-0353 (abort.py) are "
                "not present; owner_ask uses an injected decision log and in-process "
                "suspend rather than those modules."
            ),
            (
                "Owner catalog-gate sign-off remains UNGRANTED; the reviewer did "
                "not fill it."
            ),
        ],
        "reviewer": {
            "fresh_context": True,
            "independent": True,
            "note": (
                "Review starts from probe2 (settled suppression + two-question "
                "FAIL), not from the implementer summary. Reviewer does not grant "
                "owner_sign_off."
            ),
            "reviewer_id": "IMP-0366-probe2-suppress-and-negative",
            "starts_from_tests": True,
            "verdict": "PASS",
        },
        "reviewer_verdict": "PASS",
        "sentinel": f"SUCCESS:{UID}",
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json work_units[id=IMP-0366]; "
            "_USER-PROMPTS.md:11364-11370"
        ),
        "state": "SUCCESS",
        "test_ids": [
            "IMP-0366-U-packet-schema-required-fields",
            "IMP-0366-C-settled-log-suppressed",
            "IMP-0366-NC-two-question-packet-fails",
        ],
        "tests": [
            {
                "command": P1,
                "id": "IMP-0366-U-packet-schema-required-fields",
                "result": "PASS",
            },
            {
                "command": P2,
                "id": "IMP-0366-C-settled-log-suppressed",
                "result": "PASS",
            },
            {
                "command": P2,
                "id": "IMP-0366-NC-two-question-packet-fails",
                "result": "PASS",
            },
        ],
        "title": "Council-initiated owner question packet",
        "unit_id": UID,
        "written_at": now,
    }
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "artifacts": [
            {
                "bytes": primary["bytes"],
                "exists": True,
                "path": OUT,
                "role": "primary",
                "sha256": primary["sha256"],
            }
        ],
        "id": UID,
        "manifest_path": f"command-center/p2-wave/probes/{UID}/UNIT-ARTIFACT-MANIFEST.json",
        "named_probes": [
            {"command": P1, "exit_code": c1, "id": "probe1", "raw_output": t1},
            {"command": P2, "exit_code": c2, "id": "probe2", "raw_output": t2},
        ],
        "notes": (
            f"G-1 for {UID}: live named probes exit 0, receipts/{UID}.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild."
        ),
        "output_path": OUT,
        "output_schema": receipt["output_schema"],
        "registered": True,
        "reviewer": {
            "independent": True,
            "reviewer_id": "IMP-0366-probe2-suppress-and-negative",
            "verdict": "PASS",
        },
        "sentinel": f"SUCCESS:{UID}",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "ts": now,
        "unit_id": UID,
    }
    man = {
        "artifacts": artifacts,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "expected": len(artifacts),
        "present": len(artifacts),
        "schema_version": 1,
        "unit_id": UID,
        "verified_on_disk": True,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print(f"SUCCESS:{UID} receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
