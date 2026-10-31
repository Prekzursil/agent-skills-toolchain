"""Lossless JSON codec: ints stay ints, decimals stay Decimal (TST-0185)."""
from __future__ import annotations

from decimal import Decimal
import json
import re
from typing import Any

_NUM = re.compile(r"-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?")


def as_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        raise TypeError("bool is not a number")
    if isinstance(value, int):
        return Decimal(value)
    return Decimal(str(value))


def _parse_number(s: str) -> int | Decimal:
    if any(ch in s for ch in ".eE"):
        return Decimal(s)
    return int(s)


def parse(text: str) -> Any:
    return json.loads(text, parse_int=int, parse_float=lambda s: Decimal(s))


def _default(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return obj
    raise TypeError(type(obj))


class _Encoder(json.JSONEncoder):
    def iterencode(self, o: Any, _one_shot: bool = False):  # type: ignore[override]
        def _enc(value: Any) -> str:
            if isinstance(value, Decimal):
                text = format(value, "f")
                return text
            if isinstance(value, bool) or value is None:
                return json.dumps(value)
            if isinstance(value, int):
                return str(value)
            if isinstance(value, str):
                return json.dumps(value, ensure_ascii=False)
            if isinstance(value, list):
                return "[" + ",".join(_enc(v) for v in value) + "]"
            if isinstance(value, dict):
                parts = []
                for k, v in value.items():
                    parts.append(json.dumps(str(k), ensure_ascii=False) + ":" + _enc(v))
                return "{" + ",".join(parts) + "}"
            return json.dumps(value, ensure_ascii=False)

        yield _enc(o)


def emit(value: Any) -> str:
    return "".join(_Encoder().iterencode(value))


def extract_number_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    i = 0
    n = len(text)
    in_str = False
    esc = False
    while i < n:
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            i += 1
            continue
        if ch == '"':
            in_str = True
            i += 1
            continue
        m = _NUM.match(text, i)
        if m:
            tokens.append(m.group(0))
            i = m.end()
            continue
        i += 1
    return tokens


def assert_no_float(value: Any) -> None:
    if isinstance(value, float) and not isinstance(value, int):
        raise TypeError("float leaked into codec tree")
    if isinstance(value, list):
        for item in value:
            assert_no_float(item)
    elif isinstance(value, dict):
        for item in value.values():
            assert_no_float(item)
