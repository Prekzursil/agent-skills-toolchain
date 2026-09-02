"""Generate ``behaviour-corpus.json`` — the language-neutral BEHAVIOURAL parity contract.

Run: ``python fixtures/build_behaviour_corpus.py`` (from tools/agentspec-js).

The canonical corpus next to this one proves the two runtimes SERIALISE identically. It cannot
prove they BEHAVE identically: its emitters call ``dumpb`` and nothing else, so every decision
function — ``judge``, ``missing_fields``, ``build_argv``, ``check_dispatch``, ``plan_retry`` —
was outside the parity oracle entirely. An independent 483-case differential harness then found
**78 outcome divergences** across two suites that were both green at 100% line+branch. Every one
of those classes has a row below.

The file is GENERATED rather than hand-written for one reason: the interesting inputs are
invisible characters (U+001C, U+0085, U+FEFF, lone surrogates, astral pairs) and a hand-edited
fixture full of raw control bytes is unreviewable and easy to corrupt. Here each one is named.
"""

from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parent / "behaviour-corpus.json"

FS = "\x1c"
NEL = "\x85"
BOM = "\ufeff"
ASTRAL = "\U0001f600"
REPLACEMENT = "�"


def s(text: str) -> dict[str, object]:
    return {"s": text}


def i(value: int) -> dict[str, object]:
    return {"i": str(value)}


def f(value: str) -> dict[str, object]:
    return {"f": value}


def b(value: bool) -> dict[str, object]:
    return {"b": value}


NULL: dict[str, object] = {"n": True}


def ss(*items: str) -> dict[str, object]:
    return {"ss": list(items)}


def hx(raw: bytes) -> dict[str, object]:
    return {"hex": raw.hex()}


def kv(*pairs: tuple[str, dict[str, object]]) -> dict[str, object]:
    return {"kv": [[key, value] for key, value in pairs]}


def judge_case(case_id: str, receipt: object, **over: object) -> dict[str, object]:
    args: dict[str, object] = {
        "unit": s("u"),
        "exit": i(0),
        "receipt": receipt,
        "wall": i(1),
        "fmt": s("json"),
        "required": ss("summary"),
        "forbidden": ss(),
    }
    args.update(over)
    return {"id": case_id, "op": "judge", "args": args}


CASES: list[dict[str, object]] = []

# --- the AND-gate, on the blankness boundary that flipped it -------------------------------
CASES.append(judge_case("judge-ok", hx(b'{"summary":"done"}')))
CASES.append(judge_case("judge-exit-nonzero", hx(b'{"summary":"done"}'), exit=i(3)))
CASES.append(judge_case("judge-missing-receipt", NULL))
CASES.append(judge_case("judge-empty-receipt", hx(b"   ")))
for name, char in (
    ("fs", FS),
    ("gs", "\x1d"),
    ("rs", "\x1e"),
    ("us", "\x1f"),
    ("nel", NEL),
):
    CASES.append(judge_case(f"judge-blank-{name}", hx(char.encode("utf-8"))))
CASES.append(
    judge_case("judge-bom-single", hx(BOM.encode("utf-8") + b'{"summary":"x"}'))
)
CASES.append(judge_case("judge-bom-double", hx(BOM.encode("utf-8") * 2)))
CASES.append(judge_case("judge-bad-utf8", hx(b"\xff")))
CASES.append(judge_case("judge-bad-utf8-continuation", hx(b"\xe2\x82")))
CASES.append(judge_case("judge-nan-literal", hx(b'{"summary": NaN}')))
CASES.append(judge_case("judge-infinity-literal", hx(b'{"summary": Infinity}')))
CASES.append(judge_case("judge-top-level-array", hx(b"[1]")))
CASES.append(judge_case("judge-schema-invalid", hx(b'{"other":1}')))
CASES.append(
    judge_case("judge-blank-required-field", hx(('{"summary":"' + FS + '"}').encode()))
)
CASES.append(
    judge_case("judge-bom-required-field", hx(('{"summary":"' + BOM + '"}').encode()))
)
CASES.append(
    judge_case(
        "judge-marker",
        hx(b"TODO later"),
        fmt=s("text"),
        required=ss(),
        forbidden=ss("todo"),
    )
)
CASES.append(
    judge_case(
        "judge-progress-stream",
        hx(b"started in the background as task-1"),
        fmt=s("text"),
        required=ss(),
        forbidden=ss("todo"),
    )
)
CASES.append(judge_case("judge-blank-unit-id", hx(b'{"summary":"x"}'), unit=s(FS)))
CASES.append(judge_case("judge-bom-unit-id", hx(b'{"summary":"x"}'), unit=s(BOM)))
CASES.append(judge_case("judge-vacuous-spec", hx(b'{"summary":"x"}'), required=ss()))
CASES.append(judge_case("judge-unknown-fmt", hx(b'{"summary":"x"}'), fmt=s("yaml")))
CASES.append(judge_case("judge-float-wall", hx(b'{"summary":"x"}'), wall=f("1.5")))
CASES.append(
    judge_case("judge-huge-wall", hx(b'{"summary":"x"}'), wall=i(9007199254740993))
)

