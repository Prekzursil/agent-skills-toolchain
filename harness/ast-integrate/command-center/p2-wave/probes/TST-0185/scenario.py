"""Property corpus and live round-trip oracle for TST-0185.

Two independent signals, both required on every case:
  (a) lexical equality of the emitted number token
  (b) Decimal-typed equality after re-parse

The float-based parser is the negative control, not the path under test.
"""
from __future__ import annotations

import json
import math
import random
import sys
from decimal import Decimal, getcontext
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIX = HERE / "fixtures"
sys.path.insert(0, str(REPO))

from tools.plugin.json_codec import (  # noqa: E402
    as_decimal,
    assert_no_float,
    emit,
    extract_number_tokens,
    parse,
)

getcontext().prec = 64

TWO_40 = 2**40
TWO_53 = 2**53
TWO_63 = 2**63
SEED = 185
N_IDS = 128
N_DECIMALS = 128

INTEGER_EDGES = (
    TWO_40,
    TWO_40 + 1,
    2**52,
    TWO_53 - 2,
    TWO_53 - 1,
    TWO_53,
    TWO_53 + 1,
    TWO_53 + 2,
    2**62,
    TWO_63 - 1,
    TWO_63,
)

PLUGIN_FIXTURE = FIX / "plugin-manifest.json"
MARKET_FIXTURE = FIX / "marketplace-entry.json"


def wrap_id(token: str) -> str:
    return '{"package_id": ' + token + "}"


def wrap_score(token: str) -> str:
    return '{"quality_score": ' + token + "}"


def log_uniform_id(rng: random.Random) -> int:
    lo = math.log2(TWO_40)
    hi = math.log2(TWO_63)
    n = int(2 ** rng.uniform(lo, hi))
    return min(max(n, TWO_40), TWO_63)


def generated_ids(n: int = N_IDS, *, seed: int = SEED) -> list[int]:
    rng = random.Random(seed)
    out: list[int] = list(INTEGER_EDGES)
    seen = set(out)
    while len(out) < n:
        candidate = log_uniform_id(rng)
        if candidate not in seen:
            seen.add(candidate)
            out.append(candidate)
    return out


def generated_decimal_tokens(n: int = N_DECIMALS, *, seed: int = SEED) -> list[str]:
    """Canonical 20-significant-digit tokens (more than a double can hold)."""
    rng = random.Random(seed + 1)
    tokens: list[str] = [
        "1.2345678901234567890",
        "9.8765432109876543210",
        "1.0000000000000000001",
        "3.1415926535897932384",
        "-1.2345678901234567890",
        "2.7182818284590452353",
    ]
    seen = set(tokens)
    while len(tokens) < n:
        digits = [str(rng.randint(1, 9))] + [str(rng.randint(0, 9)) for _ in range(19)]
        significand = "".join(digits)
        token = significand[0] + "." + significand[1:]
        if rng.random() < 0.15:
            token = "-" + token
        if token not in seen:
            seen.add(token)
            tokens.append(token)
    return tokens


def float_parser_value(token: str) -> float:
    """Explicitly float-based: the control the catalog names."""
    return float(token)


def float_json_parser(text: str) -> Any:
    return json.loads(text, parse_int=float, parse_float=float)


def integer_loses_in_float(n: int) -> bool:
    return int(float(n)) != n


def decimal_loses_in_float(token: str) -> bool:
    typed = Decimal(token)
    as_float = float(token)
    try:
        recovered = Decimal(str(as_float))
    except Exception:
        return True
    return recovered != typed


def evaluate_number_document(text: str, expected_token: str) -> dict[str, Any]:
    parsed = parse(text)
    assert_no_float(parsed)
    emitted = emit(parsed)
    tokens_out = extract_number_tokens(emitted)
    if len(tokens_out) != 1:
        return {
            "pass": False,
            "reason": f"expected 1 emitted number token, got {tokens_out!r}",
            "expected_token": expected_token,
        }
    emitted_token = tokens_out[0]
    reparsed = parse(emitted)
    assert_no_float(reparsed)
    if not isinstance(parsed, dict) or len(parsed) != 1:
        return {"pass": False, "reason": "fixture shape", "expected_token": expected_token}
    key = next(iter(parsed))
    parsed_value = parsed[key]
    reparsed_value = reparsed[key]
    token_equal = emitted_token == expected_token
    typed_equal = as_decimal(parsed_value) == Decimal(expected_token)
    reparsed_equal = as_decimal(reparsed_value) == Decimal(expected_token)
    return {
        "pass": bool(token_equal and typed_equal and reparsed_equal),
        "expected_token": expected_token,
        "emitted_token": emitted_token,
        "token_equal": token_equal,
        "decimal_equal": typed_equal and reparsed_equal,
        "parsed_kind": type(parsed_value).__name__,
    }


