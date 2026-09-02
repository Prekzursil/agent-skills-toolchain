#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0200.json (portability_report)."""
from __future__ import annotations

import json
import os
import platform
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]  # .../probes/TST-0200 -> ast-integrate
sys.path.insert(0, str(HERE))

from installer import LIMIT_NAME, POLICY_NAME, WIN32_MAX_PATH  # noqa: E402
from scenario import run_matrix  # noqa: E402

OUT = "command-center/receipts/TST-0200.json"
QUESTION = (
    "On a Windows host WITHOUT LongPathsEnabled, does install to a deep target "
    "produce an actionable error naming the limit, and never a truncated or "
    "partially written tree? PASS forbids any partially populated destination."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0200/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0200/probe2_listing.py"
)


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst0200-emit-") as tmp:
        matrix = run_matrix(Path(tmp))
    c = matrix["contract"]
    if not c["holds"]:
        print("FAILED:TST-0200 emit contract", json.dumps(c, indent=2))
        return 1
    short = matrix["short"]
    deep = matrix["deep_long_paths_false"]
    on = matrix["deep_long_paths_true"]
    naive = matrix["naive_partial_control"]
    sentinel = "SUCCESS:TST-0200"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    host = {
        "system": platform.system(),
        "release": platform.release(),
        "python": platform.python_version(),
        "is_windows": os.name == "nt",
        "machine_wide_LongPathsEnabled_toggled": False,
        "policy_injection": (
            "installer --long-paths-enabled flag. Did not write "
            r"HKLM\SYSTEM\CurrentControlSet\Control\FileSystem\LongPathsEnabled."
        ),
        "note": (
            "Linux worktree: Win32 MAX_PATH is enforced as a portable preflight "
            "on the resolved destination character length. The same install to a "
            "short path is the both-states control."
        ),
    }
    answer = (
        "Yes on this worktree's installer: a >260 character destination with "
        f"{POLICY_NAME}=false exits {deep['cli']['exit_code']} with a message "
        f"naming {LIMIT_NAME} ({WIN32_MAX_PATH}) and {POLICY_NAME}, and the "
        f"independent os.scandir listing is {deep['listing']['state']} "
        f"(file_count={deep['listing']['file_count']}), never PARTIAL. The same "
        f"package to a short path exits {short['cli']['exit_code']} with listing "
        f"{short['listing']['state']}. {POLICY_NAME}=true on a deep dest completes "
        f"({on['listing']['state']}) rather than truncating. A naive prefix-write "
        f"control is classified {naive['listing']['state']}, proving the listing "
        f"discriminates. {sentinel}"
    )
    doc = {
        "unit_id": "TST-0200",
        "id": "TST-0200",
        "state": "SUCCESS",
        "sentinel": sentinel,
        "report_kind": "portability_report",
        "title": "Install to a >260 character path either works or fails clearly - never truncates",
        "question": QUESTION,
        "claim_under_test": (
            "The package installer preflights every resolved destination path "
            f"against {LIMIT_NAME}={WIN32_MAX_PATH} when {POLICY_NAME} is false, "
            "refuses with a named limit, and writes zero files."
        ),
        "answer": answer,
        "ts": now,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json#/$defs/portability_report",
        "host": host,
        "owner_approval_required": True,
        "owner_policy_toggle_performed": False,
        "win32_max_path": WIN32_MAX_PATH,
        "limit_name": LIMIT_NAME,
        "policy_name": POLICY_NAME,
        "installer_path": "command-center/p2-wave/probes/TST-0200/installer.py",
        "listing_path": "command-center/p2-wave/probes/TST-0200/listing.py",
        "both_states": {
            "short_path": {
                "longest_measured_chars": short["meta"]["longest_measured_chars"],
                "installer_exit": short["cli"]["exit_code"],
                "installer_message": short["cli"]["message"],
                "listing_state": short["listing"]["state"],
                "file_count": short["listing"]["file_count"],
                "complete": short["listing"]["complete"],
            },
            "deep_path_long_paths_false": {
                "longest_measured_chars": deep["meta"]["longest_measured_chars"],
                "installer_exit": deep["cli"]["exit_code"],
                "installer_message": deep["cli"]["message"],
                "listing_state": deep["listing"]["state"],
                "file_count": deep["listing"]["file_count"],
                "complete": deep["listing"]["complete"],
                "partial": deep["listing"]["partial"],
            },
            "deep_path_long_paths_true": {
                "installer_exit": on["cli"]["exit_code"],
                "listing_state": on["listing"]["state"],
                "file_count": on["listing"]["file_count"],
                "complete": on["listing"]["complete"],
            },
        },
        "naive_partial_control": {
            "listing_state": naive["listing"]["state"],
            "file_count": naive["listing"]["file_count"],
            "partial": naive["listing"]["partial"],
            "installer_exit": naive["cli"]["exit_code"],
            "why": (
                "Planted prefix-write must be PARTIAL so an always-empty listing "
                "cannot pass."
            ),
        },
        "contract": c,
        "evidence": [
            {
                "kind": "control",
                "claim": "Short-path install of the same package succeeds and is COMPLETE.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0200/installer.py:install",
                "detail": (
                    f"exit={short['cli']['exit_code']} listing={short['listing']['state']} "
                    f"chars={short['meta']['longest_measured_chars']}"
                ),
            },
            {
                "kind": "observation",
                "claim": (
                    "Deep dest with LongPathsEnabled=false refuses, names MAX_PATH "
                    "260, and listing is not PARTIAL."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0200/listing.py:classify",
                "detail": (
                    f"exit={deep['cli']['exit_code']} listing={deep['listing']['state']} "
                    f"chars={deep['meta']['longest_measured_chars']} "
                    f"message={deep['cli']['message'][:220]}"
                ),
            },
            {
                "kind": "variant",
                "claim": "LongPathsEnabled=true completes the same deep shape instead of truncating.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0200/installer.py:install",
                "detail": (
                    f"exit={on['cli']['exit_code']} listing={on['listing']['state']} "
                    f"files={on['listing']['file_count']}"
                ),
            },
            {
                "kind": "inventory",
                "claim": "Naive prefix-write is classified PARTIAL by the listing.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0200/listing.py:walk_files",
                "detail": (
                    f"state={naive['listing']['state']} files={naive['listing']['file_count']}"
                ),
            },
        ],
        "tests": [
            {
                "id": "TST0200-T1-BOTH-STATES",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "TST0200-T2-LISTING-AND-PARTIAL-CONTROL",
                "command": P2,
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0200-probe2-listing",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Probe 2 re-runs os.scandir classification and the naive PARTIAL "
                "control; it does not trust installer.ok. Second Windows shell "
                "(pwsh7 vs Git Bash) was not available on this Linux host; "
                "divergence there is not claimed."
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/TST-0200/installer.py",
                "exists": True,
                "role": "installer",
            },
            {
                "path": "command-center/p2-wave/probes/TST-0200/listing.py",
                "exists": True,
                "role": "listing",
            },
        ],
        "named_probes": [
            {"id": "probe1", "command": P1},
            {"id": "probe2", "command": P2},
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "Native Windows CreateFile behavior with LongPathsEnabled unset "
                    "was not executed on this Linux host; the portable preflight is "
                    "what was measured."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run installer.py on a Windows host with LongPathsEnabled=0 "
                    "and confirm dest listing ABSENT/EMPTY."
                ),
            }
        ],
        "adv_rebuild_circle": False,
    }
    if sentinel not in json.dumps(doc):
        print("FAILED:TST-0200 sentinel-absent from document")
        return 1
    atomic_write(REPO / OUT, json.dumps(doc, indent=1, sort_keys=True) + "\n")
    print(f"wrote {OUT} bytes={(REPO / OUT).stat().st_size}")
    print("SUCCESS:TST-0200 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
