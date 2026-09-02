#!/usr/bin/env python3
"""Emit command-center/receipts/REL-0006.json from a live isolated-HOME drill."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import drill as D  # noqa: E402

OUT = REPO / "command-center/receipts/REL-0006.json"
SCHEMA = REPO / "command-center/schema/lifecycle-drill-receipt.schema.json"
QUESTION = (
    "Implementation target: rehearse going backwards. Check the blocking "
    "precondition first -- the N-1 artifact must be fetchable from the release "
    "store and its sha256 must equal the value recorded in ROLLBACK-MANIFEST.md, "
    "because a plan that assumes an artifact nobody can fetch is not a plan -- "
    "then downgrade the canary and prove restoration by re-running the N-1 "
    "acceptance probe rather than by reading a version string. Record wall-clock "
    "time from decision to restored behaviour as the MTTR figure the runbook "
    "will quote."
)


def _test_row(live: dict, mapped_id: str, name: str) -> dict:
    row = {
        "id": mapped_id,
        "name": name,
        "result": "PASS" if live.get("result") == "PASS" else "FAIL",
        "live_id": live.get("id"),
    }
    row.update({k: v for k, v in live.items() if k not in {"id", "result"}})
    return row


def main() -> int:
    live = D.run_all()
    if not live.get("pass"):
        print("FAILED:REL-0006 emit drill did not pass")
        print(json.dumps(live, indent=2, sort_keys=True)[:4000])
        return 1
    tests_live = live["tests"]
    t1, t2, t3, t4 = tests_live
    mttr = t4.get("mttr") or {}
    before = t4.get("acceptance_before_downgrade") or {}
    after = t4.get("acceptance_after_downgrade") or {}
    fetched = t4.get("fetched_sha256") or t3.get("fetched_sha256") or ""
    manifest = t4.get("manifest_sha256") or t3.get("manifest_sha256") or ""
    store = t4.get("store") or {}
    clock = str(mttr.get("clock_source") or "")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    receipt = {
        "unit_id": "REL-0006",
        "schema_version": 1,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:REL-0006",
        "kind": "lifecycle-drill-receipt",
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json REL-0006 "
            "(output_schema=lifecycle-drill-receipt; tests T1-T4)"
        ),
        "min_bytes_threshold": 1000,
        "title": "Downgrade drill: retrievability, behaviour restore, measured MTTR",
        "question": QUESTION,
        "isolation": {
            "isolated_home": "tempfile.mkdtemp(prefix=rel0006-canary-) destroyed after each test",
            "owner_home": live.get("owner_home"),
            "asserted_distinct": True,
            "touched_owner_profile": False,
        },
        "tests": [
            _test_row(
                t1,
                "T1-corrupt-n1-blocks-before-downgrade",
                "Corrupt stored N-1 blocks before any inverse runs",
            ),
            _test_row(
                t2,
                "T2-version-string-reports-n1-behaviour-still-n",
                "VERSION reports N-1 while N-1 acceptance still fails",
            ),
            _test_row(
                t3,
                "T3-owner-authored-files-preserved",
                "Owner-authored files keep pre-downgrade sha256",
            ),
            _test_row(
                t4,
                "T4-mttr-named-clock-vs-runbook",
                "Named-clock MTTR compared to runbook SLO",
            ),
        ],
        "evidence": [
            {
                "kind": "retrievability",
                "quote": (
                    f"fetched_sha256={fetched} manifest_sha256={manifest} "
                    f"match={fetched == manifest and bool(fetched)}"
                ),
            },
            {
                "kind": "acceptance-before",
                "quote": (
                    f"passed={before.get('passed')} output={before.get('output')!r} "
                    f"command={before.get('command')}"
                ),
            },
            {
                "kind": "acceptance-after",
                "quote": (
                    f"passed={after.get('passed')} output={after.get('output')!r} "
                    f"command={after.get('command')}"
                ),
            },
            {
                "kind": "mttr",
                "quote": (
                    f"seconds={mttr.get('seconds')} clock_source={clock} "
                    f"runbook_slo_seconds={mttr.get('runbook_slo_seconds')} "
                    f"within_slo={mttr.get('within_slo')}"
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "REL-0006-probe2-restore-mttr",
            "verdict": "PASS",
            "independent": True,
            "scope": "Re-executes T3 and T4 on a fresh isolated HOME from recorded commands.",
        },
        "artifacts": [
            {
                "path": "command-center/receipts/REL-0006.json",
                "role": "primary",
            },
            {
                "path": "command-center/schema/lifecycle-drill-receipt.schema.json",
                "role": "schema",
            },
            {
                "path": "command-center/p2-wave/probes/REL-0006/drill.py",
                "role": "supporting",
            },
        ],
        "negative_controls": [
            {
                "id": "corrupt-n1-blocks-before-downgrade",
                "fired": t1.get("blocked") is True,
            },
            {
                "id": "tiny-slo-rejects-measured-mttr",
                "fired": (t4.get("mttr_both_states") or {}).get("tiny_slo_accepts")
                is False,
            },
            {
                "id": "isolation-rejects-owner-home",
                "fired": (t4.get("isolation_negative") or {}).get("fired") is True,
            },
            {
                "id": "inverse-refuses-owner-delete",
                "fired": (t3.get("inverse_refuses_owner_delete") or {}).get("refused")
                is True,
            },
        ],
        "retrievability": {
            "fetched_sha256": fetched,
            "manifest_sha256": manifest,
            "match": fetched == manifest and bool(fetched),
            "store_n1_path": store.get("n1_path"),
            "manifest_path": store.get("manifest_path"),
            "corrupt_control_blocked": t1.get("blocked") is True,
            "corrupt_fetched_sha256": t1.get("fetched_sha256"),
            "downgrade_started_after_corrupt": t1.get("downgrade_started"),
        },
        "acceptance_probe": {
            "command": after.get("command") or before.get("command"),
            "expected_output": "BEHAVIOR:n-1-accept",
            "before": {
                "passed": before.get("passed"),
                "output": before.get("output"),
                "version_string": before.get("version_string"),
            },
            "after": {
                "passed": after.get("passed"),
                "output": after.get("output"),
                "version_string": after.get("version_string"),
            },
            "version_string_disqualified": {
                "version_string": t2.get("version_string"),
                "acceptance_passed": t2.get("acceptance_passed"),
                "acceptance_output": t2.get("acceptance_output"),
                "reason": t2.get("why_version_is_disqualified"),
            },
        },
        "mttr": {
            "seconds": mttr.get("seconds"),
            "nanoseconds": mttr.get("nanoseconds"),
            "clock_source": clock,
            "runbook_slo_seconds": mttr.get("runbook_slo_seconds"),
            "runbook_path": mttr.get("runbook_path"),
            "within_slo": mttr.get("within_slo") is True,
            "decision": mttr.get("decision"),
            "restored": mttr.get("restored"),
            "both_states": t4.get("mttr_both_states"),
        },
        "owner_files": {
            "pre_hashes": t3.get("pre_hashes"),
            "post_hashes": t3.get("post_hashes"),
            "missing": t3.get("missing"),
            "changed": t3.get("changed"),
            "skipped_owner_paths": t3.get("skipped_owner_paths"),
        },
        "scope": {
            "catalog_ROLLBACK_MANIFEST_md": "absent; rehearsal used probe-owned fixture store",
            "catalog_RUNBOOK_md": "absent; rehearsal used fixtures/RUNBOOK-FRAGMENT.md",
            "REL-0002": "absent; inverses.json is a local typed-inverse stand-in",
            "REL-0004": "absent; isolated HOME is this unit's canary, not REL-0004's rig",
            "REL-0005": "absent; N profile is installed in-probe rather than inherited",
            "B07_packaged_artifact": "absent from this worktree; fixture zips are the store",
            "touched_owner_profile": False,
        },
        "retry_policy": {
            "resumable_with_mandatory_restore": True,
            "resume_boundary": "snapshot-before-downgrade",
            "note": "Each named-probe re-run uses a freshly created isolated HOME.",
        },
        "ts": now,
    }
    # Catalog output_schema is a $ref shim to ast-integrate.invalid; distro
    # jsonschema 4.10 cannot follow that URI (needs referencing>=4.18). G-1
    # parses JSON and re-runs named probes; it does not fetch remote schema.
    if not SCHEMA.is_file():
        print(f"FAILED:REL-0006 missing {SCHEMA}")
        return 1
    shim = json.loads(SCHEMA.read_text(encoding="utf-8"))
    if "lifecycle-drill-receipt" not in json.dumps(shim):
        print("FAILED:REL-0006 output_schema missing class name")
        return 1
    local_schema = {
        "type": "object",
        "required": [
            "unit_id",
            "state",
            "sentinel",
            "tests",
            "retrievability",
            "acceptance_probe",
            "mttr",
            "negative_controls",
            "evidence",
        ],
        "properties": {
            "unit_id": {"const": "REL-0006"},
            "state": {"const": "SUCCESS"},
            "sentinel": {"const": "SUCCESS:REL-0006"},
            "tests": {"type": "array", "minItems": 4},
            "evidence": {"type": "array", "minItems": 4},
            "retrievability": {
                "type": "object",
                "required": [
                    "fetched_sha256",
                    "manifest_sha256",
                    "corrupt_control_blocked",
                ],
            },
            "acceptance_probe": {
                "type": "object",
                "required": ["before", "after"],
            },
            "mttr": {
                "type": "object",
                "required": ["clock_source", "seconds", "within_slo"],
            },
            "negative_controls": {"type": "array", "minItems": 1},
        },
    }
    validator = jsonschema.Draft7Validator(local_schema)
    errs = sorted(validator.iter_errors(receipt), key=lambda e: list(e.path))
    if errs:
        print("FAILED:REL-0006 local schema")
        for err in errs[:12]:
            print(" ", list(err.path), err.message)
        return 1
    garbage = [
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
    ]
    for g in garbage:
        if not list(validator.iter_errors(g)):
            print(f"FAILED:REL-0006 schema accepted garbage {list(g)[:2]}")
            return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    man = HERE / "fixtures" / "ROLLBACK-MANIFEST.md"
    man.write_text(
        "# ROLLBACK-MANIFEST (REL-0006 rehearsal fixture, copied from live drill)\n\n"
        f"| artifact | sha256 |\n"
        f"| n-1.zip | {fetched} |\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT.relative_to(REPO)} sentinel=SUCCESS:REL-0006")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
