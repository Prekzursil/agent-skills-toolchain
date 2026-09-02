"""Permission-set lattice for the update-time consent gate (IMP-0060).

Verdicts
--------
``WIDEN``      the candidate grants something the installed set does not cover
               (a mixed delta -- something added AND something removed -- is a
               widening too: the gate fails closed);
``NARROW``     the installed set covers the candidate and grants strictly more;
``UNCHANGED``  both sets cover each other (reordering or alias renaming only).

Three independent computations are exposed and cross-checked by
:func:`compute_delta`:

* :func:`lattice_verdict` -- pairwise ``covers(granted, requested)`` over the
  tool/scope partial order (``Write(*)`` covers ``Write(src/a.py)``);
* :func:`raw_set_verdict` -- canonical-string set containment with NO glob
  expansion.  On a covering pair the two split (NARROW on the lattice, WIDEN on
  the raw set); that split is the detector, not a picked winner;
* :func:`atom_verdict` -- pointwise membership over the finite atom universe
  built from both sides.  It must agree with the lattice; disagreement means
  ``covers()`` is broken (``Delta.lattice_atom_agree``).

Consent for a widening is explicit, persisted (:class:`ConsentStore`), keyed by
package + from-version + to-version + delta fingerprint, and never blanket.

Permission tokens
-----------------
``Tool``            every scope of ``Tool`` (same as ``Tool(*)``)
``Tool(scope)``     one glob scope, e.g. ``Write(src/**)``, ``Bash(git *)``
``ns:verb:scope``   colon form used by marketplace manifests, e.g.
                    ``net:connect:*`` covers ``net:connect:api.example``
Lower-case spellings of well-known tools (``read``, ``write``, ``bash``) are
aliases of the capitalised names and fold to them; ``Bash`` and ``Write`` stay
distinct tools.
"""
from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

WIDEN = "widen"
NARROW = "narrow"
UNCHANGED = "unchanged"

# --- catalog triples (ordered sequences: the UNCHANGED pair is a reorder) ----
WIDEN_PAIR: tuple[tuple[str, ...], tuple[str, ...]] = (
    ("Read", "Write(src/**)"),
    ("Read", "Write(src/**)", "Bash"),
)
NARROW_PAIR: tuple[tuple[str, ...], tuple[str, ...]] = (
    ("Read", "Write(src/**)", "Bash"),
    ("Read", "Write(src/**)"),
)
UNCHANGED_PAIR: tuple[tuple[str, ...], tuple[str, ...]] = (
    ("Read", "Write(src/**)"),
    ("Write(src/**)", "Read"),
)
# Negative control: a new Bash grant hidden behind reordering and alias renaming.
DISGUISED_WIDEN: tuple[tuple[str, ...], tuple[str, ...]] = (
    ("read", "write"),
    ("Write", "Bash", "Read"),
)
# Same disguise without a new grant: must stay UNCHANGED.
REORDER_RENAME_UNCHANGED: tuple[tuple[str, ...], tuple[str, ...]] = (
    ("read", "Write(src/**)"),
    ("Write(src/**)", "Read"),
)
# Reviewer-constructed wildcard scopes the catalog triples did not model.
REVIEWER_WILDCARD_WIDEN: tuple[tuple[str, ...], tuple[str, ...]] = (
    ("Read", "Write(src/**)"),
    ("Write(src/**)", "Network(*)", "Read"),
)
REVIEWER_CREDENTIAL_WILDCARD: tuple[tuple[str, ...], tuple[str, ...]] = (
    ("Read", "Write(src/**)"),
    ("Read", "Write(*)"),
)

_KNOWN_TOOLS = (
    "Read",
    "Write",
    "Edit",
    "MultiEdit",
    "NotebookEdit",
    "Bash",
    "Network",
    "Glob",
    "Grep",
    "LS",
    "WebFetch",
    "WebSearch",
    "Task",
    "Agent",
    "Skill",
    "TodoWrite",
)
_ALIASES = {name.lower(): name for name in _KNOWN_TOOLS}
_GLOB_CHARS = frozenset("*?[")


