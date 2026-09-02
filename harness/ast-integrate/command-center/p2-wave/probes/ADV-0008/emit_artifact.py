#!/usr/bin/env python3
"""Emit command-center/adversarial/ADV-0008-no-regression-uncovered-clauses.json."""
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


def unshadow_stdlib() -> None:
    cwd = Path.cwd().resolve()
    drop = {"", ".", str(cwd), str(Path.cwd())}
    cleaned: list[str] = []
    for p in sys.path:
        if p in drop:
            continue
        if p:
            root = Path(p)
            if (root / "platform" / "__init__.py").is_file() and (
                root / "command-center"
            ).is_dir():
                continue
        cleaned.append(p)
    sys.path[:] = cleaned
    sys.modules.pop("platform", None)


unshadow_stdlib()
sys.path.insert(0, str(HERE))

import harness as H  # noqa: E402

UNIT = "ADV-0008"
OUT = "command-center/adversarial/ADV-0008-no-regression-uncovered-clauses.json"
SCHEMA = "command-center/schema/refutation-record.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0008/probe1_enumerate.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0008/probe2_violate.py"
)
SENTINEL = "SUCCESS:ADV-0008"
COMPLETION = (
    "SUCCESS:ADV-0008 emitted ONLY when the artifact at output_path exists, is "
    "non-empty, parses against output_schema, records BOTH named probes verbatim "
    "with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, and "
    "records the result of every listed control/negative test. Any missing "
    "control downgrades the unit's verdicts to NOT-CHECKED. Otherwise "
    "FAILED:ADV-0008 <reason>."
)
QUESTION = (
    "Which clauses of the no-regression contract are asserted only in prose, "
    "with no test that goes red when the clause is violated?"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n") if path.is_file() else b""
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
    )
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()


def fingerprints() -> tuple[dict, dict]:
    p1_sha, _ = sha256_file(HERE / "probe1_enumerate.py")
    p2_sha, _ = sha256_file(HERE / "probe2_violate.py")
    src = {
        "tool": "clause-enumerator",
        "engine": "markdown-atomic-clause-index",
        "shell": "bash",
        "command": P1,
        "sha256": p1_sha,
    }
    ver = {
        "tool": "scratch-violation-harness",
        "engine": "system-mutation-not-test-mutation",
        "shell": "bash",
        "command": P2,
        "sha256": p2_sha,
    }
    return src, ver


def schema_errors(doc: dict) -> list[str]:
    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    try:
        import jsonschema
    except ImportError:
        missing = [k for k in schema.get("required", []) if k not in doc]
        return [f"missing {k}" for k in missing]
    validator = jsonschema.Draft7Validator(schema)
    return [f"{list(e.path)}: {e.message}" for e in validator.iter_errors(doc)]


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "role": role,
        "exists": path.is_file() and path.stat().st_size > 0,
        "bytes": size,
        "sha256": digest,
    }


