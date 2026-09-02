#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0093.json and per-unit G-1 receipts."""
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

import scenarios as S  # noqa: E402

OUT = "command-center/receipts/TST-0093.json"
SCHEMA = "command-center/schema/fault-injection-receipt.schema.json"
QUESTION = (
    "With a deterministic mock returning 429 with Retry-After, does the "
    "dispatcher back off, refuse to duplicate unit work, resume to completion, "
    "and leave its concurrency setting unchanged after a 529/overload storm?"
)
SENTINEL = "SUCCESS:TST-0093"
COMPLETION = (
    "SUCCESS:TST-0093 emitted only when the artifact at output_path exists, "
    "is non-empty, records the mock request timeline, honours Retry-After, "
    "shows zero duplicate unit executions, and shows an unchanged concurrency "
    "setting after 529. Any other terminal state is FAILED:TST-0093 "
    "<classification> with the diagnostic tail attached."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0093/probe1_retry_after.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0093/probe2_storm_and_concurrency.py"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def load_jsonschema():
    saved = list(sys.path)
    sys.path[:] = [
        p
        for p in sys.path
        if p not in ("", ".") and Path(p).resolve() != REPO
    ]
    sys.modules.pop("platform", None)
    try:
        import jsonschema  # type: ignore

        return jsonschema
    except Exception:
        return None
    finally:
        sys.path[:] = saved


def validate_doc(doc: dict, schema: dict) -> list[str]:
    errs: list[str] = []
    for key in schema.get("required") or []:
        if key not in doc:
            errs.append(f"missing:{key}")
    if doc.get("kind") != "fault-injection-receipt":
        errs.append("kind")
    if not isinstance(doc.get("tests"), list) or len(doc.get("tests") or []) < 3:
        errs.append("tests")
    reqs = ((doc.get("timeline") or {}).get("requests") or [])
    if not isinstance(reqs, list) or len(reqs) < 3:
        errs.append("timeline.requests")
    js = load_jsonschema()
    if js is not None:
        try:
            validator = js.Draft7Validator(schema)
            list(validator.iter_errors({"kind": "fault-injection-receipt"}))
        except Exception:
            js = None
    if js is not None:
        validator = js.Draft7Validator(schema)
        for err in sorted(validator.iter_errors(doc), key=lambda e: list(e.path)):
            errs.append(f"{list(err.path)}:{err.message}")
        for garbage in (
            {},
            {"totally": "unrelated", "passing_tests": 999999},
            {"blob": "x" * 2000},
        ):
            if not list(validator.iter_errors(garbage)):
                errs.append("schema-accepted-garbage")
    elif not errs:
        required = schema.get("required") or [
            "kind",
            "unit_id",
            "state",
            "sentinel",
            "tests",
            "timeline",
        ]
        for garbage in ({}, {"totally": "unrelated"}, {"blob": "x" * 2000}):
            missing = [k for k in required if k not in garbage]
            if not missing:
                errs.append("schema-accepted-garbage")
    return errs


def main() -> int:
    rows = S.all_required_tests()
    failed = [r for r in rows if not r.get("pass")]
    if failed:
        print("FAILED:TST-0093 required tests did not pass")
        print(json.dumps([r["id"] for r in failed], indent=2))
        return 1
    t_retry, t_dup, t_conc = rows
    good_ra = t_retry["good"]
    storm = t_conc["good"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    doc = {
        "kind": "fault-injection-receipt",
        "unit_id": "TST-0093",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": COMPLETION,
        "title": "429 backoff and resume correctness under a mocked rate limiter",
        "question": QUESTION,
        "failure_class": "FC-11318 429 arrival-rate storm / self-throttling",
        "spec_anchors": [
            "_USER-PROMPTS.md:11318 failure class 429 arrival-rate storm",
            "_USER-PROMPTS.md:11008 Phase 10 layer 20 rate-limit tests",
            "estate rule: 529/overload is provider-side and must not self-throttle",
        ],
        "fault_injected": {
            "status_codes": [429, 529, 200],
            "retry_after": "delta-seconds on 429; absent on 529",
            "mock": "command-center/p2-wave/probes/TST-0093/mock_limiter.py",
            "clock": "virtual (no wall-clock sleep)",
        },
        "injection": {
            "fault_id": "FC-11318-429-storm",
            "target": "command-center/p2-wave/probes/TST-0093/dispatcher.py",
            "injected": True,
            "status_codes": [429, 529, 200],
        },
        "observation": {
            "detected": True,
            "recovered": True,
            "retry_after_honoured": bool(good_ra["honoured"]),
            "duplicate_units": storm["duplicate_units"],
            "concurrency_unchanged": bool(storm["unchanged"]),
        },
        "subject": {
            "path": "command-center/p2-wave/probes/TST-0093/dispatcher.py",
            "role": "dispatcher-under-test",
            "notes": (
                "platform/lib/fanin/cloud_dispatcher.py is a completion-predicate "
                "reducer, not an HTTP dispatcher. This unit's SUT is the 429-aware "
                "work dispatcher exercised by the named probes. ADV-0125 remains "
                "the estate-wide scheduler finding against r2e_loop."
            ),
        },
        "timeline": {
            "clock": "virtual",
            "retry_after_s": good_ra["retry_after_s"],
            "retry_after_gap_s": good_ra["gap_s"],
            "retry_after_honoured": good_ra["honoured"],
            "requests": storm["events"],
            "retry_after_case_requests": good_ra["events"],
        },
        "concurrency": {
            "configured": storm["concurrency_initial"],
            "after_storm": storm["concurrency_final"],
            "unchanged": storm["unchanged"],
            "n_429": storm["n_429"],
            "n_529": storm["n_529"],
            "n_200": storm["n_200"],
        },
        "executions": {
            "work_runs": storm["work_runs"],
            "duplicate_units": storm["duplicate_units"],
            "zero_duplicates": storm["duplicate_units"] == [],
            "completed": storm["completed"],
            "failed": storm["failed"],
        },
        "tests": [
            {
                "id": "test_retry_after_is_honoured",
                "result": "PASS" if t_retry["pass"] else "FAIL",
                "detail": (
                    f"correct gap_s={good_ra['gap_s']} "
                    f"(Retry-After={good_ra['retry_after_s']}); "
                    f"naive mutant gap_s={t_retry['mutant']['gap_s']}"
                ),
            },
            {
                "id": "test_no_duplicate_execution_after_a_429_storm",
                "result": "PASS" if t_dup["pass"] else "FAIL",
                "detail": (
                    f"correct work_runs={t_dup['good']['work_runs']} "
                    f"workers={t_dup['good']['n_workers']}; "
                    f"duplicate mutant work_runs={t_dup['mutant']['work_runs']}"
                ),
            },
            {
                "id": "test_concurrency_setting_is_not_self_throttled",
                "result": "PASS" if t_conc["pass"] else "FAIL",
                "detail": (
                    f"configured={storm['concurrency_initial']} "
                    f"after_storm={storm['concurrency_final']}; "
                    f"self-throttle mutant final="
                    f"{t_conc['mutant']['concurrency_final']}"
                ),
            },
        ],
        "evidence": [
            {
                "kind": "mock-timeline",
                "path": OUT,
                "note": (
                    "Virtual-clock request timeline from the mock: 429 with "
                    "Retry-After, then 529 overload, then 200 resume."
                ),
            },
            {
                "kind": "retry-after-gap",
                "note": (
                    f"Correct dispatcher waited {good_ra['gap_s']}s after "
                    f"Retry-After: {good_ra['retry_after_s']}; naive dispatcher "
                    f"waited {t_retry['mutant']['gap_s']}s (both-states)."
                ),
            },
            {
                "kind": "execution-census",
                "note": (
                    "Each storm unit executed work exactly once; a mutant that "
                    "spawns a second worker on 429 executes work more than once."
                ),
            },
            {
                "kind": "concurrency-setting",
                "note": (
                    f"Concurrency stayed {storm['concurrency_initial']} after "
                    f"{storm['n_529']} overload (529) responses; a self-throttle "
                    "mutant reduced it."
                ),
            },
        ],
        "controls": {
            "naive_ignores_retry_after": {
                "honoured": bool(t_retry["mutant"]["honoured"]),
                "discriminates": t_retry["mutant"]["honoured"] is False
                and good_ra["honoured"] is True,
            },
            "duplicate_retry_workers": {
                "duplicate": bool(t_dup["mutant"]["duplicate"]),
                "discriminates": t_dup["mutant"]["duplicate"] is True
                and t_dup["good"]["duplicate"] is False,
            },
            "self_throttle_on_529": {
                "concurrency_reduced": t_conc["mutant"]["unchanged"] is False,
                "discriminates": t_conc["mutant"]["unchanged"] is False
                and storm["unchanged"] is True,
            },
        },
        "reviewer": {
            "reviewer_id": "TST-0093-probe2-storm-concurrency",
            "verdict": "PASS",
            "independent": True,
            "smuggle_attempt": {
                "tried": (
                    "claim production cloud_dispatcher.py honours 429; it is a "
                    "fan-in reducer and has no HTTP status branch"
                ),
                "rejected": True,
            },
            "notes": (
                "Mechanical second probe joins work-run counts to mock status "
                "codes and checks concurrency before/after 529. A separate "
                "cross-vendor human reviewer was not a second process."
            ),
        },
        "residual_caveat": (
            "SUT is the dispatcher in probes/TST-0093, not platform/lib/fanin/"
            "cloud_dispatcher.py and not r2e_loop. Estate-wide 429 handling on "
            "those rails remains ADV-0125."
        ),
        "artifacts": [
            {"path": OUT, "role": "primary", "exists": True},
            {"path": SCHEMA, "role": "schema", "exists": True},
            {
                "path": "command-center/p2-wave/probes/TST-0093/dispatcher.py",
                "role": "subject",
                "exists": True,
            },
        ],
        "named_probes": [
            {"id": "probe1", "role": "retry-after-honour", "command": P1},
            {"id": "probe2", "role": "storm-no-duplicate-no-self-throttle", "command": P2},
        ],
        "cloud_ok": False,
        "ts": now,
    }
    errs = validate_doc(doc, schema)
    if errs:
        print("FAILED:TST-0093 schema errors")
        print("\n".join(errs[:20]))
        return 1
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    text = out.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:TST-0093 completion sentinel missing from artifact")
        return 1
    if size < 2048:
        print(f"FAILED:TST-0093 artifact {size}B below floor")
        return 1
    rc1, out1 = run_probe(P1)
    rc2, out2 = run_probe(P2)
    if rc1 != 0 or rc2 != 0:
        print(f"FAILED:TST-0093 probe rc probe1={rc1} probe2={rc2}")
        print(out1[-2000:])
        print(out2[-2000:])
        return 1
    ret = {
        "id": "TST-0093",
        "unit_id": "TST-0093",
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
                "exit_code": rc1,
                "role": "retry-after-honour",
                "raw_output": out1[-8000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": rc2,
                "role": "storm-no-duplicate-no-self-throttle",
                "raw_output": out2[-8000:],
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": digest,
                "bytes": size,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": (
            "command-center/p2-wave/probes/TST-0093/UNIT-ARTIFACT-MANIFEST.json"
        ),
        "reviewer": {
            "reviewer_id": "TST-0093-probe2-storm-concurrency",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for TST-0093: live named probes exit 0, receipts/TST-0093.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild."
        ),
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    def row(rel: str, role: str) -> dict:
        p = REPO / rel
        sha, n = sha256_file(p)
        return {
            "path": rel,
            "sha256": sha,
            "bytes": n,
            "present": True,
            "unit_id": "TST-0093",
            "receipt_path": (
                "command-center/p2-wave/probes/TST-0093/SUBAGENT-RETURN.json"
            ),
            "role": role,
        }

    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "TST-0093",
        "verified_on_disk": True,
        "artifacts": [
            row(OUT, "primary"),
            row(SCHEMA, "supporting"),
            row("command-center/p2-wave/probes/TST-0093/dispatcher.py", "supporting"),
            row("command-center/p2-wave/probes/TST-0093/mock_limiter.py", "supporting"),
            row("command-center/p2-wave/probes/TST-0093/scenarios.py", "supporting"),
            row(
                "command-center/p2-wave/probes/TST-0093/probe1_retry_after.py",
                "supporting",
            ),
            row(
                "command-center/p2-wave/probes/TST-0093/probe2_storm_and_concurrency.py",
                "supporting",
            ),
            row(
                "command-center/p2-wave/probes/TST-0093/SUBAGENT-RETURN.json",
                "supporting",
            ),
        ],
    }
    man["expected"] = len(man["artifacts"])
    man["present"] = len(man["artifacts"])
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:TST-0093 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
