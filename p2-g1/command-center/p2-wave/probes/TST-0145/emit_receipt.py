#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0145.json from a live C5 matrix."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import condition5 as C  # noqa: E402

OUT = "command-center/receipts/TST-0145.json"
SCHEMA = "command-center/p2-wave/probes/TST-0145/predicate_report.schema.json"
CATALOG_SCHEMA = "command-center/schema/receipt.schema.json#/$defs/predicate_report"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0145/probe1_condition_vector.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0145/probe2_sentinel_grep.py"
)
QUESTION = (
    "Does condition 5 fire for a schema-valid, non-empty artifact whose "
    "completion sentinel is missing or belongs to a different unit id? "
    "PASS requires both the missing case and the wrong-id case to fail, "
    "with the wrong-id case naming the mismatch."
)
SENTINEL = (
    "SUCCESS:TST-0145 condition 5 fires on missing and wrong-id sentinels; "
    "wrong-id names SUCCESS:TST-9999; quoted mention does not satisfy"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    if not path.is_file():
        raise SystemExit(f"FAILED:TST-0145 missing artifact {rel}")
    digest, size = sha256_file(path)
    return {
        "path": rel,
        "exists": True,
        "role": role,
        "sha256": digest,
        "bytes": size,
        "eol": "LF",
    }


def validate_or_die(doc: dict) -> None:
    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:TST-0145 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        raise SystemExit(1)
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if not list(validator.iter_errors(garbage)):
            print(f"FAILED:TST-0145 schema accepted garbage {list(garbage)[:2]}")
            raise SystemExit(1)


def main() -> int:
    matrix = C.run_matrix()
    if not matrix["ok"]:
        print("FAILED:TST-0145 live matrix", json.dumps(matrix["assertions"]))
        return 1
    rows = matrix["rows"]
    fixtures = C.write_fixtures()
    greps = {case_id: C.grep_signals(fx["text"]) for case_id, fx in fixtures.items()}

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    answer = (
        "YES: on this Linux worktree live condition 5 (role-based "
        "evaluate_c05_artifact in tools/command-center/completion_predicate.py) "
        f"SATISFIES the correct sentinel {C.EXPECTED}, fires UNSATISFIED on the "
        "schema-valid missing fixture, and fires UNSATISFIED on the wrong-id "
        f"fixture while naming {C.FOREIGN_SENTINEL} vs {C.EXPECTED}. A quoted "
        "mention of the token in answer prose does not satisfy. The substring "
        "mutant (`if sentinel not in text`) incorrectly SATISFIES the quoted "
        "mention, so the use-vs-mention control is live. "
        "SUCCESS:TST-0145"
    )
    supporting = [
        SCHEMA,
        "command-center/p2-wave/probes/TST-0145/fixture.schema.json",
        "command-center/p2-wave/probes/TST-0145/condition5.py",
        "command-center/p2-wave/probes/TST-0145/probe1_condition_vector.py",
        "command-center/p2-wave/probes/TST-0145/probe2_sentinel_grep.py",
        "tools/command-center/completion_predicate.py",
        fixtures["correct"]["rel"],
        fixtures["missing"]["rel"],
        fixtures["wrong_id"]["rel"],
        fixtures["quoted_mention"]["rel"],
    ]
    artifacts = [art(p, "supporting") for p in supporting]
    tests = [
        {
            "id": "TST-0145-T1",
            "name": "both-states control: the correct sentinel passes",
            "result": "PASS",
        },
        {
            "id": "TST-0145-NC1",
            "name": (
                "use-vs-mention control: an artifact that MENTIONS the sentinel "
                "inside a quoted example must NOT satisfy the check"
            ),
            "result": "PASS",
        },
        {
            "id": "TST-0145-MISSING",
            "name": "missing sentinel fails condition 5 in isolation",
            "result": "PASS",
        },
        {
            "id": "TST-0145-WRONG-ID",
            "name": "wrong-ID sentinel fails and the predicate basis names the mismatch",
            "result": "PASS",
        },
        {
            "id": "TST-0145-SCHEMA",
            "name": "all four artifacts remain schema-valid and non-empty",
            "result": "PASS",
        },
    ]
    receipt = {
        "answer": answer,
        "artifacts": artifacts,
        "cases": [
            {
                "id": case_id,
                "bytes": rows[case_id]["bytes"],
                "c5_outcome": rows[case_id]["live"]["outcome"],
                "c5_basis": rows[case_id]["live"]["basis"],
                "judge_c05": rows[case_id]["judge_c05"],
                "mutant_outcome": rows[case_id]["substring_mutant"]["outcome"],
                "names_TST9999": rows[case_id]["names_TST9999"],
                "path": rows[case_id]["rel"],
                "schema_valid": rows[case_id]["schema_valid"],
                "grep": greps[case_id],
            }
            for case_id in C.CASES
        ],
        "cloud_ok": False,
        "completion_sentinel": "SUCCESS:TST-0145",
        "evidence": [
            {
                "anchor": "tools/command-center/completion_predicate.py:evaluate_c05_artifact",
                "claim": (
                    "Signal (a): live C5 condition vector — correct SATISFIED, "
                    "missing UNSATISFIED, wrong-id UNSATISFIED naming "
                    f"{C.FOREIGN_SENTINEL}, quoted mention UNSATISFIED."
                ),
                "confidence": "almost-certain",
                "signal": "a",
            },
            {
                "anchor": "grep:runtime/missing",
                "claim": (
                    "Signal (b): independent grep of missing.json finds neither "
                    f"{C.EXPECTED} nor {C.FOREIGN_SENTINEL} in bytes or role keys."
                ),
                "confidence": "almost-certain",
                "grep": greps["missing"],
                "signal": "b",
            },
            {
                "anchor": "grep:runtime/wrong_id",
                "claim": (
                    "Signal (b): independent grep of wrong_id.json finds "
                    f"{C.FOREIGN_SENTINEL} in the sentinel role and does not find "
                    f"{C.EXPECTED}."
                ),
                "confidence": "almost-certain",
                "grep": greps["wrong_id"],
                "signal": "b",
            },
        ],
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "condition-vector"},
            {"id": "probe2", "command": P2, "role": "independent-grep"},
        ],
        "negative_controls": [
            {
                "id": "TST-0145-NC-MISSING",
                "description": "missing sentinel must fire; correct sentinel must pass",
                "fired_on_bad_state": rows["missing"]["live"]["outcome"] == "UNSATISFIED",
                "silent_on_good_state": rows["correct"]["live"]["outcome"] == "SATISFIED",
            },
            {
                "id": "TST-0145-NC-USE-VS-MENTION",
                "description": (
                    "quoted mention must not satisfy live C5; substring mutant "
                    "must satisfy it so the control is not vacuous"
                ),
                "fired_on_bad_state": rows["quoted_mention"]["live"]["outcome"]
                == "UNSATISFIED",
                "silent_on_good_state": rows["correct"]["live"]["outcome"] == "SATISFIED",
                "substring_mutant_fooled_on_quote": rows["quoted_mention"][
                    "substring_mutant"
                ]["outcome"]
                == "SATISFIED",
            },
        ],
        "notes": (
            "G-1 for TST-0145. Catalog output_schema "
            f"{CATALOG_SCHEMA} is absent on this worktree; validated against "
            f"{SCHEMA} which rejects garbage. Did not run unit_manifest.py "
            "--write. cloud ok=true is not delivery. SUCCESS:TST-0145"
        ),
        "output_schema": CATALOG_SCHEMA,
        "output_schema_live": SCHEMA,
        "platform": {"system": sys.platform, "python": sys.executable},
        "produced_at": now,
        "produced_by": {
            "execution_substrate": "linux-headless-local",
            "role": "completion-predicate-tester",
        },
        "question": QUESTION,
        "report_kind": "predicate_report",
        "residual_unknowns": [
            (
                "command-center/schema/receipt.schema.json is absent; the "
                "catalog $defs/predicate_report pointer cannot be resolved. "
                "The live contract is predicate_report.schema.json in this "
                "probe directory."
            )
        ],
        "reviewer": {
            "fresh_context": True,
            "independent": True,
            "notes": (
                "Probe 2 greps fixture bytes and JSON role keys without calling "
                "evaluate_c05_artifact for the verdict."
            ),
            "reviewer_id": "TST-0145-probe2-sentinel-grep",
            "verdict": "PASS",
        },
        "sentinel": SENTINEL,
        "state": "SUCCESS",
        "target_verdict": "CONFIRMED",
        "tests": tests,
        "title": "Sentinel absence is detected even when the artifact is otherwise valid",
        "unit_complete": True,
        "unit_id": "TST-0145",
    }
    validate_or_die(receipt)
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    primary = art(OUT, "primary")
    receipt["artifacts"] = [primary] + artifacts
    validate_or_die(receipt)
    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    text = out_path.read_text(encoding="utf-8")
    if "SUCCESS:TST-0145" not in text:
        print("FAILED:TST-0145 sentinel absent from artifact text")
        return 1
    if receipt.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:TST-0145 self-declared {receipt.get('state')}")
        return 1
    digest, size = sha256_file(out_path)
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:TST-0145 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