def catalog_pairs() -> dict[str, tuple[tuple[str, ...], tuple[str, ...]]]:
    """The three catalog triples keyed by their expected verdict."""
    return {"widen": WIDEN_PAIR, "narrow": NARROW_PAIR, "unchanged": UNCHANGED_PAIR}


# --- token grammar ----------------------------------------------------------
@dataclass(frozen=True)
class Permission:
    """A parsed permission token: ``tool`` plus one glob ``scope``."""

    tool: str
    scope: str
    form: str  # "paren" | "colon" | "bare"

    def canonical(self) -> str:
        if self.form == "colon":
            return f"{self.tool}:{self.scope}"
        if self.scope == "*":
            return self.tool
        return f"{self.tool}({self.scope})"


def parse_permission(perm: Any) -> Permission:
    """Parse ``Tool``, ``Tool(scope)`` or ``ns:verb:scope``; fold tool aliases."""
    text = str(perm).strip()
    if not text:
        raise ValueError("empty permission token")
    if text.endswith(")") and "(" in text:
        tool, scope = text[:-1].split("(", 1)
        form = "paren"
    elif ":" in text:
        tool, _, scope = text.rpartition(":")
        form = "colon"
    else:
        tool, scope, form = text, "*", "bare"
    tool = tool.strip()
    scope = scope.strip() or "*"
    if not tool:
        raise ValueError(f"permission token without a tool name: {text!r}")
    if scope == "**":
        scope = "*"
    tool = _ALIASES.get(tool.lower(), tool)
    return Permission(tool=tool, scope=scope, form=form)


def canonicalize(perm: Any) -> str:
    """Stable spelling of a token: whitespace stripped, aliases folded,
    ``Tool(*)`` written ``Tool``.  Globs are never expanded and ``Bash`` and
    ``Write`` stay distinct."""
    return parse_permission(perm).canonical()


def canonical_set(perms: Iterable[Any] | None) -> frozenset[str]:
    return frozenset(canonicalize(p) for p in (perms or []) if str(p).strip())


# --- the partial order ------------------------------------------------------
def _has_glob(scope: str) -> bool:
    return any(ch in _GLOB_CHARS for ch in scope)


def scope_covers(granted: str, requested: str) -> bool:
    """True when every path matched by ``requested`` is matched by ``granted``.

    Reflexive and transitive on the accepted shapes: ``*`` covers all,
    ``p/**`` covers ``p`` and anything under ``p/``, a literal covers only
    itself, any other glob covers the literals it fnmatch-es.  A non-universal
    glob is never claimed to cover a different glob (fail closed).
    """
    if granted == requested or granted == "*":
        return True
    if granted.endswith("/**"):
        prefix = granted[:-2]
        return requested.startswith(prefix) or requested == granted[:-3]
    if _has_glob(requested):
        return False
    return fnmatch.fnmatchcase(requested, granted)


def covers(granted: Any, requested: Any) -> bool:
    """Lattice order: same tool and ``granted`` scope covers ``requested``."""
    g = parse_permission(granted)
    r = parse_permission(requested)
    # ``Tool`` and ``Tool(scope)`` share one namespace; ``ns:verb:scope`` is another.
    if (g.form == "colon") != (r.form == "colon"):
        return False
    return g.tool == r.tool and scope_covers(g.scope, r.scope)


def covered_by_set(perm: Any, grant: Iterable[Any] | None = None) -> bool:
    """True when some element of ``grant`` covers ``perm`` on the lattice."""
    if not str(perm).strip():
        return False
    return any(covers(g, perm) for g in (grant or []) if str(g).strip())


def set_covers(granted: Iterable[Any], requested: Iterable[Any]) -> bool:
    """Every requested token is covered by at least one granted token."""
    grant = [g for g in granted if str(g).strip()]
    return all(covered_by_set(r, grant) for r in requested if str(r).strip())


def lattice_verdict(installed: Iterable[Any], candidate: Iterable[Any]) -> str:
    """Verdict from pairwise ``covers()``; a mixed delta is a WIDEN."""
    a = canonical_set(installed)
    b = canonical_set(candidate)
    a_covers_b = set_covers(a, b)
    b_covers_a = set_covers(b, a)
    if a_covers_b and b_covers_a:
        return UNCHANGED
    if a_covers_b:
        return NARROW
    return WIDEN


