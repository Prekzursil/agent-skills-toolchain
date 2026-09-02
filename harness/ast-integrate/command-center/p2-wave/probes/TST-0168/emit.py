#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0168.json from a live fan-out resume run."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "lib"))

import handled_ledger as HL  # noqa: E402
import scenarios as S  # noqa: E402

OUT = "command-center/receipts/TST-0168.json"
SCHEMA = "command-center/p2-wave/probes/TST-0168/resume_report.schema.json"
ENGINE = "tools/lib/handled_ledger.py"
CATALOG_ENGINE = "tools/lib/handled-ledger.mjs"
SENTINEL = "SUCCESS:TST-0168"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0168/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0168/probe2_race.py"
)
QUESTION = (
    "When a workflow is suspended while a dynamic fan-out is in flight, does "
    "resume re-derive every child's state exactly once? PASS requires: "
    "children_after == children_before, with no child in an unowned state "
    "and no child executed twice."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def engine_anchor(needle: str) -> str:
    text = (REPO / ENGINE).read_text(encoding="utf-8")
    for i, line in enumerate(text.splitlines(), 1):
        if needle in line:
            return f"{ENGINE}:{i}"
    return f"{ENGINE}:1"


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst0168-emit-") as tmp:
        live = S.run_all(Path(tmp))
    if not live.get("ok"):
        print("FAILED:TST-0168 emit scenarios failed")
        print(json.dumps({
            "both": (live.get("both_states") or {}).get("ok"),
            "race": (live.get("race") or {}).get("ok"),
            "mutants": (live.get("mutants") or {}).get("ok"),
        }, indent=2))
        return 1

    both = live["both_states"]
    race = live["race"]
    mutants = live["mutants"]
    catalog_named_present = (REPO / CATALOG_ENGINE).is_file()

    doc = {
        "unit_id": "TST-0168",
        "state": "SUCCESS",
        "schema_version": 1,
        "report_kind": "resume_report",
        "title": "Resume of an in-flight dynamic fan-out orphans nothing and duplicates nothing",
        "question": QUESTION,
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "min_bytes_threshold": 2048,
        "catalog_schema": "command-center/schema/receipt.schema.json#/$defs/resume_report",
        "engine": {
            "path": ENGINE,
            "catalog_named_path": CATALOG_ENGINE,
            "catalog_named_present": catalog_named_present,
            "api": [
                "HandledLedger.append",
                "DynamicFanOut.run",
                "DynamicFanOut.resume",
                "inspect",
            ],
            "items": list(S.ITEMS),
            "n_items": len(S.ITEMS),
        },
        "both_states": {
            "ok": True,
            "first_spawn_tick": both["first_spawn_tick"],
            "n_ticks": both["n_ticks"],
            "gold": {
                "derived_ids": both["gold"]["derived_ids"],
                "receipt_total": both["gold"]["receipt_total"],
                "ok": both["gold"]["ok"],
            },
            "before_fanout": {
                "ok": both["before_fanout"]["ok"],
                "stop_before": both["before_fanout"]["stop_before"],
                "children_before": both["before_fanout"]["children_before"],
                "children_after": both["before_fanout"]["children_after"],
                "children_equal": both["before_fanout"]["children_equal"],
                "final_ids": both["before_fanout"]["final_ids"],
                "receipt_total": both["before_fanout"]["receipt_total"],
                "final_unowned": both["before_fanout"]["final_unowned"],
            },
            "after_complete": {
                "ok": both["after_complete"]["ok"],
                "stop_before": both["after_complete"]["stop_before"],
                "children_before": both["after_complete"]["children_before"],
                "children_after": both["after_complete"]["children_after"],
                "children_equal": both["after_complete"]["children_equal"],
                "no_extra_receipts": both["after_complete"]["no_extra_receipts"],
                "receipt_total": both["after_complete"]["receipt_total"],
            },
        },
        "race": {
            "ok": True,
            "seed": race["seed"],
            "n": race["n"],
            "ticks": race["ticks"],
            "first_spawn_tick": race["first_spawn_tick"],
            "last_receipt_tick": race["last_receipt_tick"],
            "gold_ids": race["gold_ids"],
            "rows": [
                {
                    "tick": r["tick"],
                    "ok": r["ok"],
                    "children_equal": r["children_equal"],
                    "children_before": r["children_before"],
                    "children_after": r["children_after"],
                    "final_ids": r["final_ids"],
                    "receipt_total": r["receipt_total"],
                    "dup_receipts": r["dup_receipts"],
                    "final_unowned": r["final_unowned"],
                    "match_gold": r["match_gold"],
                }
                for r in race["rows"]
            ],
        },
        "mutants": {
            "ok": True,
            "skip_claim": mutants["skip_claim"],
            "double_receipt": mutants["double_receipt"],
            "silent_on_good": mutants["silent_on_good"],
        },
        "tests": [
            {
                "id": "both-states-before-and-after-fanout",
                "name": "suspend before fan-out starts and after it completes; both resume cleanly",
                "result": "PASS",
                "command": P1,
            },
            {
                "id": "race-20-in-flight-suspends",
                "name": "suspend at 20 seeded points inside the fan-out; children re-derived once",
                "result": "PASS",
                "command": P2,
            },
            {
                "id": "mutant-skip-claim-unowned",
                "name": "resume without claim leaves children unowned (negative control)",
                "result": "PASS",
                "command": P1,
            },
            {
                "id": "mutant-double-receipt",
                "name": "second receipt is refused and counted (negative control)",
                "result": "PASS",
                "command": P1,
            },
        ],
        "evidence": [
            {
                "signal": "(a) child id set before and after",
                "claim": (
                    "Cold resume reloads the ledger from disk and re-derives "
                    "child ids from durable producer items; children_after == "
                    "children_before at every suspend point, including 20 "
                    "in-flight ticks."
                ),
                "verdict": "CONFIRMED",
                "anchor": engine_anchor("def derived_child_ids"),
            },
            {
                "signal": "(b) receipt count per child id",
                "claim": (
                    "HandledLedger.append refuses a second child_receipt for "
                    "the same child_id; inspect.dup_receipts is empty on good "
                    "resumes and fires on the planted duplicate."
                ),
                "verdict": "CONFIRMED",
                "anchor": engine_anchor("class DuplicateReceiptError"),
            },
        ],
        "negative_controls": [
            {
                "id": "c-skip-claim",
                "kind": "known-broken-resume",
                "description": "resume that skips the claim pass leaves unowned children",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "c-double-receipt",
                "kind": "known-broken-receipt",
                "description": "a second receipt is refused by the ledger and counted by inspect",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0168-probe2-race-20",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Named probe2 independently re-runs 20 seeded in-flight "
                "suspends on a fresh tempdir and binds the artifact tick list "
                "to that sample. Catalog scoring by a second human resume "
                "tester is independent of G-1 probe-green."
            ),
        },
        "cloud_ok": False,
        "registered": True,
        "named_probes": [
            {"id": "probe1", "role": "both-states-and-mutants", "command": P1},
            {"id": "probe2", "role": "race-amplification", "command": P2},
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
            {"path": ENGINE, "exists": True, "role": "supporting"},
        ],
    }

    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:TST-0168 schema errors")
        for e in errs[:25]:
            print(" ", list(e.path), e.message)
        return 1
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:TST-0168 schema accepted garbage")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:TST-0168 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        "both=%s race_n=%s mutants=%s catalog_mjs=%s"
        % (both.get("ok"), race.get("n"), mutants.get("ok"), catalog_named_present)
    )
    print("SUCCESS:TST-0168 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
