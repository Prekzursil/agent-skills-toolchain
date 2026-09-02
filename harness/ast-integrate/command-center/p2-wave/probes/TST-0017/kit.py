"""USE-vs-MENTION discriminator (TST-0017).

USED: the token is the semantic value of a typed field (status, state,
verdict, role, classification, result, outcome).
MENTIONED: the token sits in a payload string, a fenced example, inline
code, a comment, a docstring, or documentation prose.

A file that documents a defect necessarily contains that defect's text.
Default is MENTION; USE is the special case that requires a typed field
and no wrapping context.

ignore_wrappers=True is the known-broken mutant: every located span is USE.
That mutant is the detector-control fixture, not a production path.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Iterator, Literal

Role = Literal["USE", "MENTION", "ABSENT"]

USE_KEYS = frozenset(
    {
        "status",
        "state",
        "verdict",
        "role",
        "classification",
        "result",
        "outcome",
        "kind",
        "severity",
        "decision",
        "gate",
        "check_result",
    }
)
USE_KEY_SUFFIXES = ("_status", "_state", "_verdict", "_role", "_result")
MENTION_KEYS = frozenset(
    {
        "body",
        "text",
        "payload",
        "description",
        "message",
        "notes",
        "note",
        "documentation",
        "doc",
        "comment",
        "quote",
        "example",
        "question",
        "title",
        "prompt",
        "content",
        "markdown",
        "reason",
        "detail",
        "details",
        "claim",
        "prose",
        "readme",
        "help",
        "hint",
    }
)
JSON_STRING_RE = re.compile(r'"(?:\\.|[^"\\])*"')
YAML_LINE_RE = re.compile(
    r"""^[\s\-]*([A-Za-z_][\w\-]*)\s*:\s*(?:["']([^"']*)["']|(\S+))\s*$"""
)
XML_RE = re.compile(
    r"<([A-Za-z_][\w\-]*)>([^<]*)</\1>",
    re.IGNORECASE,
)
TOKEN_BOUNDARY_OK = re.compile(r"[^\w\-]")


@dataclass(frozen=True)
class Occurrence:
    token: str
    start: int
    end: int
    role: Role
    reason: str

    def as_dict(self) -> dict:
        return {
            "token": self.token,
            "start": self.start,
            "end": self.end,
            "role": self.role,
            "reason": self.reason,
        }


def _inside(ranges: list[tuple[int, int]], start: int, end: int) -> bool:
    for a, b in ranges:
        if a <= start and end <= b:
            return True
    return False


def _fence_ranges(text: str) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    i = 0
    while True:
        a = text.find("```", i)
        if a < 0:
            break
        b = text.find("```", a + 3)
        if b < 0:
            ranges.append((a, len(text)))
            break
        ranges.append((a, b + 3))
        i = b + 3
    return ranges


def _inline_code_ranges(text: str) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    fences = _fence_ranges(text)
    i = 0
    n = len(text)
    while i < n:
        if text[i] == "`" and not _inside(fences, i, i + 1):
            if text.startswith("```", i):
                i += 3
                continue
            j = text.find("`", i + 1)
            if j < 0:
                break
            if j - i > 1:
                ranges.append((i, j + 1))
            i = j + 1
            continue
        i += 1
    return ranges


def _comment_line_ranges(text: str) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    pos = 0
    for line in text.splitlines(keepends=True):
        stripped = line.lstrip()
        if stripped.startswith("#") or stripped.startswith("//") or stripped.startswith(">"):
            ranges.append((pos, pos + len(line)))
        pos += len(line)
    return ranges


def _is_use_key(key: str) -> bool:
    k = key.lower()
    if k in USE_KEYS:
        return True
    return any(k.endswith(sfx) for sfx in USE_KEY_SUFFIXES)


def _is_mention_key(key: str) -> bool:
    return key.lower() in MENTION_KEYS


def _json_string_spans(text: str) -> list[tuple[int, int, int, int]]:
    """(outer_start, outer_end, inner_start, inner_end) for each JSON string."""
    out: list[tuple[int, int, int, int]] = []
    for m in JSON_STRING_RE.finditer(text):
        out.append((m.start(), m.end(), m.start() + 1, m.end() - 1))
    return out


def _following_is_colon(text: str, outer_end: int) -> bool:
    return bool(re.match(r"\s*:", text[outer_end:]))


def _preceding_json_key(text: str, outer_start: int) -> str | None:
    m = re.search(r'"((?:\\.|[^"\\])*)"\s*:\s*$', text[:outer_start])
    if not m:
        return None
    raw = '"' + m.group(1) + '"'
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError:
        decoded = m.group(1)
    return decoded if isinstance(decoded, str) else None


def _json_context(text: str, start: int, end: int) -> tuple[str | None, bool, bool]:
    """Return (key, is_key_span, is_full_string_value)."""
    for outer_s, outer_e, inner_s, inner_e in _json_string_spans(text):
        if inner_s <= start and end <= inner_e:
            if _following_is_colon(text, outer_e):
                return None, True, False
            key = _preceding_json_key(text, outer_s)
            full = start == inner_s and end == inner_e
            return key, False, full
    return None, False, False


def _yaml_key_for_span(text: str, start: int, end: int) -> tuple[str | None, bool]:
    line_a = text.rfind("\n", 0, start) + 1
    line_b = text.find("\n", start)
    if line_b < 0:
        line_b = len(text)
    line = text[line_a:line_b]
    m = YAML_LINE_RE.match(line)
    if not m:
        return None, False
    key = m.group(1)
    quoted = m.group(2)
    bare = m.group(3)
    value = quoted if quoted is not None else (bare or "")
    rel = start - line_a
    key_at = line.find(key)
    if key_at >= 0 and key_at <= rel < key_at + len(key):
        return key, False
    val_at = line.rfind(value) if value else -1
    if value and val_at >= 0 and val_at <= rel < val_at + len(value):
        full = text[start:end] == value or value == text[start:end]
        return key, full
    return None, False


def _xml_key_for_span(text: str, start: int, end: int) -> tuple[str | None, bool]:
    for m in XML_RE.finditer(text):
        inner_s, inner_e = m.start(2), m.end(2)
        if inner_s <= start and end <= inner_e:
            return m.group(1), start == inner_s and end == inner_e
    return None, False


def _token_boundary(text: str, start: int, end: int) -> bool:
    left_ok = start == 0 or TOKEN_BOUNDARY_OK.match(text[start - 1]) is not None
    right_ok = end == len(text) or TOKEN_BOUNDARY_OK.match(text[end]) is not None
    return left_ok and right_ok


def iter_spans(text: str, token: str) -> Iterator[tuple[int, int]]:
    if not token:
        return
    start = 0
    while True:
        i = text.find(token, start)
        if i < 0:
            return
        j = i + len(token)
        if _token_boundary(text, i, j):
            yield i, j
        start = i + 1


def classify_span(
    text: str,
    start: int,
    end: int,
    *,
    ignore_wrappers: bool = False,
) -> tuple[Role, str]:
    if start < 0 or end > len(text) or start >= end:
        return "ABSENT", "out-of-range"
    if ignore_wrappers:
        return "USE", "ignore-wrappers-mutant"

    if _inside(_fence_ranges(text), start, end):
        return "MENTION", "fenced-code-block"
    if _inside(_inline_code_ranges(text), start, end):
        return "MENTION", "inline-code"
    if _inside(_comment_line_ranges(text), start, end):
        return "MENTION", "comment-or-blockquote"

    key, is_json_key, full_json = _json_context(text, start, end)
    if is_json_key:
        return "MENTION", "json-key-label"
    if key is not None:
        if _is_mention_key(key):
            return "MENTION", f"payload-field:{key}"
        if _is_use_key(key) and full_json:
            return "USE", f"typed-field:{key}"
        if _is_use_key(key) and not full_json:
            return "MENTION", f"substring-in-typed-field:{key}"
        if full_json and len(text[start:end]) <= 48:
            # Unknown short enum-like JSON value: still not USE unless typed.
            return "MENTION", f"json-string:{key}"
        return "MENTION", f"json-string:{key}"

    ykey, yfull = _yaml_key_for_span(text, start, end)
    if ykey is not None:
        if _is_mention_key(ykey):
            return "MENTION", f"yaml-payload:{ykey}"
        if _is_use_key(ykey) and yfull:
            return "USE", f"typed-yaml-field:{ykey}"
        if _is_use_key(ykey) and not yfull:
            return "MENTION", f"substring-in-yaml-field:{ykey}"

    xkey, xfull = _xml_key_for_span(text, start, end)
    if xkey is not None:
        if _is_mention_key(xkey):
            return "MENTION", f"xml-payload:{xkey}"
        if _is_use_key(xkey) and xfull:
            return "USE", f"typed-xml-field:{xkey}"

    return "MENTION", "prose"


def classify_token(
    text: str,
    token: str,
    *,
    ignore_wrappers: bool = False,
) -> list[Occurrence]:
    found: list[Occurrence] = []
    for start, end in iter_spans(text, token):
        role, reason = classify_span(
            text, start, end, ignore_wrappers=ignore_wrappers
        )
        found.append(
            Occurrence(
                token=token, start=start, end=end, role=role, reason=reason
            )
        )
    return found


def naive_substring_as_use(text: str, token: str) -> list[Occurrence]:
    """Known-broken detector: any located span is USE."""
    return classify_token(text, token, ignore_wrappers=True)


def roles(text: str, token: str, *, ignore_wrappers: bool = False) -> list[str]:
    return [
        o.role
        for o in classify_token(text, token, ignore_wrappers=ignore_wrappers)
        if o.role != "ABSENT"
    ]
