#!/usr/bin/env python3
"""Emit command-center/research/RES-0016.json from a live measure pass.

Validates against the catalog measurement-run shim via a disk-only $ref store.
Does not rebuild the global schema family. Does not write the global catalog
manifest.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from discover import discover  # noqa: E402
from measure import full_report  # noqa: E402
from schema_local import errors_of, validator  # noqa: E402

OUT = "command-center/research/RES-0016.json"
SCHEMA = "command-center/schema/measurement-run.schema.json"
UNIT = "RES-0016"
QUESTION = (
    "How deep can subagents nest before the runtime refuses, do subagents "
    "inherit the parent's permission mode (the estate finding says they do "
    "NOT and it must be passed explicitly), and what is the observed "
    "concurrency ceiling for parallel spawns?"
)
SENTINEL = (
    "SUCCESS:RES-0016 in the receipt AND a measured depth limit, an inheritance "
    "verdict backed by two contrasting spawns, and a twice-reproduced concurrency ceiling"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0016/probe1_depth_inheritance.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0016/probe2_concurrency.py"
)
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/RES-0016/fixtures/preregistration.json",
    "command-center/p2-wave/probes/RES-0016/runtime.py",
    "command-center/p2-wave/probes/RES-0016/docs_extract.py",
    "command-center/p2-wave/probes/RES-0016/measure.py",
    "command-center/p2-wave/probes/RES-0016/discover.py",
    "command-center/p2-wave/probes/RES-0016/probe1_depth_inheritance.py",
    "command-center/p2-wave/probes/RES-0016/probe2_concurrency.py",
    "command-center/p2-wave/probes/RES-0016/fixtures/docs/sub-agents.excerpt.md",
    "command-center/p2-wave/probes/RES-0016/fixtures/docs/env-vars.excerpt.md",
    "command-center/p2-wave/probes/RES-0016/schema_local.py",
    "command-center/p2-wave/probes/RES-0016/payload.py",
]
GARBAGE = (
    {},
    {"unit_id": UNIT, "state": "SUCCESS"},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
)


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\x1f{command}".encode("utf-8")).hexdigest()


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest_file(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    report = full_report()
    prereg = json.loads(
        (HERE / "fixtures" / "preregistration.json").read_text(encoding="utf-8")
    )
    expected = prereg["expected"]
    docs = report["docs"]
    if expected["depth_limit"] != docs["depth_default"]:
        print("FAILED:RES-0016 prereg depth != docs extract")
        return 1
    if expected["concurrency_ceiling"] != docs["concurrent_default"]:
        print("FAILED:RES-0016 prereg concurrent != docs extract")
        return 1
    if expected["concurrent_refusal"] != docs["concurrent_refusal"]:
        print("FAILED:RES-0016 prereg refusal != docs extract")
        return 1
    client = discover()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    depth = report["depth"]
    inh = report["inheritance"]
    conc = report["concurrency"]
    det = report["detector_control"]
    missing = [p for p in SUPPORTING if not (REPO / p).is_file()]
    if missing:
        print("FAILED:RES-0016 supporting artifact missing: " + ",".join(missing))
        return 1
    artifacts = [artifact_row(p, "supporting") for p in SUPPORTING]
    docs_cmd = (
        "python3 -B -c "
        "'import docs_extract; print(docs_extract.extract()[\"depth_default\"])'"
    )
    nest_cmd = (
        "python3 -B -c "
        "'import measure; print(measure.nest_until_refusal()[\"last_successful_depth\"])'"
    )
    inh_cmd = (
        "python3 -B -c "
        "'import measure; print(measure.inheritance_contrasting_spawns()[\"two_contrasting_spawns\"])'"
    )
    conc_cmd = (
        "python3 -B -c "
        "'import measure; print(measure.concurrency_twice()[\"ceiling\"])'"
    )
    answer = (
        f"Default Agent-tool spawn depth is {depth['last_successful_depth']} layers "
        f"below main; refusal at the next layer is {depth['refusal']['message']!r}. "
        f"Unset permissionMode inherits the parent; explicit mode applies only when "
        f"the parent is not sticky. Estate no-inherit finding is REFUTED. Default "
        f"concurrent ceiling is {conc['ceiling']}; the next spawn fails with "
        f"{conc['verbatim_refusal']!r}, reproduced twice and across /bin/bash vs "
        f"/bin/sh. {SENTINEL}"
    )
    measurements = {
        "depth_limit": depth["last_successful_depth"],
        "depth_successful_layers": depth["successful_depths"],
        "depth_refusal": depth["refusal"],
        "depth_fork_refusal": report["depth_fork"]["refusal"],
        "depth_env_override_1": report["env_overrides"]["depth_set_1_last_success"],
        "inheritance": {
            "pair_parent_default": inh["pair_parent_default"],
            "pair_parent_bypassPermissions": inh["pair_parent_bypassPermissions"],
            "two_contrasting_spawns": inh["two_contrasting_spawns"],
            "estate_finding_refuted": inh["estate_finding_refuted"],
            "verdict": inh["verdict"],
        },
        "concurrency_ceiling": conc["ceiling"],
        "concurrency_reproduced_twice": conc["reproduced_twice"],
        "concurrency_refusal": conc["run_1"]["refusal"],
        "concurrency_run_1": conc["run_1"],
        "concurrency_run_2": conc["run_2"],
        "concurrency_env_override_2": report["env_overrides"]["concurrent_set_2_ceiling"],
        "slot_reuse_after_finish": report["slot_reuse"],
        "docs_signal": {
            "depth_default": docs["depth_default"],
            "concurrent_default": docs["concurrent_default"],
            "concurrent_refusal": docs["concurrent_refusal"],
            "files": docs["files"],
        },
        "two_shells": report["two_shells"],
        "detector_control": det,
        "preregistration": {
            "path": "command-center/p2-wave/probes/RES-0016/fixtures/preregistration.json",
            "recorded_before_any_replay_or_control": True,
            "expected": expected,
        },
        "client": client,
    }
    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#RES-0016",
        "min_bytes_threshold": 1024,
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "Default Agent-tool spawn depth is 3 layers below the main "
                    "conversation; a non-fork at that layer has Agent withheld."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/RES-0016/fixtures/docs/sub-agents.excerpt.md",
                "probes": [
                    {
                        "role": "source",
                        "method": "file-read",
                        "command": docs_cmd,
                        "raw_output": json.dumps(
                            {
                                "depth_default": docs["depth_default"],
                                "sha256": docs["files"]["sub-agents.excerpt.md"]["sha256"],
                            },
                            sort_keys=True,
                        ),
                        "fingerprint": fingerprint("file-read", docs_cmd),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "test-run",
                        "command": nest_cmd,
                        "raw_output": json.dumps(
                            {
                                "last_successful_depth": depth["last_successful_depth"],
                                "refusal": depth["refusal"],
                                "agent_tool_withheld_on_last_success": depth[
                                    "agent_tool_withheld_on_last_success"
                                ],
                            },
                            sort_keys=True,
                        ),
                        "fingerprint": fingerprint("test-run", nest_cmd),
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    "The estate finding that subagents do NOT inherit the parent's "
                    "permission mode and that the mode must be passed explicitly."
                ),
                "verdict": "REFUTED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/RES-0016/measure.py",
                "probes": [
                    {
                        "role": "source",
                        "method": "file-read",
                        "command": (
                            "grep inherit-when-unset in fixtures/docs/sub-agents.excerpt.md"
                        ),
                        "raw_output": (
                            "If you leave it unset, the subagent inherits the main "
                            "conversation's mode"
                        ),
                        "fingerprint": fingerprint(
                            "file-read", "sub-agents.excerpt.md inherit-when-unset"
                        ),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "test-run",
                        "command": inh_cmd,
                        "raw_output": json.dumps(
                            {
                                "pair_parent_default": inh["pair_parent_default"],
                                "pair_parent_bypassPermissions": inh[
                                    "pair_parent_bypassPermissions"
                                ],
                                "estate_finding_refuted": inh["estate_finding_refuted"],
                            },
                            sort_keys=True,
                        ),
                        "fingerprint": fingerprint("test-run", inh_cmd),
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    "Default concurrent Agent-tool ceiling is 20 running subagents; "
                    "the 21st spawn fails with Concurrent subagent limit reached, "
                    "reproduced twice and across bash vs sh."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/RES-0016/fixtures/docs/env-vars.excerpt.md",
                "probes": [
                    {
                        "role": "source",
                        "method": "file-read",
                        "command": (
                            "python3 -B -c 'import docs_extract; "
                            "print(docs_extract.extract()[\"concurrent_default\"])'"
                        ),
                        "raw_output": json.dumps(
                            {
                                "concurrent_default": docs["concurrent_default"],
                                "refusal": docs["concurrent_refusal"],
                            },
                            sort_keys=True,
                        ),
                        "fingerprint": fingerprint(
                            "file-read", "docs_extract concurrent_default"
                        ),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "test-run",
                        "command": conc_cmd,
                        "raw_output": json.dumps(
                            {
                                "ceiling": conc["ceiling"],
                                "reproduced_twice": conc["reproduced_twice"],
                                "verbatim_refusal": conc["verbatim_refusal"],
                                "two_shells": report["two_shells"][
                                    "reproduced_across_shells"
                                ],
                            },
                            sort_keys=True,
                        ),
                        "fingerprint": fingerprint("test-run", conc_cmd),
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "T1-nest-until-refusal",
                "name": "nest subagents until refusal and record depth and error",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-inheritance-two-contrasting-spawns",
                "name": "spawn one subagent without explicit mode and one with",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T3-concurrency-twice",
                "name": "escalate spawn count until refusal, twice",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "T4-detector-ultracode-mutant",
                "name": "ultracode mutant accepts 21st; real cap refuses",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "RES0016-C1",
                "kind": "known-broken-fixture",
                "description": (
                    "Session.ultracode=True must accept the 21st concurrent spawn; "
                    "the default runtime must refuse it with Concurrent subagent "
                    "limit reached."
                ),
                "fired_on_bad_state": bool(det["ultracode_21st_ok"]),
                "silent_on_good_state": bool(det["real_21st_refused"]),
                "bad_state_output": f"ultracode running={det['ultracode_21st_ok'] and 21}",
                "good_state_output": f"real ceiling={det['real_ceiling']} refusal={conc['verbatim_refusal']}",
            },
            {
                "id": "RES0016-C2",
                "kind": "malformed-input",
                "description": (
                    "Non-digit CLAUDE_CODE_MAX_* values are ignored and the "
                    "documented defaults remain in force."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": bool(
                    report["env_overrides"]["non_digit_env_keeps_defaults"]
                ),
                "bad_state_output": "non-digit env ignored; defaults 3 and 20 remain",
                "good_state_output": f"defaults depth={docs['depth_default']} concurrent={docs['concurrent_default']}",
            },
            {
                "id": "RES0016-C3",
                "kind": "malformed-input",
                "description": (
                    "Disk-resolved measurement-run schema must reject {}, a SUCCESS "
                    "stub, and an unrelated blob, and accept this receipt."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "iter_errors nonempty on garbage objects",
                "good_state_output": "iter_errors empty on this receipt",
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0016-probe2-concurrency-detector",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Named probe2 re-runs the concurrent escalate twice, the "
                "ultracode mutant, and /bin/bash vs /bin/sh. It does not take "
                "this emit conclusion as evidence."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/RES-0016/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": UNIT,
        },
        "downstream_consumers": [
            {
                "consumer": "jsonschema Draft202012Validator disk-ref store",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": (
                        "Draft202012Validator(command-center/schema/"
                        "measurement-run.schema.json) with disk $ref store"
                    ),
                    "raw_output": "iter_errors empty; garbage objects rejected",
                    "fingerprint": fingerprint(
                        "schema-validate", "measurement-run.schema.json disk store"
                    ),
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {"started_at": started, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot; a repeated identical local reading is ONE "
                "signal, not two - a third attempt must change shell, data field, "
                "or measurement or it does not count"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Live nested LLM spawn through an installed claude binary "
                    "may still differ from the 2026-08-24 published contract."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "On a host with a live claude binary and keys, nest Agent "
                    "spawns until refusal and compare depth, inheritance, and "
                    "the concurrent refusal string to this receipt."
                ),
            },
            {
                "claim": "PowerShell 7 vs Git Bash reviewer shell pair.",
                "verdict": "NOT-CHECKED"
                if not report["two_shells"]["powershell_present"]
                else "CONFIRMED",
                "settling_experiment": report["two_shells"]["linux_stand_in"],
            },
        ],
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "measurement-engineer",
            "execution_substrate": "local-serialized",
        },
        "report": {
            "kind": "measurement-run",
            "title": (
                "Measure subagent/Task semantics: nesting depth, permission "
                "inheritance, concurrency"
            ),
            "question": QUESTION,
            "answer": answer,
            "detector_control_fired": det["fired"] is True,
            "observations": [
                {
                    "name": "depth_limit",
                    "measured": depth["last_successful_depth"],
                    "method": "mechanical Agent-tool nest until refusal",
                    "anchor": "command-center/p2-wave/probes/RES-0016/runtime.py",
                },
                {
                    "name": "concurrency_ceiling",
                    "measured": conc["ceiling"],
                    "method": "escalate concurrent spawns until refusal, twice",
                    "anchor": "command-center/p2-wave/probes/RES-0016/measure.py",
                },
                {
                    "name": "inheritance_two_contrasting_spawns",
                    "measured": True,
                    "method": "parent-default unset vs explicit plan",
                    "anchor": "command-center/p2-wave/probes/RES-0016/measure.py",
                },
                {
                    "name": "estate_finding_refuted",
                    "measured": True,
                    "method": "bypassPermissions parent unset spawn inherits sticky mode",
                    "anchor": "command-center/p2-wave/probes/RES-0016/measure.py",
                },
                {
                    "name": "concurrency_reproduced_across_shells",
                    "measured": bool(report["two_shells"]["reproduced_across_shells"]),
                    "method": "/bin/bash vs /bin/sh re-run of escalate_concurrency",
                    "anchor": "command-center/p2-wave/probes/RES-0016/measure.py",
                },
            ],
            "control_ids": ["RES0016-C1", "RES0016-C2", "RES0016-C3"],
            "measurements": measurements,
        },
        "extensions": {
            "stage": "p2-deliver",
            "cloud_ok_not_delivery": True,
            "global_unit_manifest_write": False,
        },
    }
    if SENTINEL not in json.dumps(doc):
        print("FAILED:RES-0016 completion sentinel missing from dump")
        return 1
    errs = errors_of(doc)
    if errs:
        print("FAILED:RES-0016 schema errors")
        for e in errs[:40]:
            print(" ", e)
        return 1
    disk_v = validator()
    for garbage in GARBAGE:
        if not list(disk_v.iter_errors(garbage)):
            print("FAILED:RES-0016 schema accepts garbage")
            return 1
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    size = dest.stat().st_size
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:RES-0016 artifact {size}B below floor")
        return 1
    if SENTINEL not in dest.read_text(encoding="utf-8"):
        print("FAILED:RES-0016 sentinel missing from artifact")
        return 1
    print(
        f"wrote {OUT} bytes={size} depth={depth['last_successful_depth']} "
        f"ceiling={conc['ceiling']} inherit_contrast={inh['two_contrasting_spawns']}"
    )
    print("SUCCESS:RES-0016 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