def evaluate_integer(n: int) -> dict[str, Any]:
    token = str(n)
    row = evaluate_number_document(wrap_id(token), token)
    row["kind"] = "int64-id"
    row["value_int"] = n
    row["above_2_53"] = n > TWO_53
    row["float_int_equal"] = int(float(n)) == n
    row["float_loses"] = integer_loses_in_float(n)
    return row


def evaluate_decimal_token(token: str) -> dict[str, Any]:
    row = evaluate_number_document(wrap_score(token), token)
    row["kind"] = "decimal-20sig"
    row["float_loses"] = decimal_loses_in_float(token)
    row["significant_digits"] = sum(ch.isdigit() for ch in token.lstrip("-"))
    return row


def evaluate_fixture(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    source_tokens = extract_number_tokens(text)
    parsed = parse(text)
    assert_no_float(parsed)
    # Keep object key order so number tokens stay in source document order.
    emitted = emit(parsed)
    emitted_tokens = extract_number_tokens(emitted)
    reparsed = parse(emitted)
    token_equal = source_tokens == emitted_tokens
    typed_ok = True
    source_values = _numbers_in_order(parsed)
    reparsed_values = _numbers_in_order(reparsed)
    if len(source_values) != len(source_tokens) or len(reparsed_values) != len(source_tokens):
        typed_ok = False
    else:
        for value, token in zip(source_values, source_tokens):
            if as_decimal(value) != Decimal(token):
                typed_ok = False
                break
        for value, token in zip(reparsed_values, source_tokens):
            if as_decimal(value) != Decimal(token):
                typed_ok = False
                break
    rel = path.relative_to(REPO).as_posix()
    return {
        "path": rel,
        "pass": bool(token_equal and typed_ok and source_tokens),
        "source_tokens": source_tokens,
        "emitted_tokens": emitted_tokens,
        "token_equal": token_equal,
        "decimal_equal": typed_ok,
        "source_tokens": source_tokens,
        "token_equal": token_equal,
        "decimal_equal": typed_ok,
        "n_numbers": len(source_tokens),
    }


def _numbers_in_order(value: Any) -> list[Any]:
    out: list[Any] = []

    def walk(node: Any) -> None:
        if isinstance(node, bool) or node is None:
            return
        if isinstance(node, (int, Decimal)):
            out.append(node)
            return
        if isinstance(node, list):
            for item in node:
                walk(item)
            return
        if isinstance(node, dict):
            for item in node.values():
                walk(item)

    walk(value)
    return out


def run_property_suite() -> dict[str, Any]:
    id_rows = [evaluate_integer(n) for n in generated_ids()]
    dec_rows = [evaluate_decimal_token(tok) for tok in generated_decimal_tokens()]
    plugin = evaluate_fixture(PLUGIN_FIXTURE)
    market = evaluate_fixture(MARKET_FIXTURE)
    id_fail = [r for r in id_rows if not r["pass"]]
    dec_fail = [r for r in dec_rows if not r["pass"]]
    above = [r for r in id_rows if r["above_2_53"]]
    if not above:
        raise RuntimeError("corpus produced no ids above 2^53")
    if not all(r["significant_digits"] >= 20 for r in dec_rows):
        raise RuntimeError("decimal corpus dropped below 20 significant digits")
    passed = (
        not id_fail
        and not dec_fail
        and plugin["pass"]
        and market["pass"]
    )
    return {
        "pass": passed,
        "n_ids": len(id_rows),
        "n_ids_above_2_53": len(above),
        "n_id_fail": len(id_fail),
        "n_decimals": len(dec_rows),
        "n_decimal_fail": len(dec_fail),
        "id_edge_tokens": [str(n) for n in INTEGER_EDGES],
        "plugin_fixture": plugin,
        "marketplace_fixture": market,
        "n_ids": len(id_rows),
        "n_ids_above_2_53": len(above),
        "n_id_fail": len(id_fail),
        "n_decimals": len(dec_rows),
        "n_decimal_fail": len(dec_fail),
        "id_edge_tokens": [str(n) for n in INTEGER_EDGES],
        "plugin_fixture": plugin,
        "marketplace_fixture": market,
        "id_fail_samples": id_fail[:5],
        "decimal_fail_samples": dec_fail[:5],
        "signal_a": "string equality of the emitted token",
        "signal_b": "Decimal-typed comparison after re-parse",
    }


def run_float_negative_control() -> dict[str, Any]:
    """Both-states on the float parser, plus our path on the same tokens."""
    exact = TWO_53
    lost = TWO_53 + 1
    exact_float_ok = int(float(exact)) == exact
    lost_float_ok = int(float(lost)) == lost
    # JSON float parser (parse_int=float) must lose 2^53+1
    json_lost = float_json_parser(str(lost))
    json_exact = float_json_parser(str(exact))
    json_lost_fails = json_lost != lost
    json_exact_ok = json_exact == float(exact) and int(json_exact) == exact

    lossless_exact = evaluate_integer(exact)
    lossless_lost = evaluate_integer(lost)

    decimal_token = "1.2345678901234567890"
    float_dec_loses = decimal_loses_in_float(decimal_token)
    lossless_dec = evaluate_decimal_token(decimal_token)

    # 20-digit decimal through json.loads default (float) must not equal Decimal
    default_json = json.loads(wrap_score(decimal_token))
    default_is_float = isinstance(default_json["quality_score"], float)
    default_ne = Decimal(str(default_json["quality_score"])) != Decimal(decimal_token)

    fired = (
        exact_float_ok
        and (not lost_float_ok)
        and json_lost_fails
        and json_exact_ok
        and lossless_exact["pass"]
        and lossless_lost["pass"]
        and float_dec_loses
        and lossless_dec["pass"]
        and default_is_float
        and default_ne
    )
    return {
        "pass": fired,
        "float_preserves_2_53": exact_float_ok,
        "float_preserves_2_53_plus_1": lost_float_ok,
        "json_parse_int_float_loses_2_53_plus_1": json_lost_fails,
        "json_parse_int_float_preserves_2_53": json_exact_ok,
        "lossless_preserves_2_53": lossless_exact["pass"],
        "lossless_preserves_2_53_plus_1": lossless_lost["pass"],
        "float_loses_20_digit_decimal": float_dec_loses,
        "lossless_preserves_20_digit_decimal": lossless_dec["pass"],
        "stdlib_json_loads_uses_float_for_decimals": default_is_float,
        "stdlib_json_loads_decimal_mismatch": default_ne,
        "float_preserves_2_53": exact_float_ok,
        "float_preserves_2_53_plus_1": lost_float_ok,
        "json_parse_int_float_loses_2_53_plus_1": json_lost_fails,
        "lossless_preserves_2_53_plus_1": lossless_lost["pass"],
        "float_loses_20_digit_decimal": float_dec_loses,
        "stdlib_json_loads_uses_float_for_decimals": default_is_float,
        "lost_id": lost,
        "exact_id": exact,
        "json_lost_value": json_lost,
    }


def run_all() -> dict[str, Any]:
    props = run_property_suite()
    control = run_float_negative_control()
    return {
        "pass": bool(props["pass"] and control["pass"]),
        "property": props,
        "float_control": control,
        "codec": "tools/plugin/json_codec.py",
        "seed": SEED,
        "seed": SEED,
        "float_control": control,
        "float_control": control,
    }


run_property_suite = run_property_suite
run_float_negative_control = run_float_negative_control
run_all = run_all
SEED = SEED


if __name__ == "__main__":
    result = run_all()
    print(json.dumps({k: result[k] for k in ("pass", "seed", "codec")}, sort_keys=True))
    print(json.dumps(result["property"], sort_keys=True, default=str)[:2000])
    print(json.dumps(result["float_control"], sort_keys=True, default=str)[:2000])
    raise SystemExit(0 if result["pass"] else 1)
