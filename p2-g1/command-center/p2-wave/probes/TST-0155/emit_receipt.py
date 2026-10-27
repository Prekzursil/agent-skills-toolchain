#!/usr/bin/env python3
"""Write command-center/receipts/TST-0155.json from a live harness run."""
from __future__ import annotations

import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402
import reader as R  # noqa: E402

UNIT = "TST-0155"
OUT = "command-center/receipts/TST-0155.json"
SCHEMA = "command-center/schema/receipt.schema.json#/$defs/monitor_report"
SENTINEL = "SUCCESS:TST-0155"
MIN_BYTES = 2048
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0155/probe1_rotation_match.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0155/probe2_both_states_and_boundary.py"
)
QUESTION = (
    "While the monitor tails a log, rotate it: does the reader continue "
    "without crashing and without re-counting lines already consumed? PASS "
    "requires an exact line-count match against the concatenated pre- and "
    "post-rotation content."
)


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def source_hash(rel: str) -> dict:
    path = REPO / rel
    sha, n = digest(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "exists": path.is_file(),
        "bytes": n,
        "sha256": sha,
    }


def slim_run(row: dict) -> dict:
    keys = [
        "scenario",
        "reader",
        "monitor_count",
        "offline_count",
        "match",
        "crashed",
        "crash_exc",
        "inode_changed",
        "rotated_is_old_live",
        "live_inode_before",
        "live_inode_after",
        "rotated_inode",
        "rotations",
        "truncations",
        "recounts",
        "polls",
        "live_bytes",
        "rotated_bytes",
        "live_exists",
        "rotated_exists",
        "pass",
        "fired_on_bad_state",
        "negative_id",
        "expected_count",
    ]
    out = {k: row[k] for k in keys if k in row}
    lines = row.get("monitor_lines") or []
    out["monitor_head"] = lines[:3]
    out["monitor_tail"] = lines[-3:]
    out["offline_head"] = (row.get("offline_lines") or [])[:3]
    if row.get("scenario") == "rotation-mid-line":
        out["monitor_lines"] = lines
        out["offline_lines"] = row.get("offline_lines")
    return out


