"""Plugin installer: typed handoff -> safe extract -> staged projection -> atomic activation.

The installer is the single placement authority for plugin payloads.  Every
caller -- the marketplace's ``install_from_handoff`` delegation, the repair
seeder, direct tooling -- ends up in :func:`install_direct`, which takes only
*typed* arguments.  Nothing inside the package (``plugin.json``,
``package.json`` scripts, forged ``projection_map`` fields) is consulted for
placement decisions; the manifest is just another file that gets copied.

Pipeline for one transaction::

    dest_home/
      .staging/<transaction_id>/extract/   <- _safe_extract: tar members, filter="data"
      .staging/<transaction_id>/stage/     <- _project_into_stage: shutil.copy2 per entry
      .staging/<transaction_id>/previous/  <- the old live root, parked during _activate
      .grants/<package_id>.json            <- permissions accepted for this package
      plugins/<package_id>/                <- live root, swapped in with os.replace

Safety properties (each is enforced in code, not by convention):

* the payload's sha256 must equal the declared digest before any byte is read
  as an archive (``DigestMismatchError``);
* archive members that are links, devices or fifos, carry absolute or ``..``
  paths, or exceed the size/count budget are refused before extraction
  (``UnsafeArchiveError``); extraction itself runs under ``filter="data"``;
* projection entries must name regular files inside the extracted payload and
  destinations inside the package's own live root, and the staged tree must
  equal the projected set exactly (``ProjectionError``);
* a re-install whose declared permissions strictly widen the recorded grant
  is refused (``PermissionWideningBlocked``);
* the live root is replaced with a single ``os.replace`` and restored if the
  swap fails (``ActivationError``); a refused install leaves ``dest_home`` as
  it was found;
* the installer never spawns a process and never writes outside ``dest_home``:
  an install-time script in the payload is at most a copied file.

The workspace directory is transaction-scoped and removed on both success and
failure, so two homes installed from the same payload under different
transaction ids hold identical file sets.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import shutil
import tarfile
from pathlib import Path
from typing import Any, Iterable, Mapping

from plugin import errors as _errors
from plugin.payload import payload_digest as _tree_digest
from plugin.permission_diff import WIDEN, compute_delta

SCHEMA_VERSION = 1
HANDOFF_KIND = "install-handoff"
DIGEST_ALGORITHM = "sha256"

PLUGINS_DIR = "plugins"
STAGING_DIR = ".staging"
GRANTS_DIR = ".grants"

MAX_MEMBERS = 10_000
MAX_MEMBER_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024

_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._@+-]{0,127}$")
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
_DRIVE_RE = re.compile(r"^[A-Za-z]:")
_RESERVED_NAMES = frozenset(
    {"con", "prn", "aux", "nul"}
    | {f"com{i}" for i in range(1, 10)}
    | {f"lpt{i}" for i in range(1, 10)}
)


# --------------------------------------------------------------------------- errors


class InstallerError(Exception):
    """Base class: the install was refused and nothing was activated."""


class HandoffError(InstallerError, _errors.InstallError):
    """The handoff or an argument is untyped, malformed or unsafe."""


class MissingTransactionIdError(HandoffError, _errors.MissingTransactionIdError):
    """No transaction id was supplied; no files may be placed."""


class DigestMismatchError(InstallerError, _errors.DigestMismatchError):
    """The payload's sha256 does not equal the declared digest."""


class UnsafeArchiveError(InstallerError, _errors.InstallError):
    """An archive member would escape the stage, is a link or device, or exceeds the budget."""


class ProjectionError(InstallerError, _errors.ProjectionError):
    """A projection entry escapes its root, names a missing source, or the stage census disagrees."""


class PermissionWideningBlocked(InstallerError, _errors.PermissionWideningBlocked):
    """The candidate grant strictly widens the grant recorded for ``package_id``."""

    def __init__(self, added: Iterable[str], *, installed: Iterable[str], candidate: Iterable[str]) -> None:
        super().__init__(sorted(added), installed=sorted(installed), candidate=sorted(candidate))