def raw_set_verdict(installed: Iterable[Any], candidate: Iterable[Any]) -> str:
    """Canonical-string set containment, no glob expansion.  Any string that
    was not granted before is a widening (fail closed)."""
    a = canonical_set(installed)
    b = canonical_set(candidate)
    if a == b:
        return UNCHANGED
    if b < a:
        return NARROW
    return WIDEN


def atom_universe(installed: Iterable[Any], candidate: Iterable[Any]) -> frozenset[str]:
    """Finite universe: every canonical token seen on either side."""
    return canonical_set(installed) | canonical_set(candidate)


def atoms_covered(grant: Iterable[str], universe: Iterable[str]) -> frozenset[str]:
    """Members of ``universe`` that some element of ``grant`` covers."""
    grant = list(grant)
    return frozenset(u for u in universe if covered_by_set(u, grant))


def atom_verdict(installed: Iterable[Any], candidate: Iterable[Any]) -> str:
    """Independent re-derivation of the lattice verdict by pointwise membership
    over the finite atom universe."""
    universe = atom_universe(installed, candidate)
    atoms_a = atoms_covered(canonical_set(installed), universe)
    atoms_b = atoms_covered(canonical_set(candidate), universe)
    if atoms_a == atoms_b:
        return UNCHANGED
    if atoms_b < atoms_a:
        return NARROW
    return WIDEN


def independent_set_containment(installed: Iterable[Any] | None, candidate: Iterable[Any] | None) -> str:
    """Raw set containment over the exact strings (no canonicalisation, no
    glob expansion).  Returns ``widen``/``narrow``/``unchanged``/``mixed``."""
    a, b = frozenset(installed or []), frozenset(candidate or [])
    if a < b:
        return WIDEN
    if b < a:
        return NARROW
    if a == b:
        return UNCHANGED
    return "mixed"


# --- the delta ----------------------------------------------------------------
@dataclass
class Delta:
    """Result of :func:`compute_delta`.  ``added``/``removed`` are sorted
    canonical tokens: what the candidate newly grants / no longer grants
    measured on the lattice (not raw string difference)."""

    verdict: str
    added: list[str]
    removed: list[str]
    lattice_verdict: str = ""
    raw_set_verdict: str = ""
    atom_verdict: str = ""
    lattice_atom_agree: bool = True
    installed: list[str] = field(default_factory=list)
    candidate: list[str] = field(default_factory=list)

    @property
    def methods_agree(self) -> bool:
        return self.lattice_atom_agree

    @property
    def signals_agree(self) -> bool:
        return self.lattice_verdict == self.raw_set_verdict

    def fingerprint(self) -> str:
        """sha256 over the canonical added/removed sets (order-free)."""
        blob = json.dumps({"added": sorted(self.added), "removed": sorted(self.removed)}, sort_keys=True)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def as_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "added": list(self.added),
            "removed": list(self.removed),
            "lattice_verdict": self.lattice_verdict,
            "raw_set_verdict": self.raw_set_verdict,
            "atom_verdict": self.atom_verdict,
            "lattice_atom_agree": self.lattice_atom_agree,
            "fingerprint": self.fingerprint(),
        }


def compute_delta(installed: Iterable[Any] | None, candidate: Iterable[Any] | None) -> Delta:
    """Compute the permission delta and cross-check the three methods."""
    inst = [str(p).strip() for p in (installed or []) if str(p).strip()]
    cand = [str(p).strip() for p in (candidate or []) if str(p).strip()]
    a = canonical_set(inst)
    b = canonical_set(cand)
    added = sorted(tok for tok in b if not covered_by_set(tok, a))
    removed = sorted(tok for tok in a if not covered_by_set(tok, b))
    lat = lattice_verdict(a, b)
    raw = raw_set_verdict(a, b)
    atom = atom_verdict(a, b)
    return Delta(
        verdict=lat,
        added=added,
        removed=removed,
        lattice_verdict=lat,
        raw_set_verdict=raw,
        atom_verdict=atom,
        lattice_atom_agree=(lat == atom),
        installed=inst,
        candidate=cand,
    )


