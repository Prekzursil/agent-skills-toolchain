"""Gated mojibake detector.

The catalog names the naive repair ``text.encode('latin-1').decode('utf-8')``
as subtly wrong: it is not cp1252-aware, it is not span-gated, and applying it
before a structured parse mutates logical strings (including the correctly
encoded pair U+00D7 U+00A5). This detector:

* maps characters through cp1252 (not latin-1) to recover putative UTF-8 bytes
* accepts only characteristic UTF-8 lead bytes C2/C3 (2-byte Latin-1) and E2
  (3-byte punctuation/symbols)
* rejects reversible coincidences such as times-yen (lead 0xD7)
* is intended to run on logical strings after parse, never on raw serialized
  bytes before parse
"""
from __future__ import annotations

from dataclasses import asdict, dataclass


ALLOWED_2BYTE_LEAD = frozenset({0xC2, 0xC3})
ALLOWED_3BYTE_LEAD = frozenset({0xE2})


def cp1252_byte(ch: str) -> int | None:
    try:
        raw = ch.encode("cp1252")
    except UnicodeEncodeError:
        return None
    if len(raw) != 1:
        return None
    return raw[0]


def naive_latin1_repair(text: str) -> str:
    """The catalog's forbidden one-liner. Raises or silently mangles."""
    return text.encode("latin-1").decode("utf-8")


def mutant_any_nonascii(text: str) -> bool:
    """Unusable detector: flags every non-ASCII scalar."""
    return any(ord(c) > 127 for c in text)


def _plausible_recovered_2byte(ch: str) -> bool:
    return len(ch) == 1 and 0x00A0 <= ord(ch) <= 0x00FF


def _plausible_recovered_3byte(ch: str) -> bool:
    if len(ch) != 1:
        return False
    o = ord(ch)
    return (
        0x2000 <= o <= 0x206F
        or 0x20A0 <= o <= 0x20CF
        or 0x2100 <= o <= 0x214F
        or 0x2190 <= o <= 0x21FF
        or 0x2600 <= o <= 0x26FF
        or 0x2700 <= o <= 0x27BF
    )


@dataclass(frozen=True)
class Span:
    start: int
    end: int
    original: str
    recovered: str
    utf8_hex: str
    lead_byte: int


def detect_spans(text: str) -> list[Span]:
    """Return gated mojibake spans in a logical Unicode string."""
    if not text:
        return []
    spans: list[Span] = []
    i = 0
    n = len(text)
    while i < n:
        b0 = cp1252_byte(text[i])
        if b0 in ALLOWED_3BYTE_LEAD and i + 2 < n:
            b1 = cp1252_byte(text[i + 1])
            b2 = cp1252_byte(text[i + 2])
            if (
                b1 is not None
                and b2 is not None
                and 0x80 <= b1 <= 0xBF
                and 0x80 <= b2 <= 0xBF
            ):
                raw = bytes((b0, b1, b2))
                try:
                    rec = raw.decode("utf-8")
                except UnicodeDecodeError:
                    rec = None
                if rec is not None and _plausible_recovered_3byte(rec):
                    spans.append(
                        Span(
                            start=i,
                            end=i + 3,
                            original=text[i : i + 3],
                            recovered=rec,
                            utf8_hex=raw.hex(),
                            lead_byte=b0,
                        )
                    )
                    i += 3
                    continue
        if b0 in ALLOWED_2BYTE_LEAD and i + 1 < n:
            b1 = cp1252_byte(text[i + 1])
            if b1 is not None and 0x80 <= b1 <= 0xBF:
                raw = bytes((b0, b1))
                try:
                    rec = raw.decode("utf-8")
                except UnicodeDecodeError:
                    rec = None
                if rec is not None and _plausible_recovered_2byte(rec):
                    spans.append(
                        Span(
                            start=i,
                            end=i + 2,
                            original=text[i : i + 2],
                            recovered=rec,
                            utf8_hex=raw.hex(),
                            lead_byte=b0,
                        )
                    )
                    i += 2
                    continue
        i += 1
    return spans


