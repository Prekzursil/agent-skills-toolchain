"""The canonical registry index: load, verify, search, resolve, federate.

FAIL-CLOSED LOADING
    Marketplace-first FM-1 rates the index a single point of TOTAL failure: one malformed
    entry unresolves every package. So :func:`load_index` validates the whole document
    before any entry is readable and raises otherwise -- there is no partial view. A caller
    cannot accidentally operate on the half of an index that happened to parse.

REVOCATION AND ADVISORIES ARE NOT OPTIONAL DATA
    :func:`load_revocation` and :func:`load_advisories` return ``None`` when the list is
    ABSENT, and the caller's trust policy decides what absence means
    (``on_missing.revocation_list``, default ``refuse``). This module deliberately does not
    default an absent list to "nothing is revoked": that substitution is exactly how a
    revocation channel becomes decorative, and it is the failure mode this build was told
    to prove it does not have.

FEDERATION CANNOT INTRODUCE TRUST
    A mirror is another filesystem root. :func:`federate` merges mirror entries into a
    resolution view, but every entry keeps its own publisher signature and is re-verified
    by the installer against the CONSUMER's trust policy. A mirror in
    ``verify-and-require-primary-index`` mode must additionally match the primary index on
    ``(name, version, manifest_digest)``, which defeats a mirror serving a package the
    primary never published.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import schemas, versions
from .canon import canonical_bytes, digest_doc, ensure_within, read_json
from .crypto import verify_document

INDEX_NAME = "index.json"


class RegistryError(RuntimeError):
    """The registry root is unusable (missing, malformed, or fails its own schema)."""


@dataclass(frozen=True)
class RegistryRoot:
    """A filesystem registry root and its loaded, validated documents."""

    root: Path
    index: dict[str, Any]
    mirror_id: str | None = None
    trust_mode: str = "verify-always"

    @property
    def registry_id(self) -> str:
        return str(self.index["registry_id"])

    @property
    def entries(self) -> list[dict[str, Any]]:
        return list(self.index.get("entries", []))


def index_path(root: str | Path) -> Path:
    return Path(root) / INDEX_NAME


def load_index(root: str | Path) -> dict[str, Any]:
    """Load and fully validate ``<root>/index.json``. Raises on anything less than valid."""
    path = index_path(root)
    if not path.is_file():
        raise RegistryError(f"no registry index at {path}")
    try:
        doc = read_json(path)
    except ValueError as exc:
        raise RegistryError(
            f"registry index is not parseable JSON: {path}: {exc}"
        ) from exc
    try:
        schemas.validate("registry-index", doc)
    except schemas.ValidationFailed as exc:
        raise RegistryError(
            f"registry index fails its own schema: {path}: {exc}"
        ) from exc
    return doc


def open_root(
    root: str | Path, *, mirror_id: str | None = None, trust_mode: str = "verify-always"
) -> RegistryRoot:
    return RegistryRoot(Path(root).resolve(), load_index(root), mirror_id, trust_mode)


def index_digest(index: dict[str, Any]) -> str:
    """Digest over the canonical index INCLUDING its signature -- the lockfile pins this."""
    return digest_doc(index)


def verify_index_signature(
    index: dict[str, Any], maintainer_keys: list[str]
) -> tuple[bool, str]:
    """The index must be signed by one of the consumer's declared maintainer keys."""
    block = index.get("signature") or {}
    public = block.get("public_key")
    if public not in maintainer_keys:
        return (
            False,
            f"index signed by {public!r}, which is not a declared registry-maintainer key",
        )
    return verify_document(index, "mkt.index.v1", expected_public_key=public)


# --------------------------------------------------------------------------- #
# search / resolve
# --------------------------------------------------------------------------- #


