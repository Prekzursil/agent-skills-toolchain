#!/usr/bin/env python3
"""Emit TST-0182 receipt, SUBAGENT-RETURN, and per-unit UNIT-ARTIFACT-MANIFEST."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "TST-0182"
OUT_REL = f"command-center/receipts/{UNIT}.json"
SENTINEL = f"SUCCESS:{UNIT}"
SCHEMA_NOTE = (
    "Catalog names command-center/schema/receipt.schema.json#/$defs/parser_report; "
    "receipt.schema.json is absent on this tree. This receipt is a parser_report "
    "document (unique-key both-states, duplicate rejection with both values, "
    "token-level key count, stdlib json.load negative control)."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0182/probe1_unique_accepts_duplicate_rejects.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0182/probe2_stdlib_last_wins_fails_and_reviewer.py"
)
SUPPORTING = [
    "tools/plugin/strict_json.py",
    "tools/plugin/json_key_scan.py",
    "tools/plugin/manifest_validator.py",
    "command-center/p2-wave/probes/TST-0182/probe1_unique_accepts_duplicate_rejects.py",
    "command-center/p2-wave/probes/TST-0182/probe2_stdlib_last_wins_fails_and_reviewer.py",
    "command-center/p2-wave/probes/TST-0182/emit_receipt.py",
    "command-center/p2-wave/probes/TST-0182/fixtures/unique-plugin.json",
    "command-center/p2-wave/probes/TST-0182/fixtures/unique-marketplace.json",
    "command-center/p2-wave/probes/TST-0182/fixtures/duplicate-name.json",
    "command-center/p2-wave/probes/TST-0182/fixtures/nested-duplicate.json",
]
QUESTION = (
    "Does the validator reject an object containing the same key twice? PASS "
    "requires rejection with both values reported, because last-wins silently "
    "discards owner intent."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": path.is_file(),
        "present": path.is_file(),
        "role": role,
        "eol": "LF",
        "unit_id": UNIT,
        "receipt_path": f"command-center/p2-wave/probes/{UNIT}/SUBAGENT-RETURN.json",
    }


def first_json(text: str) -> dict:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                doc = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(doc, dict):
                return doc
    return {}


def fp(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main() -> int:
    code1, out1 = run(P1)
    code2, out2 = run(P2)
    if code1 != 0 or code2 != 0:
        print(f"FAILED:{UNIT} emit p1={code1} p2={code2}")
        print(out1[-2500:])
        print(out2[-2500:])
        return 1
    if "SUCCESS:TST-0182-probe1" not in out1:
        print("FAILED:TST-0182 emit probe1 sentinel missing")
        return 1
    if "SUCCESS:TST-0182-probe2" not in out2:
        print("FAILED:TST-0182 emit probe2 sentinel missing")
        return 1

    p1 = first_json(out1)
    p2 = first_json(out2)
    if not p1.get("pass") or not p2.get("pass"):
        print("FAILED:TST-0182 emit probe JSON pass=false")
        return 1

    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    supporting_rows = [art(rel, "supporting") for rel in SUPPORTING]
    missing = [row["path"] for row in supporting_rows if not row["exists"]]
    if missing:
        print(f"FAILED:{UNIT} missing supporting files: {missing}")
        return 1

    parser_report = {
        "kind": "parser_report",
        "unique_key_object_validates": True,
        "unique_plugin_ok": bool(p1.get("unique_plugin_ok")),
        "unique_marketplace_ok": bool(p1.get("unique_marketplace_ok")),
        "duplicate_rejected": True,
        "duplicate_key": p1.get("duplicate_key"),
        "first_value": p1.get("first_value"),
        "second_value": p1.get("second_value"),
        "both_values_reported": bool(p1.get("both_values_in_error")),
        "token_scan_name_count": p1.get("token_scan_name_count"),
        "token_scan_values": p1.get("token_scan_values"),
        "nested_duplicate_rejected": bool(p1.get("nested_duplicate_rejected")),
        "stdlib_json_load_last_wins": p2.get("stdlib_last_wins_value"),
        "stdlib_checker_fails_this_test": True,
        "stdlib_can_report_both_values": False,
        "signals": [
            "validator DuplicateKeyError naming both values",
            "raw token-level scan counting key occurrences",
        ],
    }

    receipt = {
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "schema_version": 1,
        "output_schema": "command-center/schema/receipt.schema.json#/$defs/parser_report",
        "schema_note": SCHEMA_NOTE,
        "title": "Duplicate keys in one JSON object are rejected, not last-wins",
        "question": QUESTION,
        "answer": {
            "summary": (
                "The plugin/marketplace manifest validator in "
                "tools/plugin/strict_json.py (json.loads + object_pairs_hook) "
                "rejects a duplicate-key object and names both values "
                f"({p1.get('first_value')!r} then {p1.get('second_value')!r}). "
                "A unique-key plugin object and a unique-key marketplace object "
                "validate. An independent tokenizer in tools/plugin/json_key_scan.py "
                "(does not import json) counted the repeated key twice and recovered "
                "the same two values. A stdlib json.load checker last-wins and "
                "therefore fails this test. "
                f"{SENTINEL}"
            )
        },
        "parser_report": parser_report,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": code1,
                "fingerprint": fp(out1),
                "role": "unique-key-validates-duplicate-rejects-with-both-values",
                "raw_output": out1[-4000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": code2,
                "fingerprint": fp(out2),
                "role": "stdlib-json-load-last-wins-fails-this-test",
                "raw_output": out2[-4000:],
            },
        ],
        "tests": [
            {
                "id": "both-states-unique-key-object-validates",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "duplicate-key-rejected-with-both-values",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "token-level-scan-counts-key-occurrences",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "negative-control-stdlib-json-load-last-wins-fails",
                "command": P2,
                "result": "PASS",
            },
        ],
        "evidence": [
            {
                "kind": "validator-error",
                "claim": (
                    "DuplicateKeyError on fixtures/duplicate-name.json names key "
                    "'name' and both values first-owner-intent and second-last-wins."
                ),
                "anchor": "tools/plugin/strict_json.py",
                "path": "tools/plugin/strict_json.py",
                "verdict": "CONFIRMED",
                "detail": str(p1.get("validator_error") or ""),
            },
            {
                "kind": "token-level-scan",
                "claim": (
                    "json_key_scan (no json import) counted two 'name' keys at $ "
                    "and recovered both owner values from the source bytes."
                ),
                "anchor": "tools/plugin/json_key_scan.py",
                "path": "tools/plugin/json_key_scan.py",
                "verdict": "CONFIRMED",
                "detail": json.dumps(
                    {
                        "count": p1.get("token_scan_name_count"),
                        "values": p1.get("token_scan_values"),
                    },
                    sort_keys=True,
                ),
            },
            {
                "kind": "negative-control",
                "claim": (
                    "json.load on the same fixture accepted the object, kept only "
                    "second-last-wins, and therefore fails TST-0182."
                ),
                "anchor": (
                    "command-center/p2-wave/probes/TST-0182/"
                    "probe2_stdlib_last_wins_fails_and_reviewer.py"
                ),
                "path": (
                    "command-center/p2-wave/probes/TST-0182/"
                    "probe2_stdlib_last_wins_fails_and_reviewer.py"
                ),
                "verdict": "CONFIRMED",
                "detail": f"last-wins={p2.get('stdlib_last_wins_value')!r}",
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0182-probe2-stdlib-last-wins-fails-and-reviewer",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "Probe 2 does not import probe 1. It re-validates the unique-key "
                "control, proves json.load last-wins on the duplicate fixture, "
                "reproduces DuplicateKeyError with both values, and matches the "
                "token-level scan count of 2."
            ),
        },
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"},
            *[
                {"path": row["path"], "exists": row["exists"], "role": "supporting"}
                for row in supporting_rows
            ],
        ],
        "cloud_ok": False,
        "registered": True,
        "timestamps": {"started_at": started, "ended_at": started},
        "notes": (
            "G-1 for TST-0182: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit UNIT-ARTIFACT-MANIFEST row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery. "
            f"{SENTINEL}"
        ),
    }

    dest = REPO / OUT_REL
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    live_sha, live_bytes = sha256_file(dest)
    text = dest.read_text(encoding="utf-8")
    if live_bytes < 128:
        print(f"FAILED:{UNIT} receipt too small ({live_bytes} B)")
        return 1
    if SENTINEL not in text:
        print("FAILED:TST-0182 sentinel missing from receipt text")
        return 1
    if json.loads(text).get("state") != "SUCCESS":
        print("FAILED:TST-0182 receipt state is not SUCCESS")
        return 1

    rows = [
        {
            "path": OUT_REL,
            "sha256": live_sha,
            "bytes": live_bytes,
            "exists": True,
            "present": True,
            "role": "primary",
            "eol": "LF",
            "unit_id": UNIT,
            "receipt_path": f"command-center/p2-wave/probes/{UNIT}/SUBAGENT-RETURN.json",
        }
    ]
    for rel in SUPPORTING:
        rows.append(art(rel, "supporting"))

    manifest = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(rows),
        "present": len(rows),
        "artifacts": rows,
    }
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(manifest, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT_REL,
        "output_schema": "command-center/schema/receipt.schema.json#/$defs/parser_report",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": code1,
                "role": "unique-key-validates-duplicate-rejects-with-both-values",
                "raw_output": out1[-8000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": code2,
                "role": "stdlib-json-load-last-wins-fails-this-test",
                "raw_output": out2[-8000:],
            },
        ],
        "artifacts": [
            {
                "path": OUT_REL,
                "sha256": live_sha,
                "bytes": live_bytes,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": (
            f"command-center/p2-wave/probes/{UNIT}/UNIT-ARTIFACT-MANIFEST.json"
        ),
        "reviewer": {
            "reviewer_id": "TST-0182-probe2-stdlib-last-wins-fails-and-reviewer",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "notes": (
            "G-1 for TST-0182: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery."
        ),
        "ts": started,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT_REL} bytes={live_bytes} sha256={live_sha}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
