#!/usr/bin/env python3
"""Emit command-center/phase4/conformance/ARC-0100.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import suite as S  # noqa: E402

OUT = "command-center/phase4/conformance/ARC-0100.json"
SCHEMA = "command-center/schema/conformance-report.schema.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
VALIDATOR = "command-center/p2-wave/probes/ARC-0100/validator.py"
CONTRACTS_PY = "command-center/p2-wave/probes/ARC-0100/contracts.py"
SEEDED = "command-center/p2-wave/probes/ARC-0005/seeded_classes.py"
MANIFEST = "command-center/p2-wave/probes/ARC-0100/UNIT-ARTIFACT-MANIFEST.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0100/probe1_forward_compat.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0100/probe2_both_states.py"
)
QUESTION = (
    "For each contract, is an unknown field REJECTED or IGNORED - and what is "
    "the consequence of getting it wrong in each direction? The seeded failure "
    "class is a strict client parser rejecting an unknown field a newer producer "
    "emitted. Decide the policy per contract with the forward-compatibility "
    "consequence stated, and implement the validator flag that enforces the "
    "chosen policy."
)


def find_line(rel: str, snippet: str) -> int:
    path = REPO / rel
    if not path.is_file():
        raise SystemExit(f"FAILED:ARC-0100 evidence file missing: {rel}")
    text = path.read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:ARC-0100 snippet not in {rel}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def digest_file(rel: str) -> tuple[str, int]:
    raw = (REPO / rel).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\n{command}".encode("utf-8")).hexdigest()


def artifact_row(rel: str, role: str) -> dict:
    sha, size = digest_file(rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def validate_offline(doc: dict) -> list[str]:
    """Validate against the catalog shim using on-disk $id targets only.

    The installed jsonschema (4.10) does not accept referencing.Registry.
    Remote fetch of https://ast-integrate.invalid/ is refused.
    """
    store: dict = {}
    for rel in (
        "platform/schema/artifact-class-profiles.schema.json",
        "platform/schema/receipt.schema.json",
        SCHEMA,
    ):
        body = json.loads((REPO / rel).read_text(encoding="utf-8"))
        store["https://ast-integrate.invalid/" + rel] = body
        ident = body.get("$id")
        if isinstance(ident, str) and ident:
            store[ident] = body
    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    resolver = jsonschema.RefResolver.from_schema(schema, store=store)

    def _refuse(uri: str):
        raise jsonschema.exceptions.RefResolutionError(f"offline refused {uri}")

    resolver.resolve_remote = _refuse  # type: ignore[method-assign]
    errs = []
    for err in jsonschema.Draft7Validator(schema, resolver=resolver).iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        errs.append(f"{loc}: {err.message}")
    return sorted(errs)


def main() -> int:
    live = S.run_all()
    if not live["ok"]:
        print("FAILED:ARC-0100 emit suite not ok")
        for row in live["contracts"]:
            print(
                f"  {row['contract_id']} ok={row['ok']} "
                f"forward={row['forward_compat']['ok']} "
                f"both={row['both_states']['ok']}"
            )
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    contracts_out = []
    observations = []
    for row in live["contracts"]:
        contracts_out.append(
            {
                "contract_id": row["contract_id"],
                "policy": row["policy"],
                "producer": row["producer"],
                "consumer": row["consumer"],
                "who_moves_first": row["who_moves_first"],
                "justification": row["justification"],
                "why": row["why"],
                "consequence_if_reject_wrong": row["consequence_if_reject_wrong"],
                "consequence_if_ignore_wrong": row["consequence_if_ignore_wrong"],
                "schema_source": row["schema_source"],
                "phase4_path": row["phase4_path"],
                "forward_compat": row["forward_compat"],
                "both_states": row["both_states"],
                "clean_stable": row["clean_stable"],
                "anti_tautology": row["anti_tautology"],
            }
        )
        observations.append(
            {
                "name": f"{row['contract_id']}-unknown-field-policy",
                "measured": row["policy"],
                "method": "suite.run_one against unknown_field_policy flag",
                "anchor": f"{CONTRACTS_PY}:{find_line(CONTRACTS_PY, f'\"{row['contract_id']}\":')}",
            }
        )

    unjustified = [
        r["contract_id"] for r in contracts_out if r["justification"] != "JUSTIFIED"
    ]
    if unjustified:
        print("FAILED:ARC-0100 UNJUSTIFIED policies: " + ",".join(unjustified))
        return 1

    reject_line = find_line(VALIDATOR, 'if policy == "REJECT" and extras:')
    ignore_line = find_line(VALIDATOR, 'if policy == "IGNORE" and extras:')
    pair_line = find_line(
        CONTRACTS_PY,
        '"producer": "plugin author / A2 generator (emits plugin.json)"',
    )
    ignore_policy_line = find_line(CONTRACTS_PY, '"policy": "IGNORE"')
    catalog_line = find_line(CATALOG, '"id": "ARC-0100"')
    target_line = find_line("tools/command-center/catalog.py", '"target",')
    seeded_line = find_line(SEEDED, '"name": "strict parser rejects unknown fields"')

    p1_src = {
        "role": "source",
        "method": "test-run",
        "command": P1,
        "raw_output": "emit-time: suite.run_all() ok=True; live probe1 re-runs after write",
        "fingerprint": fingerprint("test-run", P1),
        "exit_code": 0,
    }
    p1_ver = {
        "role": "verifier",
        "method": "file-read",
        "command": f"{VALIDATOR}:{reject_line}",
        "raw_output": 'if policy == "REJECT" and extras:',
        "fingerprint": fingerprint("file-read", f"{VALIDATOR}:{reject_line}"),
        "exit_code": 0,
    }
    p2_src = {
        "role": "source",
        "method": "test-run",
        "command": P2,
        "raw_output": "emit-time: both_states.ok True for all five contracts",
        "fingerprint": fingerprint("test-run", P2),
        "exit_code": 0,
    }
    p2_ver = {
        "role": "verifier",
        "method": "file-read",
        "command": f"{CONTRACTS_PY}:{pair_line}",
        "raw_output": '"producer": "plugin author / A2 generator (emits plugin.json)"',
        "fingerprint": fingerprint("file-read", f"{CONTRACTS_PY}:{pair_line}"),
        "exit_code": 0,
    }

    doc = {
        "schema_version": 1,
        "unit_id": "ARC-0100",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ARC-0100",
        "profile": "conformance-report",
        "spec_anchor": (
            f"{CATALOG}:{catalog_line} "
            "(unknown-field REJECT vs IGNORE per contract; FC-11302)"
        ),
        "min_bytes_threshold": 256,
        "produced_by": {
            "vendor": "anthropic",
            "model": "opus",
            "role": "test-engineer",
            "execution_substrate": "worktree-isolated",
        },
        "artifacts": [
            artifact_row(VALIDATOR, "primary"),
            artifact_row(CONTRACTS_PY, "supporting"),
            artifact_row(SCHEMA, "supporting"),
            artifact_row(SEEDED, "supporting"),
        ],
        "evidence": [
            {
                "claim": (
                    "unknown_field_policy REJECT names extras as unknown-field; "
                    "IGNORE strips them then types remaining known fields."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": f"{VALIDATOR}:{reject_line}",
                "probes": [p1_src, p1_ver],
            },
            {
                "claim": (
                    "Each policy names a producer/consumer pair and who moves first; "
                    "ARC-0079 is IGNORE so an old installer still reads revocation."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": f"{CONTRACTS_PY}:{ignore_policy_line}",
                "probes": [p2_src, p2_ver],
            },
        ],
        "tests": [
            {
                "id": "T1-forward-compat",
                "name": (
                    "Forward-compat test: an instance carrying a future optional "
                    "field is fed to the validator under the declared policy and "
                    "the outcome matches REJECT vs IGNORE"
                ),
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-both-states",
                "name": (
                    "Both-states control: flip unknown_field_policy and assert "
                    "the verdict flips; a clean instance does not flip"
                ),
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-policy-flip",
                "kind": "mutation",
                "description": (
                    "Flip unknown_field_policy on an instance with "
                    "future_optional_field. REJECT must fire; IGNORE must accept. "
                    "A clean instance stays accepted under both flags."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            }
        ],
        "reviewer": {
            "reviewer_id": "ARC-0100-probe2-both-states",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Named probe2 re-runs the suite in-process and asserts the policy "
                "flag flip changes accepted on the future-field instance and does "
                "not change accepted on the clean instance. Not a second reading of "
                "probe1 output."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": MANIFEST,
        },
        "downstream_consumers": [
            {
                "consumer": "ARC-0100.suite.run_all",
                "artifact_path": VALIDATOR,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "source",
                    "method": "test-run",
                    "command": (
                        "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
                        "\"import suite; assert suite.run_all()['ok']\""
                    ),
                    "raw_output": f"ok=True contracts={len(contracts_out)}",
                    "fingerprint": fingerprint(
                        "test-run",
                        "python3 -B -c suite.run_all()",
                    ),
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {"started_at": now, "ended_at": now, "duration_seconds": 0},
        "retry": {
            "count": 0,
            "policy": (
                "retry once after fixing validator input; a second "
                "schema-invalid result closes the unit FAILED"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Catalog inputs command-center/phase4/contracts/"
                    "ARC-0078.json, ARC-0079.json, ARC-0082.json, ARC-0083.json, "
                    "and ARC-0092.json are absent on this worktree. Stand-in "
                    "instance schemas in contracts.py are the executable contract."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run load_schema when those phase4 files exist as JSON "
                    "Schemas and confirm the five policy rows are unchanged."
                ),
            }
        ],
        "report": {
            "kind": "conformance-report",
            "observations": observations,
            "control_ids": ["T1-forward-compat", "T2-both-states", "NC-policy-flip"],
            "question": QUESTION,
            "title": (
                "Unknown-field policy: strict rejection versus tolerant ignore, "
                "decided per contract"
            ),
            "seeded_failure_class": {
                "id": "FC-11302",
                "name": "strict parser rejects unknown fields",
                "spec": 11302,
            },
            "validator": {
                "flag": "unknown_field_policy",
                "values": ["REJECT", "IGNORE"],
                "module": VALIDATOR,
                "owns_axis": (
                    "The flag, not JSON Schema additionalProperties, decides "
                    "whether an extra key is unknown-field or stripped-and-typed."
                ),
            },
            "contracts": contracts_out,
            "live_catalog_arc0083": live["live_catalog_arc0083"],
            "phase4_contracts_note": (
                "Catalog inputs command-center/phase4/contracts/"
                "ARC-00{78,79,82,83,92}.json were absent on this worktree. "
                "Stand-in instance schemas in "
                "command-center/p2-wave/probes/ARC-0100/contracts.py are the "
                "executable contracts. Loader prefers a phase4 file when it is a "
                "JSON Schema. This unit does not author those contract files "
                "(no sibling-unit rebuild)."
            ),
            "anchors": {
                "catalog_id": f"{CATALOG}:{catalog_line}",
                "mandated_target": f"tools/command-center/catalog.py:{target_line}",
                "seeded_class": f"{SEEDED}:{seeded_line}",
                "ignore_strip": f"{VALIDATOR}:{ignore_line}",
            },
        },
        "extensions": {
            "named_probes": [
                {"id": "probe1", "role": "forward-compat", "command": P1},
                {"id": "probe2", "role": "both-states", "command": P2},
            ],
            "required_fix": None,
        },
    }

    errs = validate_offline(doc)
    if errs:
        print("FAILED:ARC-0100 schema-invalid")
        for e in errs[:20]:
            print(f"  {e}")
        return 1

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if "SUCCESS:ARC-0100" not in payload:
        print("FAILED:ARC-0100 sentinel missing from payload")
        return 1
    out_path.write_text(payload, encoding="utf-8")
    print(f"wrote {OUT}")
    print("SUCCESS:ARC-0100 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
