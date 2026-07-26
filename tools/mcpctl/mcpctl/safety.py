"""Always-on redaction + terminal-control-strip layer (pure, stdlib-only).

Two independent guarantees, in order of strength:

1. **Structural.** :func:`env_fields` is the ONLY route by which an MCP server's
   ``env`` block enters mcpctl's data model, and it captures a variable NAME plus a
   three-way classification -- never the value. A credential therefore cannot reach
   a row, a renderer, or a JSON dump, because it was never parsed into the model in
   the first place. This is stronger than redacting at render time, which fails open
   the moment a new render path is added.
2. **Textual (defence in depth).** :func:`redact_text` masks credential shapes in
   free text that mcpctl *does* carry -- a server's ``command``/``args`` and an
   injected ``last_error`` string, both of which can echo a token.

``monitorcore`` is reused when importable, but is NOT the security floor
-------------------------------------------------------------------------
``monitorcore.textsafe.strip_controls`` is imported when available (single source of
truth for the C0/C1/ESC/BEL/DEL byte class) and mcpctl falls back to a byte-identical
local regex otherwise -- ``tests/test_safety_contract.py`` asserts the two agree on a
byte corpus, so drift in either copy fails loudly instead of silently.

``monitorcore.redact`` is layered *after* mcpctl's own pattern set, never instead of
it. MEASURED reason (``tools/monitorcore/monitorcore/redact.py:32-59``): that pattern
set covers ``sk-``, ``ghp_``, ``github_pat_``, ``AKIA``, ``xox?-``, Bearer-JWT, PEM,
``.gitcrypt.key``, ``gh[oure]_`` and a bare JWT -- and nothing else. The credential
shapes this box's MCP ``env`` blocks actually carry include ``xai-...`` and
``AIza...`` keys plus wholly opaque tokens (``SONARQUBE_TOKEN``,
``FB_PAGE_ACCESS_TOKEN``, ``DIGITALOCEAN_API_TOKEN``, ...), none of which match any
upstream pattern. A layer that depended on the import would therefore be green while
blind, so mcpctl owns its own patterns and the import only ever masks *more*.
"""

from __future__ import annotations

import importlib
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import ModuleType
from typing import cast

__all__ = [
    "EnvField",
    "Upstream",
    "env_fields",
    "load_upstream",
    "make_redactor",
    "pick_strip",
    "redact_text",
    "safe",
    "strip_controls",
]

# All C0 bytes except TAB/LF/CR, plus DEL and every C1 byte. Byte-identical to
# monitorcore.textsafe._CONTROL_RE (textsafe.py:50); the contract test enforces that.
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")

# Secret shapes FIRST, home-path collapse LAST -- a home path inside a masked secret
# must not be collapsed before the secret pattern has had its turn.
_SECRET_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # Prefixed, structurally unambiguous.
    (re.compile(r"ghp_[A-Za-z0-9]{36}"), "[REDACTED:gh-pat]"),
    (re.compile(r"github_pat_[A-Za-z0-9_]{22,}"), "[REDACTED:gh-pat]"),
    (re.compile(r"gh[oure]_[A-Za-z0-9]{36}"), "[REDACTED:gh-token]"),
    (re.compile(r"sk-[A-Za-z0-9_-]{16,}"), "[REDACTED:api-key]"),
    (re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"), "[REDACTED:slack]"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "[REDACTED:aws-akid]"),
    # --- shapes upstream cannot see (redact.py:32-59 has no pattern for either) ---
    (re.compile(r"xai-[A-Za-z0-9_-]{16,}"), "[REDACTED:xai-key]"),
    (re.compile(r"AIza[0-9A-Za-z_-]{35}"), "[REDACTED:google-key]"),
    # Opaque fallback: a credential-ish LABEL followed by a long value. This is what
    # catches a token whose issuer uses no recognisable prefix at all.
    (
        re.compile(
            r"(?i)\b(authorization|api[-_]?keys?|apikey|access[-_]?token|token"
            r"|secret|bearer|password|passwd|pwd)\b\s*[:=]\s*"
            r"(?:Bearer\s+)?[A-Za-z0-9._\-+/]{16,}={0,2}"
        ),
        r"\1=[REDACTED:opaque]",
    ),
)