def ungated_reversible_spans(text: str) -> list[tuple[int, int, str, str]]:
    """Harvest-era defect: any 2-char latin-1 reversible pair, including times-yen."""
    out: list[tuple[int, int, str, str]] = []
    i = 0
    n = len(text)
    while i + 1 < n:
        pair = text[i : i + 2]
        try:
            rec = pair.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            i += 1
            continue
        if rec and rec != pair:
            out.append((i, i + 2, pair, rec))
            i += 2
            continue
        i += 1
    return out


def control_vectors() -> dict:
    bad = "caf\u00c3\u00a9"
    good_fr = "Fran\u00e7ais"
    good_jp = "\u65e5\u672c\u8a9e"
    good_dash = "\u2014"
    good_ru = "\u041f\u0440\u0438\u0432\u0435\u0442"
    collision = "\u00d7\u00a5"
    curly = "\u00e2\u20ac\u2122"
    warn = "\u00e2\u0161\u00a0"
    prod_bad = detect_spans(bad)
    prod_curly = detect_spans(curly)
    prod_warn = detect_spans(warn)
    prod_fr = detect_spans(good_fr)
    prod_jp = detect_spans(good_jp)
    prod_dash = detect_spans(good_dash)
    prod_ru = detect_spans(good_ru)
    prod_col = detect_spans(collision)
    ungated_col = ungated_reversible_spans(collision)
    naive_collision = None
    naive_collision_error = None
    try:
        naive_collision = naive_latin1_repair(collision)
    except (UnicodeEncodeError, UnicodeDecodeError) as exc:
        naive_collision_error = type(exc).__name__
    naive_curly_error = None
    try:
        naive_latin1_repair(curly)
    except (UnicodeEncodeError, UnicodeDecodeError) as exc:
        naive_curly_error = type(exc).__name__
    mutant_on_good = mutant_any_nonascii(good_fr)
    mutant_on_jp = mutant_any_nonascii(good_jp)
    return {
        "bad_fixture": bad,
        "bad_fired": bool(prod_bad),
        "curly_fixture": curly,
        "curly_fired": bool(prod_curly),
        "warn_fixture": warn,
        "warn_fired": bool(prod_warn),
        "good_fr_silent": not prod_fr,
        "good_jp_silent": not prod_jp,
        "good_dash_silent": not prod_dash,
        "good_ru_silent": not prod_ru,
        "collision": collision,
        "collision_silent": not prod_col,
        "ungated_flags_collision": bool(ungated_col),
        "naive_latin1_collision_result": naive_collision,
        "naive_latin1_collision_error": naive_collision_error,
        "naive_latin1_cannot_encode_curly": naive_curly_error is not None,
        "naive_latin1_curly_error": naive_curly_error,
        "mutant_flags_correct_french": mutant_on_good,
        "mutant_flags_japanese": mutant_on_jp,
        "production_both_states": bool(prod_bad)
        and (not prod_fr)
        and (not prod_jp)
        and (not prod_dash)
        and (not prod_ru)
        and (not prod_col),
        "mutant_killed": mutant_on_good and mutant_on_jp,
        "ungated_refuted": bool(ungated_col) and (not prod_col),
        "bad_spans": [asdict(s) for s in prod_bad],
        "curly_spans": [asdict(s) for s in prod_curly],
    }


def self_check() -> None:
    v = control_vectors()
    assert v["bad_fired"], v
    assert v["curly_fired"], v
    assert v["warn_fired"], v
    assert v["good_fr_silent"], v
    assert v["good_jp_silent"], v
    assert v["collision_silent"], v
    assert v["ungated_flags_collision"], v
    assert v["naive_latin1_collision_result"] != v["collision"], v
    assert v["naive_latin1_cannot_encode_curly"], v
    assert v["mutant_killed"], v
    assert v["production_both_states"], v

# Aliases for names used by census / control_vectors body
ALLOWED_3BYTE_LEAD = ALLOWED_3BYTE_LEAD
control_vectors = control_vectors
naive_latin1_repair = naive_latin1_repair
mutant_any_nonascii = mutant_any_nonascii

if __name__ == "__main__":
    self_check()
    print("SUCCESS:AUD-0085 detector self-check")
