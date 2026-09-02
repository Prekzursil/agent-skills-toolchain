#!/usr/bin/env python3
"""Probe 1: both-states consumer verify — untampered passes, one-byte flip fails."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import jsonschema  # noqa: E402

from common import OUTPUT_REL, SCHEMA_REL, SENTINEL, UNIT_ID  # noqa: E402
from engine import build_all, run_verify, tamper_one_byte  # noqa: E402


def main() -> int:
    art = REPO / OUTPUT_REL
    if not art.is_file() or art.stat().st_size <= 0:
        print("FAILED:REL-0012-probe1 receipt missing")
        return 1
    text = art.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:REL-0012-probe1 sentinel-absent")
        return 1
    doc = json.loads(text)
    if doc.get("unit_id") != UNIT_ID:
        print("FAILED:REL-0012-probe1 unit_id", doc.get("unit_id"))
        return 1
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:REL-0012-probe1 self-declared", doc.get("state"))
        return 1
    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    jsonschema.Draft7Validator(schema).validate(doc)

    with tempfile.TemporaryDirectory(prefix="rel0012-p1-") as tmp_s:
        tmp = Path(tmp_s)
        built = build_all(tmp / "out")
        clean_code, clean_cmd, clean_out = run_verify(
            built["artifact"], built["provenance"], built["tree"], built["notes"]
        )
        tampered = tmp / "artifact.tampered.zip"
        tamper_one_byte(built["artifact"], tampered)
        tamper_code, tamper_cmd, tamper_out = run_verify(
            tampered, built["provenance"], built["tree"], built["notes"]
        )

    if clean_code != 0:
        print("FAILED:REL-0012-probe1 untampered did not pass")
        print(clean_out)
        return 1
    if tamper_code == 0:
        print("FAILED:REL-0012-probe1 tampered did not fail (unconditional-pass)")
        print(tamper_out)
        return 1
    if "DIGEST-MISMATCH" not in tamper_out:
        print("FAILED:REL-0012-probe1 tamper reason not DIGEST-MISMATCH")
        print(tamper_out)
        return 1

    ver = doc.get("verification") or {}
    unt = ver.get("untampered") or {}
    tam = ver.get("tampered") or {}
    if unt.get("ok") is not True or int(unt.get("exit_code", 1)) != 0:
        print("FAILED:REL-0012-probe1 receipt untampered not recorded as pass")
        return 1
    if tam.get("ok") is not False or int(tam.get("exit_code", 0)) == 0:
        print("FAILED:REL-0012-probe1 receipt tampered not recorded as fail")
        return 1
    if "DIGEST-MISMATCH" not in str(tam.get("output") or "") and tam.get(
        "reason"
    ) != "DIGEST-MISMATCH":
        print("FAILED:REL-0012-probe1 receipt missing tamper reason")
        return 1

    tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    for tid in ("T-tamper-one-byte", "T-untampered-passes"):
        row = tests.get(tid)
        if not row or row.get("result") != "PASS":
            print(f"FAILED:REL-0012-probe1 test {tid} not PASS")
            return 1

    print(
        json.dumps(
            {
                "probe": "probe1-tamper-and-untampered",
                "untampered_exit": clean_code,
                "tampered_exit": tamper_code,
                "tamper_reason": "DIGEST-MISMATCH",
                "clean_cmd": clean_cmd,
                "tamper_cmd": tamper_cmd,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:REL-0012-probe1 both-states verify (untampered pass / tamper fail)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
