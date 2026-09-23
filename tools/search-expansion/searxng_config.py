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

SECOND MEASURED BASIS (2026-09-02, from this cloud VM - NOT the owner's instance)
--------------------------------------------------------------------------------
The default-mix FLIPS in `INDEPENDENT_ENGINES` (plan G-3 / Wave 1 item 1a) rest on
evidence gathered here, not on a live `--apply`:

* `google` OFF. Keyless Google scraping is dead: benbusby/whoogle-search is archived with
  an EOL notice ("Google has now killed the last User-Agent string that still worked",
  README, 2026-07-24) and searxng/searxng#6359 ("GSA for iPhone useragent do no longer
  work") was closed 2026-08-22. Upstream `searx/settings.yml` now ships `google` with
  `disabled: true`; the hub's own deploy config still force-enables it, which is the
  override this entry exists to cancel wherever the block is applied.
* `mwmbl` ON. Keyless. `https://api.mwmbl.org/api/v1/search/?s=` (the URL the upstream
  engine module builds) answered HTTP 200 with 44 results in 0.41 s. Upstream ships it
  `disabled: true`, nothing else needed.
* `marginalia` ON, status `rate-limited` - NOT `works`. Upstream ships it `disabled: true`
  AND `inactive: true` (the module is not even loaded) with `api_key: None`, so the block
  must set all three of `disabled`, `inactive`, `api_key`. Upstream `init()` logs
  "invalid api_key (public)" but still returns True, so the module loads. The endpoint the
  module calls, `https://api2.marginalia-search.com/search`, answered **HTTP 429 "QPM
  Limit Exceeded" on the FIRST request** with `API-Key: public` (0.45 s) - the key is
  shared by every instance that uses it, so its quota is effectively always spent. It is
  switched on anyway because the approved plan says so and because SearXNG fails it
  truthfully (`unresponsive_engines: [marginalia, too many requests]`, then a suspension
  that costs ~0 latency); it is kept OUT of `enabled_specs()` so query routing never
  spends a call on it. A personal key (free, non-commercial) replaces `public` in the
  `extra` tuple. Do not self-host Marginalia to dodge the limit.

The block is RENDERED here and its YAML is parsed in the tests; it has NOT been applied to
the owner's instance from this VM. The owner applies it with `--dry-run`, then `--apply`.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

__all__ = [
    "BEGIN_MARKER",
    "END_MARKER",
    "INDEPENDENT_ENGINES",
    "MANAGED_ENGINES",
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

#: The markers are the block's identity in the owner's file. They still say "regional"
#: although the block now also carries the independent-index flips: renaming them would
#: orphan any previously applied block (`remove_block` would no longer find it).
BEGIN_MARKER = "# >>> harness:search-expansion regional engines >>>"
END_MARKER = "# <<< harness:search-expansion regional engines <<<"

_STATUS_WORKS = "works"
#: Enabled in the block by decision, but measured answering 429 - see the module header.
_STATUS_RATE_LIMITED = "rate-limited"
#: Measured/evidenced dead: rendered as `disabled: true` to override any force-enable.
_STATUS_DEAD = "dead"
_ON_STATUSES = frozenset({_STATUS_WORKS, _STATUS_RATE_LIMITED})


class ConflictError(RuntimeError):
    """Raised when the target file already owns a key this block would duplicate."""


@dataclass(frozen=True)
class EngineSpec:
    """One SearXNG engine, with the verdict measured against the live instance.

    ``status`` is observed behaviour. Three values drive rendering: ``works`` and
    ``rate-limited`` are switched ON (``disabled: false``), ``dead`` is switched OFF
    (``disabled: true``); any other value (``blocked``, ``silent-fail``, ``broken``) is
    documented as an inert comment. ``extra`` holds further ``key: value`` pairs rendered
    verbatim under the entry - the smallest extension that lets one entry say
    ``inactive: false`` and ``api_key: public``.
    """

    name: str
    shortcut: str
    region: str
    status: str
    detail: str
    timeout: float = 6.0
    extra: tuple[tuple[str, str], ...] = ()

    @property
    def works(self) -> bool:
        """Measured returning results. The only status query routing may target."""
        return self.status == _STATUS_WORKS

    @property
    def switched_on(self) -> bool:
        """Rendered with ``disabled: false`` (measured working, or rate-limited-by-plan)."""
        return self.status in _ON_STATUSES

    @property
    def switched_off(self) -> bool:
        """Rendered with ``disabled: true`` (measured dead)."""
        return self.status == _STATUS_DEAD


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

#: Default-mix flips measured 2026-09-02 (module header has the receipts). Kept apart from
#: `REGIONAL_ENGINES` so query routing, which fans out over that table, is unchanged.
INDEPENDENT_ENGINES: tuple[EngineSpec, ...] = (
    EngineSpec(
        "google",
        "go",
        "global",
        _STATUS_DEAD,
        "keyless scraping dead (Whoogle EOL 2026-07-24, searxng#6359 closed 2026-08-22); "
        "upstream ships it disabled, checked 2026-09-02",
    ),
    EngineSpec(
        "mwmbl",
        "mwm",
        "independent",
        _STATUS_WORKS,
        "api.mwmbl.org/api/v1/search probed 2026-09-02: HTTP 200, 44 results, 0.41 s; "
        "keyless; upstream ships it disabled",
        6.0,
    ),
    EngineSpec(
        "marginalia",
        "mar",
        "independent",
        _STATUS_RATE_LIMITED,
        "api2.marginalia-search.com with the shared `public` key: HTTP 429 QPM Limit "
        "Exceeded at FIRST touch, 2026-09-02; on by plan G-3, fails truthfully - put a "
        "personal key in `extra` to make it useful",
        6.0,
        (("inactive", "false"), ("api_key", "public")),
    ),
)

#: Everything the block manages, in render order: regional first, then the flips.
MANAGED_ENGINES: tuple[EngineSpec, ...] = REGIONAL_ENGINES + INDEPENDENT_ENGINES


def enabled_specs(
    specs: tuple[EngineSpec, ...] = REGIONAL_ENGINES,
) -> tuple[EngineSpec, ...]:
    """The measured-WORKING engines - the ones query planning may route to.

    Narrower than what the block switches on: a ``rate-limited`` engine is rendered
    ``disabled: false`` (see :attr:`EngineSpec.switched_on`) but is excluded here, because
    an explicit ``engines=<name>`` call to an engine that answers 429 is a wasted call.
    """
    return tuple(s for s in specs if s.works)


def render_engines_block(specs: tuple[EngineSpec, ...] = MANAGED_ENGINES) -> str:
    """Render the managed YAML block.

    Emits a partial engine list, which `use_default_settings: true` merges by name into the
    built-in definitions — so only the keys being changed appear: ``disabled`` (both
    directions), ``timeout`` for switched-on engines, and any ``extra`` pairs verbatim.
    Engines that failed the live probe are emitted as comments: visible, documented, inert.
    """
    lines = [
        BEGIN_MARKER,
        "# Regional engines verified against this instance on 2026-07-24;",
        "# independent-index flips (google off, mwmbl + marginalia on) measured 2026-09-02.",
        "# Managed block - edit via tools/search-expansion/searxng_regional.py.",
        "# NOTE: a disabled engine is STILL reachable via `engines=<name>` or `!<shortcut>`;",
        "# this block only controls what joins the DEFAULT result mix.",
        "engines:",
    ]
    for spec in specs:
        if spec.switched_on:
            lines += [
                f"  # {spec.region}: {spec.detail} (bang !{spec.shortcut})",
                f"  - name: {spec.name}",
                "    disabled: false",
                f"    timeout: {spec.timeout}",
            ]
        elif spec.switched_off:
            lines += [
                f"  # {spec.region}: {spec.detail} (bang !{spec.shortcut})",
                f"  - name: {spec.name}",
                "    disabled: true",
            ]
        else:
            continue
        lines += [f"    {key}: {value}" for key, value in spec.extra]
    broken = [s for s in specs if not (s.switched_on or s.switched_off)]
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
