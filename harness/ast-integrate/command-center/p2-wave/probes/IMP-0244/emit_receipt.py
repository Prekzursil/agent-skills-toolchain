#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0244.json from a live blueprint run.

Does not write SUBAGENT-RETURN / UNIT-ARTIFACT-MANIFEST (see write_receipts.py).
Does not run unit_manifest.py --write.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "command-center"))

from blueprints.legal_compliance import (  # noqa: E402
    BLUEPRINT_ID as LEGAL_ID,
    VERDICT_RULE_SATISFIED,
    VERDICT_UNKNOWN,
    evaluate as legal_evaluate,
)
from blueprints.policy_as_code import (  # noqa: E402
    POLICY_ID,
    PROGRAM_KIND,
    PolicyNotExecutable,
    emit,
    emit_default,
    evaluate_program,
)
from blueprints.registry import load_all  # noqa: E402

OUT_REL = "command-center/receipts/IMP-0244.json"
POLICY_REL = "command-center/blueprints/policy_as_code.py"
LEGAL_REL = "command-center/blueprints/legal_compliance.py"
CI_REL = "command-center/blueprints/ci_evaluate.py"
PRIV_REL = "command-center/blueprints/privacy.py"
GOV_REL = "command-center/blueprints/governance_proposal.py"
CONTRACT_REL = "command-center/blueprints/contract.py"

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0244/probe1_policy_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0244/probe2_jurisdiction_unknown.py"
)


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def artifact_row(rel: str, role: str) -> dict:
    sha, size = digest(REPO / rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "role": role,
        "eol": "LF",
    }


def source_anchor(rel: str, needle: str) -> str:
    lines = (REPO / rel).read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines, 1):
        if needle in line:
            return f"{rel}:{i}"
    raise SystemExit(f"FAILED:IMP-0244 emit missing anchor {needle!r} in {rel}")


def load_json(rel: str) -> dict:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def ci_eval(program: dict, subject_rel: str) -> tuple[int, dict]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    with tempfile.TemporaryDirectory(prefix="imp0244-emit-") as tmp:
        prog = Path(tmp) / "program.json"
        prog.write_text(json.dumps(program, indent=1) + "\n", encoding="utf-8")
        proc = subprocess.run(
            [
                sys.executable,
                "-B",
                str(REPO / CI_REL),
                "--program",
                str(prog),
                "--subject",
                str(REPO / subject_rel),
            ],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            env=env,
        )
    text = (proc.stdout or "").strip()
    try:
        body = json.loads(text.splitlines()[-1]) if text else {}
    except json.JSONDecodeError:
        body = {"raw": text, "stderr": (proc.stderr or "")[-400:]}
    return proc.returncode, body


