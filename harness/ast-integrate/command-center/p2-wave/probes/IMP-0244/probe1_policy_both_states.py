#!/usr/bin/env python3
"""Probe 1: emitted policy FAILs a violating subject and PASSes a compliant one.

Both-states, so the policy is not vacuous. Evaluation is the CI hook
(command-center/blueprints/ci_evaluate.py) against an emitted program —
not a markdown essay. Prose-only source is refused at emit().
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "command-center"))

from blueprints.policy_as_code import (  # noqa: E402
    POLICY_ID,
    PROGRAM_KIND,
    SOURCE_POLICY,
    PolicyNotExecutable,
    emit,
    emit_default,
)
from blueprints.registry import load_all  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0244.json"
CI = REPO / "command-center/blueprints/ci_evaluate.py"
FIX_OK = HERE / "fixtures/policy-compliant.json"
FIX_BAD = HERE / "fixtures/policy-violating.json"
FIX_PROSE = HERE / "fixtures/policy-prose-only.md"
FIX_SRC = HERE / "fixtures/policy-source.json"
UNIT = "IMP-0244"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def ci_eval(program_path: Path, subject_path: Path) -> tuple[int, dict]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [
            sys.executable,
            "-B",
            str(CI),
            "--program",
            str(program_path),
            "--subject",
            str(subject_path),
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
        body = {"raw": text, "stderr": (proc.stderr or "")[-800:]}
    return proc.returncode, body


def main() -> int:
    loaded = load_all()
    ids = [b.id for b in loaded]
    if POLICY_ID not in ids:
        return fail(f"policy-as-code not registered: {ids}")
    if len(ids) != 4:
        return fail(f"expected 4 blueprints, got {ids}")

    program = emit_default()
    if program.get("kind") != PROGRAM_KIND:
        return fail(f"emitted kind={program.get('kind')} want={PROGRAM_KIND}")
    if not program.get("ops"):
        return fail("emitted program has no ops")
    if len(program["ops"]) < 2:
        return fail("emitted program is thinner than the source rule list")

    from_file = emit(json.loads(FIX_SRC.read_text(encoding="utf-8")))
    if from_file["ops"] != program["ops"]:
        return fail("fixture source policy did not emit the same ops as SOURCE_POLICY")
    if from_file["ops"] != emit(SOURCE_POLICY)["ops"]:
        return fail("SOURCE_POLICY drift versus emit_default")

    try:
        emit(FIX_PROSE.read_text(encoding="utf-8"))
        return fail("prose-only markdown was emitted as executable policy")
    except PolicyNotExecutable:
        pass

    with tempfile.TemporaryDirectory(prefix="imp0244-p1-") as tmp:
        prog_path = Path(tmp) / "program.json"
        prog_path.write_text(json.dumps(program, indent=1) + "\n", encoding="utf-8")
        rc_bad, body_bad = ci_eval(prog_path, FIX_BAD)
        rc_ok, body_ok = ci_eval(prog_path, FIX_OK)

    print(
        json.dumps(
            {
                "blueprint_ids": ids,
                "emitted_ops": len(program["ops"]),
                "ci_violating": {"rc": rc_bad, "body": body_bad},
                "ci_compliant": {"rc": rc_ok, "body": body_ok},
                "prose_refused": True,
            },
            sort_keys=True,
        )
    )

    if rc_bad != 1:
        return fail(f"violating fixture CI rc={rc_bad} want=1 body={body_bad}")
    if body_bad.get("decision") != "FAIL":
        return fail(f"violating decision={body_bad.get('decision')} want=FAIL")
    if not body_bad.get("violations"):
        return fail("violating fixture produced FAIL with empty violations")
    if rc_ok != 0:
        return fail(f"compliant fixture CI rc={rc_ok} want=0 body={body_ok}")
    if body_ok.get("decision") != "PASS":
        return fail(f"compliant decision={body_ok.get('decision')} want=PASS")
    if body_ok.get("violations"):
        return fail(f"compliant unexpectedly violated {body_ok.get('violations')}")
    if body_ok.get("prose_consulted") or body_bad.get("prose_consulted"):
        return fail("CI interpreter consulted source prose")

    if not ART.is_file():
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:IMP-0244" not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    pac = doc.get("policy_as_code") or {}
    if pac.get("violating_decision") != "FAIL":
        return fail("receipt did not record violating FAIL")
    if pac.get("compliant_decision") != "PASS":
        return fail("receipt did not record compliant PASS")
    if pac.get("prose_refused") is not True:
        return fail("receipt did not record prose refuse")

    print(
        f"violating_fail=True compliant_pass=True ops={len(program['ops'])} "
        f"prose_refused=True ids={ids}"
    )
    print("SUCCESS:IMP-0244-probe1 emitted policy fails violating, passes compliant")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
