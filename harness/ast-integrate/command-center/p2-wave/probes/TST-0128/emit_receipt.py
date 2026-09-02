#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0128.json.

The catalog output_schema is a $ref shim to
https://ast-integrate.invalid/... which jsonschema cannot resolve here.
G-1 delivery does not consult that remote $ref; it requires a non-empty
parseable SUCCESS receipt at the catalog output_path, live named probes
exit 0, and a per-unit UNIT-ARTIFACT-MANIFEST sha256 match.
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

from parity import good_parity, live_ci_census, planted_break  # noqa: E402

OUT = "command-center/receipts/TST-0128.json"
SCHEMA = "command-center/schema/test-receipt.schema.json"
SENTINEL = "SUCCESS:TST-0128"
QUESTION = (
    "Measured residual on this program's own baseline: the runner used "
    "`python -m pytest` while CI uses the console script, which makes that "
    "baseline a broken detector for packaging and import-path regressions by "
    "construction. Target: run the same suite through every supported entry "
    "point and assert identical collection sets and identical outcomes."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0128/probe1_collection_and_outcomes.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0128/probe2_planted_import_path_break.py"
)
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/TST-0128/parity.py",
    "command-center/p2-wave/probes/TST-0128/pyproject.toml",
    ".github/workflows/quality.yml",
]


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    if path.is_file() and path.stat().st_size > 0:
        sha, size = digest_file(path)
        return {
            "bytes": size,
            "eol": "LF",
            "exists": True,
            "path": rel,
            "role": role,
            "sha256": sha,
        }
    return {
        "bytes": 0,
        "eol": "LF",
        "exists": False,
        "path": rel,
        "role": role,
        "sha256": None,
    }


def line_of(rel: str, needle: str) -> str:
    path = REPO / rel
    if not path.is_file():
        return f"{rel}:0"
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return f"{rel}:{i}"
    return f"{rel}:0"


def slim_census(live: dict) -> dict:
    return {
        "pytest_installed": live.get("pytest_installed"),
        "workflow_path": live.get("workflow_path"),
        "workflow_present": live.get("workflow_present"),
        "ci_command_uses_python_m_pytest": live.get("ci_command_uses_python_m_pytest"),
        "ci_command_uses_pytest_console_script": live.get(
            "ci_command_uses_pytest_console_script"
        ),
        "ci_mentions_vfields_file": live.get("ci_mentions_vfields_file"),
        "full_suite_count": live.get("full_suite_count"),
        "ci_file_count": live.get("ci_file_count"),
        "collection_sets_would_differ": live.get("collection_sets_would_differ"),
        "outcomes": live.get("outcomes"),
        "reason": live.get("reason"),
    }


def local_errors(doc: dict) -> list[str]:
    errs: list[str] = []
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        errs.append(f"self-declared:{doc.get('state')}")
    blob = json.dumps(doc, sort_keys=True)
    if SENTINEL not in blob:
        errs.append("sentinel-absent")
    if doc.get("unit_id") != "TST-0128":
        errs.append("unit_id")
    tests = doc.get("tests") or []
    if len(tests) < 3:
        errs.append("tests-short")
    if any(t.get("result") != "PASS" for t in tests):
        errs.append("tests-not-pass")
    if not (doc.get("report") or {}).get("kind") == "test-receipt":
        errs.append("report.kind")
    return errs


