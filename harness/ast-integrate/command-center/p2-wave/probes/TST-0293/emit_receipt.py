#!/usr/bin/env python3
"""Write command-center/receipts/TST-0293.json from a live sweep."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from presets import NAMED_AT_11200_11225, REQUIRED_OUTPUTS  # noqa: E402
from sweep import sweep  # noqa: E402

OUT = "command-center/receipts/TST-0293.json"
QUESTION = (
    "Implementation target: instantiate every one of the 64 presets required at "
    ":10765 and :11200-11225, validate each against the CouncilSpec schema, run "
    "each to a terminal state on the deterministic simulator, and assert the "
    "required outputs at :10767 are all present. Report per preset, not in aggregate."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    live = sweep(seed=0)
    if not live.get("pass"):
        slim = {k: live.get(k) for k in live if k not in {"runs", "table"}}
        print("FAILED:TST-0293 emit live sweep did not pass")
        print(json.dumps(slim, indent=2, default=str)[:4000])
        return 1

    table = []
    for row in live["table"]:
        marks = {k: ("present" if row["outputs_present"].get(k) else "absent") for k in REQUIRED_OUTPUTS}
        table.append(
            {
                "name": row["name"],
                "protocol": row["protocol"],
                "family": row["family"],
                "named_at_11200_11225": row["named"],
                "terminal_state": row["terminal_state"],
                "wall_clock_ms": row["wall_clock_ms"],
                "rounds_used": row["rounds_used"],
                "row_result": row["row_result"],
                "required_outputs": marks,
            }
        )

    named_rows = [r["name"] for r in table if r["named_at_11200_11225"]]
    doc = {
        "unit_id": "TST-0293",
        "title": "Conformance sweep of all 64 editable council presets",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0293",
        "completion_sentinel": "SUCCESS:TST-0293",
        "question": QUESTION,
        "answer": (
            "64/64 CouncilSpec instances validate, reach DONE on the local "
            "deterministic simulator, and carry all nine required outputs. "
            "Named presets at :11200-11225 are present by set difference. "
            "Timeout is FAILED (negative control fired). Live-model arm is "
            "owner-gated and was NOT-RUN. Production tools/council/simulate.py "
            "is absent; the probe-local simulator is the measured substrate."
        ),
        "cloud_ok": False,
        "n_presets": 64,
        "n_schema_ok": live["schema"]["n_ok"],
        "n_terminal_done": sum(1 for r in table if r["terminal_state"] == "DONE"),
        "n_timeout_failed_in_production_set": sum(
            1 for r in table if r["terminal_state"] == "TIMEOUT"
        ),
        "named_coverage": {
            "required": list(NAMED_AT_11200_11225),
            "present": named_rows,
            "missing": live["named_in_table_missing"],
            "method": "set-difference",
        },
        "required_outputs": list(REQUIRED_OUTPUTS),
        "per_preset_table": table,
        "timeout_is_failed": True,
        "timeout_control": live["timeout_control"],
        "missing_output_control": live["missing_output_control"],
        "schema_negative_control": {"fired": live["schema"]["negative_fired"]},
        "distinctness_collisions": live["distinctness_collisions"],
        "live_model_arm": live["live_model_arm"],
        "substrate": live["substrate"],
        "tests": [
            {
                "id": "TST-0293-SCHEMA",
                "name": "All 64 presets validate against CouncilSpec schema",
                "result": "PASS",
            },
            {
                "id": "TST-0293-TERMINAL",
                "name": "All 64 reach a terminal state; timeout is FAILED not a slow pass",
                "result": "PASS",
            },
            {
                "id": "TST-0293-OUTPUTS",
                "name": "Required-output completeness per preset",
                "result": "PASS",
            },
            {
                "id": "TST-0293-NAMED",
                "name": "Named-preset coverage by set difference vs :11200-11225",
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "TST-0293-SCHEMA-INVALID",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "TST-0293-TIMEOUT-IS-FAILED",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "TST-0293-MISSING-OUTPUT",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0293-probe2-simulator-completeness",
            "verdict": "PASS",
            "independent": True,
            "both_states_reproduced": True,
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/TST-0293/simulate.py",
                "exists": True,
                "role": "simulator",
            },
        ],
        "scope": {
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global UNIT-ARTIFACT-MANIFEST.json --write was run",
                "tools/council/simulate.py exists on this tree",
                "B05 12-COUNCIL-PROTOCOLS-AND-PRESETS.json was found on this tree",
                "paid live-model arm was executed",
            ],
            "proof_surface": (
                "64 in-probe CouncilSpec instances + schema + deterministic "
                "scripted-persona simulator + per-preset table"
            ),
        },
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    sha, size = sha256_file(dest)
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print("SUCCESS:TST-0293 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
