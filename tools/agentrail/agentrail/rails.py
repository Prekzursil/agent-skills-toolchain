"""RAIL ROWS -- the config layer. Adding an agent CLI is a TOML row, never new Python.

PURE: :func:`load_rows` takes TOML *text*, not a path, so nothing here touches a filesystem.
The CLI reads the bytes through :class:`agentrail.ports.RailFileSystem` and hands the text in.

Two transport vocabularies exist and they are NOT the same thing:

* :data:`NATIVE_TRANSPORTS` -- what a vendor CLI *accepts*. Includes ``"argv"``, because some
  CLIs really do want ``tool -p "<prompt>"``.
* :data:`agentspec.argv.PROMPT_TRANSPORTS` -- what agentrail is *allowed to use*: ``file`` and
  ``stdin``, closed. A prompt on argv produced the measured ``os error 206`` at
  ``payload_len=34472``, so a row declaring ``native_transport = "argv"`` is SPILLED by
  :func:`agentrail.plan.spill_transport` onto one of the two legal transports. The enum is
  never widened; the caller is adapted to it.
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from string import Template
from typing import Any

from agentspec.argv import PROMPT_TRANSPORTS, WINDOWS_CMDLINE_CAP, RailSpec
from agentspec.spec import RECEIPT_FORMATS, ReceiptSpec

from agentrail import CONFIG_VERSION

NATIVE_TRANSPORTS: tuple[str, ...] = ("argv", "file", "stdin")
"""What a vendor CLI accepts. A superset of the two agentrail may actually use."""

_REQUIRED_KEYS: tuple[str, ...] = ("native_transport", "receipt_format")


class ConfigError(ValueError):
    """A rails.toml row is unusable. Raised at LOAD time, never at dispatch time."""

    reason = "policy-violation"


@dataclass(frozen=True, slots=True)
class RailRow:
    """One declarative rail. Everything a dispatch needs, and nothing a dispatch computes.

    ``exe_globs`` is ordered and load-bearing: the codex executable lives under a
    version-and-target-pinned vendor directory, so it is found by GLOB and only then by
    ``exe_fallbacks`` (the npm shim), which costs an extra Node process and therefore emits a
    warning. Hardcoding today's resolved path is a recorded defect -- see
    :mod:`agentrail.resolve` and the ``codex-glob-to-hardcoded-path`` mutation row.

    ``verified`` records whether the rail was PROVEN executable headless. ``False`` means the
    row ships but is opt-in: agy and gemini both timed out on ``--version`` at 15s, which is a
    DETECTOR failure and not a verdict, so they are neither deleted nor described as working.
    """

    name: str
    exe_globs: tuple[str, ...] = ()
    exe_fallbacks: tuple[str, ...] = ()
    hardening: tuple[str, ...] = ()
    base_flags: tuple[str, ...] = ()
    native_transport: str = "stdin"
    prompt_flag: str | None = None
    receipt_format: str = "json"
    receipt_required_fields: tuple[str, ...] = ()
    receipt_forbidden_markers: tuple[str, ...] = ()
    receipt_flag: str | None = None
    default_timeout_s: int = 900
    cap: int = WINDOWS_CMDLINE_CAP
    verified: bool = False
    notes: str = ""

    def receipt_spec(self) -> ReceiptSpec:
        """The row's :class:`agentspec.spec.ReceiptSpec`.

        Never vacuous: :func:`load_rows` rejects a json row with no ``required_fields`` and a
        text row with no ``forbidden_markers``, because ``agentspec.oracle.judge`` REFUSES a
        vacuous spec and a load-time error beats a dispatch-time crash.
        """
        return ReceiptSpec(
            fmt=self.receipt_format,
            required_fields=self.receipt_required_fields,
            forbidden_markers=self.receipt_forbidden_markers,
        )

    def rail_spec(self, exe: str, *, transport: str) -> RailSpec:
        """Bind this row to a RESOLVED executable and an agentspec-legal ``transport``.

        ``transport`` is supplied rather than read off the row because the row states what the
        vendor CLI wants and the spill decides what agentrail actually does.
        """
        if transport not in PROMPT_TRANSPORTS:
            raise ConfigError(
                f"rail {self.name!r}: transport must be one of "
                f"{list(PROMPT_TRANSPORTS)}, got {transport!r}"
            )
        return RailSpec(
            name=self.name,
            exe=exe,
            hardening=self.hardening,
            prompt_transport=transport,
            prompt_flag=self.prompt_flag if transport == "file" else None,
            cap=self.cap,
        )


def load_rows(toml_text: str) -> tuple[RailRow, ...]:
    """Parse rails.toml text into validated rows, in declaration order.

    Raises :class:`ConfigError` on anything a dispatch would otherwise discover too late.
    """
    try:
        raw = tomllib.loads(toml_text)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"rails config is not valid TOML: {exc}") from exc

    version = raw.get("config_version")
    if version != CONFIG_VERSION:
        raise ConfigError(
            f"rails config version must be {CONFIG_VERSION!r}, got {version!r}"
        )

    table = raw.get("rail")
    if not isinstance(table, dict) or not table:
        raise ConfigError("rails config declares no [rail.<name>] tables")

    rows = tuple(_row(name, body) for name, body in table.items())
    return rows


def expand_rows(
    rows: Sequence[RailRow], variables: Mapping[str, str]
) -> tuple[RailRow, ...]:
    """Substitute ``${VAR}`` in every path field. PURE -- the caller supplies the values.

    STRICT on purpose: an unknown variable raises :class:`ConfigError` rather than surviving
    as a literal ``${HOME}`` in a path, which would resolve to nothing and be reported as a
    missing executable -- one defect wearing another's clothes.
    """
    return tuple(
        replace(
            row,
            exe_globs=tuple(
                _expand(row.name, value, variables) for value in row.exe_globs
            ),
            exe_fallbacks=tuple(
                _expand(row.name, value, variables) for value in row.exe_fallbacks
            ),
        )
        for row in rows
    )


def _expand(name: str, value: str, variables: Mapping[str, str]) -> str:
    try:
        return Template(value).substitute(variables)
    except (KeyError, ValueError) as exc:
        raise ConfigError(
            f"rail {name!r}: cannot expand {value!r}: {exc}; "
            f"known variables: {sorted(variables)}"
        ) from exc


def row_by_name(rows: Sequence[RailRow], name: str) -> RailRow:
    """Look up a row, raising :class:`ConfigError` naming what IS available."""
    for row in rows:
        if row.name == name:
            return row
    known = ", ".join(sorted(candidate.name for candidate in rows))
    raise ConfigError(f"no rail named {name!r}; known rails: {known}")


def verified_names(rows: Sequence[RailRow]) -> tuple[str, ...]:
    """The rails PROVEN executable, sorted. The complement ships as opt-in config rows."""
    return tuple(sorted(row.name for row in rows if row.verified))


def _row(name: str, body: object) -> RailRow:
    if not isinstance(body, dict):
        raise ConfigError(f"rail {name!r}: expected a table, got {type(body).__name__}")
    if not name:
        raise ConfigError("a rail table name must be non-empty")

    missing = tuple(key for key in _REQUIRED_KEYS if key not in body)
    if missing:
        raise ConfigError(f"rail {name!r}: missing required key(s) {list(missing)}")

    unknown = tuple(sorted(set(body) - _FIELD_NAMES))
    if unknown:
        raise ConfigError(f"rail {name!r}: unknown key(s) {list(unknown)}")

    native = _string(name, body, "native_transport")
    if native not in NATIVE_TRANSPORTS:
        raise ConfigError(
            f"rail {name!r}: native_transport must be one of "
            f"{list(NATIVE_TRANSPORTS)}, got {native!r}"
        )

    fmt = _string(name, body, "receipt_format")
    if fmt not in RECEIPT_FORMATS:
        raise ConfigError(
            f"rail {name!r}: receipt_format must be one of "
            f"{list(RECEIPT_FORMATS)}, got {fmt!r}"
        )

    row = RailRow(
        name=name,
        exe_globs=_strings(name, body, "exe_globs"),
        exe_fallbacks=_strings(name, body, "exe_fallbacks"),
        hardening=_strings(name, body, "hardening"),
        base_flags=_strings(name, body, "base_flags"),
        native_transport=native,
        prompt_flag=_optional_string(name, body, "prompt_flag"),
        receipt_format=fmt,
        receipt_required_fields=_strings(name, body, "receipt_required_fields"),
        receipt_forbidden_markers=_strings(name, body, "receipt_forbidden_markers"),
        receipt_flag=_optional_string(name, body, "receipt_flag"),
        default_timeout_s=_positive_int(name, body, "default_timeout_s", 900),
        cap=_positive_int(name, body, "cap", WINDOWS_CMDLINE_CAP),
        verified=_bool(name, body, "verified"),
        notes=_optional_string(name, body, "notes") or "",
    )
    _check_row(row)
    return row


def _check_row(row: RailRow) -> None:
    """Reject at LOAD time every shape that would fail later, deeper and less legibly."""
    if not row.exe_globs and not row.exe_fallbacks:
        raise ConfigError(
            f"rail {row.name!r}: declare exe_globs and/or exe_fallbacks, or nothing can resolve"
        )
    if row.native_transport == "file" and not row.prompt_flag:
        raise ConfigError(
            f"rail {row.name!r}: native_transport 'file' requires prompt_flag"
        )
    if row.receipt_spec().is_vacuous():
        raise ConfigError(
            f"rail {row.name!r}: receipt spec is vacuous -- a json spec needs "
            f"receipt_required_fields and a text spec needs receipt_forbidden_markers, or the "
            f"completion AND-gate silently reduces to 'exit 0 AND non-empty'"
        )


def _string(name: str, body: Mapping[str, Any], key: str) -> str:
    value = body[key]
    if not isinstance(value, str):
        raise ConfigError(
            f"rail {name!r}: {key} must be a string, got {type(value).__name__}"
        )
    return value


def _optional_string(name: str, body: Mapping[str, Any], key: str) -> str | None:
    if key not in body:
        return None
    return _string(name, body, key)


def _strings(name: str, body: Mapping[str, Any], key: str) -> tuple[str, ...]:
    if key not in body:
        return ()
    value = body[key]
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ConfigError(f"rail {name!r}: {key} must be a list of strings")
    return tuple(value)


def _positive_int(name: str, body: Mapping[str, Any], key: str, default: int) -> int:
    if key not in body:
        return default
    value = body[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(
            f"rail {name!r}: {key} must be an int, got {type(value).__name__}"
        )
    if value <= 0:
        raise ConfigError(f"rail {name!r}: {key} must be positive, got {value}")
    return value


def _bool(name: str, body: Mapping[str, Any], key: str) -> bool:
    if key not in body:
        return False
    value = body[key]
    if not isinstance(value, bool):
        raise ConfigError(
            f"rail {name!r}: {key} must be a bool, got {type(value).__name__}"
        )
    return value


_FIELD_NAMES: frozenset[str] = frozenset(RailRow.__dataclass_fields__) - {"name"}
"""Derived from the dataclass, so a new field cannot be rejected as 'unknown' by a stale list."""
