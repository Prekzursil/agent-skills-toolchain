"""GENERATOR for the shared conformance corpus.

Run: ``python fixtures/build_corpus.py`` (from tools/agentspec-js). Writes
``fixtures/canonical-corpus.json`` with LF endings and ASCII-only output.

The generator exists so every non-ASCII literal in the corpus is written as an explicit
``\\uXXXX`` escape rather than a raw byte. That is not style: a raw U+2028 in a source file
splits the physical line and silently corrupts the file, which is a MEASURED failure from the
scout probe that produced this corpus's rule set.

The corpus is the CONTRACT. `src/corpus.mjs` and `parity/emit_py.py` are two independent
readers of it; the parity oracle byte-compares what they emit.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

OUT = Path(__file__).with_name("canonical-corpus.json")


def num(text: str) -> dict[str, str]:
    """A DOUBLE (Python float / JS number)."""
    return {"num": text}


def integer(text: str) -> dict[str, str]:
    """An INTEGER-TYPED value (Python int / JS BigInt). Bounded by R7."""
    return {"int": text}


def text(value: str) -> dict[str, str]:
    return {"str": value}


def arr(*items: Any) -> dict[str, Any]:
    return {"arr": list(items)}


def obj(*pairs: tuple[str, Any]) -> dict[str, Any]:
    return {"obj": [[key, value] for key, value in pairs]}


NULL = {"null": True}
TRUE = {"bool": True}
FALSE = {"bool": False}


def ok(case_id: str, value: Any, expected: str) -> dict[str, Any]:
    return {"id": case_id, "value": value, "expect": {"ok": expected}}


def reject(case_id: str, value: Any, code: str) -> dict[str, Any]:
    return {"id": case_id, "value": value, "expect": {"reject": code}}


def cases() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    # ---- literals -------------------------------------------------------------------
    rows += [
        ok("lit/null", NULL, "null"),
        ok("lit/true", TRUE, "true"),
        ok("lit/false", FALSE, "false"),
    ]

    # ---- R5/R6/R9 number rendering (ECMAScript Number::toString) ---------------------
    number_rows = [
        ("int-1", integer("1"), "1"),
        ("int-zero", integer("0"), "0"),
        ("int-neg", integer("-42"), "-42"),
        ("int-max-safe", integer("9007199254740991"), "9007199254740991"),
        ("int-min-safe", integer("-9007199254740991"), "-9007199254740991"),
        ("float-1.0", num("1.0"), "1"),
        ("float-3.0", num("3.0"), "3"),
        ("float-100.0", num("100.0"), "100"),
        ("float-pos-zero", num("0.0"), "0"),
        ("float-neg-zero", num("-0"), "0"),
        ("float-0.1", num("0.1"), "0.1"),
        ("float-0.1plus0.2", num("0.30000000000000004"), "0.30000000000000004"),
        ("float-1.5", num("1.5"), "1.5"),
        ("float-neg-1.5", num("-1.5"), "-1.5"),
        ("float-1e-4", num("1e-4"), "0.0001"),
        ("float-1e-5", num("1e-5"), "0.00001"),
        ("float-1e-6", num("1e-6"), "0.000001"),
        ("float-1e-7", num("1e-7"), "1e-7"),
        ("float-1.5e-7", num("1.5e-7"), "1.5e-7"),
        ("float-1e15", num("1e15"), "1000000000000000"),
        ("float-1e16", num("1e16"), "10000000000000000"),
        ("float-1e20", num("1e20"), "100000000000000000000"),
        ("float-1e21", num("1e21"), "1e+21"),
        ("float-neg-1e21", num("-1e21"), "-1e+21"),
        ("float-1e100", num("1e100"), "1e+100"),
        ("float-max", num("1.7976931348623157e308"), "1.7976931348623157e+308"),
        ("float-min-subnormal", num("5e-324"), "5e-324"),
        ("float-1.5e300", num("1.5e300"), "1.5e+300"),
        ("float-2pow53", num("9007199254740992"), "9007199254740992"),
        ("float-2pow63", num("9223372036854775808"), "9223372036854776000"),
    ]
    rows += [
        ok(f"num/{name}", value, expected) for name, value, expected in number_rows
    ]

    # ---- R7 / R8 rejections ----------------------------------------------------------
    rows += [
        reject(
            "num/int-2pow53", integer("9007199254740992"), "schema-invalid-int-range"
        ),
        reject(
            "num/int-2pow53-plus1",
            integer("9007199254740993"),
            "schema-invalid-int-range",
        ),
        reject("num/int-10pow30", integer("1" + "0" * 30), "schema-invalid-int-range"),
        reject(
            "num/int-neg-2pow63",
            integer("-9223372036854775808"),
            "schema-invalid-int-range",
        ),
        reject("num/nan", num("NaN"), "schema-invalid-nonfinite"),
        reject("num/inf", num("Infinity"), "schema-invalid-nonfinite"),
        reject("num/neg-inf", num("-Infinity"), "schema-invalid-nonfinite"),
    ]

    # ---- R10 / R11 string escaping ---------------------------------------------------
    string_rows = [
        ("empty", "", '""'),
        ("ascii", "abc", '"abc"'),
        ("short-escapes", "\b\f\n\r\t", '"\\b\\f\\n\\r\\t"'),
        ("quote-backslash", 'a"b\\c', '"a\\"b\\\\c"'),
        ("solidus", "a/b", '"a/b"'),
        ("nul", "\u0000", '"\\u0000"'),
        ("ctrl-1f", "\u001f", '"\\u001f"'),
        ("del-7f", "\u007f", '"\u007f"'),
        ("e-acute", "é", '"é"'),
        ("nbsp", "\u00a0", '"\u00a0"'),
        ("c1-0x80", "\u0080", '"\u0080"'),
        ("cjk", "日本語", '"日本語"'),
        ("combining", "é", '"é"'),
        ("bom-inside", "\ufeff", '"\ufeff"'),
        ("ffff", "\uffff", '"\uffff"'),
        ("u2028", "\u2028", '"\\u2028"'),
        ("u2029", "\u2029", '"\\u2029"'),
        ("astral-pair", "😀", '"\U0001f600"'),
        ("astral-max", "􏿿", '"\U0010ffff"'),
        ("lone-high-surrogate", "\ud800", '"\\ud800"'),
        ("lone-low-surrogate", "\udc00", '"\\udc00"'),
        ("high-then-nonlow", "\ud800a", '"\\ud800a"'),
        ("high-then-high", "\ud800\ud800", '"\\ud800\\ud800"'),
        ("pair-then-lone", "😀\ud800", '"\U0001f600\\ud800"'),
    ]
    rows += [
        ok(f"str/{name}", text(value), expected)
        for name, value, expected in string_rows
    ]

    # ---- R2 / R3 containers ----------------------------------------------------------
    rows += [
        ok("arr/empty", arr(), "[]"),
        ok("arr/two-ints", arr(integer("1"), integer("2")), "[1,2]"),
        ok("arr/nested-empty", arr(arr(), arr(obj())), "[[],[{}]]"),
        ok(
            "arr/mixed",
            arr(integer("1"), num("1.0"), text("a"), NULL, TRUE),
            '[1,1,"a",null,true]',
        ),
        ok("obj/empty", obj(), "{}"),
        ok("obj/one", obj(("a", integer("1"))), '{"a":1}'),
        ok(
            "obj/insertion-order-ba",
            obj(("b", integer("1")), ("a", integer("2"))),
            '{"a":2,"b":1}',
        ),
        ok(
            "obj/mixed-case",
            obj(
                ("b", integer("1")),
                ("A", integer("2")),
                ("a", integer("3")),
                ("B", integer("4")),
            ),
            '{"A":2,"B":4,"a":3,"b":1}',
        ),
        # V8 emits integer-like keys FIRST in numeric order; Python sorts them as text.
        # Neither wins: R3 imposes UTF-16 code-unit order on both sides.
        ok(
            "obj/numeric-like-keys",
            obj(
                ("10", text("x")),
                ("2", text("y")),
                ("b", text("z")),
                ("1", text("w")),
            ),
            '{"1":"w","10":"x","2":"y","b":"z"}',
        ),
        ok(
            "obj/numeric-and-empty-key",
            obj(
                ("2", integer("1")),
                ("", integer("2")),
                ("01", integer("3")),
                ("1", integer("4")),
            ),
            '{"":2,"01":3,"1":4,"2":1}',
        ),
        ok(
            "obj/nested-empties",
            obj(("a", arr()), ("b", obj()), ("c", obj(("d", arr())))),
            '{"a":[],"b":{},"c":{"d":[]}}',
        ),
        ok(
            "obj/unicode-keys",
            obj(("é", integer("1")), ("z", integer("2")), ("日", integer("3"))),
            '{"z":2,"é":1,"日":3}',
        ),
        # An astral key sorts BEFORE U+FFFF: its lead surrogate 0xD83D < 0xFFFF. Code-POINT
        # order (Python's default) gets this backwards.
        ok(
            "obj/sort-astral-vs-ffff",
            obj(("\uffff", integer("1")), ("😀", integer("2"))),
            '{"\U0001f600":2,"\uffff":1}',
        ),
        ok("obj/key-with-escape", obj(('a"b', integer("1"))), '{"a\\"b":1}'),
        ok("obj/key-with-newline", obj(("a\nb", integer("1"))), '{"a\\nb":1}'),
        # __proto__ round-trips as ordinary DATA through both canonical encoders.
        ok("obj/proto-key", obj(("__proto__", integer("1"))), '{"__proto__":1}'),
        ok(
            "obj/deep",
            obj(("a", obj(("b", obj(("c", arr(integer("1"), obj(("d", NULL))))))))),
            '{"a":{"b":{"c":[1,{"d":null}]}}}',
        ),
    ]

    # ---- the shape that actually matters: a receipt envelope -------------------------
    rows += [
        ok(
            "envelope/success",
            obj(
                ("status", text("success")),
                ("summary", text("wu-1: completed (1200 ms)")),
                ("next_actions", arr(text("consume the receipt payload"))),
                ("artifacts", arr()),
            ),
            '{"artifacts":[],"next_actions":["consume the receipt payload"],'
            '"status":"success","summary":"wu-1: completed (1200 ms)"}',
        ),
        ok(
            "envelope/error",
            obj(
                ("status", text("error")),
                ("summary", text("wu-2: receipt-missing")),
                (
                    "next_actions",
                    arr(
                        text(
                            "resolve receipt-missing before treating this unit as done"
                        )
                    ),
                ),
                ("artifacts", arr(text("logs/wu-2.log"))),
                (
                    "error",
                    obj(
                        ("code", text("receipt-missing")),
                        ("root_cause", text("severed-stream: the rail exited 0")),
                        ("retry_instruction", text("re-dispatch the SAME unit once")),
                        ("stop_condition", text("stop after 1 retry")),
                    ),
                ),
            ),
            '{"artifacts":["logs/wu-2.log"],'
            '"error":{"code":"receipt-missing","retry_instruction":"re-dispatch the SAME unit once",'
            '"root_cause":"severed-stream: the rail exited 0","stop_condition":"stop after 1 retry"},'
            '"next_actions":["resolve receipt-missing before treating this unit as done"],'
            '"status":"error","summary":"wu-2: receipt-missing"}',
        ),
        ok(
            "envelope/wall-ms-is-an-integer",
            obj(("wall_ms", integer("1200")), ("budget_micro", integer("0"))),
            '{"budget_micro":0,"wall_ms":1200}',
        ),
    ]

    # ---- R13 depth -------------------------------------------------------------------
    rows += [
        ok(
            "deep/arr-at-limit-99",
            {"nest": {"depth": 99, "kind": "arr"}},
            "[" * 99 + "1" + "]" * 99,
        ),
        ok(
            "deep/arr-at-cap-100",
            {"nest": {"depth": 100, "kind": "arr"}},
            "[" * 100 + "1" + "]" * 100,
        ),
        reject(
            "deep/arr-over-cap-101",
            {"nest": {"depth": 101, "kind": "arr"}},
            "schema-invalid-max-depth",
        ),
        reject(
            "deep/obj-over-cap-101",
            {"nest": {"depth": 101, "kind": "obj"}},
            "schema-invalid-max-depth",
        ),
    ]

    return rows


def main() -> None:
    corpus = {
        "version": 1,
        "description": (
            "The shared canonical-JSON conformance contract. Both the Python and the JS "
            "runtime are driven against these cases and their emitted BYTES are compared."
        ),
        "cases": cases(),
    }
    rendered = json.dumps(corpus, indent=2, ensure_ascii=True, sort_keys=False)
    OUT.write_text(rendered + "\n", encoding="utf-8", newline="\n")
    ids = [row["id"] for row in corpus["cases"]]
    assert len(ids) == len(set(ids)), "duplicate case ids"
    print(f"wrote {OUT} with {len(ids)} cases")


if __name__ == "__main__":
    main()
