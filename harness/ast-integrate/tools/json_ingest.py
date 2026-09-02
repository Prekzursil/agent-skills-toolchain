"""Strict vs lenient JSON ingest behind one accept/reject boundary (TST-0058).

Three loaders share one ``ParseResult`` shape:

* ``strict_loads``  - the shipped client: ``json.loads`` (RFC 8259) with the
  ``JSONDecodeError`` position reported as ``line:column``.
* ``lenient_loads`` - the dev-tool ingest. A string-aware scanner DIAGNOSES the
  JSONC/JSON5-isms a VS Code buffer tolerates (line and block comments,
  trailing commas, single-quoted strings and keys) and then REFUSES them, so
  ingest can never accept a document the client rejects. With no such feature
  present it defers to the same ``json.loads`` the client runs, which is what
  keeps the two decisions aligned by construction rather than by test luck.
* ``jsonc_loads``   - the unaligned diagnostic control: it rewrites those
  JSON5-isms away and parses the result. It exists so the differential
  detector can be shown to fire on a real split; it is not a production path.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

PARSER_STRICT = "strict"
PARSER_LENIENT = "lenient"
PARSER_JSONC = "jsonc"

FEATURE_LINE_COMMENT = "line-comment"
FEATURE_BLOCK_COMMENT = "block-comment"
FEATURE_UNTERMINATED_BLOCK_COMMENT = "unterminated-block-comment"
FEATURE_SINGLE_QUOTED_STRING = "single-quoted-string"
FEATURE_TRAILING_COMMA = "trailing-comma"

#: Every JSON5-ism the lenient path can diagnose; all of them are refused.
FEATURES_REFUSED: tuple[str, ...] = (
    FEATURE_LINE_COMMENT,
    FEATURE_BLOCK_COMMENT,
    FEATURE_UNTERMINATED_BLOCK_COMMENT,
    FEATURE_SINGLE_QUOTED_STRING,
    FEATURE_TRAILING_COMMA,
)

_WHITESPACE = " \t\r\n"


@dataclass(frozen=True)
class Feature:
    """One diagnosed JSON5-ism and where it starts (1-based line:column)."""

    name: str
    line: int
    column: int

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "line": self.line, "column": self.column}


@dataclass(frozen=True)
class ParseResult:
    """Outcome of one loader on one document."""

    parser: str
    accepted: bool
    value: Any = None
    error: str | None = None
    line: int | None = None
    column: int | None = None
    features: tuple[str, ...] = ()

    def decision(self) -> str:
        return "accept" if self.accepted else "reject"

    def as_dict(self) -> dict[str, Any]:
        return {
            "parser": self.parser,
            "decision": self.decision(),
            "accepted": self.accepted,
            "error": self.error,
            "line": self.line,
            "column": self.column,
            "features": list(self.features),
        }


def _position(text: str, index: int) -> tuple[int, int]:
    line = text.count("\n", 0, index) + 1
    last_nl = text.rfind("\n", 0, index)
    return line, index - last_nl


def _coerce_text(document: Any) -> str:
    if isinstance(document, str):
        return document
    if isinstance(document, (bytes, bytearray)):
        return bytes(document).decode("utf-8")
    raise TypeError(f"document must be str or bytes, not {type(document).__name__}")


def _skip_insignificant(text: str, index: int) -> int:
    """Index of the next significant char, skipping whitespace and comments."""
    n = len(text)
    while index < n:
        ch = text[index]
        if ch in _WHITESPACE:
            index += 1
            continue
        if text.startswith("//", index):
            end = text.find("\n", index)
            index = n if end < 0 else end
            continue
        if text.startswith("/*", index):
            end = text.find("*/", index + 2)
            index = n if end < 0 else end + 2
            continue
        break
    return index


def _convert_single_quoted(body: str) -> str:
    """Body of a single-quoted string re-escaped for double quotes."""
    out: list[str] = []
    i = 0
    n = len(body)
    while i < n:
        ch = body[i]
        if ch == "\\" and i + 1 < n:
            nxt = body[i + 1]
            if nxt == "'":
                out.append("'")
            else:
                out.append(ch + nxt)
            i += 2
            continue
        if ch == '"':
            out.append('\\"')
        else:
            out.append(ch)
        i += 1
    return "".join(out)


def scan(text: str) -> tuple[list[Feature], str]:
    """Diagnose JSON5-isms outside string literals and produce the JSON rewrite.

    The rewrite blanks comments (newlines kept so positions survive), converts
    single-quoted strings to double-quoted ones and drops trailing commas. It is
    only consumed by ``jsonc_loads``; the production paths never parse it."""
    features: list[Feature] = []
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == '"':
            j = i + 1
            while j < n:
                c = text[j]
                if c == "\\":
                    j += 2
                    continue
                if c == '"':
                    j += 1
                    break
                j += 1
            out.append(text[i:j])
            i = j
            continue
        if ch == "'":
            line, col = _position(text, i)
            features.append(Feature(FEATURE_SINGLE_QUOTED_STRING, line, col))
            j = i + 1
            while j < n:
                c = text[j]
                if c == "\\":
                    j += 2
                    continue
                if c == "'":
                    break
                j += 1
            body = text[i + 1 : min(j, n)]
            out.append('"' + _convert_single_quoted(body) + '"')
            i = min(j, n) + 1
            continue
        if text.startswith("//", i):
            line, col = _position(text, i)
            features.append(Feature(FEATURE_LINE_COMMENT, line, col))
            end = text.find("\n", i)
            end = n if end < 0 else end
            out.append(" " * (end - i))
            i = end
            continue
        if text.startswith("/*", i):
            line, col = _position(text, i)
            end = text.find("*/", i + 2)
            if end < 0:
                features.append(Feature(FEATURE_UNTERMINATED_BLOCK_COMMENT, line, col))
                end = n
            else:
                features.append(Feature(FEATURE_BLOCK_COMMENT, line, col))
                end += 2
            out.append("".join("\n" if c == "\n" else " " for c in text[i:end]))
            i = end
            continue
        if ch == ",":
            nxt = _skip_insignificant(text, i + 1)
            if nxt < n and text[nxt] in "]}":
                line, col = _position(text, i)
                features.append(Feature(FEATURE_TRAILING_COMMA, line, col))
                i += 1
                continue
        out.append(ch)
        i += 1
    return features, "".join(out)


def scan_features(document: str | bytes) -> list[Feature]:
    """Just the diagnosed JSON5-isms, in document order."""
    return scan(_coerce_text(document))[0]


def rewrite_jsonc(document: str | bytes) -> str:
    """The document with comments blanked, quotes normalised, trailing commas dropped."""
    return scan(_coerce_text(document))[1]


def _feature_names(features: list[Feature]) -> tuple[str, ...]:
    names: list[str] = []
    for feature in features:
        if feature.name not in names:
            names.append(feature.name)
    return tuple(names)


def _reject_from_exception(parser: str, exc: Exception, features: tuple[str, ...] = ()) -> ParseResult:
    if isinstance(exc, json.JSONDecodeError):
        return ParseResult(
            parser=parser,
            accepted=False,
            error=f"{exc.msg}: line {exc.lineno} column {exc.colno} (char {exc.pos})",
            line=exc.lineno,
            column=exc.colno,
            features=features,
        )
    return ParseResult(
        parser=parser,
        accepted=False,
        error=f"{type(exc).__name__}: {exc}",
        features=features,
    )


def strict_loads(document: str | bytes) -> ParseResult:
    """The shipped client's parse: RFC 8259 via ``json.loads``, nothing tolerated."""
    try:
        text = _coerce_text(document)
        value = json.loads(text)
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError, RecursionError) as exc:
        return _reject_from_exception(PARSER_STRICT, exc)
    return ParseResult(parser=PARSER_STRICT, accepted=True, value=value)