class ActivationError(InstallerError, _errors.InstallError):
    """The live root could not be swapped in; the previous root was restored when possible."""


# --------------------------------------------------------------------------- helpers


def _posix(value: str) -> str:
    return value.replace("\\", "/")


def _require_token(value: Any, field: str) -> str:
    """Validate a single path-component identifier (package or transaction id)."""
    if not isinstance(value, str) or not _TOKEN_RE.match(value):
        raise HandoffError(f"{field} must match {_TOKEN_RE.pattern}, got {value!r}")
    if value.split(".")[0].lower() in _RESERVED_NAMES:
        raise HandoffError(f"{field} {value!r} is a reserved device name")
    return value


def parse_digest(value: Any) -> str:
    """Return the lower-case sha256 hex from a digest in any accepted spelling.

    Accepted: ``"sha256:<hex>"``, bare ``"<hex>"``, or a mapping with
    ``value`` plus ``algorithm``/``alg`` (the marketplace handoff form).  Any
    other algorithm, shape, or a non-64-hex value is a ``HandoffError``.
    """
    algorithm = DIGEST_ALGORITHM
    if isinstance(value, Mapping):
        declared = value.get("algorithm", value.get("alg"))
        if declared is not None:
            algorithm = str(declared).strip().lower()
        raw = value.get("value")
    else:
        raw = value
    if not isinstance(raw, str) or not raw.strip():
        raise HandoffError("digest must be a non-empty string or a {algorithm, value} object")
    text = raw.strip()
    if ":" in text:
        prefix, _, text = text.partition(":")
        prefix = prefix.strip().lower()
        if isinstance(value, Mapping) and prefix != algorithm:
            raise HandoffError(f"digest prefix {prefix!r} contradicts algorithm {algorithm!r}")
        algorithm = prefix
    if algorithm != DIGEST_ALGORITHM:
        raise HandoffError(f"unsupported digest algorithm {algorithm!r}; only sha256 is accepted")
    text = text.strip().lower()
    if not _HEX64_RE.match(text):
        raise HandoffError("sha256 digest must be exactly 64 hex characters")
    return text


def format_digest(hex_digest: str) -> str:
    """``sha256:<hex>`` spelling used in results and handoffs."""
    return f"{DIGEST_ALGORITHM}:{hex_digest}"


