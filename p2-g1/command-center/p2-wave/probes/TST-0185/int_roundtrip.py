#!/usr/bin/env python3
"""TST-0185 measured layer: exact parse/emit path for 64-bit ids and precise decimals.

Exact lane: json.loads with parse_int=int (arbitrary precision) and
parse_float=decimal.Decimal; emit via json.dumps (Decimal serialized as its
exact digit string). Lossy lane (negative control): float()-based parsing.
"""
from __future__ import annotations

import json
from decimal import Decimal


class ExactEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return "num__" + str(o)  # plain str: json quotes it; emit_exact unquotes below
        return super().default(o)


class RawNumber(str):
    """Marker: emitted verbatim, without quotes, by emit_exact."""


def emit_exact(doc) -> str:
    text = json.dumps(doc, cls=ExactEncoder)
    # unquote RawNumber markers: "num__<digits>" -> <digits>
    out = []
    i = 0
    token = "\"num__"
    while i < len(text):
        j = text.find(token, i)
        if j < 0:
            out.append(text[i:])
            break
        out.append(text[i:j])
        k = text.find("\"", j + len(token))
        out.append(text[j + len(token):k])
        i = k + 1
    return "".join(out)


def parse_exact(text: str):
    return json.loads(text, parse_int=int, parse_float=Decimal)


def parse_float_lossy(text: str):
    """The known-broken lane: everything through float64."""
    return json.loads(text, parse_int=float, parse_float=float)