def search(
    index: dict[str, Any],
    *,
    text: str | None = None,
    category: str | None = None,
    tag: str | None = None,
    channel: str | None = None,
    publisher: str | None = None,
    include_yanked: bool = False,
    include_deprecated: bool = True,
) -> list[dict[str, Any]]:
    """Filter index entries. Case-insensitive substring over name + summary + tags.

    Yanked versions are hidden by DEFAULT: a yank is a statement that a version should not
    be picked up by discovery. It remains installable by exact pin, which is the whole
    difference between a yank and a revocation.
    """
    needle = (text or "").strip().lower()
    out = []
    for entry in index.get("entries", []):
        if entry.get("yanked") and not include_yanked:
            continue
        if entry.get("deprecated") and not include_deprecated:
            continue
        if channel is not None and entry.get("channel") != channel:
            continue
        if publisher is not None and entry.get("publisher") != publisher:
            continue
        if category is not None and category not in (entry.get("categories") or []):
            continue
        if tag is not None and tag not in (entry.get("tags") or []):
            continue
        if needle:
            haystack = " ".join(
                [
                    entry.get("name", ""),
                    entry.get("summary", ""),
                    " ".join(entry.get("tags") or []),
                ]
            ).lower()
            if needle not in haystack:
                continue
        out.append(entry)
    return sorted(out, key=lambda e: (e["name"], e["version"]))


def collections(index: dict[str, Any]) -> list[dict[str, Any]]:
    return list(index.get("collections", []))


def collection_members(
    index: dict[str, Any], collection_id: str
) -> list[dict[str, Any]]:
    """Resolve a collection to concrete index entries, honouring each member's range."""
    col = next(
        (c for c in collections(index) if c["collection_id"] == collection_id), None
    )
    if col is None:
        raise RegistryError(f"no such collection: {collection_id!r}")
    out = []
    for member in col["members"]:
        entry = resolve(index, member["name"], member.get("range", "*"))
        if entry is not None:
            out.append(entry)
    return out


def resolve(
    index: dict[str, Any],
    name: str,
    range_text: str = "*",
    *,
    channel: str | None = None,
    include_yanked: bool = False,
) -> dict[str, Any] | None:
    """Highest version of ``name`` satisfying ``range_text``, or ``None``.

    ``channel`` is a FILTER, never a fallback: asking for ``stable`` and getting a ``beta``
    build because no stable one existed is the kind of silent widening this build refuses.
    """
    candidates = [
        e
        for e in index.get("entries", [])
        if e["name"] == name
        and (channel is None or e["channel"] == channel)
        and (include_yanked or not e.get("yanked"))
    ]
    if not candidates:
        return None
    winner = versions.best([e["version"] for e in candidates], range_text)
    if winner is None:
        return None
    return next(e for e in candidates if e["version"] == winner)


def all_versions(index: dict[str, Any], name: str) -> list[str]:
    return sorted({e["version"] for e in index.get("entries", []) if e["name"] == name})


def publisher_record(index: dict[str, Any], publisher_id: str) -> dict[str, Any] | None:
    return next(
        (p for p in index.get("publishers", []) if p["id"] == publisher_id), None
    )


def publisher_key(
    index: dict[str, Any], publisher_id: str, public_key: str
) -> dict[str, Any] | None:
    """The key record for ``public_key`` under ``publisher_id``, or ``None`` if unknown."""
    rec = publisher_record(index, publisher_id)
    if rec is None:
        return None
    return next((k for k in rec["keys"] if k["public_key"] == public_key), None)


def manifest_path(root: str | Path, entry: dict[str, Any]) -> Path:
    """Containment-checked absolute path to an entry's manifest inside the registry root."""
    return ensure_within(root, entry["manifest_path"])


def load_manifest(root: str | Path, entry: dict[str, Any]) -> dict[str, Any]:
    path = manifest_path(root, entry)
    if not path.is_file():
        raise RegistryError(
            f"index entry {entry['name']}@{entry['version']} names a manifest that does not exist: {path}"
        )
    doc = read_json(path)
    schemas.validate("package-manifest", doc)
    return doc


# --------------------------------------------------------------------------- #
# revocation / advisories -- returned as None when ABSENT, never as "empty"
# --------------------------------------------------------------------------- #


def load_revocation(root: str | Path, index: dict[str, Any]) -> dict[str, Any] | None:
    rel = index.get("revocation_path")
    if not rel:
        return None
    path = ensure_within(root, rel)
    if not path.is_file():
        return None
    doc = read_json(path)
    schemas.validate("revocation", doc)
    return doc


def load_advisories(root: str | Path, index: dict[str, Any]) -> dict[str, Any] | None:
    rel = index.get("advisory_path")
    if not rel:
        return None
    path = ensure_within(root, rel)
    if not path.is_file():
        return None
    doc = read_json(path)
    schemas.validate("advisory", doc)
    return doc