def decide(installed: Iterable[Any] | None, candidate: Iterable[Any] | None) -> Delta:
    return compute_delta(installed, candidate)


# --- consent ------------------------------------------------------------------
def _widened_fingerprint(widened: Iterable[Any]) -> str:
    blob = json.dumps(sorted(canonical_set(widened)), sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


@dataclass
class Consent:
    """One explicit consent for one (package, from, to) widening."""

    package_id: str
    from_version: str
    to_version: str
    widened: tuple = ()

    def key(self) -> tuple[str, str, str]:
        return (self.package_id, self.from_version, self.to_version)

    def fingerprint(self) -> str:
        return _widened_fingerprint(self.widened)

    def authorizes(self, added: Iterable[Any]) -> bool:
        """Every newly granted token is inside the consented widening."""
        return canonical_set(added) <= canonical_set(self.widened)

    def to_json(self) -> dict[str, Any]:
        return {
            "package_id": self.package_id,
            "from_version": self.from_version,
            "to_version": self.to_version,
            "widened": [str(w) for w in self.widened],
            "fingerprint": self.fingerprint(),
        }

    @classmethod
    def from_json(cls, row: dict[str, Any]) -> "Consent":
        return cls(
            package_id=str(row.get("package_id", "")),
            from_version=str(row.get("from_version", "")),
            to_version=str(row.get("to_version", "")),
            widened=tuple(str(w) for w in (row.get("widened") or [])),
        )


class MemoryConsentStore:
    """In-memory consent records; never blanket."""

    blanket = False

    def __init__(self) -> None:
        self._items: list[Consent] = []

    @property
    def records(self) -> list[Consent]:
        return list(self._items)

    def persist(self, consent: Consent) -> None:
        if not isinstance(consent, Consent):
            raise TypeError("persist() takes a Consent")
        self._items = [c for c in self._items if c.key() != consent.key()]
        self._items.append(consent)

    def find(self, package_id: str, from_version: str, to_version: str) -> Consent | None:
        for item in self._items:
            if item.key() == (package_id, from_version, to_version):
                return item
        return None

    def allows(self, package_id: str, from_version: str, to_version: str, added: Iterable[Any]) -> bool:
        item = self.find(package_id, from_version, to_version)
        if item is None:
            return False
        return item.authorizes(added)


class ConsentStore(MemoryConsentStore):
    """Disk-backed consent records: ``{"blanket": false, "records": [...]}``.

    Records are keyed by package + from + to + delta fingerprint; a record for
    1.0.0 -> 2.0.0 never authorizes 2.0.0 -> 3.0.0.
    """

    SCHEMA_VERSION = 1

    def __init__(self, path: Path | str) -> None:
        super().__init__()
        self.path = Path(path)
        if self.path.is_file():
            self.load()

    def load(self) -> None:
        doc = json.loads(self.path.read_text(encoding="utf-8"))
        if doc.get("blanket") is not False:
            raise ValueError(f"consent store {self.path} is not a non-blanket store")
        self._items = [Consent.from_json(r) for r in (doc.get("records") or [])]

    def to_json(self) -> dict[str, Any]:
        return {
            "schema_version": self.SCHEMA_VERSION,
            "blanket": False,
            "records": [c.to_json() for c in self._items],
        }

    def save(self) -> None:
        _atomic_write(self.path, (json.dumps(self.to_json(), indent=2, sort_keys=True) + "\n").encode("utf-8"))

    def persist(self, consent: Consent) -> None:
        super().persist(consent)
        self.save()


# --- the gate -------------------------------------------------------------------
REASON_REQUIRES_CONSENT = "permission-widening-requires-consent"


@dataclass
class GateResult:
    """Outcome of :func:`gate_update`.  ``wrote`` is True only when bytes hit
    ``dest``; a blocked update leaves ``dest`` byte-identical."""

    proceed: bool
    wrote: bool
    verdict: str
    reason: str
    delta: Delta
    consent: Consent | None = None
    dest: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "proceed": self.proceed,
            "wrote": self.wrote,
            "verdict": self.verdict,
            "reason": self.reason,
            "delta": self.delta.as_dict(),
            "consent": self.consent.to_json() if self.consent else None,
            "dest": self.dest,
        }


