#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0183.json (parser_report)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
sys.path.insert(0, str(TOOLS))

from plugin.manifest_loader import (  # noqa: E402
    CANONICAL_DESCRIPTION,
    POLICY,
    encode_manifest,
    load_manifest_bytes,
    sample_manifest,
)

OUT = "command-center/receipts/TST-0183.json"
SCHEMA = "command-center/schema/receipt.schema.json#/$defs/parser_report"
SENTINEL = "SUCCESS:TST-0183"
SUT = "tools/plugin/manifest_loader.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0183/probe1_encoding_outcomes.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0183/probe2_roundtrip_and_wrong_stage.py"
)
QUESTION = (
    "How does the loader treat a UTF-8-with-BOM and a UTF-16LE manifest? "
    "PASS requires a single declared behavior (accept-and-normalize OR reject "
    "with a precise message) applied consistently, and zero mojibake in any "
    "accepted field value."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def naive_utf8(raw: bytes) -> str:
    try:
        json.loads(raw.decode("utf-8"))
        return "accepted"
    except UnicodeDecodeError:
        return "rejected:UnicodeDecodeError"
    except json.JSONDecodeError as exc:
        return f"rejected:JSONDecodeError:{exc.msg}"


def repair_before_parse(raw: bytes):
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("utf-8", errors="replace")
    out: list[str] = []
    i = 0
    while i < len(text):
        if i + 1 < len(text) and ord(text[i]) <= 0xFF and ord(text[i + 1]) <= 0xFF:
            pair = bytes((ord(text[i]), ord(text[i + 1])))
            try:
                decoded = pair.decode("utf-8")
                if decoded != pair.decode("latin-1"):
                    out.append(decoded)
                    i += 2
                    continue
            except UnicodeDecodeError:
                pass
        out.append(text[i])
        i += 1
    return json.loads("".join(out))


def main() -> int:
    fixture = sample_manifest()
    want = CANONICAL_DESCRIPTION.encode("utf-8")
    want_sha = hashlib.sha256(want).hexdigest()
    encodings = ("utf-8", "utf-8-sig", "utf-16-le", "utf-16-be")
    rows = []
    for enc in encodings:
        raw = encode_manifest(fixture, enc)
        result = load_manifest_bytes(raw)
        field = result.document["description"]
        field_b = field.encode("utf-8")
        if field_b != want:
            print(f"FAILED:TST-0183 emit {enc} field mojibake")
            return 1
        if result.document != fixture:
            print(f"FAILED:TST-0183 emit {enc} document != utf-8 fixture")
            return 1
        if result.policy != POLICY:
            print(f"FAILED:TST-0183 emit {enc} policy {result.policy}")
            return 1
        rows.append(
            {
                "accepted": True,
                "bom": result.bom,
                "detected_encoding": result.encoding,
                "field_utf8_sha256": hashlib.sha256(field_b).hexdigest(),
                "input_encoding": enc,
                "naive_utf8_outcome": naive_utf8(raw),
                "policy": result.policy,
                "source_bytes": result.source_bytes,
            }
        )

    utf8_row = next(r for r in rows if r["input_encoding"] == "utf-8")
    bom_row = next(r for r in rows if r["input_encoding"] == "utf-8-sig")
    le_row = next(r for r in rows if r["input_encoding"] == "utf-16-le")
    if utf8_row["naive_utf8_outcome"] != "accepted":
        print("FAILED:TST-0183 emit naive utf-8 rejected plain UTF-8")
        return 1
    if not bom_row["naive_utf8_outcome"].startswith("rejected"):
        print("FAILED:TST-0183 emit naive utf-8 accepted BOM")
        return 1
    if not le_row["naive_utf8_outcome"].startswith("rejected"):
        print("FAILED:TST-0183 emit naive utf-8 accepted UTF-16LE")
        return 1

    mutant_desc = repair_before_parse(encode_manifest(fixture, "utf-8"))["description"]
    if mutant_desc.encode("utf-8") == want or "\u05e5" not in mutant_desc:
        print("FAILED:TST-0183 emit wrong-stage control did not corrupt ×¥")
        return 1

    try:
        load_manifest_bytes(b'{"name": "x",}\n')
        print("FAILED:TST-0183 emit trailing comma was accepted")
        return 1
    except Exception as exc:
        reject_msg = str(exc)
        if "reject:json" not in reject_msg:
            print(f"FAILED:TST-0183 emit imprecise json reject {reject_msg}")
            return 1

    sut_sha, sut_bytes = sha256_file(REPO / SUT)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    report = {
        "answer": {
            "declared_policy": POLICY,
            "mojibake_in_accepted_fields": False,
            "summary": (
                "The live plugin/marketplace manifest loader "
                "(tools/plugin/manifest_loader.py), now used by "
                "marketplace.update.effective_permissions_from_disk, declares a "
                "single policy accept-and-normalize. UTF-8, UTF-8-with-BOM, "
                "UTF-16LE, and UTF-16BE all parse to the same document; the "
                "non-ASCII description field round-trips to identical UTF-8 "
                f"bytes (sha256={want_sha}). A naive json.loads(utf-8) path "
                "rejects BOM and UTF-16LE, so the policy is load-bearing. "
                "Pre-parse latin-1 pair repair (AUD-0085 U+00D7 U+00A5) rewrites "
                "the field to U+05E5; production never runs that repair."
            ),
            "utf16le": "accept-and-normalize",
            "utf8_plain": "accept-and-normalize",
            "utf8_with_bom": "accept-and-normalize",
        },
        "both_states": {
            "naive_stdlib_utf8_accepts_plain_utf8": True,
            "naive_stdlib_utf8_rejects_bom": True,
            "naive_stdlib_utf8_rejects_utf16le": True,
            "plain_utf8_accepted_identical_fields": True,
        },
        "cloud_ok": False,
        "encodings": rows,
        "evidence": [
            {
                "anchor": SUT,
                "claim": (
                    "Loader outcome per encoding: UTF-8, UTF-8-with-BOM, and "
                    "UTF-16LE are all accepted under accept-and-normalize and "
                    "yield the same logical document as plain UTF-8."
                ),
                "probe": P1,
                "signal": "a-loader-outcome-per-encoding",
                "status": "PASS",
            },
            {
                "anchor": SUT,
                "claim": (
                    "Byte-level comparison: description.encode('utf-8') is "
                    f"{want.hex()} (sha256={want_sha}) for every accepted "
                    "encoding. Wrong-stage pre-parse repair corrupts U+00D7 "
                    "U+00A5 to U+05E5 on this estate."
                ),
                "probe": P2,
                "signal": "b-byte-roundtrip-nonascii",
                "status": "PASS",
            },
        ],
        "id": "TST-0183",
        "measured_at": now,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "question": QUESTION,
        "regression_seed": {
            "estate": "AUD-0085 encoding/BOM/mojibake census",
            "mutant_description_contains_u05e5": True,
            "mutant_field_utf8_hex": mutant_desc.encode("utf-8").hex(),
            "production_field_utf8_hex": want.hex(),
            "seed": "mojibake repaired at the wrong pipeline stage",
            "wrong_stage": "latin-1 pair decode of JSON text before json.loads",
        },
        "reject_control": {
            "fixture": "trailing-comma JSON",
            "message_prefix": "reject:json",
            "precise": True,
            "sample": reject_msg,
        },
        "report_kind": "parser_report",
        "roundtrip": {
            "canonical_description": CANONICAL_DESCRIPTION,
            "field_utf8_hex": want.hex(),
            "field_utf8_sha256": want_sha,
            "identical_across_encodings": True,
        },
        "schema_file_present": (REPO / "command-center/schema/receipt.schema.json").is_file(),
        "sentinel": SENTINEL,
        "state": "SUCCESS",
        "sut": {
            "bytes": sut_bytes,
            "path": SUT,
            "sha256": sut_sha,
            "wired_into": "tools/marketplace/update.py:effective_permissions_from_disk",
        },
        "tests_required": [
            "both-states control: plain UTF-8 is accepted with identical field values",
            "regression seed: mojibake repaired at the wrong pipeline stage, measured on this estate",
        ],
        "title": "BOM and UTF-16 manifests behave deterministically and never mojibake",
        "unit_id": "TST-0183",
    }
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT} sentinel={SENTINEL} encodings={len(rows)}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