def lenient_loads(document: str | bytes) -> ParseResult:
    """Dev-tool ingest: diagnose JSON5-isms, refuse them, else parse as the client does.

    A comment, trailing comma or single quote outside a string literal cannot
    occur in an RFC 8259 document, so every refusal here is also a client
    rejection; with no feature present the decision IS the client's decision."""
    try:
        text = _coerce_text(document)
    except (UnicodeDecodeError, TypeError) as exc:
        return _reject_from_exception(PARSER_LENIENT, exc)
    features, _ = scan(text)
    if features:
        first = features[0]
        names = _feature_names(features)
        return ParseResult(
            parser=PARSER_LENIENT,
            accepted=False,
            error=(
                f"refused JSON5-ism {first.name} at line {first.line} column "
                f"{first.column} ({len(features)} occurrence(s) of {', '.join(names)}); "
                "the shipped client rejects it"
            ),
            line=first.line,
            column=first.column,
            features=names,
        )
    try:
        value = json.loads(text)
    except (json.JSONDecodeError, RecursionError) as exc:
        return _reject_from_exception(PARSER_LENIENT, exc)
    return ParseResult(parser=PARSER_LENIENT, accepted=True, value=value)


def jsonc_loads(document: str | bytes) -> ParseResult:
    """Unaligned control: tolerate the JSON5-isms and parse what remains.

    Detector-control only. It accepts what the client rejects, which is exactly
    the split the aligned production pair must never show."""
    try:
        text = _coerce_text(document)
    except (UnicodeDecodeError, TypeError) as exc:
        return _reject_from_exception(PARSER_JSONC, exc)
    features, rewritten = scan(text)
    names = _feature_names(features)
    try:
        value = json.loads(rewritten)
    except (json.JSONDecodeError, RecursionError) as exc:
        return _reject_from_exception(PARSER_JSONC, exc, names)
    return ParseResult(parser=PARSER_JSONC, accepted=True, value=value, features=names)


def decisions_agree(left: ParseResult, right: ParseResult) -> bool:
    """Both accept or both reject."""
    return bool(left.accepted) == bool(right.accepted)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def values_agree(left: ParseResult, right: ParseResult) -> bool:
    """Both accepted and the parsed values are identical (canonical JSON compare)."""
    if not (left.accepted and right.accepted):
        return False
    try:
        return _canonical(left.value) == _canonical(right.value)
    except (TypeError, ValueError):
        return left.value == right.value


__all__ = [
    "FEATURES_REFUSED",
    "FEATURE_BLOCK_COMMENT",
    "FEATURE_LINE_COMMENT",
    "FEATURE_SINGLE_QUOTED_STRING",
    "FEATURE_TRAILING_COMMA",
    "FEATURE_UNTERMINATED_BLOCK_COMMENT",
    "Feature",
    "PARSER_JSONC",
    "PARSER_LENIENT",
    "PARSER_STRICT",
    "ParseResult",
    "decisions_agree",
    "jsonc_loads",
    "lenient_loads",
    "rewrite_jsonc",
    "scan",
    "scan_features",
    "strict_loads",
    "values_agree",
]
