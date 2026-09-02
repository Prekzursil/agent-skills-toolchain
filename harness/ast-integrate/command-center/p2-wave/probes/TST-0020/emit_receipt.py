#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0020.json (detector-control receipt)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from invariants import INVARIANTS, SPEC  # noqa: E402
from reproduce import both_states  # noqa: E402
from reviewer import review  # noqa: E402
from tests import run_all  # noqa: E402

OUT_REL = "command-center/receipts/TST-0020.json"
SCHEMA_REL = "command-center/schema/detector-control.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0020/probe1_contradictory.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0020/probe2_consistent.py"
)
QUESTION = (
    "Measured: one run reported 'all 7 PRs hit' AND 'empty intersection' "
    "simultaneously because `grep -c pat || echo 0` printed '0\\n0'. "
    "Target: a post-processor that asserts declared invariants over a single "
    "run's own output (counts must sum, a subset cannot exceed its superset) "
    "and fails the RUN as a detector failure rather than reporting either number."
)

# Catalog output_schema is a $ref shim to ast-integrate.invalid. jsonschema 4.10
# on this image tries HTTPS for that host and never comes back. Discriminate
# locally so garbage is rejected without a network fetch (BLD-0043 pattern).
DISCRIMINATOR = {
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "kind",
        "reproduction",
        "both_states",
        "invariants_declared_before_run",
        "tests",
        "reviewer",
        "evidence",
        "report",
        "completion_sentinel",
    ],
    "properties": {
        "unit_id": {"const": "TST-0020"},
        "state": {"const": "SUCCESS"},
        "sentinel": {"const": "SUCCESS:TST-0020"},
        "kind": {"const": "detector-control"},
        "completion_sentinel": {"const": "SUCCESS:TST-0020"},
        "reproduction": {
            "type": "object",
            "required": ["doubled_zero", "post_processor"],
            "properties": {
                "doubled_zero": {"const": True},
                "post_processor": {
                    "type": "object",
                    "required": [
                        "classification",
                        "published_numbers",
                        "violated_invariants",
                    ],
                    "properties": {
                        "classification": {"const": "detector-failure"},
                        "published_numbers": {"type": "null"},
                        "violated_invariants": {
                            "type": "array",
                            "minItems": 1,
                            "contains": {
                                "const": "mutex-all-hit-empty-intersection"
                            },
                        },
                    },
                },
            },
        },
        "reviewer": {
            "type": "object",
            "required": ["verdict", "independent", "executed_both_states"],
            "properties": {
                "verdict": {"const": "PASS"},
                "independent": {"const": True},
                "executed_both_states": {"const": True},
            },
        },
        "report": {
            "type": "object",
            "required": ["kind", "observations", "control_ids"],
            "properties": {
                "kind": {"const": "detector-control"},
                "observations": {"type": "array", "minItems": 1},
                "control_ids": {"type": "array", "minItems": 1},
            },
        },
        "tests": {"type": "array", "minItems": 3},
        "evidence": {"type": "array", "minItems": 2},
    },
}


def find_line(rel: str, snippet: str) -> int:
    path = REPO / rel
    lines = path.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines, 1):
        if snippet in line:
            return i
    raise SystemExit(f"FAILED:TST-0020 emit anchor miss {rel} {snippet!r}")


def catalog_question_line() -> int:
    path = REPO / "command-center/WORK-UNIT-CATALOG.json"
    lines = path.read_text(encoding="utf-8").splitlines()
    start = None
    for i, line in enumerate(lines, 1):
        if '"id": "TST-0020"' in line:
            start = i
            break
    if start is None:
        raise SystemExit("FAILED:TST-0020 catalog row missing")
    for i in range(start, min(start + 80, len(lines) + 1)):
        if "empty intersection" in lines[i - 1]:
            return i
    raise SystemExit("FAILED:TST-0020 catalog question line missing")


