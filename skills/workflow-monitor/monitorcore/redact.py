"""Strict-by-default, fail-closed secret/home-path redaction (pure, stdlib-only).

``redact(text)`` masks structured secrets first, then collapses the user's home
directory (all six real forms, including the 8.3 short name ``PREKZU~1``) to
``~``. It is a pure ``str -> (str, int)`` function: no filesystem, no globals
mutated. Every substitution is wrapped in ``try/except`` so a malformed/raising
pattern degrades to the partially-masked text and *never* surfaces the raw
input (fail-closed).

Pattern set: the LOCKED plan patterns verbatim, plus two reasoned, flagged
additions that only ever mask *more* (fail-safe for an export tool):

* ``gh[oure]_...`` - structurally precise oauth/user/server/refresh tokens.
* a *tightened* standalone JWT - both leading segments must start ``eyJ`` and
  clear a minimum length, so benign dotted base64 does not match.

Home collapse uses a single unified regex covering ``C:\\Users\\<u>``,
``C:/Users/<u>``, ``/c/Users/<u>``, ``/mnt/c/Users/<u>``, ``/home/<u>`` and the
8.3 form. (A
single anchored alternation is used deliberately: the two-regex form cannot
collapse both the git-bash ``/c/Users`` and the WSL ``/mnt/c/Users`` correctly
under any fixed application order, because each would partially match inside the
other. The observable contract - every form to ``~`` - is unchanged.)
"""

import re

from .textsafe import strip_controls

# Secrets are masked BEFORE home-path collapse. Order within this list matters
# in two places: the ``Bearer`` JWT must precede the standalone JWT (so the
# label prefix is preserved), and the ``*.gitcrypt.key`` path is consumed before
# home collapse would otherwise touch its ``C:\\Users\\...`` prefix.
_SECRET_PATTERNS = [
    (re.compile(r"sk-[A-Za-z0-9_-]{16,}"), "[REDACTED:api-key]"),
    (re.compile(r"ghp_[A-Za-z0-9]{36}"), "[REDACTED:gh-pat]"),
    (re.compile(r"github_pat_[A-Za-z0-9_]{22,}"), "[REDACTED:gh-pat]"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "[REDACTED:aws-akid]"),
    # Databricks PAT (same pattern as dbx_events._DAPI_RE) — harvest Plane B.
    (re.compile(r"dapi[A-Za-z0-9]{8,}"), "[REDACTED:dapi]"),
    (re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"), "[REDACTED:slack]"),
    (
        re.compile(
            r"(?i)Bearer\s+eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"
        ),
        "Bearer [REDACTED:jwt]",
    ),
    (
        re.compile(
            r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----"
            r"[\s\S]*?"
            r"-----END (?:[A-Z ]+ )?PRIVATE KEY-----"
        ),
        "[REDACTED:pem-private-key]",
    ),
    (re.compile(r"[^\s\"']*\.gitcrypt\.key"), "[REDACTED:gitcrypt-key]"),
    # --- reasoned additions (mask-more; near-zero false positives) ---
    (re.compile(r"gh[oure]_[A-Za-z0-9]{36}"), "[REDACTED:gh-token]"),
    (
        re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
        "[REDACTED:jwt]",
    ),
]

# Unified home-directory collapse (applied after all secrets). The optional
# leading group matches a Windows drive (``C:``), a WSL mount (``/mnt/c``) or a
# git-bash drive (``/c``); it is anchored to ``[\\/]+Users[\\/]+<name>`` so it
# can never match a bare ``/Users`` sitting inside a longer mount path. Both
# separators are ONE-OR-MORE so the JSON-serialized doubled-backslash form
# (``C:\\Users\\<u>`` produced by ``json.dumps`` on a tool_input path) collapses
# too - a single ``[\\/]`` stalls on the second backslash and leaks the username
# into every rendered ``json.dumps(tool_input)`` block.
_HOME_PATTERNS = [
    (
        re.compile(
            r"(?i)(?:(?:[A-Za-z]:|/mnt/[a-z]|/[a-z])?[\\/]+Users[\\/]+"
            r"[^\\/\r\n\"']+|/home/[^/\r\n\"\x27]+)"
        ),
        "~",
    ),
]


def redact(text: str, *, enabled: bool = True) -> tuple[str, int]:
    """Mask secrets + collapse home paths. Returns ``(masked_text, n_masked)``.

    ``enabled=False`` is an exact passthrough (``(text, 0)``). Fail-closed: any
    pattern whose substitution raises is skipped, keeping the partially-masked
    text - the raw input is never returned wholesale on an error path.
    """
    if not enabled:
        return text, 0
    total = 0
    for pattern, replacement in _SECRET_PATTERNS + _HOME_PATTERNS:
        try:
            text, n = pattern.subn(replacement, text)
            total += n
        except Exception:
            # Fail-closed: drop this pattern, keep the already-masked text.
            continue
    return text, total


def scrub(value: object) -> str:
    """THE shared ingest floor: coerce to text, strip control bytes, THEN redact.

    Every adapter that ingests attacker-influenceable text (a Codex thread label, a Claude
    agent name, an MCP server name, a Databricks unit error) must funnel through this ONE
    function rather than re-declaring it, because the ORDER is load-bearing and a copy that
    drifts silently loses a security property:

    * ``strip_controls`` FIRST, so a control byte spliced into a secret can no longer split
      the pattern past the mask, and so no ESC/BEL/OSC byte survives ingest to be painted to
      the operator's terminal later (escape-injection / OSC-8 link / OSC-52 clipboard hijack).
    * ``redact`` SECOND, fail-closed, so the raw input is never returned wholesale.

    ``None`` becomes ``""`` rather than the literal ``"None"``, so an unmeasured field never
    renders as a fake value.
    """
    text = "" if value is None else str(value)
    return redact(strip_controls(text), enabled=True)[0]


class Redactor:
    """Callable ``str -> str`` wrapper that accumulates the masked count.

    ``count`` sums ``n_masked`` across every call, feeding the renderers'
    redaction audit banner. ``Redactor(enabled=False)`` is a transparent
    passthrough that never increments ``count``.
    """

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self.count = 0

    def __call__(self, text: str) -> str:
        masked, n = redact(text, enabled=self.enabled)
        self.count += n
        return masked