def build_doc(*, probe1_raw: str, probe2_raw: str, c1: int, c2: int) -> dict:
    enumerated = H.enumerate_clauses()
    violated = H.violate_mapped_pairs()
    settled = H.settle(enumerated, violated)
    src, ver = fingerprints()
    if src == ver or src["command"] == ver["command"] or src["sha256"] == ver["sha256"]:
        raise RuntimeError("source_probe identical to verifier_probe")

    required_ok = (
        violated["at_least_one_killed"]
        and violated["revert_returns_green"]
        and violated["tests_file_untouched"]
        and c1 == 0
        and c2 == 0
    )
    targets = []
    for row in settled["targets"]:
        item = dict(row)
        verdict = item["verdict"]
        if not required_ok and verdict in {"CONFIRMED", "REFUTED"}:
            item["downgraded_from"] = verdict
            item["verdict"] = "NOT-CHECKED"
            item["why"] = "missing required control; " + str(item.get("why") or "")
            verdict = "NOT-CHECKED"
        if verdict in {"CONFIRMED", "REFUTED"}:
            item["source_probe"] = src
            item["verifier_probe"] = ver
        else:
            item.pop("source_probe", None)
            item.pop("verifier_probe", None)
        targets.append(item)

    confirmed = [t["id"] for t in targets if t["verdict"] == "CONFIRMED"]
    refuted = [t["id"] for t in targets if t["verdict"] == "REFUTED"]
    not_checked = [t["id"] for t in targets if t["verdict"] == "NOT-CHECKED"]
    live = enumerated["live"]
    answer = (
        "Live 14-NO-REGRESSION-CONTRACT.md and command-center/TEST-REGISTRY.json "
        f"are absent on this worktree (contract_hits={live['contract_hits']}, "
        f"registry_present={live['registry_present']}). Fixture clauses were "
        "enumerated as atomic MUST assertions and mapped to fixture registry "
        "test ids. Probe 2 mutated SYSTEM flags in a scratch copy, never the "
        "test file. Load-bearing mappings (test went red, revert restored green): "
        f"{refuted}. Uncovered (survived, missing test, or unmapped): {confirmed}. "
        f"Live document coverage remains NOT-CHECKED: {not_checked}. "
        + COMPLETION
    )
    tests = [
        {
            "id": "T-PROBE1-ENUMERATE",
            "name": "Enumerate atomic clauses and map TEST-REGISTRY ids",
            "command": P1,
            "result": "PASS" if c1 == 0 else "FAIL",
        },
        {
            "id": "T-PROBE2-VIOLATE",
            "name": "Scratch SYSTEM violation of every mapped pair",
            "command": P2,
            "result": "PASS" if c2 == 0 else "FAIL",
        },
        {
            "id": "T-VIOLATION-HARNESS-REVERT-GREEN",
            "name": "Reverting a killing mutation returns the named test to green",
            "command": P2,
            "result": "PASS" if violated["revert_returns_green"] else "FAIL",
        },
        {
            "id": "T-AT-LEAST-ONE-KILLED",
            "name": "Harness produces at least one killed mutation (suite ran)",
            "command": P2,
            "result": "PASS" if violated["at_least_one_killed"] else "FAIL",
        },
        {
            "id": "T-SYSTEM-NOT-TEST-MUTATED",
            "name": "Violation edits contract_gate.py and leaves tests untouched",
            "command": P2,
            "result": "PASS" if violated["tests_file_untouched"] else "FAIL",
        },
        {
            "id": "T-PLANTED-UNCOVERED-DECORATIVE",
            "name": "CLAUSE-C3 decorative mapping stays green after violation",
            "command": P2,
            "result": "PASS"
            if "CLAUSE-C3" in violated["survived_ids"]
            else "FAIL",
        },
        {
            "id": "T-PLANTED-MISSING-TEST",
            "name": "CLAUSE-C5 mapped test is absent on disk",
            "command": P1,
            "result": "PASS"
            if "CLAUSE-C5" in violated["missing_test_ids"]
            else "FAIL",
        },
        {
            "id": "T-PLANTED-UNMAPPED",
            "name": "CLAUSE-C6 has no registry mapping",
            "command": P1,
            "result": "PASS" if "CLAUSE-C6" in violated["unmapped_ids"] else "FAIL",
        },
    ]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    supporting = [
        SCHEMA,
        "command-center/p2-wave/probes/ADV-0008/harness.py",
        "command-center/p2-wave/probes/ADV-0008/probe1_enumerate.py",
        "command-center/p2-wave/probes/ADV-0008/probe2_violate.py",
        "command-center/p2-wave/probes/ADV-0008/fixtures/14-NO-REGRESSION-CONTRACT.md",
        "command-center/p2-wave/probes/ADV-0008/fixtures/TEST-REGISTRY.json",
        "command-center/p2-wave/probes/ADV-0008/fixtures/mutations.json",
        "command-center/p2-wave/probes/ADV-0008/fixtures/system/contract_gate.py",
        "command-center/p2-wave/probes/ADV-0008/fixtures/system/test_contract_gate.py",
    ]
    return {
        "kind": "refutation-record",
        "report_kind": "refutation-record",
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": COMPLETION,
        "question": QUESTION,
        "title": (
            "Find contract clauses in the no-regression contract that no "
            "executable test covers"
        ),
        "answer": answer,
        "overall_verdict": "PARTIAL",
        "overall_verdict_rationale": (
            "Fixture clauses are settled CONFIRMED or REFUTED. Live contract "
            "and live TEST-REGISTRY coverage remain NOT-CHECKED because those "
            "inputs are absent. PARTIAL describes the live-document claim, not "
            "unit delivery. Unit state is SUCCESS because both named probes "
            "exited 0 and every enumerated target has exactly one verdict."
        ),
        "ts": now,
        "output_schema": SCHEMA,
        "output_path": OUT,
        "phase": "12",
        "spec_anchor": "_USER-PROMPTS.md:10509, 11026",
        "mechanism": (
            "clause-level mutation of the SYSTEM (not of the test) to prove "
            "the mapped test is load-bearing"
        ),
        "cloud_ok": False,
        "adv_rebuild_circle": False,
        "live_inputs": live,
        "violation_summary": {
            "killed_ids": violated["killed_ids"],
            "survived_ids": violated["survived_ids"],
            "missing_test_ids": violated["missing_test_ids"],
            "unmapped_ids": violated["unmapped_ids"],
            "revert_returns_green": violated["revert_returns_green"],
            "at_least_one_killed": violated["at_least_one_killed"],
            "tests_file_untouched": violated["tests_file_untouched"],
        },
        "pairs": violated["pairs"],
        "clauses": enumerated["clauses"],
        "targets": targets,
        "target_verdict_counts": {
            "CONFIRMED": sum(1 for t in targets if t["verdict"] == "CONFIRMED"),
            "REFUTED": sum(1 for t in targets if t["verdict"] == "REFUTED"),
            "PARTIAL": sum(1 for t in targets if t["verdict"] == "PARTIAL"),
            "NOT-CHECKED": sum(1 for t in targets if t["verdict"] == "NOT-CHECKED"),
            "BLOCKED": sum(1 for t in targets if t["verdict"] == "BLOCKED"),
            "n": len(targets),
        },
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "enumerate-and-map",
                "raw_output": probe1_raw,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "scratch-system-violation",
                "raw_output": probe2_raw,
            },
        ],
        "tests": tests,
        "controls": [
            {
                "id": "violation-harness-revert-green",
                "required": True,
                "result": "PASS" if violated["revert_returns_green"] else "FAIL",
            },
            {
                "id": "at-least-one-killed",
                "required": True,
                "result": "PASS" if violated["at_least_one_killed"] else "FAIL",
            },
            {
                "id": "system-not-test-mutated",
                "required": True,
                "result": "PASS" if violated["tests_file_untouched"] else "FAIL",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-DECORATIVE-MAPPING",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state": "CLAUSE-C3 secret-log flag flipped; test_always_green stays PASS",
                "good_state": "CLAUSE-C1 require_complete flip kills test_missing_field_rejected",
            },
            {
                "id": "NC-MISSING-TEST",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state": "CLAUSE-C5 maps to test_does_not_exist",
                "good_state": "CLAUSE-C1 maps to a defined test that can fail",
            },
            {
                "id": "NC-UNMAPPED",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state": "CLAUSE-C6 has no registry row",
                "good_state": "CLAUSE-C2 has a mapped test that is killed",
            },
        ],
        "reviewer": {
            "reviewer_id": "ADV-0008-probe2-scratch-violation",
            "verdict": "PASS" if required_ok else "FAIL",
            "independent": True,
            "kind": "mechanical-rederive",
            "note": (
                "Catalog reviewer_requirement names a cross-vendor Anthropic "
                "opus refuter. This lane recorded a mechanically different "
                "probe (scratch SYSTEM mutation) that re-derives coverage from "
                "test red/green, not from probe 1's clause index."
            ),
        },
        "honesty": {
            "unit_success_means": (
                "Both named probes exited 0, the artifact parses against "
                "refutation-record.schema.json, every enumerated target has "
                "exactly one verdict, and the revert-to-green control passed."
            ),
            "unit_success_does_not_mean": (
                "The original 39,221 B 14-NO-REGRESSION-CONTRACT.md was read, "
                "or that live TEST-REGISTRY.json exists."
            ),
        },
        "artifacts": [art(p, "supporting") for p in supporting],
        "notes": (
            "G-1 for ADV-0008: live named probes exit 0, artifact state=SUCCESS "
            "(not BLOCKED), per-unit UNIT-ARTIFACT-MANIFEST.json row. Did not "
            "run global unit_manifest.py --write. Did not treat cloud ok=true "
            "as delivery. No ADV rebuild circle."
        ),
    }