def revocations_for(
    revocation: dict[str, Any],
    name: str,
    version: str,
    *,
    public_key: str | None = None,
) -> list[dict[str, Any]]:
    """Every revocation that matches this coordinate. Empty list means genuinely not revoked."""
    hits = []
    for rev in revocation.get("revocations", []):
        scope = rev["scope"]
        kind = scope["kind"]
        if kind == "package" and scope.get("name") == name:
            hits.append(rev)
        elif (
            kind == "version"
            and scope.get("name") == name
            and scope.get("version") == version
        ):
            hits.append(rev)
        elif kind == "range" and scope.get("name") == name:
            try:
                if versions.satisfies(version, scope["range"]):
                    hits.append(rev)
            except versions.VersionError:
                # An unparseable revocation range REVOKES. A revocation we cannot read is
                # not a revocation we may ignore.
                hits.append(rev)
        elif (
            kind == "key"
            and public_key is not None
            and scope.get("public_key") == public_key
        ):
            hits.append(rev)
    return hits


def open_advisories_for(
    advisories: dict[str, Any], name: str, version: str
) -> list[dict[str, Any]]:
    """Advisories in a state that still counts as OPEN for this version.

    ``fixed``, ``withdrawn`` and ``disputed`` do not gate. ``disputed`` is deliberately
    non-gating and deliberately visible: the dispute process exists so a contested claim
    stops blocking installs, and the moderation case record is where the contest lives.
    """
    out = []
    for adv in advisories.get("advisories", []):
        if adv["state"] in {"fixed", "withdrawn", "disputed"}:
            continue
        for aff in adv["affected"]:
            if aff["name"] != name:
                continue
            try:
                if versions.satisfies(version, aff["range"]):
                    out.append(adv)
                    break
            except versions.VersionError:
                out.append(adv)
                break
    return out


SEVERITY_ORDER = ("none", "low", "medium", "high", "critical")


def severity_rank(value: str) -> int:
    try:
        return SEVERITY_ORDER.index(value)
    except ValueError:
        # An unrecognised severity is treated as the WORST, not the mildest.
        return len(SEVERITY_ORDER)


# --------------------------------------------------------------------------- #
# federation
# --------------------------------------------------------------------------- #


@dataclass
class FederatedView:
    """A resolution view over a primary registry plus its enabled mirrors."""

    primary: RegistryRoot
    mirrors: list[RegistryRoot] = field(default_factory=list)
    rejected: list[dict[str, str]] = field(default_factory=list)

    def roots(self) -> list[RegistryRoot]:
        return [self.primary, *self.mirrors]

    def resolve(
        self, name: str, range_text: str = "*", *, channel: str | None = None
    ) -> tuple[RegistryRoot, dict[str, Any]] | None:
        """First root, in priority order, that can satisfy the request."""
        for root in self.roots():
            entry = resolve(root.index, name, range_text, channel=channel)
            if entry is None:
                continue
            if (
                root.trust_mode == "verify-and-require-primary-index"
                and root is not self.primary
            ):
                primary_entry = resolve(
                    self.primary.index,
                    name,
                    f"={entry['version']}",
                    channel=channel,
                    include_yanked=True,
                )
                if (
                    primary_entry is None
                    or primary_entry["manifest_digest"] != entry["manifest_digest"]
                ):
                    self.rejected.append(
                        {
                            "mirror": str(root.mirror_id),
                            "package": f"{name}@{entry['version']}",
                            "reason": "mirror entry is absent from, or disagrees with, the primary index",
                        }
                    )
                    continue
            return root, entry
        return None


def federate(primary_root: str | Path) -> FederatedView:
    """Open the primary registry and every enabled mirror it declares, in priority order."""
    primary = open_root(primary_root)
    mirrors: list[RegistryRoot] = []
    for mirror in sorted(primary.index.get("mirrors", []), key=lambda m: m["priority"]):
        if not mirror.get("enabled", True):
            continue
        mirror_root = ensure_within(primary.root, mirror["root"])
        if not index_path(mirror_root).is_file():
            continue
        mirrors.append(
            open_root(
                mirror_root,
                mirror_id=mirror["mirror_id"],
                trust_mode=mirror["trust_mode"],
            )
        )
    return FederatedView(primary=primary, mirrors=mirrors)


def signed_index_bytes(index: dict[str, Any]) -> bytes:
    """The canonical bytes of the index as signed -- exposed for drift diagnostics."""
    return canonical_bytes({k: v for k, v in index.items() if k != "signature"})