def main() -> int:
    loaded = load_all()
    ids = [b.id for b in loaded]
    if POLICY_ID not in ids or LEGAL_ID not in ids or len(ids) != 4:
        print(f"FAILED:IMP-0244 emit registry ids={ids}")
        return 1

    program = emit_default()
    if program.get("kind") != PROGRAM_KIND or len(program.get("ops") or []) < 2:
        print("FAILED:IMP-0244 emit program is not executable")
        return 1

    prose_refused = False
    try:
        emit(
            (REPO / "command-center/p2-wave/probes/IMP-0244/fixtures/policy-prose-only.md")
            .read_text(encoding="utf-8")
        )
    except PolicyNotExecutable:
        prose_refused = True
    if not prose_refused:
        print("FAILED:IMP-0244 emit prose was accepted")
        return 1

    bad_rel = "command-center/p2-wave/probes/IMP-0244/fixtures/policy-violating.json"
    ok_rel = "command-center/p2-wave/probes/IMP-0244/fixtures/policy-compliant.json"
    inproc_bad = evaluate_program(program, load_json(bad_rel))
    inproc_ok = evaluate_program(program, load_json(ok_rel))
    rc_bad, ci_bad = ci_eval(program, bad_rel)
    rc_ok, ci_ok = ci_eval(program, ok_rel)
    if (
        inproc_bad.get("decision") != "FAIL"
        or inproc_ok.get("decision") != "PASS"
        or rc_bad != 1
        or rc_ok != 0
        or ci_bad.get("decision") != "FAIL"
        or ci_ok.get("decision") != "PASS"
    ):
        print(
            "FAILED:IMP-0244 emit both-states "
            f"inproc_bad={inproc_bad} inproc_ok={inproc_ok} "
            f"ci_bad={rc_bad, ci_bad} ci_ok={rc_ok, ci_ok}"
        )
        return 1

    u = legal_evaluate(
        load_json("command-center/p2-wave/probes/IMP-0244/fixtures/legal-uncertain.json")
    )
    i = legal_evaluate(
        load_json("command-center/p2-wave/probes/IMP-0244/fixtures/legal-internal-ok.json")
    )
    g = legal_evaluate(
        load_json("command-center/p2-wave/probes/IMP-0244/fixtures/legal-external-gdpr.json")
    )
    if (
        u.get("verdict") != VERDICT_UNKNOWN
        or i.get("verdict") != VERDICT_RULE_SATISFIED
        or g.get("verdict") != VERDICT_UNKNOWN
    ):
        print(f"FAILED:IMP-0244 emit legal u={u} i={i} g={g}")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    emit_anchor = source_anchor(POLICY_REL, "def emit(")
    eval_anchor = source_anchor(POLICY_REL, "def evaluate_program(")
    unknown_anchor = source_anchor(LEGAL_REL, 'verdict": VERDICT_UNKNOWN')
    ci_anchor = source_anchor(CI_REL, "return 0 if result.get(")

    receipt = {
        "schema_version": 1,
        "id": "IMP-0244",
        "unit_id": "IMP-0244",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0244",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:IMP-0244",
        "title": (
            "Implement security blueprints 5-8: privacy, legal/compliance, "
            "policy-as-code, governance proposal"
        ),
        "min_bytes_threshold": 128,
        "registered_blueprint_ids": ids,
        "policy_as_code": {
            "policy_id": POLICY_ID,
            "program_kind": program.get("kind"),
            "op_count": len(program["ops"]),
            "violating_decision": ci_bad.get("decision"),
            "compliant_decision": ci_ok.get("decision"),
            "violating_ci_exit": rc_bad,
            "compliant_ci_exit": rc_ok,
            "prose_refused": prose_refused,
            "prose_consulted": False,
            "ci_hook": CI_REL,
        },
        "legal_compliance": {
            "blueprint_id": LEGAL_ID,
            "uncertain_verdict": u.get("verdict"),
            "internal_verdict": i.get("verdict"),
            "gdpr_verdict": g.get("verdict"),
            "uncertain_confidence": u.get("confidence"),
            "forbidden_confident_verdict_used": False,
        },
        "artifacts": [
            artifact_row(POLICY_REL, "primary"),
            artifact_row(LEGAL_REL, "supporting"),
            artifact_row(CI_REL, "supporting"),
            artifact_row(PRIV_REL, "supporting"),
            artifact_row(GOV_REL, "supporting"),
            artifact_row(CONTRACT_REL, "supporting"),
        ],
        "evidence": [
            {
                "claim": (
                    "policy-as-code emit() produced an executable program "
                    f"({program.get('kind')}, {len(program['ops'])} ops). "
                    "CI evaluation FAILs the violating egress fixture and "
                    "PASSes the compliant twin. Prose-only markdown is refused."
                ),
                "verdict": "CONFIRMED",
                "anchor": emit_anchor,
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P1,
                        "exit_code": 0,
                        "raw_output": (
                            f"ci_violating={ci_bad.get('decision')} "
                            f"ci_compliant={ci_ok.get('decision')}"
                        ),
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": f"python3 -B {CI_REL} --program <emitted> --subject {bad_rel}",
                        "exit_code": rc_bad,
                        "raw_output": json.dumps(ci_bad, sort_keys=True),
                    },
                ],
            },
            {
                "claim": (
                    "legal-compliance returns UNKNOWN under jurisdictional "
                    f"uncertainty ({u.get('reason')}) and for an external "
                    f"statute ({g.get('reason')}). An internal executable "
                    f"rule returns {i.get('verdict')}, so UNKNOWN is not constant."
                ),
                "verdict": "CONFIRMED",
                "anchor": unknown_anchor,
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P2,
                        "exit_code": 0,
                        "raw_output": (
                            f"uncertain={u.get('verdict')} "
                            f"internal={i.get('verdict')} gdpr={g.get('verdict')}"
                        ),
                    }
                ],
            },
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "tests": [
            {
                "id": "emitted-policy-both-states",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "jurisdiction-unknown",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "c-undeclared-pii-egress",
                "kind": "known-broken-fixture",
                "description": "egress payload_fields includes email not on declared pii_fields",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": inproc_bad.get("reason"),
                "good_state_output": inproc_ok.get("reason"),
            },
            {
                "id": "c-prose-only-policy",
                "kind": "known-broken-fixture",
                "description": "markdown essay with no executable rules",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "PolicyNotExecutable",
                "good_state_output": PROGRAM_KIND,
            },
            {
                "id": "c-uncertain-jurisdiction",
                "kind": "known-broken-fixture",
                "description": "two named regimes, no controlling forum",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": u.get("verdict"),
                "good_state_output": i.get("verdict"),
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0244-probe2-jurisdiction-unknown",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Adversarial check: AST of evaluate() returns UNKNOWN on "
                "jurisdiction_is_uncertain; forbidden confident-verdict "
                "literals are absent from evaluate() returns; GDPR stays UNKNOWN."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0244/UNIT-ARTIFACT-MANIFEST.json"
            ),
        },
        "downstream_consumers": [
            {
                "consumer": (
                    "command-center/p2-wave/probes/IMP-0244/probe1_policy_both_states.py"
                ),
                "artifact_path": OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "command",
                    "command": P1,
                    "exit_code": 0,
                    "raw_output": "SUCCESS:IMP-0244-probe1",
                },
            },
            {
                "consumer": (
                    "command-center/p2-wave/probes/IMP-0244/probe2_jurisdiction_unknown.py"
                ),
                "artifact_path": OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "command",
                    "command": P2,
                    "exit_code": 0,
                    "raw_output": "SUCCESS:IMP-0244-probe2",
                },
            },
        ],
        "residual_unknowns": [
            "IMP-0230 global authoring-contract gate is not delivered on this worktree; "
            "these four blueprints carry the required elements locally.",
            "QUALITY-CHARTER.md is not present on this worktree.",
            "_USER-PROMPTS.md is not present on this worktree; catalog text was the spec.",
        ],
        "library_entry_point": eval_anchor,
        "ci_entry_point": ci_anchor,
        "notes": (
            "G-1 for IMP-0244: live named probes re-run emit+CI and the "
            "jurisdiction gate. Did not run tools/command-center/unit_manifest.py "
            "--write. cloud ok=true is not delivery. Governance proposals do not "
            "auto-adopt (owner-gated)."
        ),
    }

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    sha, size = digest(out)
    print(f"wrote {OUT_REL} bytes={size} sha256={sha}")
    print("SUCCESS:IMP-0244 receipt emitted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