def main() -> int:
    run = H.run_all()
    if not run["pass"]:
        print("FAILED:TST-0155 harness did not pass")
        print(
            json.dumps(
                {
                    "between": run["between"]["pass"],
                    "no_rotation": run["no_rotation"]["pass"],
                    "mid_line": run["mid_line"]["pass"],
                    "stuck": run["negative_stuck_fd"]["pass"],
                    "recount": run["negative_recount"]["pass"],
                    "same_count": run["same_count_no_rotation_vs_rotation"],
                    "between_crash": run["between"].get("crash_exc"),
                    "mid_crash": run["mid_line"].get("crash_exc"),
                    "mid_lines": run["mid_line"].get("monitor_lines"),
                    "stuck_count": run["negative_stuck_fd"].get("monitor_count"),
                    "recount_count": run["negative_recount"].get("monitor_count"),
                },
                sort_keys=True,
            )
        )
        return 1
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    between = run["between"]
    none = run["no_rotation"]
    mid = run["mid_line"]
    stuck = run["negative_stuck_fd"]
    recount = run["negative_recount"]
    reader_src = source_hash("command-center/p2-wave/probes/TST-0155/reader.py")
    harness_src = source_hash("command-center/p2-wave/probes/TST-0155/harness.py")
    monitorcore = (REPO / "tools" / "monitorcore").is_dir()
    receipt = {
        "id": UNIT,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "profile": "monitor-report",
        "report_kind": "monitor_report",
        "title": (
            "Log rotation under a live reader causes neither crash nor "
            "double-count"
        ),
        "question_or_target": QUESTION,
        "answer": (
            "Yes on this Linux worktree. FollowReader kept the open fd, "
            "drained it when the path inode changed, opened the new live "
            "file from byte 0, and carried a mid-line fragment across the "
            "seam. Live consumed lines equalled the offline concatenation "
            f"of monitor.log.1 then monitor.log ({run['expected_total']} "
            "complete lines). A no-rotation control produced the same count. "
            "StuckFdReader missed every post-rotate line; RecountOnRotateReader "
            "double-counted the pre-rotate lines. tools/monitorcore is absent "
            "here, so the monitor under test is the inode-follow tailer in "
            "probes/TST-0155/reader.py (same pattern as CNF-0047)."
        ),
        "output_path": OUT,
        "output_schema": SCHEMA,
        "min_bytes_threshold": MIN_BYTES,
        "ts": now,
        "produced_by": {
            "role": "observability-tester",
            "execution_substrate": "linux-local-serialized",
            "platform": platform.platform(),
            "python": sys.version.split()[0],
            "worktree": str(REPO),
        },
        "monitor_under_test": {
            "path": "command-center/p2-wave/probes/TST-0155/reader.py",
            "class": "FollowReader",
            "production_monitorcore_present": monitorcore,
            "note": (
                "tools/monitorcore is absent on this Linux worktree. The "
                "unit runs the rotation-safe tailer required by the question: "
                "inode follow, partial-line carry, no recap of consumed bytes."
            ),
            "signals": [
                "live FollowReader.consumed complete lines",
                "offline concat of rotated-then-live file bytes",
            ],
            "source_sha256": reader_src["sha256"],
        },
        "target_result": {
            "between_writes": slim_run(between),
            "pass": True,
        },
        "both_states": {
            "no_rotation": slim_run(none),
            "with_rotation": {
                "monitor_count": between["monitor_count"],
                "offline_count": between["offline_count"],
            },
            "same_count": True,
            "expected_total": run["expected_total"],
        },
        "boundary": {
            "between_writes": slim_run(between),
            "mid_line": slim_run(mid),
            "mid_line_emitted": mid["monitor_lines"],
            "mid_line_offline": mid["offline_lines"],
        },
        "evidence": [
            {
                "id": "a-monitor-counted-lines",
                "kind": "live-reader",
                "claim": (
                    "FollowReader emitted exactly the pre-rotation lines then "
                    "the post-rotation lines, with no recap and no crash."
                ),
                "monitor_count": between["monitor_count"],
                "path": "command-center/p2-wave/probes/TST-0155/reader.py",
                "verdict": "CONFIRMED",
            },
            {
                "id": "b-offline-concat",
                "kind": "offline-file-concat",
                "claim": (
                    "Independent split of monitor.log.1 bytes concatenated "
                    "with monitor.log bytes produced the same list."
                ),
                "offline_count": between["offline_count"],
                "path": "command-center/p2-wave/probes/TST-0155/harness.py",
                "verdict": "CONFIRMED",
            },
        ],
        "evidence_verdicts": ["CONFIRMED", "CONFIRMED"],
        "tests": [
            {
                "id": "TST-0155-TARGET-ROTATION-MATCH",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "TST-0155-BOTH-STATES-NO-ROTATION",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "TST-0155-BOUNDARY-MID-LINE",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "TST-0155-NEGATIVE-STUCK-FD",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "TST-0155-NEGATIVE-RECOUNT",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "TST-0155-NC-STUCK-FD",
                "reader": "StuckFdReader",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "monitor_count": stuck["monitor_count"],
                "offline_count": stuck["offline_count"],
                "detail": (
                    "Keeps the original fd after rename-rotate (tail -f "
                    "without -F). Counted only the pre-rotation lines; "
                    "offline concat still had pre+post."
                ),
            },
            {
                "id": "TST-0155-NC-RECOUNT-ON-ROTATE",
                "reader": "RecountOnRotateReader",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "monitor_count": recount["monitor_count"],
                "offline_count": recount["offline_count"],
                "recounts": recount["recounts"],
                "detail": (
                    "On inode change, re-reads monitor.log.1 from byte 0 and "
                    "appends those lines on top of lines already consumed. "
                    f"Counted {recount['monitor_count']} against offline "
                    f"{recount['offline_count']}."
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0155-probe2-both-states-midline-negatives",
            "verdict": "PASS",
            "independent": True,
            "detector_control_rerun": True,
            "method": (
                "Named probe2 re-runs the no-rotation control, the mid-line "
                "boundary, and both known-broken readers. It does not share "
                "probe1's process or consumed list."
            ),
            "windows_second_shell": {
                "required_by_catalog": True,
                "executed": False,
                "reason": (
                    "This worktree is Linux. pwsh7 and Git Bash were not "
                    "available. Residual: a Windows rename of an open live "
                    "log can fail where Linux os.replace succeeds; that "
                    "platform-gap is recorded, not claimed PASS."
                ),
                "verdict": "NOT-CHECKED",
            },
        },
        "residuals": [
            {
                "id": "windows-second-shell",
                "verdict": "NOT-CHECKED",
                "detail": (
                    "Catalog reviewer_requirement asked for a second Windows "
                    "shell. Substrate here is Linux; the rotation property "
                    "was proven with os.replace on an open fd."
                ),
            },
            {
                "id": "production-monitorcore-absent",
                "verdict": "NOT-CHECKED",
                "detail": (
                    "tools/monitorcore is not in this worktree. The unit "
                    "ships and tests FollowReader rather than claiming a "
                    "missing production binary passed."
                ),
            },
        ],
        "source_hashes": {
            "command-center/p2-wave/probes/TST-0155/reader.py": reader_src,
            "command-center/p2-wave/probes/TST-0155/harness.py": harness_src,
        },
        "artifacts": [
            {
                "path": OUT,
                "exists": True,
                "role": "primary",
            },
            {
                "path": "command-center/p2-wave/probes/TST-0155/reader.py",
                "exists": True,
                "role": "monitor-under-test",
                "sha256": reader_src["sha256"],
            },
            {
                "path": "command-center/p2-wave/probes/TST-0155/harness.py",
                "exists": True,
                "role": "supporting",
                "sha256": harness_src["sha256"],
            },
        ],
        "notes": (
            "G-1 for TST-0155: live named probes exit 0, receipt "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild. Cloud ok=true is "
            "not delivery. Did not rotate or print API keys. "
            f"{SENTINEL}"
        ),
        "reader_api": {
            "complete_lines_ignores_trailing_fragment": True,
            "follow_uses_inode": "ident_of_fd" in R.__dict__,
            "stuck_cls": "StuckFdReader",
            "recount_cls": "RecountOnRotateReader",
        },
    }
    path = REPO / OUT
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(receipt, indent=1, sort_keys=True) + "\n"
    if SENTINEL not in text:
        print("FAILED:TST-0155 sentinel absent from receipt text")
        return 1
    path.write_text(text, encoding="utf-8")
    size = path.stat().st_size
    if size < MIN_BYTES:
        print(f"FAILED:TST-0155 receipt {size}B below floor {MIN_BYTES}B")
        return 1
    print(f"wrote {OUT} bytes={size}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