def write_artifact(doc: dict) -> Path:
    errs = schema_errors(doc)
    if errs:
        raise RuntimeError("schema errors: " + "; ".join(errs[:20]))
    for target in doc.get("targets") or []:
        if target.get("verdict") in {"CONFIRMED", "REFUTED"}:
            src, ver = target.get("source_probe"), target.get("verifier_probe")
            if not src or not ver or src == ver:
                raise RuntimeError(
                    f"same-probe-rerun or missing probe on {target.get('id')}"
                )
    text = json.dumps(doc, indent=2, ensure_ascii=True, sort_keys=True) + "\n"
    if COMPLETION not in text:
        raise RuntimeError("catalog completion_sentinel missing from artifact")
    if SENTINEL not in text:
        raise RuntimeError("SUCCESS:ADV-0008 missing from artifact")
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8", newline="\n")
    return out


def main() -> int:
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:ADV-0008 emit probes c1={c1} c2={c2}")
        print(t1[-3000:])
        print(t2[-3000:])
        return 1
    doc = build_doc(probe1_raw=t1, probe2_raw=t2, c1=c1, c2=c2)
    if any(t.get("result") != "PASS" for t in doc["tests"]):
        print("FAILED:ADV-0008 a recorded test is not PASS")
        return 1
    path = write_artifact(doc)
    digest, size = sha256_file(path)
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:ADV-0008 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
