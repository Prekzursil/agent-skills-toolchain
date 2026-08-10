"""Canonical vendor identity - the resolver that closes DEFECT D1.

WHAT D1 WAS
-----------
``completion_predicate.py`` enforced "the reviewer must be a DIFFERENT vendor than the
executor" with a raw string comparison over an unvalidated free-text field::

    if rev_vendor == exec_vendor:   # <- the whole gate

Measured by ``platform/architecture/_probe_crossvendor_alias_hole.py`` against the pre-fix
tree: **10 of 10 same-vendor alias pairs were accepted as cross-vendor** -
``anthropic``/``Anthropic``, ``anthropic``/``claude``, ``openai``/``codex``,
``google``/``gemini``, ``anthropic``/``anthropic `` (trailing space), and so on. The gate was
not dead - identical spellings were rejected and a genuinely distinct vendor was accepted -
it was permissive in exactly the way that defeats its purpose, which is the worse failure:
a guard that converts a bug into a green.

WHAT THIS MODULE DOES
---------------------
Resolves a free-text vendor string to a CANONICAL IDENTITY using the alias table in
``platform/registry/VENDOR-REGISTRY.json``, and answers the only question the predicate
actually needs: are these two strings the same vendor, genuinely different vendors, or is
that NOT COMPUTABLE?

Three outcomes, never two. ``NOT-COMPUTABLE`` is first-class and it BLOCKS - it is what an
unrecognized vendor string, a hosting plane, or a placeholder resolves to. The pre-fix code
had no such state: anything that was not byte-equal was treated as distinct, so an
unregistered string silently satisfied the strongest gate on the platform.

TWO DIRECTIONS OF WRONGNESS, BOTH GUARDED
-----------------------------------------
Over-folding is as damaging as under-folding. ``bedrock``, ``vertex``, ``azure`` and
``openrouter`` each serve SEVERAL vendors' models, so folding them into one vendor would
make the gate report a genuinely cross-vendor review as same-vendor and BLOCK a valid
completion. They are registered with ``establishes_distinctness: false`` and resolve to
NOT-COMPUTABLE rather than to a vendor. The registry's ``alias_exclusions`` block records
this rule as data.

The alias table is DATA, not branches, so it can be audited and extended without touching
this file - and ``test_vendor_identity.py`` asserts that the table, the receipt schema's
``vendor_id`` enum and the councilspec vendor enum all stay in agreement.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

__all__ = [
    "Comparison",
    "IdentityKind",
    "RESOLVER_ID",
    "REGISTRY_PATH",
    "Resolution",
    "VendorIdentity",
    "VendorRegistry",
    "canonical_ids",
    "compare",
    "load_registry",
    "normalize",
    "recognized_tokens",
    "resolve",
]

RESOLVER_ID = "platform/lib/vendor_identity.py@v1"

REGISTRY_PATH = (
    Path(__file__).resolve().parents[1] / "registry" / "VENDOR-REGISTRY.json"
)

#: Domain suffixes stripped as a LAST-RESORT lookup candidate (see _candidates). Stripping is
#: never destructive: the un-stripped form is always tried first, so ``x.ai`` still resolves via
#: the dot-to-dash candidate rather than being mangled to a bare ``x``.
_DOMAIN_SUFFIXES: tuple[str, ...] = (
    ".com",
    ".ai",
    ".co",
    ".io",
    ".org",
    ".net",
    ".dev",
)

#: Any run of whitespace / underscore / hyphen collapses to a single hyphen, so ``open ai``,
#: ``open_ai`` and ``open--ai`` are one token.
_SEPARATORS = re.compile(r"[\s_\-]+")

#: Unicode categories Cc (control) and Cf (format) are removed outright. A control byte inside a
#: vendor field is never legitimate and stripping it here means it cannot survive into a terminal
#: or a log line (rules/common/bash-hud-and-terminal-emit.md section 2).
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


class IdentityKind(str, Enum):
    """What KIND of thing a registry entry names. Only some kinds are vendor identities."""

    MODEL_VENDOR = "model_vendor"
    HUMAN = "human"
    HOSTING_SUBSTRATE = "hosting_substrate"
    PLACEHOLDER = "placeholder"


class Resolution(str, Enum):
    """How a raw string resolved. Only KNOWN can participate in a distinctness verdict."""

    #: Resolved to a registry entry whose ``establishes_distinctness`` is true.
    KNOWN = "KNOWN"
    #: Resolved to a registry entry that is NOT a vendor identity (hosting plane, placeholder).
    NOT_AN_IDENTITY = "NOT-AN-IDENTITY"
    #: Not present in the registry at all. REJECTED - never treated as "distinct because different".
    UNKNOWN = "UNKNOWN"
    #: Absent, empty, or whitespace/control characters only.
    EMPTY = "EMPTY"
    #: Present but not a string (int, dict, list, ...).
    MALFORMED = "MALFORMED"


class Comparison(str, Enum):
    """The three-valued answer to "are these the same vendor?"."""

    SAME_VENDOR = "SAME-VENDOR"
    CROSS_VENDOR = "CROSS-VENDOR"
    NOT_COMPUTABLE = "NOT-COMPUTABLE"


@dataclass(frozen=True)
class VendorIdentity:
    """One resolved vendor string. ``raw`` is preserved so a report can quote what was declared."""

    raw: Any
    normalized: str
    canonical_id: str | None
    display_name: str | None
    kind: IdentityKind | None
    resolution: Resolution
    establishes_distinctness: bool
    matched_alias: str | None = None

    @property
    def is_known(self) -> bool:
        return self.resolution is Resolution.KNOWN

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw": self.raw if isinstance(self.raw, str) else repr(self.raw),
            "normalized": self.normalized,
            "canonical_id": self.canonical_id,
            "display_name": self.display_name,
            "kind": self.kind.value if self.kind else None,
            "resolution": self.resolution.value,
            "establishes_distinctness": self.establishes_distinctness,
            "matched_alias": self.matched_alias,
        }


@dataclass(frozen=True)
class VendorRegistry:
    """The loaded alias table. Immutable; build one with :func:`load_registry`."""

    registry_id: str
    schema_version: str
    #: normalized alias -> canonical id
    alias_index: Mapping[str, str]
    #: canonical id -> the registry entry
    entries: Mapping[str, Mapping[str, Any]]

    def entry(self, canonical_id: str) -> Mapping[str, Any]:
        return self.entries[canonical_id]

    @property
    def canonical_ids(self) -> tuple[str, ...]:
        return tuple(self.entries)

    @property
    def distinctness_capable_ids(self) -> tuple[str, ...]:
        return tuple(
            cid
            for cid, e in self.entries.items()
            if bool(e.get("establishes_distinctness"))
        )

    @property
    def recognized_tokens(self) -> tuple[str, ...]:
        """Every string the schema layer should accept: canonical ids plus every alias."""
        return tuple(sorted(self.alias_index))


def _normalize_key(value: str) -> str:
    """Fold one token to its lookup key. Whitespace/case/separators are not identity."""
    folded = unicodedata.normalize("NFKC", value)
    folded = _CONTROL.sub("", folded)
    folded = folded.strip().casefold()
    folded = _SEPARATORS.sub("-", folded)
    return folded.strip("-")


def normalize(value: Any) -> str:
    """Public normalizer. Non-strings and blanks normalize to ``""``."""
    if not isinstance(value, str):
        return ""
    return _normalize_key(value)


def _candidates(key: str) -> tuple[str, ...]:
    """Lookup forms tried in order. The un-mangled key always goes first."""
    forms = [key]
    if "." in key:
        dotted = _SEPARATORS.sub("-", key.replace(".", "-")).strip("-")
        if dotted and dotted not in forms:
            forms.append(dotted)
    for suffix in _DOMAIN_SUFFIXES:
        if key.endswith(suffix) and len(key) > len(suffix):
            stripped = key[: -len(suffix)].strip("-.")
            if stripped and stripped not in forms:
                forms.append(stripped)
    return tuple(forms)


def load_registry(path: Path | str | None = None) -> VendorRegistry:
    """Read and index the registry. Raises on a duplicate alias - an ambiguous table is a defect."""
    p = Path(path) if path is not None else REGISTRY_PATH
    raw = json.loads(p.read_text(encoding="utf-8"))
    entries: dict[str, Mapping[str, Any]] = {}
    alias_index: dict[str, str] = {}
    for entry in raw.get("identities", []):
        cid = entry["id"]
        if cid in entries:
            raise ValueError(f"duplicate canonical vendor id in {p}: {cid!r}")
        entries[cid] = entry
        for alias in [cid, *entry.get("aliases", [])]:
            key = _normalize_key(alias)
            if not key:
                raise ValueError(f"empty alias for vendor {cid!r} in {p}")
            owner = alias_index.get(key)
            if owner is not None and owner != cid:
                raise ValueError(
                    f"alias {alias!r} in {p} maps to both {owner!r} and {cid!r}; an "
                    "ambiguous alias table cannot ground a distinctness verdict"
                )
            alias_index[key] = cid
    if not entries:
        raise ValueError(f"{p} declares no identities")
    return VendorRegistry(
        registry_id=raw.get("registry_id", str(p)),
        schema_version=raw.get("schema_version", ""),
        alias_index=alias_index,
        entries=entries,
    )


_CACHE: VendorRegistry | None = None


def _default_registry() -> VendorRegistry:
    global _CACHE
    if _CACHE is None:
        _CACHE = load_registry()
    return _CACHE


def canonical_ids(registry: VendorRegistry | None = None) -> tuple[str, ...]:
    return (registry or _default_registry()).canonical_ids


def recognized_tokens(registry: VendorRegistry | None = None) -> tuple[str, ...]:
    return (registry or _default_registry()).recognized_tokens


def resolve(value: Any, registry: VendorRegistry | None = None) -> VendorIdentity:
    """Resolve one vendor string to a canonical identity.

    An unrecognized string returns ``Resolution.UNKNOWN`` with
    ``establishes_distinctness=False``. That is the whole point of D1: an unknown string is
    REJECTED, never promoted to "a different vendor" on the strength of not matching.
    """
    reg = registry or _default_registry()
    if not isinstance(value, str):
        empty_res = Resolution.EMPTY if value is None else Resolution.MALFORMED
        return VendorIdentity(
            raw=value,
            normalized="",
            canonical_id=None,
            display_name=None,
            kind=None,
            resolution=empty_res,
            establishes_distinctness=False,
        )
    key = _normalize_key(value)
    if not key:
        return VendorIdentity(
            raw=value,
            normalized="",
            canonical_id=None,
            display_name=None,
            kind=None,
            resolution=Resolution.EMPTY,
            establishes_distinctness=False,
        )
    for form in _candidates(key):
        cid = reg.alias_index.get(form)
        if cid is None:
            continue
        entry = reg.entry(cid)
        capable = bool(entry.get("establishes_distinctness"))
        return VendorIdentity(
            raw=value,
            normalized=key,
            canonical_id=cid,
            display_name=entry.get("display_name"),
            kind=IdentityKind(entry["kind"]),
            resolution=Resolution.KNOWN if capable else Resolution.NOT_AN_IDENTITY,
            establishes_distinctness=capable,
            matched_alias=form,
        )
    return VendorIdentity(
        raw=value,
        normalized=key,
        canonical_id=None,
        display_name=None,
        kind=None,
        resolution=Resolution.UNKNOWN,
        establishes_distinctness=False,
    )


def _unresolved_reason(who: str, ident: VendorIdentity) -> str:
    if ident.resolution is Resolution.EMPTY:
        return f"the {who} vendor is undeclared or blank"
    if ident.resolution is Resolution.MALFORMED:
        return f"the {who} vendor is not a string ({ident.to_dict()['raw']})"
    if ident.resolution is Resolution.UNKNOWN:
        return (
            f"the {who} vendor {ident.raw!r} (normalized {ident.normalized!r}) is not in "
            f"{REGISTRY_PATH.name}, so it is REJECTED rather than assumed distinct; register "
            "it there to settle this"
        )
    kind = ident.kind.value if ident.kind else "unrecognized"
    return (
        f"the {who} vendor {ident.raw!r} resolves to {ident.canonical_id!r}, which is a "
        f"{kind} and not a vendor identity, so vendor distinctness is not computable from it"
    )


def compare(
    executor_vendor: Any,
    reviewer_vendor: Any,
    registry: VendorRegistry | None = None,
) -> tuple[Comparison, str, dict[str, Any]]:
    """Compare two vendor strings by CANONICAL IDENTITY.

    Returns ``(comparison, reason, detail)``. ``detail`` carries both resolutions so a caller
    can put the evidence in a receipt instead of just a boolean.
    """
    reg = registry or _default_registry()
    ex = resolve(executor_vendor, reg)
    rv = resolve(reviewer_vendor, reg)
    detail: dict[str, Any] = {
        "resolver_id": RESOLVER_ID,
        "registry_id": reg.registry_id,
        "executor": ex.to_dict(),
        "reviewer": rv.to_dict(),
    }
    for who, ident in (("executor", ex), ("reviewer", rv)):
        if not ident.is_known:
            return (
                Comparison.NOT_COMPUTABLE,
                _unresolved_reason(who, ident),
                detail,
            )
    if ex.canonical_id == rv.canonical_id:
        return (
            Comparison.SAME_VENDOR,
            f"executor {executor_vendor!r} and reviewer {reviewer_vendor!r} both resolve to "
            f"vendor {ex.canonical_id!r}; a same-vendor reviewer inherits the executor's "
            "blind spots",
            detail,
        )
    return (
        Comparison.CROSS_VENDOR,
        f"executor resolves to {ex.canonical_id!r} and reviewer to {rv.canonical_id!r} - "
        "genuinely distinct vendors",
        detail,
    )