def payload_digest(payload_path: Path) -> str:
    """sha256 hex of a blob's raw bytes, or the census digest of a payload directory.

    Directory payloads use :func:`plugin.payload.payload_digest` so a handoff
    built by ``marketplace.handoff.build_handoff`` verifies unchanged.
    """
    path = Path(payload_path)
    if path.is_dir():
        return _tree_digest(path)
    if not path.is_file():
        raise HandoffError(f"payload_path is neither a file nor a directory: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _member_relpath(name: str, *, refuse: type[InstallerError], what: str) -> str:
    """Normalise an archive or projection path; refuse anything that could leave its root.

    ``.`` components and empty components are dropped; absolute paths, drive
    prefixes, NUL bytes and ``..`` components are refused.  The result may be
    ``""`` for a name that denotes the root itself.
    """
    if not isinstance(name, str):
        raise refuse(f"{what} must be a string, got {type(name).__name__}")
    text = _posix(name)
    if "\x00" in text:
        raise refuse(f"{what} {name!r} contains a NUL byte")
    if text.startswith("/") or _DRIVE_RE.match(text):
        raise refuse(f"{what} {name!r} is absolute")
    parts = [part for part in text.split("/") if part not in ("", ".")]
    if any(part == ".." for part in parts):
        raise refuse(f"{what} {name!r} escapes its root")
    return "/".join(parts)


def _safe_relpath(name: Any, what: str) -> str:
    rel = _member_relpath(name, refuse=ProjectionError, what=what)
    if not rel:
        raise ProjectionError(f"{what} {name!r} is empty")
    return rel


def normalise_permissions(declared: Any) -> list[str]:
    """Sorted, de-duplicated permission tokens; every token must be a non-empty string."""
    if declared is None:
        return []
    if isinstance(declared, (str, bytes)) or not isinstance(declared, Iterable):
        raise HandoffError("declared_permissions must be a list of strings")
    tokens: set[str] = set()
    for item in declared:
        if not isinstance(item, str) or not item.strip():
            raise HandoffError(f"declared permission {item!r} is not a non-empty string")
        tokens.add(item.strip())
    return sorted(tokens)


def normalise_projection(projection_map: Any, package_id: str) -> dict[str, str]:
    """Return ``{source: dest}`` with both sides as safe relative posix paths.

    Two spellings are accepted.  A flat mapping ``{source: dest}`` has ``dest``
    relative to the package's live root ``plugins/<package_id>/``.  The
    marketplace handoff form ``{"entries": [{"source", "dest"}]}`` has ``dest``
    relative to ``dest_home``; every such dest must lie under the package's own
    live root, which is exactly the "writes outside its own root" refusal.
    Duplicate destinations from different sources are refused.
    """
    pairs: list[tuple[Any, Any]] = []
    if isinstance(projection_map, Mapping) and "entries" in projection_map:
        entries = projection_map.get("entries")
        if not isinstance(entries, list):
            raise ProjectionError("projection_map.entries must be a list")
        prefix = f"{PLUGINS_DIR}/{package_id}/"
        for entry in entries:
            if not isinstance(entry, Mapping):
                raise ProjectionError(f"projection entry {entry!r} is not an object")
            source = entry.get("source")
            dest = entry.get("dest", entry.get("live", source))
            if not isinstance(dest, str):
                raise ProjectionError(f"projection entry for {source!r} has no dest")
            dest = _posix(dest)
            if not dest.startswith(prefix):
                raise ProjectionError(f"projection dest {dest!r} is outside {prefix}")
            pairs.append((source, dest[len(prefix):]))
    elif isinstance(projection_map, Mapping):
        pairs = list(projection_map.items())
    else:
        raise ProjectionError("projection_map must be a mapping or {entries: [...]}")
    if not pairs:
        raise ProjectionError("projection_map is empty; nothing to place")
    projection: dict[str, str] = {}
    owners: dict[str, str] = {}
    for source, dest in pairs:
        src = _safe_relpath(source, "projection source")
        dst = _safe_relpath(dest, "projection dest")
        if owners.get(dst, src) != src:
            raise ProjectionError(f"projection dest {dst!r} is claimed by {owners[dst]!r} and {src!r}")
        owners[dst] = src
        projection[src] = dst
    dests = sorted(projection.values())
    for index, dest in enumerate(dests[:-1]):
        if dests[index + 1].startswith(dest + "/"):
            raise ProjectionError(f"projection dest {dest!r} is both a file and a directory")
    return dict(sorted(projection.items()))


def _tree_files(root: Path) -> set[str]:
    found: set[str] = set()
    for dirpath, _dirnames, filenames in os.walk(root, followlinks=False):
        for filename in filenames:
            found.add((Path(dirpath) / filename).relative_to(root).as_posix())
    return found


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _remove_tree(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
    elif path.is_dir():
        shutil.rmtree(path, ignore_errors=True)


def _rmdir_if_empty(path: Path) -> None:
    try:
        path.rmdir()
    except OSError:
        return


# --------------------------------------------------------------------------- stages


def _safe_extract(blob: Path, extract_root: Path) -> list[str]:
    """Extract ``blob`` into ``extract_root`` and return the regular-file member paths.

    Members are vetted before a single byte is written: only regular files and
    directories are allowed (no symlinks, hardlinks, devices or fifos), names
    must be relative without ``..``, and the member count and byte budget are
    capped.  Extraction then runs under ``filter="data"`` as a second,
    independent guard; a filter refusal is surfaced as ``UnsafeArchiveError``.
    Nothing in the archive is executed.
    """
    if not hasattr(tarfile, "data_filter"):
        raise UnsafeArchiveError("this Python's tarfile has no data filter; refusing to extract")
    try:
        archive = tarfile.open(blob, mode="r:*")
    except (tarfile.TarError, EOFError, OSError) as exc:
        raise UnsafeArchiveError(f"payload is not a readable tar archive: {exc}") from exc
    files: list[str] = []
    total = 0
    with archive:
        members = archive.getmembers()
        if len(members) > MAX_MEMBERS:
            raise UnsafeArchiveError(f"archive has {len(members)} members; limit is {MAX_MEMBERS}")
        for member in members:
            if member.issym() or member.islnk():
                raise UnsafeArchiveError(f"member {member.name!r} is a link")
            if member.isdev() or member.isfifo():
                raise UnsafeArchiveError(f"member {member.name!r} is a device or fifo")
            if not (member.isfile() or member.isdir()):
                raise UnsafeArchiveError(f"member {member.name!r} has unsupported type {member.type!r}")
            rel = _member_relpath(member.name, refuse=UnsafeArchiveError, what="archive member")
            if member.isdir():
                continue
            if not rel:
                raise UnsafeArchiveError(f"file member {member.name!r} has no name")
            if member.size > MAX_MEMBER_BYTES:
                raise UnsafeArchiveError(f"member {rel!r} is {member.size} bytes; limit is {MAX_MEMBER_BYTES}")
            total += member.size
            if total > MAX_TOTAL_BYTES:
                raise UnsafeArchiveError(f"archive exceeds {MAX_TOTAL_BYTES} bytes of payload")
            files.append(rel)
        extract_root.mkdir(parents=True, exist_ok=True)
        try:
            archive.extractall(path=extract_root, members=members, filter="data")
        except tarfile.FilterError as exc:
            raise UnsafeArchiveError(f"{type(exc).__name__}: {exc}") from exc
    return sorted(files)


def _project_into_stage(extract_root: Path, stage: Path, projection: Mapping[str, str]) -> list[str]:
    """Copy each projected source into ``stage`` and return the sorted placed dests.

    Sources must be regular files (not symlinks) that resolve inside
    ``extract_root``; destinations are re-checked to resolve inside ``stage``
    even though :func:`normalise_projection` already refused escapes.  Files are
    copied with ``shutil.copy2`` so permission bits (an executable shim's 0755)
    survive without anything being run.  The staged census must equal the
    projected set, otherwise the stage is not activated.
    """
    stage.mkdir(parents=True, exist_ok=True)
    placed: list[str] = []
    for source, dest in projection.items():
        src = extract_root / source
        if src.is_symlink() or not src.is_file():
            raise ProjectionError(f"projection source {source!r} is not a regular file in the payload")
        if not _inside(src, extract_root):
            raise ProjectionError(f"projection source {source!r} resolves outside the payload")
        out = stage / dest
        if not _inside(out, stage):
            raise ProjectionError(f"projection dest {dest!r} resolves outside the stage")
        if out.exists() or out.is_symlink():
            raise ProjectionError(f"projection dest {dest!r} was already placed")
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, out)
        placed.append(dest)
    placed.sort()
    staged = _tree_files(stage)
    if staged != set(placed):
        raise ProjectionError(f"staged census {sorted(staged)} != projected {placed}")
    return placed


def _grant_path(dest_home: Path, package_id: str) -> Path:
    return dest_home / GRANTS_DIR / f"{package_id}.json"


def recorded_grant(dest_home: Path, package_id: str) -> list[str] | None:
    """Permissions recorded at the last activation of ``package_id``, or ``None``."""
    path = _grant_path(Path(dest_home), package_id)
    if not path.is_file():
        return None
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise HandoffError(f"grant ledger {path.name} is unreadable: {exc}") from exc
    if not isinstance(doc, dict) or doc.get("package_id") != package_id:
        raise HandoffError(f"grant ledger {path.name} does not describe {package_id!r}")
    return normalise_permissions(doc.get("declared_permissions"))


def _check_widening(dest_home: Path, package_id: str, candidate: list[str], live_root: Path) -> None:
    if not (live_root.exists() or live_root.is_symlink()):
        return
    installed = recorded_grant(dest_home, package_id)
    if installed is None:
        return
    delta = compute_delta(installed, candidate)
    if delta.verdict == WIDEN:
        raise PermissionWideningBlocked(delta.added, installed=installed, candidate=candidate)


def _write_grant(dest_home: Path, package_id: str, permissions: list[str], workspace: Path) -> None:
    doc = {
        "declared_permissions": list(permissions),
        "package_id": package_id,
        "schema_version": SCHEMA_VERSION,
    }
    path = _grant_path(dest_home, package_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = workspace / "grant.json"
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _activate(stage: Path, live_root: Path, workspace: Path) -> bool:
    """Swap ``stage`` in as ``live_root`` with one rename; return whether a root was replaced.

    An existing live root (directory or a legacy symlink) is first parked in the
    workspace so the final ``os.replace`` targets a free name on every platform.
    If that rename fails the parked root is put back before ``ActivationError``
    is raised.
    """
    live_root.parent.mkdir(parents=True, exist_ok=True)
    previous = workspace / "previous"
    replaced = False
    if live_root.exists() or live_root.is_symlink():
        os.replace(live_root, previous)
        replaced = True
    try:
        os.replace(stage, live_root)
    except OSError as exc:
        if replaced:
            try:
                os.replace(previous, live_root)
            except OSError:
                raise ActivationError(
                    f"could not activate {live_root.name!r} and the previous root is parked at {previous}"
                ) from exc
        raise ActivationError(f"could not activate {live_root.name!r}: {exc}") from exc
    return replaced


# --------------------------------------------------------------------------- entry points


def install_direct(
    payload_path: Path | str,
    dest_home: Path | str,
    *,
    package_id: str,
    projection_map: Any,
    transaction_id: str,
    digest: Any,
    declared_permissions: Iterable[str] | None = (),
) -> dict[str, Any]:
    """Install one payload into ``dest_home/plugins/<package_id>``.

    ``payload_path`` is a tar archive (any compression ``tarfile`` reads) or an
    already-unpacked directory; ``digest`` is its sha256 (``"sha256:<hex>"``,
    bare hex, or ``{algorithm, value}``), checked before extraction.
    ``projection_map`` selects which payload files are placed and where (see
    :func:`normalise_projection`); members not in the map are never placed and
    are reported under ``unprojected_members``.  ``declared_permissions`` are
    the grant the caller accepted for this package; on re-install a strict
    widening of the recorded grant is refused.

    Returns a result mapping with ``ok``, ``package_id``, ``transaction_id``,
    ``digest``, ``live_root`` (relative to ``dest_home``), the sorted ``placed``
    dests, ``declared_permissions``, ``replaced`` and ``unprojected_members``.
    Raises a subclass of :class:`InstallerError` on refusal; a refused install
    leaves ``dest_home`` as it was found.
    """
    if not transaction_id:
        raise MissingTransactionIdError("transaction_id is required; no files may be placed without one")
    txn = _require_token(transaction_id, "transaction_id")
    pkg = _require_token(package_id, "package_id")
    expected = parse_digest(digest)
    permissions = normalise_permissions(declared_permissions)
    projection = normalise_projection(projection_map, pkg)

    if isinstance(payload_path, (bytes, bytearray)) or not str(payload_path or ""):
        raise HandoffError("payload_path must be a filesystem path")
    payload = Path(payload_path)
    home = Path(dest_home)
    if home.exists() and not home.is_dir():
        raise HandoffError(f"dest_home {home} exists and is not a directory")
    live_root = home / PLUGINS_DIR / pkg
    workspace = home / STAGING_DIR / txn
    if payload.is_dir() and (_inside(payload, live_root) or _inside(payload, workspace)):
        raise HandoffError("payload directory lies inside the destination it would replace")

    actual = payload_digest(payload)
    if not hmac.compare_digest(actual, expected):
        raise DigestMismatchError(
            f"digest mismatch for {pkg!r}: live {format_digest(actual)} != declared {format_digest(expected)}"
        )
    _check_widening(home, pkg, permissions, live_root)

    home_was_absent = not home.exists()
    home.mkdir(parents=True, exist_ok=True)
    _remove_tree(workspace)
    workspace.mkdir(parents=True)
    try:
        if payload.is_dir():
            extract_root = payload
            members = sorted(_tree_files(payload))
        else:
            extract_root = workspace / "extract"
            members = _safe_extract(payload, extract_root)
        missing = sorted(set(projection) - set(members))
        if missing:
            raise ProjectionError(f"projection sources absent from payload: {missing}")
        stage = workspace / "stage"
        placed = _project_into_stage(extract_root, stage, projection)
        replaced = _activate(stage, live_root, workspace)
        _write_grant(home, pkg, permissions, workspace)
    except BaseException:
        _remove_tree(workspace)
        _rmdir_if_empty(home / STAGING_DIR)
        _rmdir_if_empty(home / PLUGINS_DIR)
        if home_was_absent:
            _rmdir_if_empty(home)
        raise
    _remove_tree(workspace)
    _rmdir_if_empty(home / STAGING_DIR)
    return {
        "ok": True,
        "schema_version": SCHEMA_VERSION,
        "package_id": pkg,
        "transaction_id": txn,
        "digest": format_digest(actual),
        "dest_home": str(dest_home),
        "live_root": f"{PLUGINS_DIR}/{pkg}",
        "placed": placed,
        "declared_permissions": permissions,
        "replaced": replaced,
        "unprojected_members": sorted(set(members) - set(projection)),
    }


def install_from_handoff(handoff: Mapping[str, Any], dest_home: Path | str) -> dict[str, Any]:
    """Install from a typed handoff document.

    Required keys: ``transaction_id``, ``payload_path``, ``digest``,
    ``projection_map`` and ``package_id`` (``plugin_name`` is accepted as the
    marketplace's spelling).  Optional ``schema_version`` must be ``1`` and
    optional ``kind`` must be ``"install-handoff"``.  An untyped handoff or one
    without a transaction id is refused with ``MissingTransactionIdError``.
    """
    if not isinstance(handoff, Mapping):
        raise MissingTransactionIdError(
            f"untyped handoff ({type(handoff).__name__}); a typed handoff with transaction_id is required"
        )
    transaction_id = handoff.get("transaction_id")
    if not transaction_id:
        raise MissingTransactionIdError("handoff missing transaction_id")
    schema_version = handoff.get("schema_version", SCHEMA_VERSION)
    if isinstance(schema_version, bool) or schema_version != SCHEMA_VERSION:
        raise HandoffError(f"handoff schema_version {schema_version!r} is not {SCHEMA_VERSION}")
    kind = handoff.get("kind", HANDOFF_KIND)
    if kind != HANDOFF_KIND:
        raise HandoffError(f"handoff kind {kind!r} is not {HANDOFF_KIND!r}")
    package_id = handoff.get("package_id") or handoff.get("plugin_name")
    if not package_id:
        raise HandoffError("handoff missing package_id")
    for key in ("payload_path", "digest", "projection_map"):
        if handoff.get(key) is None:
            raise HandoffError(f"handoff missing {key}")
    return install_direct(
        handoff["payload_path"],
        dest_home,
        package_id=package_id,
        projection_map=handoff["projection_map"],
        transaction_id=transaction_id,
        digest=handoff["digest"],
        declared_permissions=handoff.get("declared_permissions") or [],
    )


__all__ = [
    "ActivationError",
    "DIGEST_ALGORITHM",
    "DigestMismatchError",
    "GRANTS_DIR",
    "HANDOFF_KIND",
    "HandoffError",
    "InstallerError",
    "MAX_MEMBERS",
    "MAX_MEMBER_BYTES",
    "MAX_TOTAL_BYTES",
    "MissingTransactionIdError",
    "PLUGINS_DIR",
    "PermissionWideningBlocked",
    "ProjectionError",
    "SCHEMA_VERSION",
    "STAGING_DIR",
    "UnsafeArchiveError",
    "format_digest",
    "install_direct",
    "install_from_handoff",
    "normalise_permissions",
    "normalise_projection",
    "parse_digest",
    "payload_digest",
    "recorded_grant",
]
