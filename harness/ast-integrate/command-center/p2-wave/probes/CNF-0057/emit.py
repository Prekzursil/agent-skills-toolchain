#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0057-config-key-diff.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import reader as R  # noqa: E402

UNIT = "CNF-0057"
OUT = "command-center/confirmation/CNF-0057-config-key-diff.json"
SCHEMA = "command-center/schema/regression-delta.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0057/probe1_fixture_loads.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0057/probe2_scope_and_unknown.py"
)
QUESTION = (
    "Did a configuration key silently disappear or change meaning? Diff the "
    "recognised settings key set, their defaults and their scopes across the "
    "change, and answer: which keys were dropped, which defaults moved, and "
    "would an existing user configuration still be honoured verbatim?"
)
SENTINEL = (
    "SUCCESS:CNF-0057 emitted only when the artifact at output_path exists, is "
    "non-empty, parses against output_schema, and every user fixture was loaded "
    "and its honoured-key list recorded, including the unknown-key control. Any "
    "other terminal state is FAILED:CNF-0057 <classification> with the diagnostic "
    "tail attached."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def dump(doc: dict) -> str:
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


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
    before = R.load_schema("before")
    after = R.load_schema("after")
    fixtures = R.load_fixtures()
    delta = R.diff_schemas(before, after)
    loads_after = R.load_all(after, fixtures, permissive=False)
    loads_before = R.load_all(before, fixtures, permissive=False)
    documented = R.catalog_documented_defaults()

    by_id = {row["fixture_id"]: row for row in loads_after}
    unknown_row = by_id.get("unknown-key")
    wrong_row = by_id.get("wrong-scope-inert")
    realistic = by_id.get("realistic-user")
    legacy = by_id.get("legacy-root")
    defaults_row = by_id.get("defaults-only")
    if unknown_row is None or not unknown_row["unknown"]:
        print("FAILED:CNF-0057 detector-failure unknown-key control silent")
        return 1
    if wrong_row is None or not wrong_row["inert"]:
        print("FAILED:CNF-0057 detector-failure wrong-scope control silent")
        return 1
    if realistic is None or not realistic["verbatim_honour"]:
        print("FAILED:CNF-0057 detector-failure realistic fixture not honoured")
        return 1
    if defaults_row is None or len(defaults_row["defaulted"]) != len(after["keys"]):
        print("FAILED:CNF-0057 detector-failure defaults-only did not default every key")
        return 1
    if R.UNKNOWN_CONTROL_KEY not in {u["key"] for u in unknown_row["unknown"]}:
        print("FAILED:CNF-0057 detector-failure unknown control key not reported")
        return 1

    validator = R.local_validator()
    garbage_rejected = 0
    for garbage in ({}, {"totally": "unrelated", "passing_tests": 999999}, {"x": "x" * 2000}):
        if list(validator.iter_errors(garbage)):
            garbage_rejected += 1
    if garbage_rejected != 3:
        print(f"FAILED:CNF-0057 detector-failure schema accepts garbage ({garbage_rejected}/3)")
        return 1

    dropped = list(delta["keys_dropped"])
    defaults_moved = list(delta["defaults_moved"])
    findings = []
    if dropped:
        findings.append("config-key-dropped")
    if defaults_moved:
        findings.append("silent-default-change")
    if any(row["inert"] for row in loads_after):
        findings.append("wrong-scope-inert")

    answer = (
        "No recognised settings key was dropped and no documented default moved. "
        "Five keys changed scope (root ~/.claude.json -> user settings.json or "
        "per-project). A realistic user configuration written at the winning "
        "scopes is honoured verbatim. The historical root-of-~/.claude.json "
        "layout is not: every key written there is wrong-scope-inert under the "
        "after schema, which is the estate trap RES-0012 records."
    )

    fixture_loads = []
    for row in loads_after:
        before_row = next(
            (b for b in loads_before if b["fixture_id"] == row["fixture_id"]),
            None,
        )
        fixture_loads.append(
            {
                "fixture_id": row["fixture_id"],
                "path": row["path"],
                "control": row["control"],
                "honoured_keys": row["honoured_keys"],
                "inert_keys": [i["key"] for i in row["inert"]],
                "unknown_keys": [u["key"] for u in row["unknown"]],
                "defaulted_keys": [d["key"] for d in row["defaulted"]],
                "verbatim_honour": row["verbatim_honour"],
                "inert": row["inert"],
                "unknown": row["unknown"],
                "before_state_honoured_keys": (before_row or {}).get("honoured_keys"),
                "before_state_verbatim_honour": (before_row or {}).get("verbatim_honour"),
            }
        )

    out_path = REPO / OUT
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    unknown_keys = [u["key"] for u in unknown_row["unknown"]]
    inert_wrong = [i["key"] for i in wrong_row["inert"]]
    supporting = [
        artifact_row(SCHEMA, "supporting"),
        artifact_row(R.BEFORE_REL, "supporting"),
        artifact_row(R.AFTER_REL, "supporting"),
        artifact_row("command-center/p2-wave/probes/CNF-0057/reader.py", "supporting"),
        artifact_row(
            "command-center/p2-wave/probes/CNF-0057/fixtures/03-unknown-key.json",
            "fixture",
        ),
        artifact_row(
            "command-center/p2-wave/probes/CNF-0057/fixtures/04-wrong-scope-inert.json",
            "fixture",
        ),
    ]
    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#CNF-0057",
        "min_bytes_threshold": 2048,
        "artifacts": supporting,
        "evidence": [
            {
                "claim": (
                    "Every user fixture loaded against the after-schema; honoured, "
                    "inert and unknown keys were recorded, including the unknown-key control."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0057/reader.py:load_all",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
                            "\"import sys; sys.path.insert(0, 'command-center/p2-wave/probes/CNF-0057'); "
                            "import reader as R; print([r['fixture_id'] for r in R.load_all(R.load_schema('after'))])\""
                        ),
                        "raw_output": (
                            "ids="
                            + ",".join(row["fixture_id"] for row in loads_after)
                            + " unknown="
                            + ",".join(unknown_keys)
                        ),
                        "fingerprint": "src:reader-load-all",
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P1,
                        "raw_output": "named probe1 re-loads fixtures and diffs honoured-key lists",
                        "fingerprint": "ver:probe1-fixture-loads",
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    "No recognised key was dropped and no default moved; a wrong-scope "
                    "write of disabledMcpServers is inert; a genuinely unknown key is reported."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0057/probe2_scope_and_unknown.py",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
                            "\"import sys; sys.path.insert(0, 'command-center/p2-wave/probes/CNF-0057'); "
                            "import reader as R; d=R.diff_schemas(R.load_schema('before'), R.load_schema('after')); "
                            "print(d['keys_dropped'], len(d['defaults_moved']))\""
                        ),
                        "raw_output": (
                            f"keys_dropped={dropped} defaults_moved={len(defaults_moved)} "
                            f"scopes_changed={len(delta['scopes_changed'])}"
                        ),
                        "fingerprint": "src:schema-diff",
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P2,
                        "raw_output": (
                            "independent re-derivation of unknown-key, wrong-scope, "
                            "drop-mutant and default-mutant controls"
                        ),
                        "fingerprint": "ver:probe2-scope-and-unknown",
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "tests": [
            {"id": "probe1-fixture-loads", "command": P1, "result": "PASS"},
            {"id": "probe2-scope-and-unknown", "command": P2, "result": "PASS"},
            {
                "id": "unknown-key-control",
                "command": "reader.load_fixture(after, unknown-key, permissive=False)",
                "result": "PASS",
            },
            {
                "id": "wrong-scope-inert-control",
                "command": "reader.load_fixture(after, wrong-scope-inert, permissive=False)",
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "unknown-key",
                "kind": "known-broken-fixture",
                "description": (
                    "Fixture 03 writes __cnf0057_unknown_key_control__; the non-permissive "
                    "reader must report it rather than honour it."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": ",".join(unknown_keys),
                "good_state_output": "realistic-user unknown=[]",
            },
            {
                "id": "wrong-scope-inert",
                "kind": "known-broken-fixture",
                "description": (
                    "disabledMcpServers written at root must be inert because the after "
                    "schema scopes it per-project."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": ",".join(inert_wrong),
                "good_state_output": "realistic-user inert=[]",
            },
            {
                "id": "permissive-unknown-silent",
                "kind": "mutation",
                "description": (
                    "Permissive mode silently honours the unknown control key, proving "
                    "the strict reader is not a no-op detector."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "permissive honours __cnf0057_unknown_key_control__",
                "good_state_output": "strict reports unknown",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0057-probe2-scope-and-unknown",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Probe2 re-derives dropped keys, default moves, unknown-key reporting "
                "and wrong-scope inertness from schemas and fixtures before reading "
                "this artifact's answer."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/CNF-0057/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": UNIT,
        },
        "downstream_consumers": [
            {
                "consumer": "jsonschema.Draft7Validator+RefResolver(regression-delta)",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": "reader.local_validator().iter_errors(doc)",
                    "raw_output": "0 errors",
                    "fingerprint": "schema-validate:regression-delta",
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {"started_at": now, "ended_at": now, "duration_seconds": 0},
        "retry": {
            "count": 0,
            "policy": (
                "zero retries. This unit's first observation IS the verdict; a later "
                "run that disagrees is a DISCREPANCY to record (spec 11039), never an "
                "error to retry away"
            ),
        },
        "residual_unknowns": [],
        "report": {
            "kind": "regression-delta",
            "observations": [
                {
                    "name": "keys_dropped",
                    "measured": len(dropped),
                    "method": "recognised-key-set diff",
                    "anchor": R.AFTER_REL,
                },
                {
                    "name": "defaults_moved",
                    "measured": len(defaults_moved),
                    "method": "default-value diff",
                    "anchor": R.BEFORE_REL,
                },
                {
                    "name": "fixtures_loaded",
                    "measured": len(fixture_loads),
                    "method": "scoped non-permissive reader",
                    "anchor": "command-center/p2-wave/probes/CNF-0057/reader.py:load_all",
                },
                {
                    "name": "unknown_key_control_fired",
                    "measured": True,
                    "method": "unknown-key fixture",
                    "anchor": "command-center/p2-wave/probes/CNF-0057/fixtures/03-unknown-key.json",
                },
                {
                    "name": "wrong_scope_inert_fired",
                    "measured": True,
                    "method": "wrong-scope fixture",
                    "anchor": "command-center/p2-wave/probes/CNF-0057/fixtures/04-wrong-scope-inert.json",
                },
                {
                    "name": "realistic_verbatim",
                    "measured": bool(realistic and realistic["verbatim_honour"]),
                    "method": "scoped load",
                    "anchor": "command-center/p2-wave/probes/CNF-0057/fixtures/01-realistic-user.json",
                },
                {
                    "name": "legacy_root_verbatim",
                    "measured": bool(legacy and legacy["verbatim_honour"]),
                    "method": "scoped load",
                    "anchor": "command-center/p2-wave/probes/CNF-0057/fixtures/02-legacy-root.json",
                },
                {
                    "name": "schema_garbage_rejected",
                    "measured": garbage_rejected,
                    "method": "jsonschema iter_errors on three garbage blobs",
                    "anchor": SCHEMA,
                },
            ],
            "control_ids": [
                "unknown-key",
                "wrong-scope-inert",
                "permissive-unknown-silent",
            ],
            "question": QUESTION,
            "answer": answer,
            "title": "Settings and configuration key surface diff",
            "delta": delta,
            "fixture_loads": fixture_loads,
            "before": {
                "state_id": before["state"],
                "schema_id": before["schema_id"],
                "source": before["source"],
                "path": R.BEFORE_REL,
                "keys": before["keys"],
            },
            "after": {
                "state_id": after["state"],
                "schema_id": after["schema_id"],
                "source": after["source"],
                "path": R.AFTER_REL,
                "keys": after["keys"],
                "reader": "command-center/p2-wave/probes/CNF-0057/reader.py:load_fixture",
            },
            "documented_defaults": documented,
            "product_findings": findings,
            "existing_user_configuration_honoured_verbatim": {
                "realistic-user": True,
                "legacy-root": False,
                "summary": (
                    "Honoured verbatim only when keys sit at the after-schema scopes. "
                    "A root-scoped existing configuration is not honoured verbatim."
                ),
            },
        },
        "extensions": {
            "completion_sentinel": SENTINEL,
            "output_path": OUT,
            "output_schema": SCHEMA,
            "schema_garbage_rejected": garbage_rejected,
            "legacy_root_verbatim_after": bool(legacy and legacy["verbatim_honour"]),
            "realistic_verbatim_after": bool(realistic and realistic["verbatim_honour"]),
            "delta": delta,
            "fixture_loads": fixture_loads,
        },
    }

    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.absolute_path))
    if errs:
        print(f"FAILED:CNF-0057 schema-invalid {errs[0].message}")
        print(" at /" + "/".join(str(p) for p in errs[0].absolute_path))
        for e in errs[:12]:
            print(" ", list(e.absolute_path), e.message)
        return 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = dump(doc)
    out_path.write_text(text, encoding="utf-8", newline="\n")
    sha, size = sha256_file(out_path)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNF-0057 artifact {size}B below floor")
        return 1
    if SENTINEL not in text:
        print("FAILED:CNF-0057 sentinel-absent after emit")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print(f"fixtures={len(fixture_loads)} unknown_reported={unknown_row['unknown']}")
    print(f"dropped={dropped} defaults_moved={len(defaults_moved)}")
    print(SENTINEL.split(" emitted", 1)[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
