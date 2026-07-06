"""Paste-parse fallback — read a raw ``/mcp`` panel dump into structured rows.

The user can paste the text of Claude Code's interactive ``/mcp`` server list
(which an external tool cannot query live) and use it as both the inventory and
the current enabled/disabled state.  Handles the real panel line shapes, e.g.::

    apktool-mcp · ✔ connected · 16 tools
    codecov · ✘ failed
    hexstrike-ai · ◯ disabled
    basic-memory   ✔ connected   42 tools

Header/footer chrome ("74 servers", "↑/↓ to navigate", "Enter to view", the
"Manage MCP servers" title, etc.) is skipped.  Parsing is best-effort and
fail-soft: an unrecognisable line is simply ignored.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# canonical states
CONNECTED = "connected"
FAILED = "failed"
DISABLED = "disabled"
NEEDS_AUTH = "needs_auth"
UNKNOWN = "unknown"

# glyph -> state.  NOTE: only non-letter glyphs — a plain ascii 'x' would
# false-match server names (e.g. "hexstrike"), so real panels' ✘/✗ are used.
_GLYPH_STATE: dict[str, str] = {
    "✔": CONNECTED,
    "✓": CONNECTED,
    "☑": CONNECTED,
    "✘": FAILED,
    "✗": FAILED,
    "✕": FAILED,
    "◯": DISABLED,
    "○": DISABLED,
    "◌": DISABLED,
    "⊘": DISABLED,
    "⚠": NEEDS_AUTH,
}

# keyword -> state (matched case-insensitively in the remainder of a line)
_KEYWORD_STATE: list[tuple[str, str]] = [
    ("needs auth", NEEDS_AUTH),
    ("needs authentication", NEEDS_AUTH),
    ("authenticate", NEEDS_AUTH),
    ("connected", CONNECTED),
    ("connecting", CONNECTED),
    ("ready", CONNECTED),
    ("failed", FAILED),
    ("error", FAILED),
    ("disabled", DISABLED),
    ("off", DISABLED),
]

# separators used between fields in the panel (middle-dot, bullets, pipe, tab)
_SEP_RE = re.compile(r"\s*[·••·|\t]\s*|\s{2,}")

_TOOLS_RE = re.compile(r"(\d+)\s+tools?\b", re.IGNORECASE)
_SERVERS_HEADER_RE = re.compile(r"^\s*\d+\s+servers?\b", re.IGNORECASE)

# lines that are panel chrome, not servers
_CHROME_MARKERS = (
    "↑",
    "↓",
    "→",
    "←",
    "esc ",
    " esc",
    "enter ",
    "manage mcp",
    "mcp server",
    "to navigate",
    "to view",
    "to select",
    "to confirm",
    "to exit",
    "to go back",
)

# a plausible server name: starts with a letter/digit, contains name chars
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._:@\-]*$")


@dataclass
class ParsedServer:
    """One server parsed from a pasted ``/mcp`` panel."""

    name: str
    state: str  # connected | failed | disabled | needs_auth | unknown
    tool_count: int | None = None

    @property
    def enabled(self) -> bool:
        """A server is 'enabled' unless the panel showed it disabled."""
        return self.state != DISABLED


def _is_chrome(line: str) -> bool:
    low = line.lower()
    if _SERVERS_HEADER_RE.match(line):
        return True
    return any(marker in low for marker in _CHROME_MARKERS)


def _extract_state(text: str) -> str:
    """Derive a state from glyphs (first) then keywords in the field text."""
    for ch in text:
        if ch in _GLYPH_STATE:
            return _GLYPH_STATE[ch]
    low = text.lower()
    for kw, state in _KEYWORD_STATE:
        if kw in low:
            return state
    return UNKNOWN


def _clean_name(field: str) -> str:
    """Strip leading selection markers / glyphs from the name field."""
    name = field.strip()
    # drop a leading selection/cursor marker (>, *, -, •, [x]) and checkbox
    name = re.sub(r"^[>*\-•▸❯]\s*", "", name)
    name = re.sub(r"^\[[ xX*]\]\s*", "", name)
    # drop any leading state glyph that led the name field
    while name and name[0] in _GLYPH_STATE:
        name = name[1:].strip()
    return name.strip()


def parse_line(line: str) -> ParsedServer | None:
    """Parse a single panel line into a ParsedServer, or None if it isn't one."""
    stripped = line.strip()
    if not stripped or _is_chrome(stripped):
        return None

    fields = [f for f in _SEP_RE.split(stripped) if f.strip()]
    if not fields:
        return None

    name = _clean_name(fields[0])
    if not name or not _NAME_RE.match(name):
        return None
    # Scan the whole line for a state (glyph first, then keyword).
    state = _extract_state(stripped)
    # a bare word with no state and no separators is too ambiguous to accept
    if state == UNKNOWN and len(fields) == 1:
        return None

    tool_count: int | None = None
    m = _TOOLS_RE.search(stripped)
    if m:
        tool_count = int(m.group(1))

    return ParsedServer(name=name, state=state, tool_count=tool_count)


def parse_mcp_panel(text: str) -> list[ParsedServer]:
    """Parse a whole pasted ``/mcp`` panel into ParsedServer rows.

    De-duplicates by name (first occurrence wins) and preserves input order.
    """
    out: list[ParsedServer] = []
    seen: set[str] = set()
    for raw in text.splitlines():
        parsed = parse_line(raw)
        if parsed is None or parsed.name in seen:
            continue
        seen.add(parsed.name)
        out.append(parsed)
    return out


def inventory_ids(servers: list[ParsedServer]) -> list[str]:
    """The server names — usable as the resolver's live inventory."""
    return [s.name for s in servers]


def disabled_ids(servers: list[ParsedServer]) -> list[str]:
    """Names the panel showed as currently disabled."""
    return [s.name for s in servers if s.state == DISABLED]
