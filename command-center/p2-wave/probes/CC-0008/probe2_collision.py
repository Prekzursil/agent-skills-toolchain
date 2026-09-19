#!/usr/bin/env python3
"""CC-0008 probe 2: deliberate collision fixture must fail loudly with both paths."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "tools" / "command-center"))
import catalog_slice_merge as m  # noqa: E402


def main() -> int:
    PROBE.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="cc0008-collision-"))
    try:
        # Two slices both claiming CC-0007
        unit = {
            "id": "CC-0007",
            "title": "collision fixture",
            "phase": "0",
            "question_or_target": "malformed collision",
            "inputs": [],
            "dependencies": [],
            "assigned_model_vendor_role": {
                "model": "opus",
                "vendor": "anthropic",
                "role": "implementer",
            },
            "tool_permissions": ["Read"],
            "execution_substrate": "local-serialized",
            "timeout_seconds": 60,
            "output_path": "command-center/receipts/CC-0007.json",
            "output_schema": "command-center/schema/receipt.schema.json",
            "evidence_requirement": "fixture",
            "tests_required": ["fixture"],
            "reviewer_requirement": "fixture",
            "completion_sentinel": "SUCCESS:CC-0007",
            "retry_policy": "none",
            "failure_classification": ["detector-failure"],
            "owner_approval_required": False,
        }
        a = scratch / "slice-a.json"
        b = scratch / "slice-b.json"
        a.write_text(json.dumps([unit]) + "\n", encoding="utf-8")
        b.write_text(json.dumps([dict(unit)]) + "\n", encoding="utf-8")

        fired = False
        msg = ""
        try:
            m.load_slices(scratch)
        except m.CollisionError as exc:
            fired = True
            msg = str(exc)

        both_named = ("slice-a.json" in msg) and ("slice-b.json" in msg)
        ok = fired and both_named and "CC-0007" in msg

        # Positive control: single-claim set is silent
        clean = scratch / "clean"
        clean.mkdir()
        (clean / "only.json").write_text(json.dumps([unit]) + "\n", encoding="utf-8")
        silent_ok = False
        try:
            units, _ = m.load_slices(clean)
            silent_ok = len(units) == 1
        except Exception as exc:  # noqa: BLE001
            msg += f"\nCLEAN_UNEXPECTED={exc}"

        summary = {
            "probe": "CC-0008-probe2-collision",
            "ran_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "collision_fired": fired,
            "both_paths_named": both_named,
            "silent_on_clean": silent_ok,
            "ok": ok and silent_ok,
            "error_message": msg[:4000],
        }
        (PROBE / "probe2-collision-summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        raw = (
            "PROBE=CC-0008-probe2-collision\n"
            f"COLLISION_FIRED={fired}\n"
            f"BOTH_PATHS_NAMED={both_named}\n"
            f"SILENT_ON_CLEAN={silent_ok}\n"
            f"ERROR_MESSAGE=\n{msg}\n"
            f"VERDICT={'PASS' if summary['ok'] else 'FAIL'}\n"
        )
        (PROBE / "probe2-collision.raw.txt").write_text(raw, encoding="utf-8")
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0 if summary["ok"] else 1
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
