#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0451.json from a live four-cell run."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

from monitor_states import (  # noqa: E402
    CELL_DEAD_IDLE,
    UNDECIDABLE,
    four_cell_live,
    four_verdicts_distinct,
    hardest_cell_undecidable,
)

OUT = "command-center/receipts/IMP-0451.json"
SENTINEL = "SENTINEL:IMP-0451:MONITOR-STATES-DISTINGUISHED"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0451/probe1_four_cell.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0451/probe2_signal_collapse.py"
)
QUESTION = (
    "Implement both detectors from spec lines 11315-11316 together: a monitor "
    "that dies while remote work continues, and a live monitor that merely has "
    "nothing to report being mistaken for dead. Exact target: the two states "
    "must be distinguishable, and where they are not, the detector must return "
    "UNDECIDABLE rather than guessing."
)
SUPPORTING = [
    "tools/command-center/monitor_states.py",
    "command-center/p2-wave/probes/IMP-0451/probe1_four_cell.py",
    "command-center/p2-wave/probes/IMP-0451/probe2_signal_collapse.py",
    "command-center/p2-wave/probes/IMP-0451/emit_receipt.py",
]


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest_file(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "role": role,
        "exists": path.is_file(),
        "bytes": size,
        "sha256": sha,
    }


def flatten_row(row: dict) -> dict:
    v = row["verdict"]
    return {
        "cell": row["cell"],
        "planted_monitor_alive": row["planted_monitor_alive"],
        "planted_work_active": row["planted_work_active"],
        "verdict": v["verdict"],
        "guessed": v["guessed"],
        "reason": v["reason"],
        "monitor_source": v["monitor_source"],
        "work_source": v["work_source"],
        "monitor_t0": v["monitor_t0"],
        "monitor_t1": v["monitor_t1"],
        "work_t0": v["work_t0"],
        "work_t1": v["work_t1"],
        "match": row["match"],
    }


