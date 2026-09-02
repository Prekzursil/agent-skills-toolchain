#!/usr/bin/env python3
"""Named probe 2: byte-level code-point sequences (catalog evidence signal b).

Independent of matcher.paths_match: this probe uses unicodedata.normalize
directly and compares integer code-point lists plus UTF-8 bytes.

Negative control: byte-equality MUST fail on the NFD café fixture.
Both-states: pure ASCII code points are identical before and after NFC.
"""
from __future__ import annotations

import json
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

ART = REPO / "command-center/receipts/TST-0198.json"

NFC_CAFE = "caf\u00e9.txt"
NFD_CAFE = "cafe\u0301.txt"
NFC_GA = "\u304c.txt"
NFD_GA = "\u304b\u3099.txt"
ASCII = "readme.txt"


def cps(s: str) -> list[int]:
    return [ord(c) for c in s]


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def nfd(s: str) -> str:
    return unicodedata.normalize("NFD", s)


def _fail(msg: str) -> int:
    print(f"FAILED:TST-0198-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return _fail("receipt missing or tiny")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:TST-0198" not in ART.read_text(encoding="utf-8"):
        return _fail("sentinel absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return _fail(f"self-declared:{doc.get('state')}")

    cafe_nfc_cp = cps(NFC_CAFE)
    cafe_nfd_cp = cps(NFD_CAFE)
    ga_nfc_cp = cps(NFC_GA)
    ga_nfd_cp = cps(NFD_GA)
    ascii_cp = cps(ASCII)

    byte_eq_cafe = NFC_CAFE.encode("utf-8") == NFD_CAFE.encode("utf-8")
    str_eq_cafe = NFC_CAFE == NFD_CAFE
    nfc_eq_cafe = nfc(NFC_CAFE) == nfc(NFD_CAFE)
    nfc_eq_ga = nfc(NFC_GA) == nfc(NFD_GA)
    ascii_nfc = nfc(ASCII) == ASCII == nfd(ASCII)
    ascii_bytes = ASCII.encode("utf-8") == nfc(ASCII).encode("utf-8")

    # Round-trip of each encoding through NFC must land on the NFC sequence.
    cafe_round = cps(nfc(NFD_CAFE)) == cafe_nfc_cp == cps(nfc(NFC_CAFE))
    ga_round = cps(nfc(NFD_GA)) == ga_nfc_cp == cps(nfc(NFC_GA))

    # Sequences must actually differ (otherwise the fixture is invalid).
    cafe_differs = cafe_nfc_cp != cafe_nfd_cp
    ga_differs = ga_nfc_cp != ga_nfd_cp
    cafe_nfd_has_combining = 0x0301 in cafe_nfd_cp
    cafe_nfc_precomposed = 0x00E9 in cafe_nfc_cp
    ga_nfd_has_dakuten = 0x3099 in ga_nfd_cp
    ga_nfc_precomposed = 0x304C in ga_nfc_cp

    rec_enc = doc.get("codepoint_sequences") or {}
    rec_cafe_nfc = rec_enc.get("cafe_nfc_codepoints")
    rec_cafe_nfd = rec_enc.get("cafe_nfd_codepoints")
    if rec_cafe_nfc != cafe_nfc_cp:
        return _fail(f"receipt cafe NFC cps drift {rec_cafe_nfc} != {cafe_nfc_cp}")
    if rec_cafe_nfd != cafe_nfd_cp:
        return _fail(f"receipt cafe NFD cps drift {rec_cafe_nfd} != {cafe_nfd_cp}")
    if rec_enc.get("byte_equal_cafe") is not False:
        return _fail("receipt did not record byte-equality failure on café")
    if rec_enc.get("nfc_equal_cafe") is not True:
        return _fail("receipt did not record NFC equality on café")

    negative_fired = (not byte_eq_cafe) and (not str_eq_cafe) and cafe_differs
    both_states_ascii = ascii_nfc and ascii_bytes and ascii_cp == cps(nfc(ASCII))
    ok = (
        negative_fired
        and both_states_ascii
        and nfc_eq_cafe
        and nfc_eq_ga
        and cafe_round
        and ga_round
        and cafe_nfd_has_combining
        and cafe_nfc_precomposed
        and ga_nfd_has_dakuten
        and ga_nfc_precomposed
        and ga_differs
        and doc.get("chosen_normal_form") == "NFC"
    )
    summary = {
        "probe": "probe2-codepoints",
        "unit_id": "TST-0198",
        "pass": ok,
        "cafe_nfc_codepoints": cafe_nfc_cp,
        "cafe_nfd_codepoints": cafe_nfd_cp,
        "ga_nfc_codepoints": ga_nfc_cp,
        "ga_nfd_codepoints": ga_nfd_cp,
        "ascii_codepoints": ascii_cp,
        "byte_equal_cafe": byte_eq_cafe,
        "str_equal_cafe": str_eq_cafe,
        "nfc_equal_cafe": nfc_eq_cafe,
        "nfc_equal_ga": nfc_eq_ga,
        "ascii_trivial": both_states_ascii,
        "negative_control_fired": negative_fired,
        "independent_of": "matcher.paths_match",
        "method": "unicodedata.normalize + ord() sequences + utf-8 bytes",
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"cafe nfc={cafe_nfc_cp} nfd={cafe_nfd_cp} "
        f"byte_eq={byte_eq_cafe} nfc_eq={nfc_eq_cafe}"
    )
    print(
        f"ga nfc={ga_nfc_cp} nfd={ga_nfd_cp} nfc_eq={nfc_eq_ga} "
        f"ascii_trivial={both_states_ascii} negative_fired={negative_fired}"
    )
    if not ok:
        return _fail("code-point campaign not ok")
    print("SUCCESS:TST-0198-probe2 code-point sequences and byte-equality negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
