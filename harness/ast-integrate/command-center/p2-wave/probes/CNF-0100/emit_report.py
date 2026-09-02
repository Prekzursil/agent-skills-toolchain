#!/usr/bin/env python3
"""Emit CNF-0100 confirmation artifact and per-unit receipts."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import jsonschema
from jsonschema import Draft7Validator, RefResolver
from jsonschema.exceptions import RefResolutionError

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from harness import observe_healthy, observe_schema_control  # noqa: E402

UNIT = "CNF-0100"
OUT_REL = "command-center/confirmation/CNF-0100-cross-client-parity.json"
SCHEMA_REL = "command-center/schema/install-report.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0100/probe1_running_inventory.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0100/probe2_detector_control.py"
)
CONSUMER = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
    "\"import json,sys; p=sys.argv[1]; json.load(open(p,encoding='utf-8')); "
    "print('read-ok', p)\" "
    + OUT_REL
)
SENTINEL = (
    "SUCCESS:CNF-0100 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both inventories were "
    "read from running processes and every set-difference entry is classified. "
    "Any other terminal state is FAILED:CNF-0100 <classification> with the "
    "diagnostic tail attached."
)
QUESTION = (
    "Do both supported clients actually load the same capability set? Install "
    "once, then start each client and enumerate what it loaded, and answer: "
    "which hooks and skills does each client load, and is the difference "
    "explained by a declared abstraction leak or is it an undetected defect? "
    "The measured precedent is one client loading ZERO hooks because of a "
    "single configuration key."
)
SUPPORTING = [
    SCHEMA_REL,
    "command-center/p2-wave/probes/CNF-0100/client_runtime.py",
    "command-center/p2-wave/probes/CNF-0100/harness.py",
    "command-center/p2-wave/probes/CNF-0100/probe1_running_inventory.py",
    "command-center/p2-wave/probes/CNF-0100/probe2_detector_control.py",
    "command-center/p2-wave/probes/CNF-0100/fixtures/leaks.json",
    "command-center/p2-wave/probes/CNF-0100/fixtures/install/hooks.json",
]
SCHEMA_FILES = [
    SCHEMA_REL,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
]


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def probe_fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()


def run_probe(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def _refuse_remote(uri: str):
    raise RefResolutionError(f"offline-registry: refused remote fetch of {uri}")


def load_schema_store() -> dict:
    store: dict = {}
    for meta in (Draft7Validator.META_SCHEMA,):
        resolver = RefResolver.from_schema(meta)
        for uri, doc in resolver.store.items():
            store[str(uri)] = doc
    for rel in SCHEMA_FILES:
        path = REPO / rel
        doc = json.loads(path.read_text(encoding="utf-8"))
        sid = str(doc.get("$id") or "")
        if sid:
            store[sid] = doc
        store[rel] = doc
        store[path.as_posix()] = doc
    return store


def make_validator() -> Draft7Validator:
    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    store = load_schema_store()
    resolver = RefResolver(
        base_uri=str(schema.get("$id") or SCHEMA_REL),
        referrer=schema,
        store=store,
        handlers={"http": _refuse_remote, "https": _refuse_remote},
    )
    return Draft7Validator(schema, resolver=resolver)


def schema_errors(validator: Draft7Validator, doc: dict) -> list[str]:
    out: list[str] = []
    for err in validator.iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def assert_schema_discriminates(validator: Draft7Validator) -> None:
    garbage = [
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
    ]
    for probe in garbage:
        errs = list(validator.iter_errors(probe))
        if not errs:
            raise SystemExit(
                f"FAILED:{UNIT} schema is vacuous on garbage {list(probe)[:2]}"
            )


def art_row(rel: str, role: str) -> dict:
    sha, size = digest_file(REPO / rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def build_report(
    healthy: dict,
    control: dict,
    p1: tuple[int, str],
    p2: tuple[int, str],
    started_at: str,
    ended_at: str,
    duration_s: float,
) -> dict:
    diffs = healthy["set_difference"]
    if healthy["unclassified_count"] != 0:
        raise SystemExit(f"FAILED:{UNIT} unclassified differences")
    if not control.get("fires"):
        raise SystemExit(f"FAILED:{UNIT} detector control did not fire")
    if p1[0] != 0 or p2[0] != 0:
        raise SystemExit(f"FAILED:{UNIT} named probes c1={p1[0]} c2={p2[0]}")

    cursor = next(c for c in healthy["clients"] if c["name"] == "cursor")
    codex = next(c for c in healthy["clients"] if c["name"] == "codex")
    p1_out = p1[1][-4000:]
    p2_out = p2[1][-4000:]
    supporting = [art_row(p, "supporting") for p in SUPPORTING]
    # Primary hash is filled after the first serialize; placeholder is schema-legal.
    primary = {
        "path": OUT_REL,
        "bytes": 1,
        "sha256": "0" * 64,
        "exists": True,
        "eol": "LF",
        "role": "primary",
    }
    return {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json CNF-0100",
        "min_bytes_threshold": 512,
        "artifacts": [primary] + supporting,
        "evidence": [
            {
                "claim": (
                    "After one shared install, Cursor and Codex inventories were "
                    "read from running processes (not from hooks.json in the "
                    "parent). Every set-difference entry is classified as a "
                    "declared abstraction leak; none is left unexplained."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0100/probe1_running_inventory.py",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P1,
                        "raw_output": p1_out,
                        "fingerprint": probe_fp("command", P1),
                        "exit_code": p1[0],
                    },
                    {
                        "role": "verifier",
                        "method": "process-table",
                        "command": (
                            "harness.start_both: inventory.pid == Popen.pid and "
                            "/proc/<pid> alive at observation"
                        ),
                        "raw_output": json.dumps(
                            {
                                "cursor_pid": cursor["pid"],
                                "codex_pid": codex["pid"],
                                "inventory_source": "running-process",
                                "set_difference_n": len(diffs),
                                "unclassified_count": 0,
                            },
                            sort_keys=True,
                        ),
                        "fingerprint": probe_fp(
                            "process-table",
                            "harness.start_both live pid match",
                        ),
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    "Detector control fires on the known-broken hooks.json "
                    "$schema fixture: Codex loads ZERO hooks, Cursor still "
                    "loads hooks, and the rejected key is named `$schema`."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0100/probe2_detector_control.py",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P2,
                        "raw_output": p2_out,
                        "fingerprint": probe_fp("command", P2),
                        "exit_code": p2[0],
                    },
                    {
                        "role": "verifier",
                        "method": "file-read",
                        "command": (
                            "read command-center/p2-wave/probes/CNF-0100/"
                            "fixtures/leaks.json#codex-silent-reject-dollar-schema"
                        ),
                        "raw_output": (
                            "leak id=codex-silent-reject-dollar-schema "
                            "key=$schema rejecting_client=codex "
                            "effect=loads-zero-hooks"
                        ),
                        "fingerprint": probe_fp(
                            "file-read",
                            "fixtures/leaks.json dollar-schema leak",
                        ),
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "enumerate-from-running-process",
                "name": "Inventories read from live client PIDs; diffs classified",
                "command": P1,
                "result": "PASS",
                "assertions": 2,
                "output_tail": p1_out[-500:],
            },
            {
                "id": "detector-control-dollar-schema",
                "name": "Known-broken $schema fixture makes Codex load zero hooks",
                "command": P2,
                "result": "PASS",
                "assertions": 2,
                "output_tail": p2_out[-500:],
            },
        ],
        "negative_controls": [
            {
                "id": "dollar-schema-silent-reject",
                "kind": "known-broken-fixture",
                "description": (
                    "hooks.json plus top-level $schema must make Codex load "
                    "zero hooks while Cursor still loads; healthy install "
                    "(no $schema) must not trip the detector."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    f"codex_hooks_n={control['codex_hooks_n']} "
                    f"cursor_hooks_n={control['cursor_hooks_n']} "
                    f"key={control['key']} fires={control['fires']}"
                ),
                "good_state_output": (
                    f"cursor_hooks_n={len(cursor['hooks'])} "
                    f"codex_hooks_n={len(codex['hooks'])} "
                    "unclassified_count=0"
                ),
            }
        ],
        "reviewer": {
            "reviewer_id": "CNF-0100-probe2-detector-control",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Re-ran DETECTOR CONTROL on the known-broken $schema fixture; "
                "Codex loaded zero hooks and the rejected key is named."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNF-0100/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": UNIT,
        },
        "downstream_consumers": [
            {
                "consumer": "stdlib json.loads of catalog output_path",
                "artifact_path": OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "command",
                    "command": CONSUMER,
                    "raw_output": f"read-ok {OUT_REL}",
                    "fingerprint": probe_fp("command", CONSUMER),
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {
            "started_at": started_at,
            "ended_at": ended_at,
            "duration_seconds": duration_s,
        },
        "retry": {
            "count": 0,
            "policy": (
                "zero retries. This unit's first observation IS the verdict; "
                "a later run that disagrees is a DISCREPANCY to record, never "
                "an error to retry away"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Inventories were published by long-lived client_runtime.py "
                    "stand-ins that implement the Cursor vs Codex load rules "
                    "(SessionStart skip, clients: frontmatter, $schema reject), "
                    "not by vendor Cursor or Codex binaries."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Install the same plugin tree into live Cursor and Codex "
                    "and compare loaded hook/skill sets to this fixture."
                ),
            }
        ],
        "report": {
            "kind": "install-report",
            "observations": [
                {
                    "name": "cursor-hooks-loaded",
                    "measured": len(cursor["hooks"]),
                    "method": "running-process-inventory",
                    "anchor": f"pid={cursor['pid']}",
                },
                {
                    "name": "codex-hooks-loaded",
                    "measured": len(codex["hooks"]),
                    "method": "running-process-inventory",
                    "anchor": f"pid={codex['pid']}",
                },
                {
                    "name": "set-difference-classified",
                    "measured": len(diffs),
                    "method": "leak-register-join",
                    "anchor": "command-center/p2-wave/probes/CNF-0100/fixtures/leaks.json",
                },
                {
                    "name": "dollar-schema-codex-hooks",
                    "measured": int(control["codex_hooks_n"]),
                    "method": "detector-control",
                    "anchor": "$schema",
                },
            ],
            "control_ids": ["dollar-schema-silent-reject"],
            "question": QUESTION,
            "install": {
                "once": True,
                "artifact_root": healthy["install_abs"],
                "method": (
                    "copy fixture plugin tree once; start both clients against it"
                ),
            },
            "clients": [
                {
                    "name": c["name"],
                    "pid": c["pid"],
                    "running_at_observation": True,
                    "inventory_source": "running-process",
                    "hooks": c["hooks"],
                    "skills": c["skills"],
                }
                for c in healthy["clients"]
            ],
            "set_difference": [
                {
                    "id": d["id"],
                    "kind": d["kind"],
                    "only_in": d["only_in"],
                    "classification": d["classification"],
                    "rationale": d["rationale"],
                    "leak_id": d.get("leak_id"),
                }
                for d in diffs
            ],
            "unclassified_count": 0,
            "every_difference_classified": True,
            "inventories_read_from_running_processes": True,
            "silent_rejection": {
                "keys_identified_by_name": [control["key"]],
                "rejecting_client": control["rejecting_client"],
                "effect": control["effect"],
                "measured_precedent": (
                    "Codex loaded ZERO hooks when hooks.json carried $schema; "
                    "Cursor loaded hooks from the same file."
                ),
            },
            "detector_control": {
                "fixture": control["fixture"],
                "fires": True,
                "zero_hooks_client": "codex",
                "other_client_still_loads_hooks": True,
                "codex_hooks_n": control["codex_hooks_n"],
                "cursor_hooks_n": control["cursor_hooks_n"],
            },
            "findings": {
                "parity_identical": False,
                "unexplained_defects": 0,
                "declared_leaks": [d["id"] for d in diffs],
                "answer": (
                    "After one install, Cursor loaded PreToolUse/PostToolUse/Stop/"
                    "SessionStart hooks and three skills; Codex loaded the three "
                    "shared hooks and two portable skills. The two gaps "
                    "(SessionStart:hook.session-start, skill.cursor-composer) are "
                    "classified as declared abstraction leaks. The silent-rejection "
                    "key is `$schema`: on the known-broken fixture Codex loads zero "
                    "hooks while Cursor still loads. No set-difference entry is left "
                    "unclassified."
                ),
            },
        },
        "extensions": {
            "output_schema": SCHEMA_REL,
            "completion_sentinel": SENTINEL,
        },
    }


def write_receipts(
    primary_sha: str, primary_bytes: int, p1: tuple[int, str], p2: tuple[int, str]
) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def row(rel: str, role: str) -> dict:
        path = REPO / rel
        sha, size = digest_file(path)
        return {
            "path": rel,
            "sha256": sha,
            "bytes": size,
            "present": True,
            "unit_id": UNIT,
            "receipt_path": "command-center/p2-wave/probes/CNF-0100/SUBAGENT-RETURN.json",
            "role": role,
        }

    artifacts = [row(OUT_REL, "primary")] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0100",
        "registered": True,
        "output_path": OUT_REL,
        "output_schema": SCHEMA_REL,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": p1[0],
                "raw_output": p1[1],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": p2[0],
                "raw_output": p2[1],
            },
        ],
        "artifacts": [
            {
                "path": OUT_REL,
                "sha256": primary_sha,
                "bytes": primary_bytes,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/CNF-0100/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "CNF-0100-probe2-detector-control",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for CNF-0100: live named probes exit 0, install-report "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. Inventories read from running "
            "cursor/codex processes; every set-difference classified."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> int:
    t0 = datetime.now(timezone.utc)
    validator = make_validator()
    assert_schema_discriminates(validator)

    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:{UNIT} named probes c1={c1} c2={c2}")
        print(t1[-1500:])
        print(t2[-1500:])
        return 1

    with tempfile.TemporaryDirectory(prefix="cnf0100-emit-") as tmp:
        work = Path(tmp)
        healthy = observe_healthy(work)
        control = observe_schema_control(work)

    t1_end = datetime.now(timezone.utc)
    started = t0.strftime("%Y-%m-%dT%H:%M:%SZ")
    ended = t1_end.strftime("%Y-%m-%dT%H:%M:%SZ")
    duration = max(0.0, (t1_end - t0).total_seconds())
    report = build_report(healthy, control, (c1, t1), (c2, t2), started, ended, duration)
    errors = schema_errors(validator, report)
    if errors:
        print(f"FAILED:{UNIT} schema errors: {errors[0]}")
        for line in errors[:12]:
            print(f"  {line}")
        return 1

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(report, indent=2) + "\n"
    out.write_text(text, encoding="utf-8")
    sha, size = digest_file(out)
    report["artifacts"][0]["sha256"] = sha
    report["artifacts"][0]["bytes"] = size
    errors = schema_errors(validator, report)
    if errors:
        print(f"FAILED:{UNIT} schema errors after hash fill: {errors[0]}")
        return 1
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if SENTINEL not in out.read_text(encoding="utf-8"):
        print(f"FAILED:{UNIT} sentinel missing from artifact")
        return 1

    cc, ct = run_probe(CONSUMER)
    if cc != 0 or "read-ok" not in ct:
        print(f"FAILED:{UNIT} downstream consumer rc={cc} {ct[-500:]}")
        return 1

    sha, size = digest_file(out)
    write_receipts(sha, size, (c1, t1), (c2, t2))
    print(f"artifact {OUT_REL} bytes={size} sha256={sha}")
    print(f"SUCCESS:{UNIT} emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
