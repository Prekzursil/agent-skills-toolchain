"""Planted TESTONLY secrets for TST-0212. Never print a secret body."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LIB = REPO / "tools" / "lib"
sys.path.insert(0, str(LIB))

from security import (  # noqa: E402
    DIAGNOSTIC_PREFIXES,
    FIXED_MASK_BODY,
    MIN_BODY_CHARS,
    mask_secret,
)

MJS = LIB / "security.mjs"
NODE = os.environ.get("NODE", "node")

# Five sk- secrets of differing body lengths. Bodies are synthetic TESTONLY
# padding; probes report lengths and masked forms only.
_BODY_LENS = (8, 16, 24, 40, 72)


def _body(n: int) -> str:
    if n < MIN_BODY_CHARS:
        raise ValueError("body shorter than MIN_BODY_CHARS")
    pad = "TESTONLY"
    if n < len(pad):
        return pad[:n]
    return pad + ("x" * (n - len(pad)))


def length_secrets() -> list[str]:
    """Five sk- tokens whose total lengths differ."""
    return ["sk-" + _body(n) for n in _BODY_LENS]


def prefix_samples() -> list[tuple[str, str]]:
    """One planted token per diagnostic prefix, same body length."""
    body = _body(20)
    return [(p, p + body) for p in DIAGNOSTIC_PREFIXES]


def mask_via_python(tokens: list[str]) -> list[str]:
    return [mask_secret(t) for t in tokens]


def mask_via_mjs(tokens: list[str]) -> list[str]:
    if not MJS.is_file():
        raise FileNotFoundError(str(MJS))
    proc = subprocess.run(
        [NODE, str(MJS), "batch-mask"],
        cwd=str(REPO),
        input=json.dumps(tokens),
        capture_output=True,
        text=True,
        timeout=30,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "mjs failed")[-2000:])
    out = json.loads((proc.stdout or "").strip().splitlines()[-1])
    if not isinstance(out, list) or len(out) != len(tokens):
        raise RuntimeError("mjs batch-mask returned unexpected shape")
    return [str(x) for x in out]


def per_character_mask(token: str) -> str:
    """Negative-control mutant: remainder width equals the secret body length."""
    for prefix in DIAGNOSTIC_PREFIXES:
        if token.startswith(prefix):
            return prefix + ("*" * (len(token) - len(prefix)))
    raise ValueError("not a diagnostic-prefix token")


def public_row(token: str, masked: str) -> dict:
    prefix = next(p for p in DIAGNOSTIC_PREFIXES if token.startswith(p))
    return {
        "prefix": prefix,
        "secret_byte_len": len(token.encode("utf-8")),
        "body_char_len": len(token) - len(prefix),
        "masked": masked,
        "masked_byte_len": len(masked.encode("utf-8")),
        "prefix_readable": masked.startswith(prefix),
        "body_absent_from_mask": token[len(prefix) :] not in masked,
        "mask_body": masked[len(prefix) :] if masked.startswith(prefix) else None,
        "fixed_mask_body": FIXED_MASK_BODY,
    }