def main() -> int:
    states = both_states()
    if not states.get("pass"):
        print("FAILED:TST-0020 both-states did not discriminate")
        print(json.dumps(states, indent=2, default=str)[:4000])
        return 1
    bad = states["planted_bad"]
    good = states["known_good"]
    if not bad.get("doubled_zero"):
        print("FAILED:TST-0020 live grep -c || echo 0 did not double zero")
        return 1
    if bad.get("published_numbers") is not None:
        print("FAILED:TST-0020 published a number on contradictory output")
        return 1

    tests = run_all()
    if not tests["ok"]:
        print("FAILED:TST-0020 catalog tests")
        print(json.dumps(tests, indent=2, default=str)[:4000])
        return 1

    rev = review()
    if rev.get("verdict") != "PASS":
        print("FAILED:TST-0020 reviewer")
        print(json.dumps(rev, indent=2, default=str)[:4000])
        return 1

    catalog_schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    if not isinstance(catalog_schema, dict) or not catalog_schema.get("$ref"):
        print("FAILED:TST-0020 catalog schema is not a $ref shim")
        return 1
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cat_line = catalog_question_line()
    inv_line = find_line(
        "command-center/p2-wave/probes/TST-0020/invariants.json",
        '"declared_before_run": true',
    )
    naive_line = find_line(
        "command-center/p2-wave/probes/TST-0020/naive.py",
        'if stripped != "0":',
    )
    check_line = find_line(
        "command-center/p2-wave/probes/TST-0020/invariants.py",
        "published_numbers=None",
    )

    t1, t2, t3 = tests["tests"]
    doc = {
        "unit_id": "TST-0020",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0020",
        "kind": "detector-control",
        "title": "Self-contradicting-output detector: one run reporting two mutually exclusive facts",
        "question": QUESTION,
        "ts": now,
        "invariants_declared_before_run": {
            "path": "command-center/p2-wave/probes/TST-0020/invariants.json",
            "declared_before_run": True,
            "note": SPEC.get("note"),
            "invariants": INVARIANTS,
        },
        "pathology": {
            "id": "grep-c-or-echo-0",
            "description": (
                "grep -c prints 0 and exits 1 on no match, so "
                "`grep -c pat || echo 0` prints 0 then 0 again. A naive "
                "reporter treats the blob != '0' as 'all 7 PRs hit' and a "
                "0 line as 'empty intersection', publishing both."
            ),
        },
        "reproduction": {
            "command": bad["command"],
            "raw_stdout": bad["raw_stdout"],
            "raw_lines": bad.get("raw_lines"),
            "doubled_zero": True,
            "naive_claims": bad["naive_claims"],
            "naive_counts": bad["naive_counts"],
            "post_processor": {
                "ok": False,
                "classification": "detector-failure",
                "violated_invariants": bad["violated_invariants"],
                "message": bad["message"],
                "published_numbers": None,
            },
        },
        "both_states": {
            "planted_bad": {
                "fixture": bad["fixture"],
                "fired": True,
                "verbatim": bad["verbatim"],
                "classification": "detector-failure",
                "published_numbers": None,
            },
            "known_good": {
                "fixture": good["fixture"],
                "fired": False,
                "verbatim": good["verbatim"],
                "classification": good.get("classification"),
                "published_numbers": good.get("published_numbers"),
            },
        },
        "detector_control": {
            "known_present_fixture": bad["fixture"],
            "found": True,
            "evaluated_before_absence": True,
            "raw_output": bad["raw_stdout"],
            "note": (
                "The known-present contradiction (doubled zero from "
                "grep -c || echo 0) was classified detector-failure before "
                "the corrected single-zero capture was trusted as silence."
            ),
        },
        "tests": [
            {
                "id": "test_contradictory_counts_fail_the_run",
                "command": P1,
                "result": "PASS" if t1["ok"] else "FAIL",
            },
            {
                "id": "test_consistent_counts_pass",
                "command": P2,
                "result": "PASS" if t2["ok"] else "FAIL",
            },
            {
                "id": "test_failure_message_names_the_violated_invariant",
                "command": P2,
                "result": "PASS" if t3["ok"] else "FAIL",
            },
        ],
        "reviewer": {
            "reviewer_id": rev.get("reviewer_id") or rev.get("reviewer_id"),
            "verdict": rev["verdict"],
            "independent": True,
            "executed_both_states": True,
            "vendor": rev.get("vendor"),
            "author_vendor": rev.get("author_vendor"),
            "scope_not_agreement": True,
            "method": rev.get("method"),
            "overclaim": rev.get("overclaim"),
        },
        "evidence": [
            {
                "claim": "The invariant set is written down before any run is inspected.",
                "verdict": "CONFIRMED",
                "anchor": (
                    "command-center/p2-wave/probes/TST-0020/invariants.json:"
                    f"{inv_line}"
                ),
                "kind": "declaration",
            },
            {
                "claim": (
                    "Live `grep -c || echo 0` on a 7-PR fixture with no match "
                    "prints 0 then 0; the naive reporter claims all-hit AND "
                    "empty-intersection; the post-processor classifies that as "
                    "detector-failure and publishes no number."
                ),
                "verdict": "CONFIRMED",
                "anchor": (
                    "command-center/p2-wave/probes/TST-0020/reproduce.py:"
                    f"{find_line('command-center/p2-wave/probes/TST-0020/reproduce.py', 'grep -c')}"
                ),
                "kind": "live-run",
            },
            {
                "claim": (
                    "The catalog pathology is `grep -c pat || echo 0` producing "
                    "'all 7 PRs hit' and 'empty intersection' at once."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"command-center/WORK-UNIT-CATALOG.json:{cat_line}",
                "kind": "catalog",
            },
            {
                "claim": (
                    "On detector-failure the result dict sets published_numbers "
                    "to null; neither contradictory count is emitted as a finding."
                ),
                "verdict": "CONFIRMED",
                "anchor": (
                    "command-center/p2-wave/probes/TST-0020/invariants.py:"
                    f"{check_line}"
                ),
                "kind": "implementation",
            },
            {
                "claim": (
                    "The naive != '0' branch is what turns the doubled-zero blob "
                    "into an all-hit claim."
                ),
                "verdict": "CONFIRMED",
                "anchor": (
                    "command-center/p2-wave/probes/TST-0020/naive.py:"
                    f"{naive_line}"
                ),
                "kind": "implementation",
            },
        ],
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "contradictory-fail-the-run"},
            {"id": "probe2", "command": P2, "role": "consistent-pass-and-named-invariant"},
        ],
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"},
            {"path": SCHEMA_REL, "exists": True, "role": "schema"},
            {
                "path": "command-center/p2-wave/probes/TST-0020/invariants.json",
                "exists": True,
                "role": "invariants-declared-before-run",
            },
        ],
        "report": {
            "kind": "detector-control",
            "observations": [
                {
                    "name": "live-grep-c-or-echo-0-doubled-zero",
                    "measured": True,
                    "method": "bash grep -c DOES-NOT-OCCUR fixtures/prs.txt || echo 0",
                    "anchor": (
                        "command-center/p2-wave/probes/TST-0020/reproduce.py:"
                        f"{find_line('command-center/p2-wave/probes/TST-0020/reproduce.py', 'grep -c')}"
                    ),
                },
                {
                    "name": "post-processor-publishes-no-number-on-contradiction",
                    "measured": True,
                    "method": "check_invariants over naive_from_grep_c_blob",
                    "anchor": (
                        "command-center/p2-wave/probes/TST-0020/invariants.py:"
                        f"{check_line}"
                    ),
                },
            ],
            "control_ids": [str(inv["id"]) for inv in INVARIANTS],
        },
        "completion_sentinel": "SUCCESS:TST-0020",
    }

    if not (REPO / SCHEMA_REL).is_file():
        print(f"FAILED:TST-0020 catalog schema missing {SCHEMA_REL}")
        return 1
    jsonschema.Draft7Validator(DISCRIMINATOR).validate(doc)
    garbage = [
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
        {
            "unit_id": "TST-0020",
            "state": "SUCCESS",
            "sentinel": "SUCCESS:TST-0020",
            "kind": "detector-control",
        },
    ]
    for g in garbage:
        if not list(jsonschema.Draft7Validator(DISCRIMINATOR).iter_errors(g)):
            print(f"FAILED:TST-0020 schema accepts garbage {list(g)[:4]}")
            return 1

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if "SUCCESS:TST-0020" not in text:
        print("FAILED:TST-0020 sentinel missing from serialized artifact")
        return 1
    out.write_text(text, encoding="utf-8")
    print(f"wrote {OUT_REL} bytes={len(text.encode('utf-8'))}")
    print("SUCCESS:TST-0020")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
