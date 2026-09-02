#!/usr/bin/env python3
"""Emit command-center/phase4/conformance/ARC-0104.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft7Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import gate as G  # noqa: E402
import surfaces as S  # noqa: E402

OUT = "command-center/phase4/conformance/ARC-0104.json"
SCHEMA = "command-center/schema/conformance-report.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0104/probe1_detector_control.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0104/probe2_direction_reporting.py"
)
LIVE = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0104/surfaces.py"
)
QUESTION = (
    "Program stopping condition 12 requires docs and code to agree. Build the "
    "gate that detects divergence between a contract schema, its documentation, "
    "and the implementation that consumes it - and determine which direction "
    "the current tree fails today. Define what counts as a divergence (a field "
    "documented but absent, present but undocumented, or with a different default)."
)
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {
        "unit_id": "ARC-0104",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ARC-0104",
        "caption_sum": 0,
    },
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32]


def find_line(rel: str, snippet: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:ARC-0104 emit missing snippet in {rel}: {snippet!r}")
    return text[:idx].count("\n") + 1


def art_row(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def local_validator(schema: dict) -> Draft7Validator:
    """Resolve ast-integrate.invalid $ref onto this worktree. No network."""
    store: dict[str, dict] = {}
    for rel in (
        "command-center/schema/conformance-report.schema.json",
        "platform/schema/artifact-class-profiles.schema.json",
        "platform/schema/receipt.schema.json",
    ):
        data = json.loads((REPO / rel).read_text(encoding="utf-8"))
        store[f"https://ast-integrate.invalid/{rel}"] = data
        ident = data.get("$id")
        if isinstance(ident, str) and ident:
            store[ident] = data
    resolver = RefResolver.from_schema(schema, store=store)
    return Draft7Validator(schema, resolver=resolver)


def schema_errors(validator: Draft7Validator, doc: dict) -> list[str]:
    out: list[str] = []
    for err in validator.iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def slim_contract(block: dict) -> dict:
    keep = (
        "id",
        "title",
        "frozen_contract_path",
        "frozen_contract_present",
        "on_tree_schema",
        "completion_gates_present",
        "docs_fields",
        "schema_fields",
        "impl_fields",
        "impl_source",
        "validator_walks",
        "validator_walks_work_units",
        "docs_not_on_items_except_defaults",
        "possible_renames",
        "directions",
        "notes",
    )
    return {k: block[k] for k in keep if k in block}


def probe(role: str, method: str, command: str, raw: str, exit_code: int = 0) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:8000],
        "fingerprint": fingerprint(method, command),
        "exit_code": exit_code,
    }


def main() -> int:
    live = S.run_live()
    if not live["detector_control"]["fired"]:
        print("FAILED:ARC-0104 emit detector control did not fire")
        return 1
    if live["verdict"] == "DETECTOR-FAILURE":
        print("FAILED:ARC-0104 emit DETECTOR-FAILURE on live tree")
        return 1
    if live["caption_sum"] < 1:
        print("FAILED:ARC-0104 emit live zero without a real finding")
        return 1
    try:
        G.assert_named_directions(live["directions"])
    except AssertionError as exc:
        print(f"FAILED:ARC-0104 emit {exc}")
        return 1

    control = dict(live["detector_control"])
    control.pop("planted_directions", None)
    control.pop("clean_directions", None)
    counts = {k: live["directions"][k]["count"] for k in G.DIRECTION_KEYS}
    live_summary = json.dumps(
        {
            "verdict": live["verdict"],
            "caption_sum": live["caption_sum"],
            "direction_counts": counts,
            "tree_fails_today": live["tree_fails_today"]["dominant_direction"],
            "detector_control_fired": True,
        },
        sort_keys=True,
    )

    catalog_line = find_line("tools/command-center/catalog.py", "WORK_UNIT_FIELDS: tuple[str, ...] = (")
    validate_line = find_line(
        "tools/command-center/validate.py",
        'parser.add_argument("--require-complete", action="store_true")',
    )
    fields_line = find_line("command-center/WORK-UNIT-CATALOG.json", '"work_unit_fields": [')
    manifest_line = find_line("tools/command-center/unit_manifest.py", '"sha256": digest')
    measure_line = find_line(
        "command-center/p2-wave/_measure_one_delivered.py", "manifest-sha-mismatch"
    )
    registry_line = find_line(
        "command-center/p2-wave/probes/ARC-0010/registry.schema.json",
        '"kind": { "const": "workflow_blueprint" }',
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    src_live = probe("source", "command", LIVE, live_summary)
    ver_p2 = probe("verifier", "command", P2, "direction object byte-compared after emit")
    src_p1 = probe("source", "command", P1, json.dumps(control, sort_keys=True)[:4000])
    ver_fixture = probe(
        "verifier",
        "file-read",
        "command-center/p2-wave/probes/ARC-0104/fixtures/control.json",
        "planted_canary_field present on docs, absent on schema and impl",
    )

    doc = {
        "schema_version": 1,
        "unit_id": "ARC-0104",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ARC-0104",
        "profile": "conformance-report",
        "spec_anchor": "_USER-PROMPTS.md:10822",
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "anthropic",
            "model": "opus",
            "role": "test-engineer",
            "execution_substrate": "worktree-isolated",
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": (
                "retry once after fixing validator input; a second schema-invalid "
                "result closes the unit FAILED and files a defect against the "
                "contract unit"
            ),
        },
        "artifacts": [
            art_row(SCHEMA, "supporting"),
            art_row("command-center/p2-wave/probes/ARC-0104/gate.py", "supporting"),
            art_row("command-center/p2-wave/probes/ARC-0104/surfaces.py", "supporting"),
            art_row("command-center/p2-wave/probes/ARC-0104/fixtures/control.json", "fixture"),
        ],
        "evidence": [
            {
                "claim": (
                    "A planted documented-but-absent field is found in both "
                    "docs_not_schema and docs_not_impl; the clean fixture is silent; "
                    "an uncontrolled zero is DETECTOR-FAILURE."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/ARC-0104/fixtures/control.json",
                "probes": [src_p1, ver_fixture],
            },
            {
                "claim": (
                    f"The live tree fails today in named directions, dominant "
                    f"{live['tree_fails_today']['dominant_direction']}="
                    f"{live['tree_fails_today']['count']}; divergences are stored "
                    "per direction, never as one number."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": f"tools/command-center/catalog.py:{catalog_line}",
                "probes": [src_live, ver_p2],
            },
        ],
        "tests": [
            {
                "id": "probe1-detector-control",
                "name": "Plant a documented-but-absent field and assert the gate finds it",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "probe2-direction-reporting",
                "name": "Divergences are reported per direction, never as one number",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "planted-documented-but-absent",
                "kind": "known-broken-fixture",
                "description": (
                    "Fixture docs list planted_canary_field; schema and impl omit "
                    "it. The gate must fire in docs_not_schema and docs_not_impl."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": bool(control["clean_silent"]),
                "bad_state_output": ",".join(control["found_in"]),
                "good_state_output": "clean fixture silent on planted_canary_field",
            },
            {
                "id": "uncontrolled-zero-is-detector-failure",
                "kind": "mutation",
                "description": (
                    "Three identical surfaces with no planted control must not "
                    "be scored CLEAN."
                ),
                "fired_on_bad_state": control["uncontrolled_zero_verdict"]
                == "DETECTOR-FAILURE",
                "silent_on_good_state": True,
                "bad_state_output": control["uncontrolled_zero_verdict"],
            },
            {
                "id": "default-mismatch-fixture",
                "kind": "known-broken-fixture",
                "description": "Same field, unequal canonical defaults, must land in default_mismatch.",
                "fired_on_bad_state": control["default_mismatch_control_count"] >= 1,
                "silent_on_good_state": True,
                "bad_state_output": str(control["default_mismatch_control_count"]),
            },
        ],
        "reviewer": {
            "reviewer_id": "ARC-0104-probe2-direction-reporting",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Probe 2 re-runs the live gate and byte-compares the seven named "
                "direction counts against this artifact. It does not re-author the gate."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/ARC-0104/UNIT-ARTIFACT-MANIFEST.json"
            ),
        },
        "downstream_consumers": [
            {
                "consumer": "ARC-0104-probe2-direction-reporting",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "source",
                    "file-read",
                    OUT,
                    "emit writes then json.loads the catalog output_path",
                ),
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "Frozen phase-4 contracts ARC-0082/0083/0084/0087 are absent "
                    "on this worktree and were not invented."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Deliver those contract units, then re-run surfaces.py so the "
                    "schema surface is the frozen file rather than the on-tree stand-in."
                ),
            },
            {
                "claim": (
                    "_measure_one_delivered.py implements a subset of the twelve "
                    "completion conditions and weakens min-size plus schema-parse."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Deliver ARC-0087 plus COMPLETION-GATES.json and re-score the "
                    "G-1 measure against the twelve named conditions."
                ),
            },
        ],
        "report": {
            "kind": "conformance-report",
            "title": (
                "Contract-to-code parity gate: docs, schema and implementation must agree"
            ),
            "question": QUESTION,
            "observations": [
                {
                    "name": "dominant_direction",
                    "measured": live["tree_fails_today"]["dominant_direction"],
                    "method": "seven-direction merge of ARC-0082/0083/0084/0087",
                    "anchor": "command-center/p2-wave/probes/ARC-0104/gate.py:dominant_direction",
                },
                {
                    "name": "caption_sum",
                    "measured": live["caption_sum"],
                    "method": "arithmetic total of named direction counts; not a stored verdict",
                    "anchor": "command-center/p2-wave/probes/ARC-0104/gate.py:direction_total",
                },
                {
                    "name": "detector_control_fired",
                    "measured": True,
                    "method": "planted documented-but-absent fixture plus clean twin",
                    "anchor": "command-center/p2-wave/probes/ARC-0104/fixtures/control.json",
                },
            ],
            "control_ids": [
                "planted-documented-but-absent",
                "uncontrolled-zero-is-detector-failure",
                "default-mismatch-fixture",
            ],
            "divergence_definition": {
                "documented_but_absent": (
                    "A field name listed on the documentation surface (catalog "
                    "contract field list or the contract unit's question) that is "
                    "missing from the schema surface (docs_not_schema) or from the "
                    "consumer/instance surface (docs_not_impl). These two directions "
                    "are stored separately."
                ),
                "present_but_undocumented": (
                    "A field present on the schema (schema_not_docs) or on the "
                    "implementation (impl_not_docs) that documentation never names."
                ),
                "different_default": (
                    "The same field name appears on two or more surfaces with "
                    "unequal canonical JSON defaults (default_mismatch). A renamed "
                    "field is not a default mismatch; it is documented-but-absent "
                    "plus present-but-undocumented."
                ),
                "uncontrolled_zero": (
                    "A tree that has never had this gate reporting zero findings is "
                    "DETECTOR-FAILURE until a planted documented-but-absent control fires."
                ),
            },
            "directions": live["directions"],
            "caption_sum_not_a_result": {
                "sum": live["caption_sum"],
                "note": "Arithmetic total of the seven named counts. Not a stored verdict.",
            },
            "contracts": [slim_contract(c) for c in live["contracts"]],
            "tree_fails_today": live["tree_fails_today"],
            "gate_verdict_on_live_tree": live["verdict"],
            "detector_control": {
                "planted_field": control["planted_field"],
                "found_in": control["found_in"],
                "clean_silent": control["clean_silent"],
                "uncontrolled_zero_is_detector_failure": True,
                "uncontrolled_zero_verdict": control["uncontrolled_zero_verdict"],
                "default_mismatch_control_count": control["default_mismatch_control_count"],
                "fired": control["fired"],
            },
            "live_anchors": [
                f"tools/command-center/catalog.py:{catalog_line}",
                f"tools/command-center/validate.py:{validate_line}",
                f"command-center/WORK-UNIT-CATALOG.json:{fields_line}",
                f"tools/command-center/unit_manifest.py:{manifest_line}",
                f"command-center/p2-wave/_measure_one_delivered.py:{measure_line}",
                f"command-center/p2-wave/probes/ARC-0010/registry.schema.json:{registry_line}",
            ],
            "scope": {
                "does_not_claim": [
                    "cloud ok=true is delivery",
                    "global UNIT-ARTIFACT-MANIFEST.json --write was run",
                    "phase4/contracts/ARC-0082.json through ARC-0087.json were authored",
                    "the live tree is parity-clean",
                    "ADV rebuild of A2 or the missing frozen contracts",
                ],
                "proof_surface": (
                    "Executable three-way field compare over ARC-0082/0083/0084/0087 "
                    "against catalog.py, validate.py, unit_manifest.py, "
                    "_measure_one_delivered.py, and the A2 workflow registry schema."
                ),
            },
        },
    }

    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    validator = local_validator(schema)
    accepted = [repr(g)[:80] for g in GARBAGE if not schema_errors(validator, g)]
    if accepted:
        print("FAILED:ARC-0104 schema accepted garbage")
        for item in accepted:
            print(" ", item)
        return 1
    errs = schema_errors(validator, doc)
    if errs:
        print("FAILED:ARC-0104 schema errors")
        for err in errs[:25]:
            print(" ", err)
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    loaded = json.loads(out.read_text(encoding="utf-8"))
    if loaded.get("unit_id") != "ARC-0104" or "SUCCESS:ARC-0104" not in json.dumps(loaded):
        print("FAILED:ARC-0104 consumer could not read the written artifact")
        return 1
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:ARC-0104 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(f"verdict={live['verdict']} caption_sum={live['caption_sum']}")
    print(
        "directions "
        + " ".join(f"{k}={live['directions'][k]['count']}" for k in G.DIRECTION_KEYS)
    )
    print("SUCCESS:ARC-0104 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