# --- receipt field/marker checks ------------------------------------------------------------
for name, value in (
    ("fs", FS),
    ("nel", NEL),
    ("bom", BOM),
    ("space", " "),
    ("text", "x"),
):
    CASES.append(
        {
            "id": f"missing-{name}",
            "op": "missing_fields",
            "args": {"payload": kv(("summary", s(value))), "required": ss("summary")},
        }
    )
CASES.append(
    {
        "id": "missing-null-and-zero",
        "op": "missing_fields",
        "args": {
            "payload": kv(("summary", NULL), ("count", i(0))),
            "required": ss("summary", "count"),
        },
    }
)
CASES.append(
    {
        "id": "missing-sort-order",
        "op": "missing_fields",
        "args": {"payload": kv(("x", s("y"))), "required": ss(ASTRAL, REPLACEMENT)},
    }
)
CASES.append(
    {
        "id": "markers-ascii-case",
        "op": "present_markers",
        "args": {"text": s("STILL IN PROGRESS"), "forbidden": ss("still in progress")},
    }
)
CASES.append(
    {
        "id": "markers-dotted-capital-i",
        "op": "present_markers",
        "args": {"text": s("İ"), "forbidden": ss("i̇")},
    }
)
CASES.append(
    {
        "id": "markers-sort-order",
        "op": "present_markers",
        "args": {
            "text": s(f"{ASTRAL}{REPLACEMENT}"),
            "forbidden": ss(ASTRAL, REPLACEMENT),
        },
    }
)

# --- decoders --------------------------------------------------------------------------------
CASES.append({"id": "decode-plain", "op": "decode", "args": {"receipt": hx(b"hello")}})
CASES.append(
    {
        "id": "decode-bom",
        "op": "decode",
        "args": {"receipt": hx(BOM.encode("utf-8") + b"hi")},
    }
)
CASES.append(
    {"id": "decode-bad-start", "op": "decode", "args": {"receipt": hx(b"\xff")}}
)
CASES.append(
    {"id": "decode-truncated", "op": "decode", "args": {"receipt": hx(b"\xe2\x82")}}
)
CASES.append(
    {
        "id": "parse-object",
        "op": "parse_json_object",
        "args": {"text": s('{"b":1,"a":2}')},
    }
)
for name, text in (
    ("array", "[1]"),
    ("number", "1"),
    ("string", '"s"'),
    ("null", "null"),
    ("boolean", "true"),
    ("garbage", "{"),
    ("nan", '{"a": NaN}'),
):
    CASES.append(
        {"id": f"parse-{name}", "op": "parse_json_object", "args": {"text": s(text)}}
    )

CASES.append({"id": "loadb-ok", "op": "loadb", "args": {"receipt": hx(b'{"a":1}')}})
for name, raw in (
    ("bad-start", b'"\xff"'),
    ("truncated", b'"\xe2\x82"'),
    ("overlong", b'"\xc0\xaf"'),
    ("cesu8", b'"\xed\xa0\xbd"'),
    ("inside-object", b'{"a":"\xff"}'),
):
    CASES.append({"id": f"loadb-{name}", "op": "loadb", "args": {"receipt": hx(raw)}})

