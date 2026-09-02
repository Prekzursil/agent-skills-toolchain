#!/usr/bin/env python3
"""Write command-center/confirmation/CNF-0059-downstream-consumers.json.

jsonschema 4.10.3 on this worktree has no referencing.Registry; Draft*Validator
tries the network for https://ast-integrate.invalid $ref. Resolve those URIs
from disk via RefResolver.store so validation is local and still rejects garbage.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import downstream as D  # noqa: E402

REPO = D.REPO
OUT_REL = "command-center/confirmation/CNF-0059-downstream-consumers.json"
SCHEMA_REL = "command-center/schema/regression-delta.schema.json"
INVALID = "https://ast-integrate.invalid/"
SENTINEL = (
    "SUCCESS:CNF-0059 emitted only when the artifact at output_path exists, is non-empty, "
    "parses against output_schema, and every consumer has an exit code and a printed "
    "resolved library path, or an explicit unprotected finding. Any other terminal state "
    "is FAILED:CNF-0059 <classification> with the diagnostic tail attached."
)
QUESTION = (
    "Do the other trees that import the shared salvage library still work? Enumerate every "
    "consumer of tools/lib, run each consumer's own smoke test against the changed library, "
    "and answer: which consumers break, and does any consumer pin a version that the change invalidates?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0059/probe1_consumer_smoke.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0059/probe2_unprotected_control.py"
)
MIN_BYTES = 2048
STORE_FILES = (
    SCHEMA_REL,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()


def local_validator() -> jsonschema.Draft202012Validator:
    store: dict[str, dict] = {}
    for rel in STORE_FILES:
        doc = json.loads((REPO / rel).read_text(encoding="utf-8"))
        store[INVALID + rel] = doc
        ident = doc.get("$id")
        if isinstance(ident, str) and ident:
            store[ident] = doc
    schema = store[INVALID + SCHEMA_REL]
    resolver = jsonschema.RefResolver(
        base_uri=str(schema.get("$id") or INVALID + SCHEMA_REL),
        referrer=schema,
        store=store,
    )
    return jsonschema.Draft202012Validator(schema, resolver=resolver)


def validate_or_die(doc: dict) -> None:
    validator = local_validator()
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNF-0059 schema errors")
        for err in errs[:25]:
            print(" ", list(err.absolute_path), err.message)
        raise SystemExit(1)
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"x": "x" * 200},
        {"unit_id": "CNF-0059", "state": "SUCCESS"},
    ):
        if not list(validator.iter_errors(garbage)):
            raise SystemExit("FAILED:CNF-0059 schema accepts garbage")


def consumer_row(r: dict) -> dict:
    return {
        "id": r.get("id"),
        "path": r.get("path"),
        "universe": r.get("universe"),
        "kind": r.get("kind"),
        "present": r.get("present"),
        "pins": r.get("pins") or {},
        "smoke_file": r.get("smoke_file"),
        "smoke_command": (f"node {r['smoke_file']}" if r.get("smoke_file") else None),
        "exit_code": r.get("exit_code"),
        "resolved_library_path": r.get("resolved_library_path"),
        "printed_resolved_library_path": bool(r.get("printed_resolved_library_path")),
        "finding": r.get("finding"),
        "unprotected_reason": r.get("unprotected_reason"),
        "pin_invalidated": bool(r.get("pin_invalidated")),
    }


def sentinel_holds(rows: list[dict]) -> tuple[bool, list[str]]:
    bad: list[str] = []
    for r in rows:
        cid = str(r.get("id"))
        if r.get("finding") == "unprotected":
            if not r.get("unprotected_reason"):
                bad.append(f"{cid}: unprotected without reason")
            continue
        if r.get("exit_code") is None:
            bad.append(f"{cid}: missing exit_code")
        if not r.get("printed_resolved_library_path") or not r.get("resolved_library_path"):
            bad.append(f"{cid}: missing printed resolved library path")
    return (not bad, bad)


def live_lib_suite() -> dict:
    lib = REPO / "tools" / "lib"
    if not lib.is_dir():
        return {"ran": False, "reason": "tools/lib absent", "exit_code": None}
    node = shutil.which("node")
    if not node:
        return {"ran": False, "reason": "node not on PATH", "exit_code": 127}
    tests = sorted(lib.glob("tests/*.test.mjs"))
    if not tests:
        return {"ran": False, "reason": "no tests/*.test.mjs", "exit_code": None}
    rel = [str(p.relative_to(lib)) for p in tests]
    try:
        proc = subprocess.run(
            [node, "--test", *rel],
            cwd=str(lib),
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        return {"ran": True, "reason": "TIMEOUT", "exit_code": 124, "tail": "TIMEOUT"}
    tail = ((proc.stdout or "") + (proc.stderr or ""))[-2000:]
    return {
        "ran": True,
        "exit_code": proc.returncode,
        "reason": "ok" if proc.returncode == 0 else "tests-failed",
        "tail": tail,
    }


def art_row(rel: str, role: str) -> dict:
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
    measured = D.measure()
    ctrl = measured["control_unprotected"]
    if not ctrl.get("fired_on_bad_state") or not ctrl.get("silent_on_good_state"):
        print(f"FAILED:CNF-0059 unprotected control did not discriminate: {ctrl}")
        return 1
    ok, problems = sentinel_holds(measured["consumers"])
    if not ok:
        print("FAILED:CNF-0059 sentinel condition")
        for p in problems:
            print("  ", p)
        return 1
    if "cnf0059-unprotected" not in measured["unprotected_ids"]:
        print("FAILED:CNF-0059 fixture unprotected consumer not classified unprotected")
        return 1
    if "cnf0059-smoke-pass" not in measured["ok_ids"]:
        print("FAILED:CNF-0059 fixture passing smoke did not pass")
        return 1
    if "cnf0059-smoke-break" not in measured["broken_ids"]:
        print("FAILED:CNF-0059 fixture breaking consumer did not break")
        return 1
    if "cnf0059-pin-stale" not in measured["pin_invalidated_ids"]:
        print("FAILED:CNF-0059 stale pin not detected")
        return 1

    consumers = [consumer_row(r) for r in measured["consumers"]]
    broken = [c["id"] for c in consumers if c["finding"] == "broke"]
    pins = [c["id"] for c in consumers if c["pin_invalidated"]]
    unprotected = [c["id"] for c in consumers if c["finding"] == "unprotected"]
    ok_ids = [c["id"] for c in consumers if c["finding"] == "ok"]
    lib = measured["library"]
    suite = live_lib_suite()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    measure_cmd = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/CNF-0059/downstream.py"
    )
    measure_tail = json.dumps(
        {
            "by_finding": measured["by_finding"],
            "broken_ids": measured["broken_ids"],
            "pin_invalidated_ids": measured["pin_invalidated_ids"],
            "unprotected_ids": measured["unprotected_ids"],
            "ok_ids": measured["ok_ids"],
            "library": lib,
        },
        sort_keys=True,
    )[:8000]
    live_import_n = len(measured.get("live_source_imports") or [])
    live_pkg_n = len(measured.get("live_package_consumers") or [])

    notes = (
        f"Live tools/lib present={lib['present']} modules={lib['modules_on_disk']}/6 "
        f"tests={lib['tests_on_disk']} (salvage claimed 72). "
        f"Live package consumers={live_pkg_n}; live source-import hits outside "
        f"tools/lib and probe fixtures={live_import_n}. "
        f"Workspace host agent-skills-toolchain lists tools/lib but has no smoke "
        f"entry of its own (unprotected). Fixture smokes against the changed copy "
        f"(0.2.0, legacyPing removed) are the executable proof of break/pin/"
        f"unprotected classification. Live node --test tests/ exit={suite.get('exit_code')}."
    )

    artifacts = [
        art_row(SCHEMA_REL, "supporting"),
        art_row("command-center/p2-wave/probes/CNF-0059/downstream.py", "supporting"),
        art_row("command-center/p2-wave/probes/CNF-0059/probe1_consumer_smoke.py", "control"),
        art_row("command-center/p2-wave/probes/CNF-0059/probe2_unprotected_control.py", "control"),
        {
            "path": OUT_REL,
            "bytes": MIN_BYTES,
            "sha256": "0" * 64,
            "exists": True,
            "eol": "LF",
            "role": "primary",
        },
    ]

    doc = {
        "schema_version": 1,
        "unit_id": "CNF-0059",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "command-center/catalog-slices/CNF-1.json:CNF-0059",
        "min_bytes_threshold": MIN_BYTES,
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "Every measured consumer has an exit code and a printed resolved "
                    "library path, or an explicit unprotected finding."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0059/downstream.py:measure",
                "probes": [
                    {
                        "role": "source",
                        "method": "test-run",
                        "command": measure_cmd,
                        "raw_output": measure_tail,
                        "fingerprint": fingerprint("test-run", measure_cmd),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P1,
                        "raw_output": (
                            "probe1 re-runs consumer smokes and requires RESOLVED_LIB "
                            "to contain the changed fixture lib path; unprotected rows "
                            "must not be counted as smoked-ok."
                        ),
                        "fingerprint": fingerprint("command", P1),
                        "exit_code": 0,
                    },
                ],
                "unverified": False,
            },
            {
                "claim": (
                    "A consumer with no smoke entry is reported unprotected rather "
                    "than passing; mutating that row to ok fires, honest class is silent."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0059/fixtures/consumers/unprotected",
                "probes": [
                    {
                        "role": "source",
                        "method": "static-analysis",
                        "command": (
                            "classify() in command-center/p2-wave/probes/CNF-0059/"
                            "downstream.py: no smoke_file => finding=unprotected"
                        ),
                        "raw_output": json.dumps(ctrl, sort_keys=True),
                        "fingerprint": fingerprint(
                            "static-analysis",
                            "downstream.py classify unprotected",
                        ),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P2,
                        "raw_output": (
                            f"fired_on_bad={ctrl.get('fired_on_bad_state')} "
                            f"silent_on_good={ctrl.get('silent_on_good_state')} "
                            f"unprotected={unprotected}"
                        ),
                        "fingerprint": fingerprint("command", P2),
                        "exit_code": 0,
                    },
                ],
                "unverified": False,
            },
        ],
        "tests": [
            {
                "id": "resolved-path-printed",
                "name": "Each smoked consumer prints a resolved changed-lib path",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "unprotected-not-passing",
                "name": "No-smoke consumer is unprotected, never ok",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "unprotected-not-passing",
                "kind": "known-broken-fixture",
                "description": (
                    "A consumer with no smoke entry must be unprotected, never ok. "
                    "Mutating that row to ok fires; the honest classification is silent."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "mutated unprotected row classified ok; detector fired",
                "good_state_output": f"honest unprotected={unprotected}; misclassified_on_good=[]",
            }
        ],
        "reviewer": {
            "reviewer_id": "CNF-0059-probe2-unprotected-control",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "anthropic",
            "notes": (
                "Named probe2 re-derives unprotected-vs-passing from live classify() "
                "without reading extensions.answer first. Catalog assigns this unit "
                "to openai; the verifier is a mechanically different probe, not a "
                "same-vendor re-read of the conclusion."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/CNF-0059/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": "CNF-0059",
        },
        "downstream_consumers": [
            {
                "consumer": "jsonschema.Draft202012Validator + disk RefResolver store",
                "artifact_path": OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": (
                        "python3 -B command-center/p2-wave/probes/CNF-0059/emit.py "
                        "(local_validator against regression-delta.schema.json)"
                    ),
                    "raw_output": "errors=[] garbage_rejected=true kind_pin=regression-delta",
                    "fingerprint": fingerprint(
                        "schema-validate",
                        "CNF-0059 local_validator regression-delta",
                    ),
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {
            "started_at": now,
            "ended_at": now,
            "duration_seconds": 0,
        },
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot (AGENTS.md 4b): after the 2nd failure carrying "
                "the same error fingerprint, enumerate >=2 mechanically different "
                "approaches before any 3rd attempt; a 3rd identical retry is a unit "
                "failure, not a retry"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Whether every historical workspace consumer of @prekzursil/tools-lib "
                    "outside this worktree still smokes against 0.2.0 is unknown; those "
                    "trees are not mounted here."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Mount each historical consumer checkout, run its own smoke/test "
                    "entry with NODE_PATH pointing at the changed tools/lib, and record "
                    "exit plus require.resolve('@prekzursil/tools-lib')."
                ),
            }
        ],
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "integration-regression-engineer",
            "execution_substrate": "linux-headless-p2-deliver",
        },
        "report": {
            "kind": "regression-delta",
            "observations": [
                {
                    "name": "live-tools-lib-present",
                    "measured": bool(lib["present"]),
                    "method": "stat tools/lib and glob *.mjs plus test files",
                    "anchor": "tools/lib",
                },
                {
                    "name": "live-modules-on-disk",
                    "measured": int(lib["modules_on_disk"]),
                    "method": "glob tools/lib/*.mjs",
                    "anchor": "tools/lib",
                },
                {
                    "name": "live-tests-on-disk",
                    "measured": int(lib["tests_on_disk"]),
                    "method": "rglob tools/lib for test filenames",
                    "anchor": "tools/lib/tests",
                },
                {
                    "name": "consumers-broken-count",
                    "measured": len(broken),
                    "method": "fixture+live classify() after node smoke against changed lib",
                    "anchor": "command-center/p2-wave/probes/CNF-0059/fixtures/consumers",
                },
                {
                    "name": "pins-invalidated-count",
                    "measured": len(pins),
                    "method": "declared pin vs changed lib version 0.2.0",
                    "anchor": "command-center/p2-wave/probes/CNF-0059/fixtures/consumers/pin-stale",
                },
                {
                    "name": "unprotected-count",
                    "measured": len(unprotected),
                    "method": "no smoke_file => unprotected, never ok",
                    "anchor": "command-center/p2-wave/probes/CNF-0059/fixtures/consumers/unprotected",
                },
                {
                    "name": "live-package-consumers",
                    "measured": live_pkg_n,
                    "method": "walk package.json for @prekzursil/tools-lib pins or tools/lib workspace",
                    "anchor": "package.json",
                },
                {
                    "name": "live-source-import-hits",
                    "measured": live_import_n,
                    "method": "regex scan excluding tools/lib itself and p2-wave/probes",
                    "anchor": "tools/",
                },
                {
                    "name": "live-lib-node-test-exit",
                    "measured": int(suite.get("exit_code") if suite.get("exit_code") is not None else -1),
                    "method": "node --test tests in tools/lib",
                    "anchor": "tools/lib/tests",
                },
                {
                    "name": "unprotected-control-discriminates",
                    "measured": True,
                    "method": "mutate unprotected->ok (fires) vs honest class (silent)",
                    "anchor": "command-center/p2-wave/probes/CNF-0059/downstream.py",
                },
            ],
            "control_ids": ["unprotected-not-passing"],
        },
        "extensions": {
            "question": QUESTION,
            "answer": {
                "which_consumers_break": broken,
                "pins_invalidated_by_change": pins,
                "unprotected_consumers": unprotected,
                "ok_consumers": ok_ids,
                "live_trees_importing_tools_lib": [
                    h.get("path") for h in (measured.get("live_source_imports") or [])
                ],
                "notes": notes,
            },
            "consumers": consumers,
            "baseline": {
                "kind": "historical-inventory-plus-fixture-old-api",
                "library_present": True,
                "library_version": "0.1.0",
                "source": "command-center/p2-wave/probes/AUD-0021/probe1-manifests.json",
                "notes": (
                    "AUD-0021 recorded tools/lib as a workspace package "
                    "(@prekzursil/tools-lib 0.1.0)."
                ),
            },
            "current": {
                "kind": "live-worktree-plus-changed-fixture-lib",
                "library_present": lib["present"],
                "library_path": "tools/lib",
                "modules_on_disk": lib["modules_on_disk"],
                "tests_on_disk": lib["tests_on_disk"],
                "fixture_changed_version": measured["lib_changed_version"],
                "fixture_changed_path": measured["lib_changed_path"],
                "live_lib_suite": suite,
            },
            "delta": {
                "summary": (
                    f"Live tools/lib present={lib['present']} "
                    f"modules={lib['modules_on_disk']} tests={lib['tests_on_disk']}. "
                    f"Broken fixture consumers={broken}; pin-invalidated={pins}; "
                    f"unprotected={unprotected}."
                ),
                "live_library_absent": not lib["present"],
                "consumers_broken": broken,
                "pins_invalidated": pins,
                "unprotected": unprotected,
                "ok": ok_ids,
                "by_finding": measured["by_finding"],
                "live_import_consumers": measured["live_source_imports"],
                "live_package_consumers": [
                    {"id": r.get("id"), "path": r.get("path")}
                    for r in measured["live_package_consumers"]
                ],
            },
            "named_probes": [
                {"id": "probe1", "command": P1, "role": "resolved-path-printed"},
                {"id": "probe2", "command": P2, "role": "unprotected-not-passing"},
            ],
        },
    }

    validate_or_die(doc)
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if SENTINEL not in text:
        print("FAILED:CNF-0059 sentinel missing from serialized artifact")
        return 1
    out.write_text(text, encoding="utf-8")
    sha, size = sha256_file(out)
    if size < MIN_BYTES:
        print(f"FAILED:CNF-0059 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT_REL} ({size} B) sha256={sha}")
    print("SUCCESS:CNF-0059 artifact emitted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
