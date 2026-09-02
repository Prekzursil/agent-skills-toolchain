"""Seeded document generator plus planted divergences for TST-0121.

Distinct from TST-0058 (fixed corpus): this generator searches. The same
seed must reproduce the identical document stream.
"""
from __future__ import annotations

import json
import random
from typing import Any

# Planted accept/reject: lenient keeps the comment, strict must reject.
PLANTED_COMMENT = '{\n  // planted-comment TST-0121\n  "planted": true\n}\n'

# Planted value disagreement: both accept; strict last-wins, lenient first-wins.
PLANTED_DUP = '{"dup": "first", "dup": "second"}'

PLANTED = (
    ("accept-reject", PLANTED_COMMENT),
    ("value", PLANTED_DUP),
)

STRINGS = (
    "ok",
    "a/b",
    'say "hi"',
    "trail,",
    "",
    "x",
)


def gen_value(rng: random.Random, depth: int) -> Any:
    if depth >= 3:
        return rng.choice(
            [None, True, False, rng.randint(-9, 9), rng.choice(STRINGS)]
        )
    kind = rng.choice(("atom", "atom", "list", "obj", "obj"))
    if kind == "atom":
        pick = rng.choice(("n", "b", "s", "z"))
        if pick == "n":
            return rng.choice((0, 1, -2, 3.5, 10))
        if pick == "b":
            return rng.choice((True, False, None))
        if pick == "z":
            return 0
        return rng.choice(STRINGS)
    if kind == "list":
        n = rng.randint(0, 3)
        return [gen_value(rng, depth + 1) for _ in range(n)]
    n = rng.randint(0, 3)
    obj: dict[str, Any] = {}
    for i in range(n):
        obj[f"k{i}"] = gen_value(rng, depth + 1)
    return obj


def _quote_scan_to_single(text: str) -> str:
    n = len(text)
    i = 0
    out: list[str] = []
    while i < n:
        ch = text[i]
        if ch == '"':
            out.append("'")
            i += 1
            while i < n:
                c = text[i]
                if c == "\\":
                    if i + 1 >= n:
                        out.append(c)
                        i += 1
                        break
                    nxt = text[i + 1]
                    if nxt == '"':
                        out.append('\\"')
                    elif nxt == "'":
                        out.append("\\'")
                    else:
                        out.append("\\")
                        out.append(nxt)
                    i += 2
                    continue
                if c == '"':
                    out.append("'")
                    i += 1
                    break
                out.append(c)
                i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def mutate(text: str, rng: random.Random) -> tuple[str, str]:
    mut = rng.choice(
        (
            "none",
            "comment",
            "trailing_comma",
            "single_quotes",
            "duplicate_key",
            "truncate",
            "garbage",
        )
    )
    if mut == "none":
        return text, mut
    if mut == "comment":
        if text.startswith("{") or text.startswith("["):
            return text[0] + " /*fuzz*/ " + text[1:], mut
        return "/*fuzz*/ " + text, mut
    if mut == "trailing_comma":
        stripped = text.rstrip()
        if stripped.endswith("}") or stripped.endswith("]"):
            return stripped[:-1] + "," + stripped[-1], mut
        return text, "none"
    if mut == "single_quotes":
        return _quote_scan_to_single(text), mut
    if mut == "duplicate_key":
        inner = text
        return '{"dup": "first", "dup": "second", "payload": ' + inner + "}", mut
    if mut == "truncate" and len(text) > 1:
        return text[:-1], mut
    if mut == "garbage":
        return text + " ??", mut
    return text, mut


def generated_documents(seed: int, count: int) -> list[tuple[int, str, str]]:
    """Return (index, mutation, text) for `count` generated documents."""
    rng = random.Random(seed)
    docs: list[tuple[int, str, str]] = []
    for i in range(count):
        raw = json.dumps(gen_value(rng, 0), ensure_ascii=True)
        text, mut = mutate(raw, rng)
        docs.append((i, mut, text))
    return docs


def campaign_documents(seed: int, generated_count: int) -> list[dict[str, Any]]:
    """Generated stream plus planted divergences spliced at stable indices."""
    gen = generated_documents(seed, generated_count)
    rows: list[dict[str, Any]] = []
    for idx, mut, text in gen:
        rows.append(
            {
                "index": idx,
                "origin": "generated",
                "mutation": mut,
                "input": text,
            }
        )
    # Deterministic splice points so a reproduction with the same seed
    # yields the same ordered stream (generated prefix + planted tail).
    base = len(rows)
    for offset, (kind, text) in enumerate(PLANTED):
        rows.append(
            {
                "index": base + offset,
                "origin": "planted",
                "mutation": f"planted-{kind}",
                "input": text,
                "expected_kind": kind,
            }
        )
    return rows