# Unified home-directory collapse: Windows drive, WSL mount, git-bash drive, or a
# POSIX /home/<user>. Both separators are one-or-more so the JSON-escaped
# double-backslash form collapses too.
_HOME_RE = re.compile(
    r"(?i)(?:(?:[A-Za-z]:|/mnt/[a-z]|/[a-z])?[\\/]+Users[\\/]+[^\\/\r\n\"']+"
    r"|/home/[^/\r\n\"']+)"
)


@dataclass(frozen=True)
class EnvField:
    """One ``env`` entry reduced to a NAME plus a classification.

    ``kind`` is one of:

    * ``present``   -- a non-empty literal value is configured (value NOT captured).
    * ``absent``    -- the key exists but carries no value.
    * ``reference`` -- the value is a ``${VAR}`` indirection, so the literal
      credential lives in the environment, not in this config file.
    """

    name: str
    kind: str


@dataclass(frozen=True)
class Upstream:
    """The two monitorcore callables mcpctl reuses when they are importable."""

    strip_controls: Callable[[str], str]
    redact: Callable[[str], tuple[str, int]]


def load_upstream(
    importer: Callable[[str], ModuleType] = importlib.import_module,
) -> Upstream | None:
    """Import monitorcore's text helpers, or ``None`` when unavailable.

    ``importer`` is injected so both outcomes are exercised hermetically.
    """
    try:
        textsafe = importer("monitorcore.textsafe")
        redact_mod = importer("monitorcore.redact")
    except ImportError:
        return None
    return Upstream(
        strip_controls=cast("Callable[[str], str]", textsafe.strip_controls),
        redact=cast("Callable[[str], tuple[str, int]]", redact_mod.redact),
    )


def _fallback_strip_controls(text: str) -> str:
    return _CONTROL_RE.sub("", text)


def pick_strip(upstream: Upstream | None) -> Callable[[str], str]:
    """Return monitorcore's ``strip_controls`` when present, else the local copy."""
    if upstream is None:
        return _fallback_strip_controls
    return upstream.strip_controls


def make_redactor(upstream: Upstream | None) -> Callable[[str], str]:
    """Build the redactor: mcpctl's own patterns, then monitorcore's if present."""

    def _redact(text: str) -> str:
        for pattern, replacement in _SECRET_PATTERNS:
            text = pattern.sub(replacement, text)
        if upstream is not None:
            text = upstream.redact(text)[0]
        return _HOME_RE.sub("~", text)

    return _redact


UPSTREAM: Upstream | None = load_upstream()
_STRIP: Callable[[str], str] = pick_strip(UPSTREAM)
_REDACT: Callable[[str], str] = make_redactor(UPSTREAM)


def strip_controls(text: str) -> str:
    """Drop terminal control bytes (ESC/BEL/C0-except-TAB-LF-CR/DEL/C1)."""
    return _STRIP(text)


def redact_text(text: str) -> str:
    """Mask credential shapes, then collapse the home directory to ``~``."""
    return _REDACT(text)


def safe(text: str) -> str:
    """The one function every untrusted string passes through before rendering."""
    return strip_controls(redact_text(text))


def env_fields(env: object) -> tuple[EnvField, ...]:
    """Reduce an ``env`` block to name+classification pairs, sorted by name.

    A non-mapping ``env`` (absent, null, or a malformed list) yields ``()`` rather
    than raising -- a hand-edited config must never crash a read-only inventory.
    NOTE: the value is inspected to classify it and is then discarded; it is never
    stored on the returned records.
    """
    if not isinstance(env, Mapping):
        return ()
    fields: list[EnvField] = []
    for raw_name, raw_value in cast("Mapping[object, object]", env).items():
        name = strip_controls(str(raw_name))
        value = "" if raw_value is None else str(raw_value)
        if not value:
            kind = "absent"
        elif value.startswith("${") and value.endswith("}"):
            kind = "reference"
        else:
            kind = "present"
        fields.append(EnvField(name=name, kind=kind))
    return tuple(sorted(fields, key=lambda f: f.name))
