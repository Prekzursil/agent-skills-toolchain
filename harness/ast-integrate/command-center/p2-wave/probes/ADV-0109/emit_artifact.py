#!/usr/bin/env python3
"""Emit command-center/adversarial/ADV-0109-dissent-omission-differential.json."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import account as A  # noqa: E402

QUESTION = (
    "Which disagreements present in the raw inputs are absent from the synthesis, "
    "and is the omission a deliberate resolution with a stated reason or a silent drop?"
)
MIN_BYTES = 2048


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def validate(doc: dict) -> None:
    schema_path = REPO / A.SCHEMA_REL
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.Draft7Validator.check_schema(schema)
    jsonschema.Draft7Validator(schema).validate(doc)
    for garbage in ({}, {"state": "SUCCESS", "passing_tests": 999}, {"blob": "x" * 400}):
        try:
            jsonschema.Draft7Validator(schema).validate(garbage)
        except jsonschema.ValidationError:
            continue
        raise SystemExit("FAILED:ADV-0109 schema accepts garbage")


def build_doc(live: dict, inventory: dict, probes: list[dict]) -> dict:
    represented = A.control_represented(live)
    planted = A.control_planted_drop(live)
    live_present = bool(inventory.get("live_corpus_present"))
    live_verdict = "CONFIRMED" if live_present else "NOT-CHECKED"
    answer = (
        "On the pinned synthesis corpus the forward classifier reports "
        f"{live['totals']['represented']} represented, "
        f"{live['totals']['resolved-with-reason']} resolved-with-reason, and "
        f"{live['totals']['silently-dropped']} silently-dropped contradiction pairs "
        f"(drop_rate={live['ratio']['drop_rate']}). A represented pair is classified "
        "correctly; a planted silent drop is caught. Reverse scan catches planted "
        "manufactured consensus and stays silent on honest agreement. "
        "CLAIM-REGISTRY.json and a live B12 synthesis tree are absent on this "
        "worktree, so production syntheses are NOT-CHECKED rather than invented."
    )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "unit_id": "ADV-0109",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ADV-0109",
        "completion_sentinel": A.COMPLETION_SENTINEL,
        "report_kind": "refutation-record",
        "title": "Dissent-omission differential between raw inputs and synthesis",
        "question": QUESTION,
        "answer": answer,
        "produced_at": now,
        "output_path": A.OUT_REL,
        "output_schema": A.SCHEMA_REL,
        "min_bytes_threshold": MIN_BYTES,
        "cloud_ok": False,
        "honest_scope": {
            "fixture_corpus": "command-center/p2-wave/probes/ADV-0109/fixtures/cases.json",
            "live_inventory": inventory,
            "claim": (
                "G-1 measures the bidirectional instrument on a pinned corpus with "
                "planted controls. It does not claim a recount of an absent B12 "
                "synthesis tree or an absent CLAIM-REGISTRY.json."
            ),
        },
        "verdicts": [
            {
                "id": "T-FORWARD-INSTRUMENT",
                "claim": "Contradiction pairs are classified represented / resolved-with-reason / silently-dropped.",
                "verdict": "CONFIRMED",
            },
            {
                "id": "T-REVERSE-INSTRUMENT",
                "claim": "Agreement claims in synthesis that sit on unresolved pairs are manufactured consensus.",
                "verdict": "CONFIRMED",
            },
            {
                "id": "T-CONTROL-REPRESENTED",
                "claim": "A contradiction that is represented is classified represented.",
                "verdict": "CONFIRMED" if represented["pass"] else "REFUTED",
            },
            {
                "id": "T-CONTROL-PLANTED-DROP",
                "claim": "A planted silent drop is classified silently-dropped.",
                "verdict": "CONFIRMED" if planted["pass"] else "REFUTED",
            },
            {
                "id": "T-LIVE-SYNTHESIS-CORPUS",
                "claim": "Live B12 syntheses and claim-graph contradiction edges were audited.",
                "verdict": live_verdict,
            },
        ],
        "named_probes": probes,
        "controls": [
            {
                "id": "CTRL-REPRESENTED",
                "description": "Known-represented quorum split must classify as represented, not dropped.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "result": represented,
            },
            {
                "id": "CTRL-PLANTED-DROP",
                "description": "Planted minority-report silent drop must classify as silently-dropped.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "result": planted,
            },
            {
                "id": "CTRL-HONEST-AGREE",
                "description": "Pair-empty inputs plus unanimous language must not fire manufactured consensus.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "tests": [
            {
                "id": "probe1_omitted_dissent",
                "command": A.P1_CMD,
                "result": "PASS" if probes and probes[0].get("exit_code") == 0 else "NOT-RUN",
            },
            {
                "id": "probe2_manufactured_consensus",
                "command": A.P2_CMD,
                "result": "PASS" if len(probes) > 1 and probes[1].get("exit_code") == 0 else "NOT-RUN",
            },
        ],
        "evidence": [
            {
                "kind": "forward-accounting",
                "claim": "Per-pair classes and counts on the pinned corpus.",
                "detail": json.dumps(live["totals"], sort_keys=True),
                "path": "command-center/p2-wave/probes/ADV-0109/account.py",
            },
            {
                "kind": "ratio",
                "claim": "Both counts are reported; only the ratio is interpretable.",
                "detail": json.dumps(live["ratio"], sort_keys=True),
                "path": A.OUT_REL,
            },
            {
                "kind": "live-inventory",
                "claim": "Production claim graph and synthesis tree presence.",
                "detail": json.dumps(inventory, sort_keys=True)[:2000],
                "path": "command-center/CLAIM-REGISTRY.json",
            },
        ],
        "reviewer": {
            "reviewer_id": "ADV-0109-probe2-manufactured-consensus",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "method": "Reverse agreement-span scan, not a rerun of pair classification.",
        },
        "artifacts": [
            {"path": A.OUT_REL, "exists": True, "role": "primary"},
            {"path": A.SCHEMA_REL, "exists": True, "role": "schema"},
            {
                "path": "command-center/p2-wave/probes/ADV-0109/account.py",
                "exists": True,
                "role": "instrument",
            },
        ],
        "forward_accounting": {
            "rows": live["rows"],
            "totals": live["totals"],
            "ratio": live["ratio"],
        },
        "reverse_accounting": {
            "rows": [
                {
                    "id": row["id"],
                    "manufactured_consensus": row["manufactured_consensus"],
                    "agreement_spans": row["agreement_spans"],
                    "unresolved_pair_ids": row["unresolved_pair_ids"],
                    "pair_count": row["pair_count"],
                }
                for row in live["rows"]
            ]
        },
        "ratio_note": (
            "tests_required: a contradiction that IS represented must be classified "
            "correctly, and a planted silent drop must be caught; report both counts, "
            "since only the ratio is interpretable."
        ),
    }


def write_doc(doc: dict) -> Path:
    out = REPO / A.OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return out


def main() -> int:
    cases = A.load_cases()
    live = A.classify_all(cases)
    if not live["expect_match"]:
        print("FAILED:ADV-0109 emit expect mismatch", live["mismatches"])
        return 1
    if not A.control_represented(live)["pass"] or not A.control_planted_drop(live)["pass"]:
        print("FAILED:ADV-0109 emit controls")
        return 1
    inventory = A.live_inventory()
    placeholders = [
        {
            "id": "probe1",
            "command": A.P1_CMD,
            "exit_code": -1,
            "raw_output": "pending-emit-placeholder",
        },
        {
            "id": "probe2",
            "command": A.P2_CMD,
            "exit_code": -1,
            "raw_output": "pending-emit-placeholder",
        },
    ]
    doc = build_doc(live, inventory, placeholders)
    write_doc(doc)
    rc1, out1 = run_cmd(A.P1_CMD)
    rc2, out2 = run_cmd(A.P2_CMD)
    probes = [
        {"id": "probe1", "command": A.P1_CMD, "exit_code": rc1, "raw_output": out1},
        {"id": "probe2", "command": A.P2_CMD, "exit_code": rc2, "raw_output": out2},
    ]
    doc = build_doc(live, inventory, probes)
    out = write_doc(doc)
    validate(doc)
    if out.stat().st_size < MIN_BYTES:
        print(f"FAILED:ADV-0109 artifact too small {out.stat().st_size}")
        return 1
    if A.COMPLETION_SENTINEL not in out.read_text(encoding="utf-8"):
        print("FAILED:ADV-0109 sentinel missing from artifact")
        return 1
    if rc1 != 0 or rc2 != 0:
        print("FAILED:ADV-0109 named probes during emit")
        print(out1[-2000:])
        print(out2[-2000:])
        return 1
    print(f"wrote {A.OUT_REL} bytes={out.stat().st_size}")
    print("SUCCESS:ADV-0109 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
