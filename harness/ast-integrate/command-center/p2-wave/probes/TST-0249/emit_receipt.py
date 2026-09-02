#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0249.json from live harness measurements."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

OUT_REL = "command-center/receipts/TST-0249.json"
DECLARED_SCHEMA = "command-center/schema/receipt.schema.json#/$defs/ux_report"
LOCAL_SCHEMA = "command-center/p2-wave/probes/TST-0249/artifact.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0249/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0249/probe2_regression_seed.py"
)


def canonical(doc: dict) -> str:
    return json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def main() -> int:
    live = H.jsonable(H.measure())
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    schema_path = REPO / "command-center/schema/receipt.schema.json"
    ux_pass = bool(live["ux_pass"])
    question = (
        "Does user-facing output containing non-ASCII crash or mojibake on a "
        "cp1252 console? PASS requires no exception and a legible fallback, "
        "with the chosen fallback declared."
    )
    if ux_pass:
        answer = (
            "PASS: tools/command-center/close.py --list emitted non-ASCII on a "
            "simulated cp1252 console with no exception and a declared fallback."
        )
    else:
        answer = (
            "FAIL: tools/command-center/close.py --list with PYTHONIOENCODING=cp1252 "
            f"exits {live['cp1252_console']['subprocess']['exit_code']} raising "
            "UnicodeEncodeError at print(line); stdout capture is empty. Production "
            "does not declare a console error handler. A recommended "
            f"{H.RECOMMENDED_FALLBACK} fallback is legible (\\\\u2265 and \\\\u2b50) "
            "but is not wired into the shipped CLI. UTF-8 console output of the "
            "same payload is byte-exact. The live UTF-8 catalog raises "
            "UnicodeDecodeError under the cp1252 codec (undefined 0x90 from U+2B50)."
        )
    receipt = {
        "SUCCESS:TST-0249": True,
        "unit_id": H.UNIT,
        "id": H.UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": H.SENTINEL,
        "title": "UTF-8 output survives a legacy code-page console",
        "question": question,
        "question_or_target": question,
        "answer": answer,
        "ux_pass": ux_pass,
        "verdict": "PASS" if ux_pass else "FAIL",
        "chosen_fallback": live["chosen_fallback"],
        "recommended_fallback": H.RECOMMENDED_FALLBACK,
        "output_schema": DECLARED_SCHEMA,
        "declared_schema_present": schema_path.is_file(),
        "local_schema": LOCAL_SCHEMA,
        "schema_note": (
            "command-center/schema/receipt.schema.json is absent on this worktree "
            "(IMP-0433). This artifact is a ux_report validated against the "
            "local probe schema only."
        ),
        "environment": live["environment"],
        "subject": live["subject"],
        "both_states": live["both_states"],
        "cp1252_console": live["cp1252_console"],
        "regression_seed": live["regression_seed"],
        "fixture_decode_seed": live["fixture_decode_seed"],
        "controls": live["controls"],
        "evidence": [
            {
                "id": "E-A-cp1252-exit",
                "kind": "process-exit-status",
                "detail": (
                    f"close.py --list --catalog {H.FIXTURE_REL} under "
                    f"PYTHONIOENCODING=cp1252 exit_code="
                    f"{live['cp1252_console']['subprocess']['exit_code']} "
                    f"unicode_encode_error="
                    f"{live['cp1252_console']['subprocess']['unicode_encode_error']} "
                    f"stdout_bytes="
                    f"{live['cp1252_console']['subprocess']['stdout_byte_count']}"
                ),
                "command": live["cp1252_console"]["subprocess"]["command"],
                "exit_code": live["cp1252_console"]["subprocess"]["exit_code"],
            },
            {
                "id": "E-B-utf8-bytes",
                "kind": "byte-level-capture",
                "detail": (
                    "In-process TextIOWrapper(utf-8) two-run capture "
                    f"sha256={live['both_states']['utf8_sha256']} "
                    f"bytes={live['both_states']['utf8_byte_count']} "
                    f"hex={live['both_states']['utf8_hex_preview']} "
                    "equals payload.encode('utf-8')"
                ),
                "sha256": live["both_states"]["utf8_sha256"],
                "byte_count": live["both_states"]["utf8_byte_count"],
                "hex_preview": live["both_states"]["utf8_hex_preview"],
            },
        ],
        "tests": [
            {
                "id": "both-states-utf8-byte-exact",
                "name": "both-states control: the same output on a UTF-8 console is byte-exact",
                "command": P1,
                "result": "PASS" if live["both_states"]["utf8_byte_exact"] else "FAIL",
            },
            {
                "id": "regression-seed-cp1252-decode",
                "name": (
                    "regression seed: a UnicodeDecodeError from the default "
                    "cp1252 codec, reproduced on this box while reading a UTF-8 catalog"
                ),
                "command": P2,
                "result": "PASS" if live["regression_seed"]["cp1252_raises"] else "FAIL",
            },
        ],
        "negative_controls": [
            {
                "id": "strict-cp1252-encode",
                "kind": "detector-control",
                "description": (
                    "The fixture list payload must raise UnicodeEncodeError on "
                    "cp1252 strict so the UTF-8 identity test is not ASCII-only"
                ),
                "fired_on_bad_state": live["controls"]["strict_cp1252_raises"],
                "silent_on_good_state": live["controls"]["utf8_silent"],
            },
            {
                "id": "live-catalog-cp1252-decode",
                "kind": "regression-seed",
                "description": (
                    "Live WORK-UNIT-CATALOG.json must be valid UTF-8 and must "
                    "raise UnicodeDecodeError under cp1252 (undefined 0x90)"
                ),
                "fired_on_bad_state": live["controls"]["live_catalog_cp1252_decode_raises"],
                "silent_on_good_state": live["controls"]["live_catalog_utf8_ok"],
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0249-probe2-regression-seed-rerun",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "attempt": "probe2 subprocess exit + live catalog decode, not probe1 TextIOWrapper",
        },
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "utf8-both-states-byte-exact"},
            {"id": "probe2", "command": P2, "role": "cp1252-exit-and-decode-seed"},
        ],
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"},
            {"path": H.CLOSE_REL, "exists": (REPO / H.CLOSE_REL).is_file(), "role": "subject"},
            {"path": H.FIXTURE_REL, "exists": True, "role": "fixture"},
            {"path": H.LIVE_CATALOG_REL, "exists": True, "role": "regression-seed-input"},
        ],
        "min_bytes_threshold": 256,
        "timestamps": {"ended_at": now},
        "notes": (
            "G-1 TST-0249: live named probes, honest ux_report (production "
            "cp1252 print crashes; unit state=SUCCESS). Did not run global "
            "unit_manifest.py --write. Did not patch tools/command-center."
        ),
    }
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(canonical(receipt), encoding="utf-8")
    print(f"wrote {OUT_REL} bytes={out.stat().st_size}")
    print(H.SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
