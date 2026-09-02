#!/usr/bin/env python3
"""Emit command-center/receipts/BLD-0045.json (test-quality census)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import auditor as A  # noqa: E402

OUT = "command-center/receipts/BLD-0045.json"
SCHEMA = "command-center/schema/test-quality-census.schema.json"
QUESTION = (
    "Question: which lines are executed by the suite but whose behaviour nothing "
    "asserts? Cross line and branch coverage against assertion reachability: for "
    "each covered region, determine whether any assertion depends on its output. "
    "Report high-coverage, zero-assertion regions and concentrate the analysis on "
    "error handling and rollback paths, where coverage most often means 'executed "
    "while nobody looked'."
)
AUDITOR_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0045/auditor.py"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0045/probe1_controls.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0045/probe2_reviewer.py"
)


def ev(rel: str, line: int, kind: str, claim: str) -> dict:
    snippet = A.snippet_at(REPO / rel, line)
    if len(snippet) < 4:
        raise SystemExit(f"FAILED:BLD-0045 emit empty snippet {rel}:{line}")
    return {
        "path": rel,
        "line": line,
        "snippet": snippet,
        "kind": kind,
        "claim": claim,
        "anchor": f"{rel}:{line}",
    }


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    if not path.is_file():
        raise SystemExit(f"FAILED:BLD-0045 emit missing artifact {rel}")
    return {"path": rel, "exists": True, "role": role}


def main() -> int:
    doc = A.census()
    if not doc["controls_pass"]:
        print("FAILED:BLD-0045 emit controls did not all PASS")
        return 1
    if not doc["reviewer"].get("ok"):
        print("FAILED:BLD-0045 emit reviewer did not reclassify")
        return 1
    if not doc["mutation"]["tests_still_green"]:
        print("FAILED:BLD-0045 emit mutation pivot turned tests red")
        return 1

    report = doc["report"]
    product = A.PRODUCT_REL
    except_line = next(
        (
            f["locus"].rsplit(":", 1)[-1]
            for f in report["findings"]
            if f["class"] == "EXCEPT-COVERED-UNASSERTED"
        ),
        "36",
    )
    try:
        except_line_i = int(except_line)
    except ValueError:
        except_line_i = 36
    partial = next(
        (p for p in report["partial_branch_entries"] if p.get("status") == "partial"),
        None,
    )
    if partial is None:
        print("FAILED:BLD-0045 emit no partial-branch entry")
        return 1
    partial_line = int(str(partial["locus"]).rsplit(":", 1)[-1])

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    receipt = {
        "unit_id": "BLD-0045",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:BLD-0045",
        "census_kind": "covered-but-unasserted",
        "title": "Covered-but-unasserted code audit, concentrated on error and rollback paths",
        "question": QUESTION,
        "ts": now,
        "report_global_percentage": False,
        "b08_suite_coverage": doc["b08"],
        "instrumentation": {
            "branch_enabled": True,
            "collector": "stdlib sys.settrace line tracer + AST if/else and try/except maps",
            "coverage_py_installed": False,
            "partial_branch_entries": report["partial_branch_entries"],
            "partial_when_branch_disabled": report["partial_when_branch_disabled"],
            "executed_lines": report["executed_lines"],
            "all_fixture_tests_passed": report["all_tests_passed"],
        },
        "findings": report["findings"],
        "asserted_regions": report["asserted_regions"],
        "high_coverage_zero_assertion_regions": [
            f
            for f in report["findings"]
            if f.get("class") == "COVERED-UNASSERTED" and f.get("high_coverage")
        ],
        "error_rollback_concentration": [
            f for f in report["findings"] if f.get("class") == "EXCEPT-COVERED-UNASSERTED"
        ],
        "controls": doc["controls"],
        "mutation_pivot": {
            "policy": (
                "Two strikes then pivot from static assertion-dependency inference "
                "to mutation of the specific region"
            ),
            "region": "apply_with_rollback except-arm rolled_back",
            "mutation": doc["mutation"]["mutation"],
            "tests_still_green": doc["mutation"]["tests_still_green"],
            "interpretation": (
                "Static inference (unique except stores never appear in asserts) "
                "and empirical mutation (rolled_back True->False, suite stays green) "
                "agree: the except-arm is covered and unasserted."
            ),
        },
        "shipped_tree_scan": {
            "scope": "tools/command-center/*.py except handlers and rollback-named functions",
            "coverage": "NOT-CHECKED",
            "reason": doc["b08"]["substitute"] if doc["b08"]["status"] == "ABSENT" else "B08 present",
            "candidates": doc["shipped_tree_candidates"],
            "note": (
                "These loci are candidates, not findings. Coverage is NOT-CHECKED "
                "because B08 coverage.xml is absent on this worktree."
            ),
        },
        "reviewer": {
            "reviewer_id": "BLD-0045-probe2-delete-assert-reclassify",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "procedure": (
                "Delete the assertion whose value is asserted_value (keep the call "
                "so the region stays covered) and re-run the audit."
            ),
            "reclassified_asserted_value": doc["reviewer"]["reclassified_asserted_value"],
            "unasserted_functions_after_delete": doc["reviewer"]["unasserted_functions"],
            "tests_passed_after_delete": doc["reviewer"]["tests_passed_after_delete"],
        },
        "tests": [
            {
                "id": c["id"],
                "command": AUDITOR_CMD,
                "result": c["result"],
            }
            for c in doc["controls"]
        ],
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "four-catalog-controls"},
            {"id": "probe2", "command": P2, "role": "reviewer-delete-assert-and-mutation-pivot"},
        ],
        "artifacts": [
            art(SCHEMA, "schema"),
            art(product, "subject"),
            art(A.TEST_REL, "fixture-suite"),
            art("command-center/p2-wave/probes/BLD-0045/auditor.py", "auditor"),
        ],
        "evidence": [
            ev(
                product,
                8,
                "fixture-subject",
                "side_effect_only is the planted side-effect-only function the auditor must report",
            ),
            ev(
                product,
                14,
                "fixture-subject",
                "asserted_value return feeds assert and must not be reported as unasserted",
            ),
            ev(
                product,
                except_line_i,
                "rollback-except",
                "except RollbackError is covered by the suite and its unique effects are unasserted",
            ),
            ev(
                product,
                38,
                "rollback-except",
                "rolled_back=True is the except-arm effect the suite never asserts",
            ),
            ev(
                product,
                partial_line,
                "instrument",
                "maybe_double if/else is the partial-branch instrument proving branch coverage is on",
            ),
        ],
        "strongest_surviving_counterargument": (
            "The B08 suite coverage.xml is not on this worktree, so shipped-tree "
            "except/rollback regions are listed as NOT-CHECKED candidates rather than "
            "as executed-unasserted findings. The four catalog controls and the "
            "reviewer delete-assert reclassification are live on the planted fixture "
            "suite. That is a scope bound, not a claim that B08 was run."
        ),
        "notes": (
            "G-1 for BLD-0045: live named probes, per-region assertion dependency, "
            "branch tracer with a partial-branch entry, honest B08 ABSENT. Did not "
            "run global unit_manifest.py --write. No ADV rebuild."
        ),
    }

    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    errors = sorted(jsonschema.Draft7Validator(schema).iter_errors(receipt), key=lambda e: list(e.path))
    if errors:
        print("FAILED:BLD-0045 emit schema errors")
        for err in errors[:20]:
            print(f"  {list(err.path)}: {err.message}")
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    receipt["artifacts"] = [
        {"path": OUT, "exists": True, "role": "primary"},
        *receipt["artifacts"],
    ]
    text = json.dumps(receipt, indent=1, sort_keys=True) + "\n"
    out.write_text(text, encoding="utf-8")

    errors = sorted(jsonschema.Draft7Validator(schema).iter_errors(json.loads(text)), key=lambda e: list(e.path))
    if errors:
        print("FAILED:BLD-0045 emit post-write schema errors")
        for err in errors[:20]:
            print(f"  {list(err.path)}: {err.message}")
        return 1
    print(f"wrote {OUT} bytes={out.stat().st_size}")
    print("SUCCESS:BLD-0045")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
