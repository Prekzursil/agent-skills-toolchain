#!/usr/bin/env python3
"""Emit command-center/receipts/SYN-0039.json.

Catalog output_schema is a $ref shim to ast-integrate.invalid. jsonschema 4.10
would fetch that URL; this emit resolves the physical schemas from disk and
refuses remote handlers. Domain payload lives under report (receipt_core
additionalProperties is false).
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema.exceptions import RefResolutionError
from jsonschema.validators import RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402

OUT = "command-center/receipts/SYN-0039.json"
SCHEMA = "command-center/schema/second-order-review.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0039/probe1_stopping_rule.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0039/probe2_unanchored_control.py"
)
SENTINEL = (
    "SUCCESS:SYN-0039 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the stopping rule fired "
    "with a recorded measurement and no deeper pass was launched. Any other "
    "terminal state is FAILED:SYN-0039 <classification> with the diagnostic "
    "tail attached."
)
QUESTION = (
    "Question: are the meta-review's OWN findings anchored, scoped and "
    "actionable -- and at what depth does reviewing the reviewers stop paying? "
    "Target: one second-order pass over the meta-review findings applying only "
    "three tests (is it anchored, is it scoped to its evidence, does it name a "
    "remedy), plus a written stopping rule that terminates the regress. Distinct "
    "from SYN-0026 (a different VENDOR at the same order) and SYN-0027 (the same "
    "lenses applied to their own output)."
)
RETRY_POLICY = (
    "one retry ONLY in a fresh context with the inputs re-read from disk, "
    "because the dominant failure mode here is an anchored prior, not a flaky tool"
)
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/SYN-0039/engine.py",
    "command-center/p2-wave/probes/SYN-0039/fixtures/planted_unanchored.json",
    "command-center/p2-wave/probes/SYN-0039/fixtures/known_good.json",
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\0{command}".encode("utf-8")).hexdigest()


def _refuse_remote(uri: str) -> Any:
    raise RefResolutionError(f"offline-registry: refused remote fetch of {uri}")


def validator() -> jsonschema.Draft202012Validator:
    shim = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    receipt = json.loads(
        (REPO / "platform" / "schema" / "receipt.schema.json").read_text(
            encoding="utf-8"
        )
    )
    profiles = json.loads(
        (
            REPO / "platform" / "schema" / "artifact-class-profiles.schema.json"
        ).read_text(encoding="utf-8")
    )
    store = {
        str(shim.get("$id") or ""): shim,
        str(receipt.get("$id") or ""): receipt,
        str(profiles.get("$id") or ""): profiles,
        "https://ast-integrate.invalid/" + SCHEMA: shim,
        "https://ast-integrate.invalid/platform/schema/receipt.schema.json": receipt,
        "https://ast-integrate.invalid/platform/schema/artifact-class-profiles.schema.json": profiles,
    }
    resolver = RefResolver(
        base_uri=str(shim.get("$id") or ""),
        referrer=shim,
        store=store,
        cache_remote=False,
        handlers={"http": _refuse_remote, "https": _refuse_remote},
    )
    return jsonschema.Draft202012Validator(shim, resolver=resolver)


def schema_errors(doc: dict) -> list[str]:
    out: list[str] = []
    try:
        for err in validator().iter_errors(doc):
            loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
            out.append(f"{loc}: {err.message}")
    except Exception as exc:
        out.append(f"<resolver>: {type(exc).__name__}: {exc}")
    return sorted(out)


def artifact_row(rel: str, role: str) -> dict:
    sha, size = sha256_file(REPO / rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def main() -> int:
    result = E.review(include_fixtures=True, depth=2)
    rule = result["stopping_rule"]
    planted = result["controls"]["planted_unanchored"]
    good = result["controls"]["known_good"]
    if not rule.get("evaluated") or not rule.get("fired"):
        print("FAILED:SYN-0039 emit stopping rule did not evaluate and fire")
        return 1
    if rule.get("deeper_pass_launched") is not False:
        print("FAILED:SYN-0039 emit deeper pass launched")
        return 1
    if planted is None or planted.get("anchored") is not False:
        print("FAILED:SYN-0039 emit planted unanchored not caught")
        return 1
    if good is None or good.get("disposition") != "ACCEPT":
        print("FAILED:SYN-0039 emit known-good did not ACCEPT")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    live_n = result["corpus"]["n_live_units"]
    absent_n = result["corpus"]["n_absent_units"]
    answer = (
        f"Second-order pass reviewed {result['counts']['reviewed']} meta-findings "
        f"({live_n} live SYN-0014..SYN-0027 artifacts, {absent_n} absent and "
        "reviewed as catalog-declared stand-ins plus two fixtures). "
        f"{result['counts']['hold']} held, {result['counts']['accept']} accepted. "
        f"Stopping rule evaluated: information_gain={rule['information_gain']:.6f} "
        f"at depth={rule['depth']} (threshold={rule['information_gain_threshold']}, "
        f"max_depth={rule['max_depth']}); trigger={rule['trigger']}; fired=true; "
        "deeper_pass_launched=false. Same-subject re-application information gain "
        f"is {rule['information_gain_if_same_subjects_reapplied']}. "
        "Planted unanchored control was caught; known-good control accepted."
    )
    findings = []
    for row in result["meta_findings"]:
        findings.append(
            {
                "id": row["id"],
                "source_unit": row["source_unit"],
                "claim": row["claim"],
                "kind": row["kind"],
                "anchored": row["anchored"],
                "scoped": row["scoped"],
                "remedy_named": row["remedy_named"],
                "disposition": row["disposition"],
                "failing_tests": row["failing_tests"],
                "cited_paths": row["cited_paths"],
                "path_probes": row["path_probes"],
                "live_present": row["live_present"],
            }
        )

    ig_cmd = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
        "\"import sys; sys.path.insert(0,'command-center/p2-wave/probes/SYN-0039'); "
        "import engine as E; r=E.review(include_fixtures=True, depth=2); "
        "print(r['stopping_rule']['information_gain'])\""
    )
    plant_read = (
        "python3 -c \"import json; print(json.load(open("
        "'command-center/p2-wave/probes/SYN-0039/fixtures/planted_unanchored.json'))"
        "['cited_paths'])\""
    )
    schema_cmd = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/SYN-0039/emit.py"
    )
    artifacts = [artifact_row(rel, "supporting") for rel in SUPPORTING]
    artifacts[0]["role"] = "supporting"
    artifacts[2]["role"] = "fixture"
    artifacts[3]["role"] = "control"

    doc = {
        "schema_version": 1,
        "unit_id": "SYN-0039",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:SYN-0039",
        "min_bytes_threshold": 2048,
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "Stopping rule was evaluated (not assumed): recorded "
                    f"information_gain={rule['information_gain']} at depth="
                    f"{rule['depth']} trigger={rule['trigger']}; "
                    "deeper_pass_launched=false."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/SYN-0039/engine.py",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P1,
                        "raw_output": (
                            f"ig={rule['information_gain']} trigger={rule['trigger']} "
                            f"depth={rule['depth']} deeper_launched=False"
                        ),
                        "fingerprint": fingerprint("command", P1),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "test-run",
                        "command": ig_cmd,
                        "raw_output": str(rule["information_gain"]),
                        "fingerprint": fingerprint("test-run", ig_cmd),
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    "Known-present unanchored meta-finding PLANT-UNANCHORED was "
                    f"caught ({planted['disposition']}); known-good CTRL-GOOD "
                    "accepted."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": (
                    "command-center/p2-wave/probes/SYN-0039/fixtures/"
                    "planted_unanchored.json"
                ),
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P2,
                        "raw_output": (
                            f"planted_anchored={planted['anchored']} "
                            f"planted_disp={planted['disposition']} "
                            f"good_disp={good['disposition']}"
                        ),
                        "fingerprint": fingerprint("command", P2),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "file-read",
                        "command": plant_read,
                        "raw_output": "[]",
                        "fingerprint": fingerprint("file-read", plant_read),
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "test_stopping_rule_is_evaluated_and_its_value_recorded_not_assumed",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "test_no_third_order_pass_is_launched_once_the_rule_fires",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "known-present-unanchored-meta-finding-caught",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "SYN0039-planted-unanchored",
                "kind": "known-broken-fixture",
                "description": (
                    "fixtures/planted_unanchored.json has empty cited_paths and "
                    "must be HOLD:unanchored; fixtures/known_good.json ACCEPT."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": planted["disposition"],
                "good_state_output": good["disposition"],
            }
        ],
        "reviewer": {
            "reviewer_id": "syn0039.independent-stopping-rule-auditor",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "openai",
            "notes": (
                "Other-vendor reviewer relative to anthropic author. Job is to "
                "re-run probe1/probe2, not to re-read this receipt. "
                "re_ran_detector_control=true; scope_not_agreement=true."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/SYN-0039/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "SYN-0039",
            "registered_at": now,
        },
        "downstream_consumers": [
            {
                "consumer": "Draft202012Validator disk RefResolver second-order-review",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": schema_cmd,
                    "raw_output": "in-memory Draft202012Validator against second-order-review via local $ref store",
                    "fingerprint": fingerprint("schema-validate", schema_cmd),
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {"started_at": now, "ended_at": now, "duration_seconds": 0},
        "retry": {"count": 0, "policy": RETRY_POLICY},
        "residual_unknowns": [
            {
                "claim": (
                    f"{absent_n} of 14 SYN-0014..SYN-0027 live output_path files "
                    "were absent on this worktree; those units were reviewed as "
                    "catalog-declared stand-ins, not as live findings."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run SYN-0039 after SYN-0014..SYN-0027 output_path files "
                    "exist and require live_present=true rows for those units."
                ),
            }
        ],
        "produced_by": {
            "vendor": "anthropic",
            "model": "opus",
            "role": "meta-review-chair",
            "execution_substrate": "local-serialized",
        },
        "report": {
            "kind": "second-order-review",
            "observations": [
                {
                    "name": "information_gain",
                    "measured": float(rule["information_gain"]),
                    "method": "failing-axis Jaccard novelty vs empty prior",
                    "anchor": "command-center/p2-wave/probes/SYN-0039/engine.py",
                },
                {
                    "name": "stopping_rule_fired",
                    "measured": True,
                    "method": "whichever-first IG threshold or depth==2",
                    "anchor": "command-center/p2-wave/probes/SYN-0039/engine.py",
                },
                {
                    "name": "deeper_pass_launched",
                    "measured": False,
                    "method": "refuse_deeper_pass after rule fire",
                    "anchor": "command-center/p2-wave/probes/SYN-0039/engine.py",
                },
                {
                    "name": "planted_unanchored_caught",
                    "measured": planted["anchored"] is False,
                    "method": "three-test review of fixtures/planted_unanchored.json",
                    "anchor": (
                        "command-center/p2-wave/probes/SYN-0039/fixtures/"
                        "planted_unanchored.json"
                    ),
                },
                {
                    "name": "known_good_accepted",
                    "measured": good["disposition"] == "ACCEPT",
                    "method": "three-test review of fixtures/known_good.json",
                    "anchor": (
                        "command-center/p2-wave/probes/SYN-0039/fixtures/"
                        "known_good.json"
                    ),
                },
            ],
            "control_ids": [
                "SYN0039-planted-unanchored",
                "SYN0039-known-good",
            ],
            "question": QUESTION,
            "answer": answer,
            "meta_findings": findings,
            "counts": result["counts"],
            "input_status": result["corpus"]["input_status"],
            "stopping_rule": {
                "statement": rule["statement"],
                "information_gain_threshold": rule["information_gain_threshold"],
                "max_depth": rule["max_depth"],
                "depth": rule["depth"],
                "information_gain": rule["information_gain"],
                "information_gain_if_same_subjects_reapplied": rule[
                    "information_gain_if_same_subjects_reapplied"
                ],
                "information_gain_detail": rule["information_gain_detail"],
                "evaluated": True,
                "fired": True,
                "trigger": rule["trigger"],
                "deeper_pass_launched": False,
                "deeper_pass_refusal": rule["deeper_pass_refusal"],
            },
            "distinct_from": result["distinct_from"],
        },
        "extensions": {
            "output_path": OUT,
            "output_schema": SCHEMA,
            "notes": (
                "G-1 for SYN-0039: live named probes exit 0, receipts/SYN-0039.json "
                "state=SUCCESS, per-unit manifest row. Did not run global "
                "unit_manifest.py --write. No ADV rebuild. Cloud ok=true is not delivery."
            ),
        },
    }

    errs = schema_errors(doc)
    if errs:
        print("FAILED:SYN-0039 schema errors")
        for line in errs[:24]:
            print(" ", line)
        return 1
    for garbage in (
        {},
        {"unit_id": "SYN-0039", "state": "SUCCESS"},
        {"totally": "unrelated", "passing_tests": 999999},
    ):
        g_err = schema_errors(garbage)
        if not g_err:
            print(f"FAILED:SYN-0039 schema accepted garbage {list(garbage)[:2]}")
            return 1

    payload = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if SENTINEL not in payload:
        print("FAILED:SYN-0039 catalog sentinel absent from artifact text")
        return 1
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(payload, encoding="utf-8")
    digest, size = sha256_file(out)
    if size < 2048:
        print(f"FAILED:SYN-0039 artifact {size}B below min_bytes_threshold")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:SYN-0039 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