# --- argv ------------------------------------------------------------------------------------
CASES.append(
    {"id": "cmdline-plain", "op": "render_cmdline", "args": {"argv": ss("codex", "-x")}}
)
CASES.append(
    {"id": "cmdline-space", "op": "render_cmdline", "args": {"argv": ss("a b")}}
)
CASES.append(
    {"id": "cmdline-fs", "op": "render_cmdline", "args": {"argv": ss("a" + FS + "b")}}
)
CASES.append(
    {"id": "cmdline-nel", "op": "render_cmdline", "args": {"argv": ss("a" + NEL + "b")}}
)
CASES.append(
    {"id": "cmdline-bom", "op": "render_cmdline", "args": {"argv": ss("a" + BOM + "b")}}
)
CASES.append({"id": "cmdline-empty", "op": "render_cmdline", "args": {"argv": ss("")}})
CASES.append(
    {
        "id": "build-argv-file",
        "op": "build_argv",
        "args": {
            "exe": s("codex"),
            "prompt": s("do the thing"),
            "transport": s("file"),
            "flags": ss("--ignore-user-config"),
            "prompt_flag": s("--prompt-file"),
            "prompt_path": s("/tmp/p.md"),
        },
    }
)
CASES.append(
    {
        "id": "build-argv-astral-over-cap",
        "op": "build_argv",
        "args": {
            "exe": s("codex"),
            "prompt": s("p"),
            "transport": s("file"),
            "flags": ss(ASTRAL * 16400),
            "prompt_flag": s("-f"),
            "prompt_path": s("/t"),
        },
    }
)
CASES.append(
    {
        "id": "build-argv-astral-under-cap",
        "op": "build_argv",
        "args": {
            "exe": s("codex"),
            "prompt": s("p"),
            "transport": s("file"),
            "flags": ss(ASTRAL * 16000),
            "prompt_flag": s("-f"),
            "prompt_path": s("/t"),
        },
    }
)
CASES.append(
    {
        "id": "build-argv-prompt-on-argv",
        "op": "build_argv",
        "args": {
            "exe": s("codex"),
            "prompt": s("x" * 64),
            "transport": s("file"),
            "flags": ss("--flag=" + "x" * 64),
            "prompt_flag": s("-f"),
            "prompt_path": s("/t"),
        },
    }
)
CASES.append(
    {
        "id": "build-argv-unknown-transport",
        "op": "build_argv",
        "args": {
            "exe": s("codex"),
            "prompt": s("p"),
            "transport": s("argv"),
            "flags": ss(),
            "prompt_flag": NULL,
            "prompt_path": NULL,
        },
    }
)
CASES.append(
    {
        "id": "prompt-on-argv-astral-32",
        "op": "prompt_on_argv",
        "args": {"element": s("z" + ASTRAL * 32), "prompt": s(ASTRAL * 32)},
    }
)
CASES.append(
    {
        "id": "prompt-on-argv-astral-31",
        "op": "prompt_on_argv",
        "args": {"element": s("z" + ASTRAL * 31), "prompt": s(ASTRAL * 31)},
    }
)
CASES.append(
    {
        "id": "prompt-on-argv-short-substring",
        "op": "prompt_on_argv",
        "args": {"element": s("--output-last-message"), "prompt": s("a")},
    }
)

# --- dispatch policy, budget, retry -----------------------------------------------------------
for name, timeout in (
    ("int", i(30)),
    ("null", NULL),
    ("zero", i(0)),
    # 2.5 and NOT 2.0: an INTEGRAL double is not a portable corpus input. JS has one numeric
    # type, so a literal 2.0 IS the integer 2 there and can never be refused, while Python
    # sees a float and refuses it. That asymmetry is inherent to the object models and is
    # disclosed in the README rather than asserted here; what IS portable, and is the rule
    # that matters, is "a non-integral or out-of-range number is refused by BOTH".
    ("float", f("2.5")),
    ("unsafe", i(9007199254740993)),
):
    CASES.append(
        {
            "id": f"dispatch-{name}",
            "op": "check_dispatch",
            "args": {"background": b(False), "timeout": timeout, "awaited": b(False)},
        }
    )
CASES.append(
    {
        "id": "dispatch-background-awaited",
        "op": "check_dispatch",
        "args": {"background": b(True), "timeout": i(30), "awaited": b(True)},
    }
)
for name, micro in (
    ("int", i(5)),
    ("float", f("2.5")),
    ("unsafe", i(9007199254740993)),
):
    CASES.append(
        {
            "id": f"debit-{name}",
            "op": "debit",
            "args": {
                "limit": i(9007199254740991),
                "unit": s("u"),
                "attempt": i(1),
                "micro": micro,
            },
        }
    )
CASES.append(
    {
        "id": "debit-over-limit",
        "op": "debit",
        "args": {"limit": i(4), "unit": s("u"), "attempt": i(1), "micro": i(5)},
    }
)
CASES.append(
    {
        "id": "cost-per-success-max",
        "op": "cost_per_success",
        "args": {
            "limit": i(9007199254740991),
            "micro": i(9007199254740991),
            "successes": i(3),
        },
    }
)
CASES.append(
    {
        "id": "cost-per-success-zero",
        "op": "cost_per_success",
        "args": {"limit": i(10), "micro": i(9), "successes": i(0)},
    }
)
for attempt in (1, 5, 6, 7, 60, 0):
    CASES.append(
        {
            "id": f"backoff-{attempt}",
            "op": "rate_limit_backoff_ms",
            "args": {"attempt": i(attempt)},
        }
    )
