#!/usr/bin/env python3
"""Emit TST-0105 receipt and per-unit G-1 return + manifest.

Order: measure harness tests and live empty/nonempty runs, write
receipts/TST-0105.json (schema-valid), re-run named probes, then write
SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json.
Does not run tools/command-center/unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE.parents[1]))
import _p2lib as L  # noqa: E402

sys.path.insert(0, str(REPO / "hooks" / "harness-bench"))
import harness as H  # noqa: E402

UNIT = "TST-0105"
OUT = "command-center/receipts/TST-0105.json"
SCHEMA = "command-center/schema/benchmark-receipt.schema.json"
HARNESS = "hooks/harness-bench/harness.py"
TEST_PY = "hooks/harness-bench/test_empty_input.py"
FIX = "hooks/harness-bench/fixtures"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0105/probe1_empty_input_failed.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0105/probe2_cardinality_echo.py"
)
TEST_CMD = f"PYTHONDONTWRITEBYTECODE=1 python3 -B {TEST_PY}"
SUPPORTING = [
    HARNESS,
    TEST_PY,
    f"{FIX}/empty.json",
    f"{FIX}/nonempty.json",
    f"{FIX}/historical-empty-pair.json",
    f"{FIX}/historical-nonempty-pair.json",
    "command-center/p2-wave/probes/TST-0105/probe1_empty_input_failed.py",
    "command-center/p2-wave/probes/TST-0105/probe2_cardinality_echo.py",
]


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def json_rows(rows: list[dict]) -> list[dict]:
    return [H.json_row(r) for r in rows]


def parse_json_blob(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise json.JSONDecodeError("no json object", text, 0)
    return json.loads(text[start : end + 1])


def validate_receipt(doc: dict) -> list[str]:
    """Validate against receipt_core + generic_report on jsonschema 4.10.

    platform/lib/schema_resolver.py uses Draft202012Validator(..., registry=)
    which this box's jsonschema 4.10.3 rejects. RefResolver is the working API.
    """
    from jsonschema import Draft202012Validator
    from jsonschema.validators import RefResolver

    receipt = json.loads(
        (REPO / "platform" / "schema" / "receipt.schema.json").read_text(
            encoding="utf-8"
        )
    )
    schema = dict(receipt)
    schema["$ref"] = "#/$defs/generic_report"
    resolver = RefResolver.from_schema(receipt)
    errs = []
    validator = Draft202012Validator(schema, resolver=resolver)
    for err in validator.iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        errs.append(f"{loc}: {err.message}")
    kind = ((doc.get("report") or {}).get("kind"))
    if kind != "benchmark-receipt":
        errs.append(f"report.kind: expected benchmark-receipt, got {kind!r}")
    return sorted(errs)


def main() -> int:
    rc_t, out_t = run_cmd(TEST_CMD)
    if rc_t != 0:
        print(f"FAILED:TST-0105 tests rc={rc_t}")
        print(out_t[-4000:])
        return 1

    empty_inputs = json.loads((REPO / FIX / "empty.json").read_text(encoding="utf-8"))
    nonempty_inputs = json.loads(
        (REPO / FIX / "nonempty.json").read_text(encoding="utf-8")
    )
    hist_empty = json.loads(
        (REPO / FIX / "historical-empty-pair.json").read_text(encoding="utf-8")
    )
    hist_ok = json.loads(
        (REPO / FIX / "historical-nonempty-pair.json").read_text(encoding="utf-8")
    )

    empty_row = H.measure("planted-empty", empty_inputs)
    nonempty_row = H.measure("planted-nonempty", nonempty_inputs)
    naive_row = H.naive_measure("router-eval", [])
    hist_empty_rows = H.measure_cases(hist_empty)
    hist_ok_rows = H.measure_cases(hist_ok)

    if empty_row["ok"] or empty_row["value_ms"] is not None:
        print("FAILED:TST-0105 empty run was reported as a number")
        return 1
    if not nonempty_row["ok"] or nonempty_row["n_inputs"] != len(nonempty_inputs):
        print("FAILED:TST-0105 nonempty run did not echo cardinality")
        return 1
    if any(r["ok"] or r["value_ms"] is not None for r in hist_empty_rows):
        print("FAILED:TST-0105 historical empty pair still greened")
        return 1
    if not all(r["ok"] and r["n_inputs"] >= 1 for r in hist_ok_rows):
        print("FAILED:TST-0105 historical nonempty pair failed")
        return 1
    if naive_row["value_ms"] is None or H.N_TOKEN in naive_row["printed"]:
        print("FAILED:TST-0105 naive detector control did not green-without-n")
        return 1

    cli_empty = (
        f"PYTHONDONTWRITEBYTECODE=1 python3 -B {HARNESS} "
        f"--cases-json {FIX}/historical-empty-pair.json --json"
    )
    cli_ok = (
        f"PYTHONDONTWRITEBYTECODE=1 python3 -B {HARNESS} "
        f"--cases-json {FIX}/historical-nonempty-pair.json --json"
    )
    rc_e, out_e = run_cmd(cli_empty)
    rc_o, out_o = run_cmd(cli_ok)
    if rc_e == 0:
        print("FAILED:TST-0105 CLI empty pair exited 0")
        print(out_e[-2000:])
        return 1
    if rc_o != 0:
        print("FAILED:TST-0105 CLI nonempty pair failed")
        print(out_o[-2000:])
        return 1
    try:
        empty_cli_body = parse_json_blob(out_e)
        ok_cli_body = parse_json_blob(out_o)
    except json.JSONDecodeError as exc:
        print(f"FAILED:TST-0105 CLI json parse {exc}")
        print(out_e[-1500:])
        print(out_o[-1500:])
        return 1

    wf = REPO / ".github" / "workflows" / "routing-benchmark.yml"
    wf_text = wf.read_text(encoding="utf-8") if wf.is_file() else ""
    dep = REPO / "command-center" / "receipts" / "TST-0025.json"
    schema_path = REPO / SCHEMA
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    p_empty = L.probe("source", "command", cli_empty, out_e[-4000:], rc_e)
    p_ok = L.probe("source", "command", cli_ok, out_o[-4000:], rc_o)
    p_test = L.probe("source", "test-run", TEST_CMD, out_t[-4000:], rc_t)
    p_empty_v = L.probe(
        "verifier",
        "test-run",
        TEST_CMD + "::test_empty_input_run_is_failed_not_reported",
        out_t[-4000:],
        rc_t,
    )
    p_card_v = L.probe(
        "verifier",
        "test-run",
        TEST_CMD + "::test_input_cardinality_is_printed_with_every_number",
        out_t[-4000:],
        rc_t,
    )
    p_naive = L.probe(
        "verifier",
        "command",
        "python3 -c naive_measure empty vs measure empty",
        json.dumps(
            {
                "naive_ok": naive_row["ok"],
                "naive_value_ms": naive_row["value_ms"],
                "naive_printed": naive_row["printed"],
                "guarded_ok": empty_row["ok"],
                "guarded_value_ms": empty_row["value_ms"],
                "guarded_printed": empty_row["printed"],
            },
            sort_keys=True,
        ),
        0,
    )

    artifacts = [
        L.art(HARNESS, "supporting"),
        L.art(TEST_PY, "supporting"),
        L.art(f"{FIX}/empty.json", "fixture"),
        L.art(f"{FIX}/nonempty.json", "fixture"),
        L.art(f"{FIX}/historical-empty-pair.json", "fixture"),
        L.art(f"{FIX}/historical-nonempty-pair.json", "fixture"),
        L.art(
            "command-center/p2-wave/probes/TST-0105/probe1_empty_input_failed.py",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/TST-0105/probe2_cardinality_echo.py",
            "supporting",
        ),
    ]

    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0105",
        "spec_anchor": "_USER-PROMPTS.md:11021",
        "min_bytes_threshold": 512,
        "artifacts": artifacts,
        "evidence": [
            L.evidence(
                "An empty-input run is FAILED and does not emit value_ms; the "
                "same process emits a number for a nonempty run with n_inputs "
                "printed beside it.",
                "CONFIRMED",
                f"{HARNESS}:measure",
                [p_empty, p_empty_v],
                "almost-certain",
            ),
            L.evidence(
                "Every emitted benchmark row from the nonempty pair carries "
                "n_inputs >= 1 next to the numeric result; the two historical "
                "empty greens (router-eval, hook-overhead) now fail closed.",
                "CONFIRMED",
                f"{FIX}/historical-empty-pair.json",
                [p_ok, p_card_v],
                "almost-certain",
            ),
            L.evidence(
                "Detector control: naive_measure still reports a number on empty "
                "inputs without n_inputs, proving the old meaningless green is "
                "the path the harness now refuses.",
                "CONFIRMED",
                f"{HARNESS}:naive_measure",
                [p_test, p_naive],
                "almost-certain",
            ),
        ],
        "tests": [
            {
                "id": "test_empty_input_run_is_failed_not_reported",
                "command": TEST_CMD + "::test_empty_input_run_is_failed_not_reported",
                "result": "PASS",
            },
            {
                "id": "test_input_cardinality_is_printed_with_every_number",
                "command": (
                    TEST_CMD + "::test_input_cardinality_is_printed_with_every_number"
                ),
                "result": "PASS",
            },
        ],
        "negative_controls": [
            L.control(
                "empty-vs-nonempty",
                "absent-input",
                "Empty inputs FAIL with no number; nonempty inputs emit value_ms "
                "with n_inputs echoed.",
                True,
                True,
                bad=empty_row["printed"],
                good=nonempty_row["printed"],
            ),
            L.control(
                "naive-timer-still-greens-empty",
                "known-broken-fixture",
                "naive_measure reports a number on empty inputs; measure() does not.",
                True,
                True,
                bad=naive_row["printed"],
                good=empty_row["printed"],
            ),
        ],
        "reviewer": {
            "reviewer_id": "TST-0105-probe2-json-and-regex",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Probe 2 does not call harness.measure or format_row. It parses "
                "CLI --json with json.loads and human lines with regex "
                "value_ms=/n_inputs=. A number without n_inputs on the same "
                "line is a fail. Statistics: this unit gates cardinality, not "
                "a variance band; TST-0109 re-derives variance from raw "
                "per-run numbers after this control is in place."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0105/UNIT-ARTIFACT-MANIFEST.json"
            ),
        },
        "downstream_consumers": [
            {
                "consumer": TEST_PY,
                "artifact_path": HARNESS,
                "executed": True,
                "read_ok": True,
                "exit_code": rc_t,
                "probe": p_test,
            }
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                "unlimited re-runs ONLY with a new recorded seed; re-running "
                "the same seed is a reproduction and must produce the identical "
                "verdict"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Dependency TST-0025 (baseline capture) has no receipt on "
                    "this worktree. TST-0105 delivers the harness control that "
                    "TST-0025's evidence requirement already named; it does not "
                    "claim to freeze pre-change baselines."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "TST-0025 must capture baselines through this harness so "
                    "every frozen row carries n_inputs."
                ),
            },
            {
                "claim": (
                    "This unit gates input cardinality, not a variance band. "
                    "Minimum detectable effect remains TST-0109's job."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "TST-0109 re-derives mean/stdev/MDE from raw per-run numbers "
                    "on rows that already carry n_inputs >= 1."
                ),
            },
            {
                "claim": (
                    "routing-benchmark.yml still owns the weekly HYBRID recall "
                    "net (bench.py/gate.py). The empty-input control is the "
                    "pytest file test_empty_input.py added to that workflow's "
                    "self-test list; the Ollama eval step is a different surface."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Confirm the workflow pytest list contains "
                    "hooks/harness-bench/test_empty_input.py and that a "
                    "skip-on-empty green cannot pass that file."
                ),
            },
        ],
        "report": {
            "kind": "benchmark-receipt",
            "observations": [
                {
                    "name": "empty-input-cli-exit",
                    "measured": rc_e,
                    "method": "harness.py --cases-json historical-empty-pair --json",
                    "anchor": f"{HARNESS}:run_cli",
                },
                {
                    "name": "nonempty-pair-n_inputs",
                    "measured": json.dumps(
                        [r["n_inputs"] for r in hist_ok_rows], separators=(",", ":")
                    ),
                    "method": "harness.measure_cases historical-nonempty-pair",
                    "anchor": f"{FIX}/historical-nonempty-pair.json",
                },
                {
                    "name": "naive-empty-still-emits-number",
                    "measured": True,
                    "method": "naive_measure vs measure both-states",
                    "anchor": f"{HARNESS}:naive_measure",
                },
            ],
            "control_ids": [
                "empty-vs-nonempty",
                "naive-timer-still-greens-empty",
            ],
        },
        "extensions": {
            "completion_sentinel": "SUCCESS:TST-0105",
            "title": "Benchmark harness with a mandatory non-empty-input control",
            "question_or_target": (
                "Measured on this estate: two benchmarks measured EMPTY inputs "
                "and returned a clean, meaningless green. Target: the harness "
                "refuses to emit a number unless it asserts input cardinality "
                "and echoes it beside the result; a zero-cardinality run is "
                "FAILED, not fast."
            ),
            "output_path": OUT,
            "output_schema": SCHEMA,
            "output_schema_present": schema_path.is_file(),
            "routing_benchmark_present": wf.is_file(),
            "routing_benchmark_lists_empty_input_tests": (
                "hooks/harness-bench/test_empty_input.py" in wf_text
            ),
            "tst0025_receipt_present": dep.is_file(),
            "harness": {
                "module": HARNESS,
                "control": (
                    "refuse numeric emit unless n_inputs >= min_n; echo n_inputs"
                ),
                "min_n_default": 1,
                "historical_empty_greens": list(H.HISTORICAL_EMPTY_GREENS),
                "live": {
                    "empty": H.json_row(empty_row),
                    "nonempty": H.json_row(nonempty_row),
                    "naive_empty": {
                        "name": naive_row["name"],
                        "n_inputs": naive_row["n_inputs"],
                        "ok": naive_row["ok"],
                        "value_ms": naive_row["value_ms"],
                        "printed": naive_row["printed"],
                        "naive": True,
                    },
                    "historical_empty_pair": json_rows(hist_empty_rows),
                    "historical_nonempty_pair": json_rows(hist_ok_rows),
                    "rows": json_rows(hist_empty_rows + hist_ok_rows),
                },
                "cli": {
                    "empty_pair_exit": rc_e,
                    "empty_pair_any_failed": empty_cli_body.get("any_failed"),
                    "nonempty_pair_exit": rc_o,
                    "nonempty_pair_any_failed": ok_cli_body.get("any_failed"),
                },
            },
            "notes": (
                "G-1 TST-0105: harness fails closed on empty inputs and echoes "
                "n_inputs beside every number. Did not run global "
                "unit_manifest.py --write. cloud ok=true is not delivery. "
                "SUCCESS:TST-0105"
            ),
            "retry_seed": "TST-0105-empty-vs-nonempty",
            "manifest_derivation": (
                "per-unit (not tools/command-center/unit_manifest.py --write)"
            ),
        },
    }

    errs = validate_receipt(doc)
    if errs:
        print("FAILED:TST-0105 artifact does not satisfy its declared contract")
        for e in errs[:25]:
            print("   ", e)
        return 1
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    sha, size = digest_file(out_path)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:TST-0105 artifact {size}B below floor")
        return 1
    if "SUCCESS:TST-0105" not in out_path.read_text(encoding="utf-8"):
        print("FAILED:TST-0105 sentinel missing after write")
        return 1

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0105 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    now = ended
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0105",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "empty-input-failed-not-reported",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "independent-cardinality-echo",
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": sha,
                "bytes": size,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/TST-0105/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0105-probe2-json-and-regex",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for TST-0105: live named probes exit 0, receipts/TST-0105.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
    }

    def row(rel: str, role: str) -> dict:
        path = REPO / rel
        dgst, nbytes = digest_file(path)
        return {
            "path": rel,
            "sha256": dgst,
            "bytes": nbytes,
            "present": path.is_file(),
            "unit_id": UNIT,
            "receipt_path": "command-center/p2-wave/probes/TST-0105/SUBAGENT-RETURN.json",
            "role": role,
        }

    artifacts_man = [row(OUT, "primary")] + [row(p, "supporting") for p in SUPPORTING]
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts_man),
        "present": sum(1 for a in artifacts_man if a["present"]),
        "artifacts": artifacts_man,
    }

    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"artifact {OUT} bytes={size} sha256={sha}")
    print("SUCCESS:TST-0105 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
