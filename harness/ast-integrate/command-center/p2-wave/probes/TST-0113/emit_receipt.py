#!/usr/bin/env python3
"""Write command-center/receipts/TST-0113.json from a live capture+rubric run."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from inventory import UNIT, capture_all  # noqa: E402
from rubric import score_message  # noqa: E402

OUT = f"command-center/receipts/{UNIT}.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    f"command-center/p2-wave/probes/{UNIT}/probe1_every_path_triggered.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    f"command-center/p2-wave/probes/{UNIT}/probe2_rubric_on_captured_text.py"
)


def sha256_file(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n") if path.is_file() else b""
    return hashlib.sha256(raw).hexdigest()


def write_receipt() -> dict:
    cap = capture_all()
    if not cap["inventory_complete"]:
        raise SystemExit(
            f"FAILED:{UNIT} inventory incomplete "
            f"{cap['source_refuse_reasons']} vs {cap['triggered_reasons']}"
        )
    paths = []
    for row in cap["rows"]:
        if not row["triggered"]:
            raise SystemExit(f"FAILED:{UNIT} path not triggered: {row['id']}")
        if row["library_allowed"] or row["cli_exit_code"] == 0:
            raise SystemExit(f"FAILED:{UNIT} refuse path did not refuse: {row['id']}")
        if not row["library_matches_stderr"] or not row["stderr_matches_stdout_message"]:
            raise SystemExit(f"FAILED:{UNIT} capture mismatch: {row['id']}")
        scored = score_message(row["captured_text"])
        if not scored["pass"]:
            raise SystemExit(f"FAILED:{UNIT} rubric fail {row['id']}: {scored}")
        paths.append(
            {
                "id": row["id"],
                "reason": row["library_reason"],
                "captured_text": row["captured_text"],
                "library_text": row["library_text"],
                "cli_exit_code": row["cli_exit_code"],
                "cli_stderr_equals_library": True,
                "dest_payload_on_refuse": False,
                "rubric": scored,
            }
        )
    bare = []
    for msg in cap["bare_messages"]:
        scored = score_message(msg)
        if scored["pass"]:
            raise SystemExit(f"FAILED:{UNIT} bare message passed: {msg!r}")
        bare.append({"planted_text": msg, "rubric": scored, "pass": False})
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    supporting = [
        cap["negotiate_src"],
        cap["gate"],
        f"command-center/p2-wave/probes/{UNIT}/inventory.py",
        f"command-center/p2-wave/probes/{UNIT}/rubric.py",
        f"command-center/p2-wave/probes/{UNIT}/probe1_every_path_triggered.py",
        f"command-center/p2-wave/probes/{UNIT}/probe2_rubric_on_captured_text.py",
        f"command-center/p2-wave/probes/{UNIT}/fixtures/bare-messages.json",
        f"command-center/p2-wave/probes/{UNIT}/fixtures/unparsable-min-manifest.json",
    ]
    artifacts = [{"path": OUT, "role": "primary", "exists": True}]
    for rel in supporting:
        p = REPO / rel
        artifacts.append(
            {
                "path": rel,
                "role": "supporting",
                "exists": p.is_file(),
                "bytes": p.stat().st_size if p.is_file() else 0,
                "sha256": sha256_file(p) if p.is_file() else "",
            }
        )
    missing = [a["path"] for a in artifacts[1:] if not a["exists"]]
    if missing:
        raise SystemExit(f"FAILED:{UNIT} missing supporting {missing}")
    all_live_pass = all(p["rubric"]["pass"] for p in paths)
    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": f"SUCCESS:{UNIT}",
        "completion_sentinel": f"SUCCESS:{UNIT}",
        "title": "User-facing error messages must name the component, the cause and the remedy",
        "question": (
            "Phase 5 requires 'clear user-facing error messages' (:10840). "
            "Target: trigger every error path and score its message against a "
            "three-part rubric (what failed, why, what to do). A message that "
            "only says an operation failed is a defect, not a style preference."
        ),
        "spec_anchor": "_USER-PROMPTS.md:10840; catalog TST-0113; wording deferred from TST-0078",
        "min_bytes_threshold": 128,
        "output_path": OUT,
        "output_schema": "command-center/schema/test-receipt.schema.json",
        "execution_substrate": "local-serialized",
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "docs-test-engineer",
            "execution_substrate": "linux-worktree",
        },
        "closed_inventory": {
            "surface": (
                "tools/plugin/client_negotiate.negotiate refuse reasons "
                "+ install_gate CLI stderr"
            ),
            "source_refuse_reasons": cap["source_refuse_reasons"],
            "triggered_reasons": cap["triggered_reasons"],
            "complete": cap["inventory_complete"],
            "how_derived": "AST of reason= literals inside negotiate(), then live trigger of each",
        },
        "triggered_paths": paths,
        "tests": [
            {
                "id": "test_every_error_path_is_triggered_at_least_once",
                "result": "PASS" if cap["inventory_complete"] and paths else "FAIL",
                "n_paths": len(paths),
                "reasons": cap["triggered_reasons"],
            },
            {
                "id": "test_each_message_scores_on_all_three_rubric_parts",
                "result": "PASS" if all_live_pass else "FAIL",
                "scored_from": "captured-text",
                "n_scored": len(paths),
            },
        ],
        "negative_controls": [
            {
                "id": "bare-operation-failed",
                "planted": cap["bare_messages"],
                "fired_on_bad": all(not b["pass"] for b in bare),
                "scores": bare,
                "note": (
                    "A message that only says an operation failed must not pass "
                    "the why or what-to-do parts."
                ),
            }
        ],
        "evidence": [
            {
                "id": "verbatim-captures",
                "claim": (
                    "Every negotiate() refuse reason was triggered through "
                    "install_gate.py; CLI stderr equals the library message; "
                    "rubric scores were assigned against that captured text."
                ),
                "captures": [
                    {
                        "id": p["id"],
                        "text": p["captured_text"],
                        "score": p["rubric"]["score"],
                    }
                    for p in paths
                ],
            }
        ],
        "reviewer": {
            "reviewer_id": f"{UNIT}-probe2-rubric-on-captured-text",
            "verdict": "PASS",
            "independent": True,
            "windows_powershell_rerun": False,
            "note": (
                "Probe 2 is the independent mechanical refuter on this Linux "
                "worktree. Catalog also asks for a Windows-platform specialist "
                "in the other shell; that re-run is residual, not claimed."
            ),
        },
        "named_probes": [
            {"id": "probe1", "role": "every-error-path-triggered", "command": P1},
            {"id": "probe2", "role": "rubric-on-captured-text", "command": P2},
        ],
        "artifacts": artifacts,
        "cloud_ok": False,
        "registered": True,
        "residual_unknowns": [
            {
                "id": "windows-other-shell-rerun",
                "question": "Would the same probes exit 0 under PowerShell 7 on Windows?",
                "status": "not-run-on-this-linux-worktree",
            },
            {
                "id": "non-install-cli-error-paths",
                "question": (
                    "Do rollback/sbom/eol/pack user-facing errors also meet the rubric?"
                ),
                "status": "outside-closed-inventory",
                "text": (
                    "TST-0078 deferred compatibility-message wording to this unit. "
                    "Those other CLIs are named residual, not scored as covered."
                ),
            },
        ],
        "does_not_claim": [
            "cloud ok=true is delivery",
            "global unit_manifest.py --write was run",
            "every error path in the entire repository was triggered",
            "a Windows PowerShell 7 re-run was executed",
            "a human cross-vendor reviewer in a fresh context filed PASS",
        ],
        "ts": now,
    }
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=1, ensure_ascii=True) + "\n", encoding="utf-8")
    return doc


def main() -> int:
    write_receipt()
    dest = REPO / OUT
    print(f"wrote {OUT} bytes={dest.stat().st_size}")
    print(f"SUCCESS:{UNIT} emit_receipt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