for name, reason, attempt in (
    ("rate-limited-1", "rate-limited", 1),
    ("rate-limited-6", "rate-limited", 6),
    ("win-arg-limit-1", "win-arg-limit-34472", 1),
    ("win-arg-limit-2", "win-arg-limit", 2),
    ("severed", "severed-stream", 1),
    ("unknown", "not-a-reason", 1),
):
    CASES.append(
        {
            "id": f"plan-retry-{name}",
            "op": "plan_retry",
            "args": {"reason": s(reason), "attempt": i(attempt)},
        }
    )

# --- terminal markers, progress, envelope -------------------------------------------------------
for name, unit in (
    ("plain", "unit-1"),
    ("newly-assigned", "a\u088f"),
    ("newly-assigned-2", "a\u0c5c"),
    ("escape", "a\x1b"),
    ("space", "a b"),
    ("bom", "a" + BOM),
    ("tag", "a\U000e0020"),
    ("empty", ""),
    ("astral", "a" + ASTRAL),
):
    CASES.append(
        {"id": f"success-line-{name}", "op": "success_line", "args": {"unit": s(unit)}}
    )
for name, text in (
    ("result", "the answer is 42"),
    ("background", "STARTED IN THE BACKGROUND as task-1"),
    ("progress-lines", "[codex] reading\n[codex] writing"),
    ("progress-lines-fs", "[codex] reading" + FS + "[codex] writing"),
    ("progress-lines-nel", "[codex] reading" + NEL + "[codex] writing"),
    ("blank-line-bom", "[codex] reading\n" + BOM + "\n"),
    ("empty", ""),
):
    CASES.append(
        {"id": f"classify-{name}", "op": "classify", "args": {"text": s(text)}}
    )
CASES.append(
    {
        "id": "observation-success",
        "op": "validate_observation",
        "args": {
            "status": s("success"),
            "summary": s("done"),
            "next": ss("consume the receipt"),
            "code": NULL,
            "root_cause": s(""),
            "retry_instruction": s(""),
            "stop_condition": s(""),
        },
    }
)
for name, summary in (("fs", FS), ("bom", BOM), ("space", " ")):
    CASES.append(
        {
            "id": f"observation-blank-summary-{name}",
            "op": "validate_observation",
            "args": {
                "status": s("success"),
                "summary": s(summary),
                "next": ss("x"),
                "code": NULL,
                "root_cause": s(""),
                "retry_instruction": s(""),
                "stop_condition": s(""),
            },
        }
    )
CASES.append(
    {
        "id": "observation-error-blank-affordances",
        "op": "validate_observation",
        "args": {
            "status": s("error"),
            "summary": s("boom"),
            "next": ss(),
            "code": s("not-a-reason"),
            "root_cause": s(FS),
            "retry_instruction": s(BOM),
            "stop_condition": s(""),
        },
    }
)

# --- the wire predicates themselves --------------------------------------------------------------
for name, text in (
    ("fs", FS),
    ("nel", NEL),
    ("bom", BOM),
    ("empty", ""),
    ("nbsp", " "),
    ("ideographic-space", "　"),
    ("text", " x "),
):
    CASES.append(
        {"id": f"is-blank-{name}", "op": "wire_is_blank", "args": {"text": s(text)}}
    )
for name, text in (
    ("ascii", "abc"),
    ("astral", ASTRAL * 32),
    ("lone-surrogate", "\ud83d"),
):
    CASES.append(
        {"id": f"utf16-len-{name}", "op": "wire_utf16_len", "args": {"text": s(text)}}
    )
for name, text in (("ascii", "TODO"), ("dotted-i", "İ"), ("e-acute", "É")):
    CASES.append(
        {"id": f"fold-{name}", "op": "wire_fold_ascii_case", "args": {"text": s(text)}}
    )
for name, text in (
    ("plain", "unit-1"),
    ("newly-assigned", "a\u088f"),
    ("noncharacter", "a\ufdd0"),
    ("private-use", "a\ue000"),
    ("variation-selector", "a️"),
):
    CASES.append(
        {
            "id": f"printable-{name}",
            "op": "wire_is_printable_id",
            "args": {"text": s(text)},
        }
    )


def main() -> int:
    ids = [case["id"] for case in CASES]
    if len(set(ids)) != len(ids):
        raise SystemExit("FAILED:corpus duplicate case ids")
    OUT.write_bytes(
        (json.dumps({"cases": CASES}, indent=2, ensure_ascii=True) + "\n").encode(
            "utf-8"
        )
    )
    print(f"SUCCESS:corpus {len(CASES)} behaviour cases written to {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
