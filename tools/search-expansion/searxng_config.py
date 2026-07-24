"""Pure config logic for enabling SearXNG's regional engines — no I/O lives here.

Split from the CLI on purpose: every decision that can corrupt the owner's `settings.yml`
(is a managed block already present? does a conflicting `engines:` key already exist? what
exactly changes?) is a pure string transform, so it is unit-testable to 100% without
touching a live instance. `searxng_regional.py` owns the file writes, the container
restart, and the health check.

MEASURED BASIS (2026-07-24, SearXNG 2026.6.29+e535e4c61 at 127.0.0.1:8890)
--------------------------------------------------------------------------
Every engine below was queried live in its own language before being classified. Engines
that failed are kept in the table with their failure mode rather than deleted, so a future
reader can see they were considered and why they are off — and can re-probe them.

A `disabled` engine is still reachable via `engines=<name>` or its `!<shortcut>` bang; this
block only decides what joins the DEFAULT result mix.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

__all__ = [
    "BEGIN_MARKER",
    "END_MARKER",
    "REGIONAL_ENGINES",
    "EngineSpec",
    "ConflictError",
    "apply_block",
    "enabled_specs",
    "find_top_level_key",
    "has_managed_block",
    "remove_block",
    "render_engines_block",
    "unified_diff",
]

BEGIN_MARKER = "# >>> harness:search-expansion regional engines >>>"
END_MARKER = "# <<< harness:search-expansion regional engines <<<"

_STATUS_WORKS = "works"


class ConflictError(RuntimeError):
    """Raised when the target file already owns a key this block would duplicate."""


@dataclass(frozen=True)
class EngineSpec:
    """One SearXNG engine, with the verdict measured against the live instance."""

    name: str
    shortcut: str
    region: str
    status: str
    detail: str
    timeout: float = 6.0

    @property
    def works(self) -> bool:
        return self.status == _STATUS_WORKS


#: Measured 2026-07-24. `status` is the observed behaviour, not an aspiration.
REGIONAL_ENGINES: tuple[EngineSpec, ...] = (
    EngineSpec("yandex", "yd", "RU", _STATUS_WORKS, "10 results", 6.0),
    EngineSpec("quark", "qk", "CN", _STATUS_WORKS, "11-12 results; slow", 10.0),
    EngineSpec("360search", "360so", "CN", _STATUS_WORKS, "4-5 results; slow", 10.0),
    EngineSpec(
        "baidu kaifa", "bdk", "CN", _STATUS_WORKS, "10 results; dev vertical", 8.0
    ),
    EngineSpec("naver news", "nvrn", "KR", _STATUS_WORKS, "10 results", 6.0),
    EngineSpec("seznam", "szn", "CZ", _STATUS_WORKS, "10 results", 6.0),
    EngineSpec("mojeek", "mjk", "independent", _STATUS_WORKS, "10 results", 6.0),
    EngineSpec("baidu", "bd", "CN", "blocked", "CAPTCHA, then sticky suspension", 6.0),
    EngineSpec("sogou", "sogou", "CN", "blocked", "timeout, then CAPTCHA", 6.0),
    EngineSpec("naver", "nvr", "KR", "silent-fail", "n=0 with NO error reported", 6.0),
    EngineSpec("yahoo", "yh", "global", "broken", "HTTP protocol error", 6.0),
    EngineSpec("qwant", "qw", "FR", "broken", "access denied", 6.0),
)


def enabled_specs(
    specs: tuple[EngineSpec, ...] = REGIONAL_ENGINES,
) -> tuple[EngineSpec, ...]:
    """The engines this block will switch on — measured-working ones only."""
    return tuple(s for s in specs if s.works)


def render_engines_block(specs: tuple[EngineSpec, ...] = REGIONAL_ENGINES) -> str:
    """Render the managed YAML block.

    Emits a partial engine list, which `use_default_settings: true` merges by name into the
    built-in definitions — so only the keys being changed appear. Engines that failed the
    live probe are emitted as comments: visible, documented, and inert.
    """
    lines = [
        BEGIN_MARKER,
        "# Regional engines verified against this instance on 2026-07-24.",
        "# Managed block - edit via tools/search-expansion/searxng_regional.py.",
        "# NOTE: a disabled engine is STILL reachable via `engines=<name>` or `!<shortcut>`;",
        "# this block only controls what joins the DEFAULT result mix.",
        "engines:",
    ]
    for spec in specs:
        if not spec.works:
            continue
        lines += [
            f"  # {spec.region}: {spec.detail} (bang !{spec.shortcut})",
            f"  - name: {spec.name}",
            "    disabled: false",
            f"    timeout: {spec.timeout}",
        ]
    broken = [s for s in specs if not s.works]
    if broken:
        lines.append("  # Measured NOT working on 2026-07-24 - left off deliberately.")
        lines.append(
            "  # Re-probe with `searxng_regional.py --probe` before enabling any:"
        )
        for spec in broken:
            lines.append(
                f"  #   {spec.name} ({spec.region}) -> {spec.status}: {spec.detail}"
            )
    lines.append(END_MARKER)
    return "\n".join(lines) + "\n"


def has_managed_block(text: str) -> bool:
    """True when a previously applied managed block is present."""
    return BEGIN_MARKER in text and END_MARKER in text


def find_top_level_key(text: str, key: str) -> int | None:
    """Line number (1-based) of an unindented `key:` outside the managed block, else None.

    Guards the one way this splice can produce invalid YAML: a second top-level `engines:`
    mapping key. YAML forbids duplicate keys, and a silently broken settings file takes the
    owner's search down, so the caller must refuse rather than guess how to merge.
    """
    inside = False
    pattern = re.compile(rf"^{re.escape(key)}\s*:")
    for number, line in enumerate(text.splitlines(), start=1):
        if line.startswith(BEGIN_MARKER):
            inside = True
            continue
        if line.startswith(END_MARKER):
            inside = False
            continue
        if not inside and pattern.match(line):
            return number
    return None


def remove_block(text: str) -> str:
    """Strip the managed block, returning the file to its pre-apply content."""
    if not has_managed_block(text):
        return text
    out: list[str] = []
    inside = False
    for line in text.splitlines(keepends=True):
        if line.startswith(BEGIN_MARKER):
            inside = True
            continue
        if line.startswith(END_MARKER):
            inside = False
            continue
        if not inside:
            out.append(line)
    return "".join(out)


def apply_block(text: str, block: str) -> str:
    """Return `text` with the managed block appended, replacing any previous copy.

    Idempotent: applying twice yields the same file, so a re-run is safe. Raises
    `ConflictError` if the file already defines its own top-level `engines:` key.
    """
    base = remove_block(text)
    conflict = find_top_level_key(base, "engines")
    if conflict is not None:
        raise ConflictError(
            f"settings.yml already defines a top-level 'engines:' key at line {conflict}; "
            "merge by hand rather than appending a duplicate YAML key"
        )
    # Normalise the trailing newlines instead of just ensuring one: `remove_block` leaves
    # the separator blank line behind, so a naive append grows the file by one blank line
    # on every re-apply. Collapsing first makes re-running `--apply` a true no-op.
    base = base.rstrip("\n")
    return f"{base}\n\n{block}" if base else block


def unified_diff(before: str, after: str, path: str = "settings.yml") -> str:
    """Human-reviewable diff of exactly what `--apply` would change."""
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        )
    )