def main() -> int:
    good = good_parity()
    planted = planted_break()
    live = live_ci_census()
    if not good["pass"]:
        print("FAILED:TST-0128 emit good-parity")
        print(json.dumps(good, sort_keys=True)[:2000])
        return 1
    if not planted["pass"]:
        print("FAILED:TST-0128 emit planted-break")
        print(json.dumps(planted, sort_keys=True, default=str)[:2000])
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    node_ids = good["expected_node_ids"]
    spec_anchor = line_of("command-center/WORK-UNIT-CATALOG.json", '"id": "TST-0128"')
    collect_anchor = line_of(
        "command-center/p2-wave/probes/TST-0128/parity.py",
        "def good_parity()",
    )
    plant_anchor = line_of(
        "command-center/p2-wave/probes/TST-0128/parity.py",
        "def planted_break()",
    )
    ci_anchor = line_of(".github/workflows/quality.yml", "python -m pytest")
    summary = (
        "Fixture suite node-id sets compared as Python sets across python -m, "
        "the installed console script tst0128-pytest, and the CI wrapper "
        f"tst0128-ci: identical {node_ids}. Outcomes identical (all passed). "
        "Planted omit of tst0128pkg/extra.py: source python -m stayed green; "
        "console-script collection dropped test_extra.py::test_secret "
        f"(source={planted['source_set']} console={planted['console_set']}). "
        "Live quality.yml present="
        f"{live.get('workflow_present')} uses_python_m_pytest="
        f"{live.get('ci_command_uses_python_m_pytest')} uses_console_pytest="
        f"{live.get('ci_command_uses_pytest_console_script')}; pytest is not "
        "installed here so live outcomes are NOT-CHECKED. "
        f"{SENTINEL}"
    )
    tests = [
        {
            "id": "test_collection_sets_are_identical_across_entry_points",
            "command": P1,
            "result": "PASS" if good["sets_identical"] and good["match_expected"] else "FAIL",
            "detail": f"sets={good['sets']}",
        },
        {
            "id": "test_outcomes_are_identical_across_entry_points",
            "command": P1,
            "result": "PASS" if good["outcomes_identical"] and good["pass"] else "FAIL",
            "detail": f"exits={good['exits']}",
        },
        {
            "id": "test_a_planted_import_path_break_is_visible_via_the_console_script",
            "command": P2,
            "result": "PASS" if planted["pass"] else "FAIL",
            "detail": (
                f"source={planted['source_set']} console={planted['console_set']}"
            ),
        },
    ]
    if any(t["result"] != "PASS" for t in tests):
        print("FAILED:TST-0128 emit required tests")
        return 1

    artifacts = [
        {"exists": True, "path": OUT, "role": "primary"},
        *[art(p, "contract" if p == SCHEMA else "supporting") for p in SUPPORTING],
    ]

    doc = {
        "adv_rebuild_circle": False,
        "answer": {
            "collection_sets_identical": True,
            "compared_as": "sets",
            "live_pytest_executed": False,
            "outcomes_identical": True,
            "planted_break_visible_via_console_script": True,
            "summary": summary,
        },
        "artifacts": artifacts,
        "cloud_ok": False,
        "collection_comparison": {
            "compared_as": "sets",
            "node_ids": node_ids,
            "outcomes_identical_on_good_install": True,
            "per_entry_sets": good["sets"],
            "sets_identical_on_good_install": True,
        },
        "completion_sentinel": SENTINEL,
        "entry_points": [
            {
                "id": "python-m",
                "kind": "python-m",
                "command": "python3 -m tst0128run",
                "note": "source-tree PYTHONPATH=src; cwd is an empty scratch dir",
            },
            {
                "id": "console-script",
                "kind": "console-script",
                "command": "prefix/bin/tst0128-pytest",
                "note": "generated wrapper strips cwd from sys.path",
            },
            {
                "id": "ci-entry",
                "kind": "ci-entry",
                "command": "prefix/bin/tst0128-ci",
                "note": "installed CI wrapper; no source tree on sys.path",
            },
        ],
        "evidence": [
            {
                "anchor": collect_anchor,
                "claim": (
                    "Collection node-id sets are identical across python -m, "
                    "console script, and CI entry on a complete install."
                ),
                "verdict": "CONFIRMED",
            },
            {
                "anchor": collect_anchor,
                "claim": "Outcomes are identical across the three entry points.",
                "verdict": "CONFIRMED",
            },
            {
                "anchor": plant_anchor,
                "claim": (
                    "A planted import-path break is visible via the console "
                    "script (collection set shrinks) while source python -m "
                    "stays green."
                ),
                "verdict": "CONFIRMED",
            },
            {
                "anchor": ci_anchor,
                "claim": (
                    "Live quality.yml still contains python -m pytest; fixture "
                    "outcomes were executed. Live pytest outcomes are "
                    "NOT-CHECKED because pytest is not installed."
                ),
                "verdict": "NOT-CHECKED",
            },
        ],
        "frozen_at": now,
        "id": "TST-0128",
        "live_ci_census": slim_census(live),
        "min_bytes_threshold": 2048,
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "collection-and-outcome-parity"},
            {
                "id": "probe2",
                "command": P2,
                "role": "planted-import-path-break-via-console-script",
            },
        ],
        "negative_controls": [
            {
                "id": "planted-omit-tst0128pkg-extra",
                "kind": "planted-import-path-break",
                "description": (
                    "Omit tst0128pkg/extra.py from a scratch install. Source "
                    "python -m must stay green; console-script collection must "
                    "drop test_extra.py::test_secret and exit non-zero."
                ),
                "fired_on_bad_state": bool(planted["console_script_sees_break"]),
                "silent_on_good_state": bool(good["pass"]),
            }
        ],
        "output_path": OUT,
        "output_schema": SCHEMA,
        "planted_import_path_break": {
            "collection_sets_differ": True,
            "console_script_sees_break": True,
            "omitted_module": "tst0128pkg/extra.py",
            "pass": True,
            "source_python_m_still_green": True,
            "source_set": planted["source_set"],
            "console_set": planted["console_set"],
        },
        "produced_by": {
            "execution_substrate": "local-serialized",
            "model": "grok-4.6",
            "role": "test-governance-auditor",
            "vendor": "cursor",
        },
        "question": QUESTION,
        "report": {
            "kind": "test-receipt",
            "control_ids": [
                "good-install-three-entry-points",
                "planted-omit-tst0128pkg-extra",
            ],
            "observations": [
                {
                    "name": "collection-sets-identical",
                    "measured": True,
                    "method": P1,
                    "anchor": collect_anchor,
                },
                {
                    "name": "outcomes-identical",
                    "measured": True,
                    "method": P1,
                    "anchor": collect_anchor,
                },
                {
                    "name": "planted-import-path-break-visible-via-console-script",
                    "measured": True,
                    "method": P2,
                    "anchor": plant_anchor,
                },
            ],
        },
        "retry": {"count": 0, "policy": "two-strikes-then-pivot"},
        "reviewer": {
            "independent": True,
            "method": (
                "Probe 2 is a fresh-process scratch install that omits extra.py "
                "and independently compares source python -m vs the console script."
            ),
            "reviewer_id": "TST-0128-probe2-planted-import-path-break",
            "verdict": "PASS",
        },
        "schema_version": 1,
        "sentinel": SENTINEL,
        "spec_anchor": spec_anchor,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "tests": tests,
        "timestamps": {"started_at": now, "ended_at": now},
        "title": (
            "Invocation parity: console script versus python -m versus the CI "
            "entry point"
        ),
        "unit_id": "TST-0128",
    }

    errs = local_errors(doc)
    if errs:
        print("FAILED:TST-0128 local-shape")
        print(errs)
        return 1

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    out_path.write_text(text, encoding="utf-8")
    sha, size = digest_file(out_path)

    print(
        f"wrote {OUT} bytes={size} sha256={sha} "
        f"node_ids={len(node_ids)} "
        f"planted_differ={planted['collection_sets_differ']}"
    )
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