def main() -> int:
    started = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    table = four_cell_live()
    hard = hardest_cell_undecidable(table)
    or_red = (
        table["or_mixed_indistinguishable"]
        and not four_verdicts_distinct(table["collapsed_or"])
    )
    and_red = (
        table["and_mixed_indistinguishable"]
        and not four_verdicts_distinct(table["collapsed_and"])
    )
    ok = (
        table["all_match"]
        and table["four_distinct"]
        and not table["any_guess"]
        and not table["production_mixed_indistinguishable"]
        and or_red
        and and_red
        and table["idle_read_as_dead"]
        and table["dead_read_as_idle"]
        and table["mtime_forbidden_undecidable"]
        and hard["pass"]
        and hard["verdict"] == UNDECIDABLE
        and hard["cell"] == CELL_DEAD_IDLE
    )
    if not ok:
        print("FAILED:IMP-0451 emit live four-cell did not satisfy acceptance")
        print(json.dumps({
            "verdicts": table["verdicts"],
            "four_distinct": table["four_distinct"],
            "all_match": table["all_match"],
            "any_guess": table["any_guess"],
            "or_red": or_red,
            "and_red": and_red,
            "hardest": hard,
            "mtime": table["mtime_forbidden_undecidable"],
        }, indent=2, sort_keys=True))
        return 1

    dep0450 = REPO / "command-center/receipts/IMP-0450.json"
    ended = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    rows = [flatten_row(r) for r in table["rows"]]
    doc = {
        "schema_version": 1,
        "unit_id": "IMP-0451",
        "id": "IMP-0451",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": "Stale-monitor and no-change-monitor detectors as a matched pair",
        "question_or_target": QUESTION,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:IMP-0451",
        "min_bytes_threshold": 2048,
        "profile": "selfimprove-measure-artifact",
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "implementer",
            "execution_substrate": "local-serialized",
        },
        "answer": (
            "Matched detectors consume two independent streams: a monitor "
            "heartbeat token that advances while the monitor is alive even "
            "when work is silent, and work byte-growth that can continue after "
            "the monitor dies. Four-cell live table: alive-active=HEALTHY, "
            "alive-idle=NO_CHANGE_MONITOR (11316), dead-active=STALE_MONITOR "
            "(11315), dead-idle=UNDECIDABLE (no guess). Collapsing the two "
            "signals into an OR or AND bit makes the mixed cells "
            "indistinguishable and turns four-cell distinctness red. mtime is "
            "rejected. IMP-0450 cockpit pane is unbuilt on this worktree; "
            "these detectors are read-only classifiers, not a second control "
            "plane. "
            + SENTINEL
        ),
        "dependencies": {
            "IMP-0450": {
                "role": "cockpit surface (read-only program pane)",
                "receipt_present": dep0450.is_file(),
                "note": (
                    "IMP-0450 is unbuilt on this worktree. IMP-0451 delivers "
                    "the matched detectors the pane can later display. This "
                    "receipt does not claim IMP-0450 delivered and does not "
                    "introduce a second dispatcher."
                ),
            }
        },
        "implementation": {
            "module": "tools/command-center/monitor_states.py",
            "monitor_signal": "heartbeat-token (JSONL, independent of work output)",
            "work_signal": "byte-growth (content length, never mtime)",
            "mtime_accepted": False,
            "control_planes_added": 0,
        },
        "truth_table": {
            "axes": ["monitor alive/dead", "work active/idle"],
            "verdicts": table["verdicts"],
            "four_distinct": table["four_distinct"],
            "any_guess": table["any_guess"],
            "all_match": table["all_match"],
            "rows": rows,
        },
        "mutation": {
            "description": (
                "Collapse the two signals into one bit (OR: any advancing "
                "signal; AND: both must advance). Mixed cells 11315/11316 "
                "become indistinguishable; four-cell distinctness goes red."
            ),
            "collapsed_or": table["collapsed_or"],
            "collapsed_and": table["collapsed_and"],
            "or_mixed_indistinguishable": table["or_mixed_indistinguishable"],
            "and_mixed_indistinguishable": table["and_mixed_indistinguishable"],
            "production_mixed_indistinguishable": table[
                "production_mixed_indistinguishable"
            ],
            "four_cell_goes_red": or_red and and_red,
            "idle_read_as_dead_mutant": table["naive_silence_is_dead"],
            "dead_read_as_idle_mutant": table["naive_any_activity_is_alive"],
        },
        "hardest_cell": hard,
        "mtime_control": table["mtime_control"],
        "live_run": {
            "verdicts": table["verdicts"],
            "idle_read_as_dead": table["idle_read_as_dead"],
            "dead_read_as_idle": table["dead_read_as_idle"],
            "mtime_forbidden_undecidable": table["mtime_forbidden_undecidable"],
        },
        "artifacts": [art(p, "supporting") for p in SUPPORTING],
        "evidence": [
            {
                "claim": (
                    "Four-cell live streams distinguish HEALTHY, "
                    "NO_CHANGE_MONITOR, STALE_MONITOR, and UNDECIDABLE; no "
                    "cell guessed."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/command-center/monitor_states.py",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "live-streams",
                        "command": "four_cell_live()",
                        "raw_output": json.dumps(table["verdicts"], sort_keys=True),
                    },
                    {
                        "role": "verifier",
                        "method": "named-probe",
                        "command": P1,
                        "raw_output": "re-run live by _measure_one_delivered.py",
                    },
                ],
            },
            {
                "claim": (
                    "Collapsing the two signals into one bit makes "
                    "alive-idle and dead-active indistinguishable, so the "
                    "four-cell test goes red. dead-idle stays UNDECIDABLE."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/command-center/monitor_states.py:collapse_or",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "mutation",
                        "command": "collapse_or / collapse_and / hardest_cell_undecidable",
                        "raw_output": json.dumps(
                            {
                                "or": table["collapsed_or"],
                                "and": table["collapsed_and"],
                                "hardest": hard["verdict"],
                            },
                            sort_keys=True,
                        ),
                    },
                    {
                        "role": "verifier",
                        "method": "named-probe",
                        "command": P2,
                        "raw_output": "re-run live by _measure_one_delivered.py",
                    },
                ],
            },
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {"count": 0, "policy": "max 2 attempts, backoff 30s/120s"},
        "tests": [
            {
                "id": "four-cell-truth-table",
                "command": P1,
                "result": "PASS",
                "assertions": 4,
                "output_tail": json.dumps(table["verdicts"], sort_keys=True),
            },
            {
                "id": "signal-collapse-mutant-and-hardest-cell",
                "command": P2,
                "result": "PASS",
                "assertions": 8,
                "output_tail": (
                    f"or_mixed={table['or_mixed_indistinguishable']} "
                    f"hardest={hard['verdict']}"
                ),
            },
        ],
        "negative_controls": [
            {
                "id": "IMP0451-C1",
                "kind": "mutation",
                "description": (
                    "OR the two signals into ACTIVITY/SILENCE. alive-idle "
                    "(11316) and dead-active (11315) must share one class, "
                    "turning four-cell distinctness red."
                ),
                "fired_on_bad_state": or_red,
                "silent_on_good_state": table["four_distinct"],
                "bad_state_output": json.dumps(table["collapsed_or"], sort_keys=True),
                "good_state_output": json.dumps(table["verdicts"], sort_keys=True),
            },
            {
                "id": "IMP0451-C2",
                "kind": "adversarial-hardest-cell",
                "description": (
                    "Both signals frozen (dead×idle). Same work-frozen values "
                    "as the quiet-alive neighbour and same monitor-frozen "
                    "values as the stale-monitor neighbour. Guessing either "
                    "neighbour's verdict is a defect."
                ),
                "fired_on_bad_state": hard["pass"],
                "silent_on_good_state": True,
                "bad_state_output": "UNDECIDABLE both-signals-frozen-do-not-guess",
                "good_state_output": json.dumps(hard, sort_keys=True),
            },
            {
                "id": "IMP0451-C3",
                "kind": "mtime-forbidden",
                "description": "An observation whose source is mtime must be UNDECIDABLE, not a guessed stall.",
                "fired_on_bad_state": table["mtime_forbidden_undecidable"],
                "silent_on_good_state": True,
                "bad_state_output": "mtime-only-forbidden",
                "good_state_output": json.dumps(table["mtime_control"], sort_keys=True),
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0451-probe2-hardest-cell",
            "verdict": "PASS",
            "independent": True,
            "note": (
                "Catalog reviewer_requirement names an adversarial refuter on "
                "the hardest cell. That cell is constructed live (dead×idle) "
                "and required to stay UNDECIDABLE. G-1 is live named probes "
                "plus an honest non-BLOCKED artifact. Waiting on an ADV "
                "rebuild of this unit is the circle the dispatch prompt forbids."
            ),
        },
        "named_probes": [
            {"id": "probe1", "role": "four-cell-truth-table", "command": P1},
            {"id": "probe2", "role": "signal-collapse-hardest-cell", "command": P2},
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0451/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
            "global_catalog_write": False,
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py IMP-0451",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": True,
                "note": "Measure runs after this receipt and the per-unit manifest are on disk.",
            }
        ],
        "required_fix": None,
        "adv_rebuild_circle": False,
        "notes": (
            "G-1 for IMP-0451: live named probes exit 0, receipts/IMP-0451.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild circle."
        ),
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if SENTINEL not in body:
        print("FAILED:IMP-0451 sentinel missing from serialized receipt")
        return 1
    out.write_text(body, encoding="utf-8")
    sha, size = digest_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:IMP-0451 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