def _atomic_write(dest: Path, body: bytes) -> None:
    """Write via a same-directory temp file + rename so ``dest`` is never
    observed half-written."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{dest.name}.", suffix=".tmp", dir=str(dest.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(body)
        os.replace(tmp, dest)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def gate_update(
    package_id: str,
    from_version: str,
    to_version: str,
    installed: Iterable[Any] | None,
    candidate: Iterable[Any] | None,
    consent_store: MemoryConsentStore | None = None,
    consent_action: bool = False,
    dest: Path | str | None = None,
    candidate_body: bytes | None = None,
) -> GateResult:
    """Decide whether the candidate may be applied, then (only then) write it.

    NARROW and UNCHANGED proceed silently.  WIDEN proceeds only with an
    explicit ``consent_action`` (which is persisted to ``consent_store`` when
    one is given) or a previously persisted consent for exactly this
    (package, from, to) pair covering every added token.  Otherwise nothing is
    written and ``reason`` is ``permission-widening-requires-consent``.
    """
    delta = compute_delta(installed, candidate)
    dest_str = str(dest) if dest is not None else None
    consent: Consent | None = None
    if delta.verdict == WIDEN:
        if consent_action:
            consent = Consent(package_id, from_version, to_version, tuple(delta.added))
            if consent_store is not None:
                consent_store.persist(consent)
            reason = "widening-consented"
        elif consent_store is not None and consent_store.allows(package_id, from_version, to_version, delta.added):
            consent = consent_store.find(package_id, from_version, to_version)
            reason = "widening-previously-consented"
        else:
            return GateResult(
                proceed=False,
                wrote=False,
                verdict=WIDEN,
                reason=REASON_REQUIRES_CONSENT,
                delta=delta,
                dest=dest_str,
            )
    else:
        reason = f"{delta.verdict}-proceeds-silently"
    wrote = False
    if dest is not None and candidate_body is not None:
        _atomic_write(Path(dest), bytes(candidate_body))
        wrote = True
    return GateResult(
        proceed=True,
        wrote=wrote,
        verdict=delta.verdict,
        reason=reason,
        delta=delta,
        consent=consent,
        dest=dest_str,
    )


def gate_from_manifests(
    installed_manifest: dict[str, Any],
    candidate_manifest: dict[str, Any],
    consent_store: MemoryConsentStore | None = None,
    consent_action: bool = False,
    dest: Path | str | None = None,
    candidate_body: bytes | None = None,
) -> GateResult:
    """Run :func:`gate_update` on two ``plugin.json``-style manifests
    (``name``, ``version``, ``permissions``)."""
    package_id = str(candidate_manifest.get("name") or installed_manifest.get("name") or "")
    if not package_id:
        raise ValueError("manifests carry no package name")
    return gate_update(
        package_id=package_id,
        from_version=str(installed_manifest.get("version") or ""),
        to_version=str(candidate_manifest.get("version") or ""),
        installed=installed_manifest.get("permissions") or [],
        candidate=candidate_manifest.get("permissions") or [],
        consent_store=consent_store,
        consent_action=consent_action,
        dest=dest,
        candidate_body=candidate_body,
    )


__all__ = [
    "WIDEN",
    "NARROW",
    "UNCHANGED",
    "WIDEN_PAIR",
    "NARROW_PAIR",
    "UNCHANGED_PAIR",
    "DISGUISED_WIDEN",
    "REORDER_RENAME_UNCHANGED",
    "REVIEWER_WILDCARD_WIDEN",
    "REVIEWER_CREDENTIAL_WILDCARD",
    "REASON_REQUIRES_CONSENT",
    "Permission",
    "Delta",
    "Consent",
    "MemoryConsentStore",
    "ConsentStore",
    "GateResult",
    "catalog_pairs",
    "parse_permission",
    "canonicalize",
    "canonical_set",
    "scope_covers",
    "covers",
    "covered_by_set",
    "set_covers",
    "lattice_verdict",
    "raw_set_verdict",
    "atom_verdict",
    "independent_set_containment",
    "compute_delta",
    "decide",
    "gate_update",
    "gate_from_manifests",
]
