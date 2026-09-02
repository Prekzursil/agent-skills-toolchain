#!/usr/bin/env python3
"""Probe 2 (signal b): byte-level non-ASCII round-trip + wrong-stage repair control.

Mechanically independent of probe 1:
  * hashlib of description.encode('utf-8') across encodings (not document ==)
  * the AUD-0085 pre-parse latin-1 pair 'repair' must corrupt U+00D7 U+00A5
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
sys.path.insert(0, str(TOOLS))

from plugin.manifest_loader import (  # noqa: E402
    CANONICAL_DESCRIPTION,
    encode_manifest,
    load_manifest_bytes,
    sample_manifest,
)

ART = REPO / "command-center/receipts/TST-0183.json"
ENCODINGS = ("utf-8", "utf-8-sig", "utf-16-le")


def fail(msg: str) -> int:
    print(f"FAILED:TST-0183-probe2 {msg}")
    return 1


def check_artifact_if_present() -> str | None:
    if not ART.is_file():
        return None
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:TST-0183" not in text:
        return "artifact sentinel absent"
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return f"artifact self-declared {st}"
    return None


def field_utf8_digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def repair_before_parse(raw: bytes):
    """Wrong pipeline stage (AUD-0085): treat U+00D7 U+00A5 as double-decoded
    UTF-8 and 'fix' the JSON *text* before json.loads.

    On correctly encoded UTF-8 this silently rewrites ×¥ (U+00D7 U+00A5) to
    ץ (U+05E5). On UTF-16LE, utf-8 decode fails or replacement-corrupts.
    """
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
    art_err = check_artifact_if_present()
    if art_err:
        return fail(art_err)

    want_bytes = CANONICAL_DESCRIPTION.encode("utf-8")
    want_digest = hashlib.sha256(want_bytes).hexdigest()
    if b"\xc3\x97\xc2\xa5" not in want_bytes:
        return fail("canonical field is missing UTF-8 for U+00D7 U+00A5")

    doc = sample_manifest()
    digests = {}
    for enc in ENCODINGS:
        raw = encode_manifest(doc, enc)
        loaded = load_manifest_bytes(raw)
        got = loaded.document["description"]
        if not isinstance(got, str):
            return fail(f"{enc} description is not a string")
        got_b = got.encode("utf-8")
        if got_b != want_bytes:
            return fail(
                f"{enc} field utf-8 {got_b.hex()} != canonical {want_bytes.hex()}"
            )
        digests[enc] = field_utf8_digest(got)

    if len(set(digests.values())) != 1 or digests["utf-8"] != want_digest:
        return fail(f"field utf-8 digests diverged {digests}")

    utf8_raw = encode_manifest(doc, "utf-8")
    mutant_ok = False
    mutant_desc = None
    try:
        mutant_doc = repair_before_parse(utf8_raw)
        mutant_desc = mutant_doc.get("description")
        mutant_ok = True
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        mutant_ok = False

    if mutant_ok:
        if not isinstance(mutant_desc, str):
            return fail("mutant description missing")
        if mutant_desc.encode("utf-8") == want_bytes:
            return fail(
                "wrong-stage repair left U+00D7 U+00A5 intact; control is not red"
            )
        if "\u05e5" not in mutant_desc:
            return fail(
                f"wrong-stage repair did not produce U+05E5; got {mutant_desc!r}"
            )
        mutant_state = "accepted-with-mojibake"
    else:
        mutant_state = "rejected"

    utf16_raw = encode_manifest(doc, "utf-16-le")
    utf16_mutant_failed = False
    try:
        repaired = repair_before_parse(utf16_raw)
        if repaired.get("description", "").encode("utf-8") != want_bytes:
            utf16_mutant_failed = True
        else:
            return fail("wrong-stage repair accepted UTF-16LE with canonical bytes")
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        utf16_mutant_failed = True
    if not utf16_mutant_failed:
        return fail("utf-16le mutant control did not go red")

    payload = {
        "canonical_utf8_hex": want_bytes.hex(),
        "canonical_utf8_sha256": want_digest,
        "encodings_byte_identical": True,
        "field_sha256": digests,
        "mutant_description": mutant_desc,
        "mutant_state": mutant_state,
        "pass": True,
        "probe": "probe2-roundtrip-and-wrong-stage",
        "unit_id": "TST-0183",
        "utf16le_mutant_red": True,
        "wrong_stage_seed": "AUD-0085 U+00D7 U+00A5 pre-parse latin-1 pair repair",
    }
    print(json.dumps(payload, sort_keys=True, ensure_ascii=True))
    print(
        f"field_sha256={want_digest[:16]}… mutant={mutant_state} "
        "utf16le_mutant_red=True"
    )
    print("SUCCESS:TST-0183-probe2 byte round-trip; wrong-stage repair went red")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
