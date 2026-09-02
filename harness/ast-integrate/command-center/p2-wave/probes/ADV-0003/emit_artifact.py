#!/usr/bin/env python3
"""Emit command-center/adversarial/ADV-0003-exit-zero-missing-artifact-injection.json."""
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
OUT_REL = "command-center/adversarial/ADV-0003-exit-zero-missing-artifact-injection.json"
SCHEMA_REL = "command-center/schema/exploit-proof.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0003/probe1_barrier_injection.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0003/probe2_scandir_oracle.py"
)
SENTINEL = "SUCCESS:ADV-0003"
COMPLETION = (
    "SUCCESS:ADV-0003 emitted ONLY when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, records BOTH named probes "
    "verbatim with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, "
    "and records the result of every listed control/negative test. Any missing "
    "control downgrades the unit's verdicts to NOT-CHECKED. Otherwise "
    "FAILED:ADV-0003 <reason>."
)
PROBE1_TEXT = (
    "Probe 1: run the mock workers through each barrier and record the "
    "barrier's verdict plus the exact filesystem state."
)
PROBE2_TEXT = (
    "Probe 2 (mechanically different): filesystem audit (os.scandir of the "
    "output root) taken independently of the barrier's own reporting, so a "
    "barrier that reports the file exists can be contradicted by the "
    "directory listing."
)
QUESTION = (
    "For each fan-in barrier in the program, does a worker that exits 0 "
    "while writing no artifact (or writing to a path one character off) get "
    "recorded as complete?"
)


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
        timeout=120,
    )
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()


def parse_json_prefix(raw: str) -> dict:
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        doc = json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return {}
    return doc if isinstance(doc, dict) else {}


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def validate(doc: dict) -> None:
    schema_path = REPO / SCHEMA_REL
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    try:
        import jsonschema  # type: ignore
    except ImportError as exc:
        required = schema.get("required") or []
        missing = [k for k in required if k not in doc]
        if missing:
            raise RuntimeError(f"schema required keys missing: {missing}") from exc
        return
    jsonschema.Draft7Validator(schema).validate(doc)


