"""Adversarial argv corpus for TST-0191 (500 values, required classes first)."""
from __future__ import annotations

import random

REQUIRED_CLASSES: list[tuple[str, str]] = [
    ("space", "has space"),
    ("dquote", 'say "hi"'),
    ("squote", "say 'hi'"),
    ("amp", "a&b"),
    ("pipe", "a|b"),
    ("redir", "a>b"),
    ("newline", "line1\nline2"),
    ("pct_var", "%VAR%"),
    ("pct_path", "%PATH%"),
    ("unicode", "café-中文-🙂"),
    ("mixed", 'mix & | > %VAR% café "q"'),
]

# Concatenation mutation payloads: identity-breaking without extra shell commands.
SAFE_MUTATION: list[str] = [
    "has space",
    'say "hi"',
    "say 'hi'",
    "%VAR%",
    "café-中文-🙂",
]


def generate_adversarial(n: int = 500, seed: int = 191) -> list[str]:
    rng = random.Random(seed)
    atoms = [
        " ",
        '"',
        "'",
        "&",
        "|",
        ">",
        "\n",
        "\t",
        "%VAR%",
        "%PATH%",
        "%CD%",
        "café",
        "中文",
        "🙂",
        "ё",
        "`",
        "$HOME",
        "$(x)",
        ";",
        "*",
        "?",
        "\\",
        "<",
        "(",
        ")",
        "[",
        "]",
        "{",
        "}",
        "~",
        "\r",
        "a b",
        "has space",
    ]
    out = [value for _name, value in REQUIRED_CLASSES]
    seen = set(out)
    attempts = 0
    while len(out) < n and attempts < n * 40:
        attempts += 1
        parts: list[str] = []
        for _ in range(rng.randint(1, 5)):
            if rng.random() < 0.65:
                parts.append(rng.choice(atoms))
            else:
                parts.append(
                    "".join(rng.choice("abcdef0123_-") for _ in range(rng.randint(1, 8)))
                )
        text = "".join(parts)
        if "\0" in text or text in seen or not text or len(text) > 180:
            continue
        seen.add(text)
        out.append(text)
    if len(out) < n:
        raise RuntimeError(f"adversarial corpus short: {len(out)} < {n}")
    return out[:n]