def build_doc(p1: dict, p2: dict, raw1: str, raw2: str, c1: int, c2: int) -> dict:
    checks1 = p1.get("checks") or {}
    checks2 = p2.get("checks") or {}
    inv = p1.get("inventory") or {}
    barriers = inv.get("barriers") or []
    case = p2.get("case_collision") or {}
    production_rejects = bool(checks1.get("missing_rejected_by_production")) and bool(
        checks1.get("near_miss_rejected_by_production")
    )
    control_accepts = bool(checks1.get("valid_accepted_by_production"))
    scandir_contradicts_mutant = bool(
        checks2.get("mutant_exists_claim_contradicted_by_scandir")
    )
    case_explicit = bool(checks2.get("case_collision_classified_explicitly"))
    all_ok = (
        c1 == 0
        and c2 == 0
        and production_rejects
        and control_accepts
        and scandir_contradicts_mutant
        and case_explicit
    )
    if not all_ok:
        raise RuntimeError(
            "emit gates failed: "
            + json.dumps(
                {
                    "c1": c1,
                    "c2": c2,
                    "production_rejects": production_rejects,
                    "control_accepts": control_accepts,
                    "scandir_contradicts_mutant": scandir_contradicts_mutant,
                    "case_explicit": case_explicit,
                    "checks1": checks1,
                    "checks2": checks2,
                },
                default=str,
            )[:4000]
        )

    roles = [str(b.get("role") or "") for b in barriers]
    answer = (
        "No. All seven production fan-in barriers (local-runner, "
        "cloud-dispatcher, monitor, harvester, workflow-fan-in, "
        "cross-vendor-adapter, final-synthesis) call agentspec.oracle.judge "
        "and do not take the worker exit code as input. A mock worker that "
        "exits 0 and writes nothing is recorded incomplete (receipt absent). "
        "Workers that exit 0 and write a near-miss path (Output.json, "
        "'output.json ' with a trailing space, or a backslash-named file) "
        "are recorded incomplete (expected output.json absent on disk). The "
        "detector control — the same worker writing a valid receipt plus "
        "output.json — is accepted by every barrier, so rejection is not a "
        "reject-everything detector. An exit-zero-is-complete mutant accepts "
        "the missing worker; independent os.scandir of that tree lists no "
        "output.json and therefore contradicts the mutant's exists-claim. "
        f"Windows Output.json vs output.json classified as "
        f"{case.get('classification')}: silently_accepted="
        f"{case.get('silently_accepted')}."
    )

    enumerated = []
    for b in barriers:
        role = str(b.get("role") or "unnamed")
        enumerated.append(
            {
                "id": f"fan-in-{role}-exit-zero-missing-recorded-complete",
                "question": (
                    f"Does the {role} barrier record an exit-0 missing-artifact "
                    "worker as complete?"
                ),
                "verdict": "REFUTED",
                "meaning": (
                    "REFUTED means the barrier did not treat exit 0 with a "
                    "missing artifact as complete."
                ),
            }
        )
    enumerated.extend(
        [
            {
                "id": "near-miss-path-recorded-complete",
                "question": (
                    "Does a worker that exits 0 and writes to a one-character-off "
                    "path get recorded as complete?"
                ),
                "verdict": "REFUTED",
            },
            {
                "id": "scandir-contradicts-barrier-exists-claim",
                "question": (
                    "Can os.scandir of the output root contradict a barrier that "
                    "reports the file exists?"
                ),
                "verdict": "CONFIRMED",
                "meaning": (
                    "CONFIRMED on the exit-zero mutant, which claims the artifact "
                    "exists while scandir lists no output.json. Production "
                    "barriers agree with scandir."
                ),
            },
            {
                "id": "windows-case-collision-output-json",
                "question": (
                    "Is Output.json vs output.json classified explicitly rather "
                    "than silently accepted?"
                ),
                "verdict": "REFUTED",
                "classification": case.get("classification"),
                "silently_accepted": case.get("silently_accepted"),
                "meaning": (
                    "REFUTED means silent-accept of the case-collision did not "
                    "occur; the variant is classified explicitly."
                ),
            },
        ]
    )

    tests = [
        {
            "id": "T-DETECTOR-CONTROL-VALID-WORKER-ACCEPTED",
            "name": (
                "detector control: a worker that DOES write a valid artifact "
                "must be accepted, proving the barrier is not rejecting everything"
            ),
            "result": "PASS" if control_accepts else "FAIL",
        },
        {
            "id": "T-CASE-COLLISION-EXPLICIT",
            "name": (
                "case-collision variant on Windows (Output.json vs output.json) "
                "must be classified explicitly, not silently accepted"
            ),
            "result": "PASS" if case_explicit else "FAIL",
            "classification": case.get("classification"),
        },
        {
            "id": "T-MISSING-REJECTED",
            "name": "exit-0 worker that writes nothing is not recorded complete",
            "result": "PASS" if checks1.get("missing_rejected_by_production") else "FAIL",
        },
        {
            "id": "T-NEAR-MISS-REJECTED",
            "name": "exit-0 near-miss path is not recorded complete",
            "result": "PASS" if checks1.get("near_miss_rejected_by_production") else "FAIL",
        },
        {
            "id": "T-SCANDIR-CONTRADICTS-MUTANT",
            "name": "os.scandir contradicts mutant exists-claim on the missing tree",
            "result": "PASS" if scandir_contradicts_mutant else "FAIL",
        },
        {
            "id": "T-SEVEN-BARRIERS",
            "name": "all seven dispatcher/workflow fan-in barriers were exercised",
            "result": "PASS" if checks1.get("seven_production_barriers") else "FAIL",
            "roles": roles,
        },
    ]
    if any(t["result"] != "PASS" for t in tests):
        raise RuntimeError("emit tests not all PASS")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "unit_id": "ADV-0003",
        "id": "ADV-0003",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": COMPLETION,
        "report_kind": "exploit-proof",
        "title": "Exit-zero-with-missing-artifact injection against every fan-in barrier",
        "question": QUESTION,
        "answer": answer,
        "overall_verdict": "REFUTED",
        "mechanism": (
            "fault injection of the exit-code/artifact divergence directly at "
            "the barrier, with an out-of-band filesystem oracle"
        ),
        "spec_anchor": "_USER-PROMPTS.md:10646, 11312",
        "output_path": OUT_REL,
        "output_schema": SCHEMA_REL,
        "produced_at": now,
        "enumerated_targets": enumerated,
        "probes": [
            {
                "id": "probe1",
                "verbatim": PROBE1_TEXT,
                "command": P1,
                "exit_code": c1,
                "raw_output": raw1,
                "role": "barrier-injection",
            },
            {
                "id": "probe2",
                "verbatim": PROBE2_TEXT,
                "command": P2,
                "exit_code": c2,
                "raw_output": raw2,
                "role": "scandir-oracle",
            },
        ],
        "named_probes": [
            {
                "id": "probe1",
                "verbatim": PROBE1_TEXT,
                "command": P1,
                "exit_code": c1,
                "raw_output": raw1,
                "role": "barrier-injection",
            },
            {
                "id": "probe2",
                "verbatim": PROBE2_TEXT,
                "command": P2,
                "exit_code": c2,
                "raw_output": raw2,
                "role": "scandir-oracle",
            },
        ],
        "tests": tests,
        "negative_controls": [
            {
                "id": "NC-EXIT-ZERO-MUTANT",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state": (
                    "mutant treats worker exit 0 as complete and claims "
                    "output.json exists while scandir lists it absent"
                ),
                "good_state": (
                    "production barriers reject missing/near-miss and accept "
                    "the valid control; scandir agrees"
                ),
                "result": "PASS",
            }
        ],
        "reviewer": {
            "reviewer_id": "ADV-0003-probe2-scandir-oracle",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "os.scandir of the output root, mechanically different from "
                "barrier.consider()"
            ),
        },
        "evidence": [
            {
                "claim": (
                    "seven production fan-in consider() sites reject exit-0 "
                    "missing-artifact and near-miss writes"
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/agentspec/agentspec/fanin/",
            },
            {
                "claim": (
                    "detector control: valid artifact worker is accepted by "
                    "every production barrier"
                ),
                "verdict": "CONFIRMED",
                "anchor": PROBE1_TEXT,
            },
            {
                "claim": (
                    "os.scandir contradicts the exit-zero mutant exists-claim "
                    "on the missing tree"
                ),
                "verdict": "CONFIRMED",
                "anchor": PROBE2_TEXT,
            },
            {
                "claim": (
                    "Output.json vs output.json classified explicitly; not "
                    "silently accepted"
                ),
                "verdict": "CONFIRMED",
                "anchor": str(case.get("classification")),
            },
        ],
        "inventory": inv,
        "case_collision": case,
        "worker_exit_codes": p1.get("worker_exit_codes"),
        "hypothesis": (
            "A worker that exits 0 with no artifact (or a one-character-off "
            "path) is recorded complete by a fan-in barrier."
        ),
        "result": (
            "Hypothesis REFUTED on production barriers; CONFIRMED on the "
            "exit-zero mutant, which probe 2's scandir oracle catches."
        ),
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0:
        print("FAILED:ADV-0003 emit probe1")
        print(t1[-4000:])
        return 1
    if c2 != 0:
        print("FAILED:ADV-0003 emit probe2")
        print(t2[-4000:])
        return 1
    j1 = parse_json_prefix(t1)
    j2 = parse_json_prefix(t2)
    try:
        doc = build_doc(j1, j2, t1, t2, c1, c2)
    except RuntimeError as exc:
        print(f"FAILED:ADV-0003 emit {exc}")
        return 1
    validate(doc)
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if SENTINEL not in text:
        print("FAILED:ADV-0003 catalog sentinel missing from serialisation")
        return 1
    if COMPLETION not in text:
        print("FAILED:ADV-0003 completion_sentinel missing from serialisation")
        return 1
    if PROBE1_TEXT not in text or PROBE2_TEXT not in text:
        print("FAILED:ADV-0003 named probe text missing")
        return 1
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    sha, size = sha256_file(out)
    print(f"wrote {OUT_REL} bytes={size} sha256={sha}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
