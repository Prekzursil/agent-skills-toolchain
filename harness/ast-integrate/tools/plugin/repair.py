"""Repair: re-deploy drifted estate files (IMP-0025) and heal a damaged install tree (TST-0074).

Two repair surfaces live here.

**Estate repair** -- :func:`plan_repair` / :func:`apply_repair`.  Both trees are
walked, every file in their union is classified with the two-directional drift
classifier (:mod:`plugin.drift`) and only ``REPO-AHEAD`` and
``IDENTICAL-MODULO-EOL`` files are re-deployed from the repo side.  ``DIVERGED``
and ``LIVE-AHEAD`` files carry live-unique content and are refused; a dry run
returns the exact touch set without writing a byte.

**Install-tree repair** -- :func:`seed_install` / :func:`repair_install`.
``seed_install`` builds the deterministic demo payload, installs it through
:func:`plugin.installer.install_direct` (the single placement authority) and
records a *repair source* beside -- never inside -- the live root::

    <home>/plugins/<package_id>/                       live root (installer)
    <home>/plugins/.releases/<package_id>/<txn>.payload   the installed blob
    <home>/plugins/.releases/<package_id>/repair-source.json
        payload digest, projection, per-member sha256 + mode

``repair_install`` re-verifies the payload against the recorded digest, then
compares every projected file in the live root with its payload member (bytes
and mode) and restores whatever differs.  A projected file whose member is
absent from the payload is *unrepairable*: it is named in the report and the
repair answers ``ok=False`` instead of pretending.  Restores are atomic
(temp file + ``os.replace``) and re-verified after writing.

Nothing here spawns a process, consults the marketplace pin, or writes outside
the home or live root it was handed.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import io
import json
import os
import shutil
import stat
import sys
import tarfile
from pathlib import Path
from typing import Any, Iterable, Mapping

from plugin import installer
from plugin.drift import (
    DIVERGED,
    IDENTICAL,
    LIVE_AHEAD,
    REPAIRABLE,
    REPO_AHEAD,
    classify_pair,
)
from plugin.payloadutil import (
    MANIFEST_REL,
    PACKAGE_NAME,
    PACKAGE_VERSION,
    PAYLOAD_MODES,
    SHIM_REL,
    SKILL_REL,
    blob_digest,
    coerce_bytes,
    payload_files_for,
    write_deterministic_tar,
)

__all__ = [
    "COMPONENT_FOR_MODE",
    "CORRUPTION_MODES",
    "DEFAULT_PERMISSIONS",
    "RED_JOURNEY",
    "RELEASES_DIR",
    "REPAIR_SOURCE_NAME",
    "RepairError",
    "RepairSourceError",
    "SILENT_CORRUPTION_MODES",
    "apply_corruption",
    "apply_repair",
    "drop_payload_member",
    "iter_rel_files",
    "load_repair_source",
    "main",
    "plan_repair",
    "repair_install",
    "seed_install",
]

SCHEMA_VERSION = 1
RELEASES_DIR = ".releases"
REPAIR_SOURCE_NAME = "repair-source.json"
PAYLOAD_SUFFIX = ".payload"
DEFAULT_PERMISSIONS: tuple[str, ...] = ("fs:plugin-root",)
_TMP_SUFFIX = ".repair-tmp"

# Corruption modes a golden journey (plugin.journeys) observes, and the journey each one reddens.
CORRUPTION_MODES: tuple[str, ...] = (
    "missing_file",
    "truncated_skill",
    "truncated_manifest",
    "missing_plugin_json",
)
# Damage repair also heals, but that no shipped journey observes yet (no shim/mode journey).
SILENT_CORRUPTION_MODES: tuple[str, ...] = ("wrong_permissions", "missing_shim")
COMPONENT_FOR_MODE: dict[str, str] = {
    "missing_file": SKILL_REL,
    "truncated_skill": SKILL_REL,
    "truncated_manifest": MANIFEST_REL,
    "missing_plugin_json": MANIFEST_REL,
    "wrong_permissions": SHIM_REL,
    "missing_shim": SHIM_REL,
}
RED_JOURNEY: dict[str, str] = {
    "missing_file": "skill_read",
    "truncated_skill": "skill_read",
    "truncated_manifest": "plugin_json",
    "missing_plugin_json": "plugin_json",
}


class RepairError(Exception):
    """Repair could not proceed; nothing was written."""


class RepairSourceError(RepairError):
    """The recorded repair source is absent, unreadable or does not describe the package."""


# --------------------------------------------------------------------------- estate repair


def iter_rel_files(root: str | Path) -> dict[str, Path]:
    """``{posix relpath: Path}`` for every regular file under ``root`` (empty when absent)."""
    base = Path(root)
    out: dict[str, Path] = {}
    if not base.is_dir():
        return out
    for path in sorted(base.rglob("*")):
        if path.is_file():
            out[path.relative_to(base).as_posix()] = path
    return out


def plan_repair(
    repo: str | Path, live: str | Path, one_directional: bool = False
) -> dict[str, Any]:
    """Classify the union of both trees and list exactly what a repair would touch.

    A file present on one side only is ``REPO-AHEAD`` (repo only) or
    ``LIVE-AHEAD`` (live only); every shared file goes through
    :func:`plugin.drift.classify_pair`.  The touch set is the ``REPAIRABLE``
    subset (``REPO-AHEAD`` + ``IDENTICAL-MODULO-EOL``); ``DIVERGED`` and
    ``LIVE-AHEAD`` are refused because the live side holds unique lines.
    ``one_directional`` selects the length-only classifier and exists so the
    mutation probe can show the two-directional rule is load-bearing.
    """
    repo_root = Path(repo)
    live_root = Path(live)
    repo_files = iter_rel_files(repo_root)
    live_files = iter_rel_files(live_root)
    keys = sorted(set(repo_files) | set(live_files))
    classifications: dict[str, str] = {}
    for rel in keys:
        if rel not in repo_files:
            klass = LIVE_AHEAD
        elif rel not in live_files:
            klass = REPO_AHEAD
        else:
            klass = classify_pair(
                repo_files[rel].read_bytes(),
                live_files[rel].read_bytes(),
                one_directional=bool(one_directional),
            )
        classifications[rel] = klass
    touch = [rel for rel in keys if classifications[rel] in REPAIRABLE]
    refused = [rel for rel in keys if classifications[rel] in (DIVERGED, LIVE_AHEAD)]
    identical = [rel for rel in keys if classifications[rel] == IDENTICAL]
    by_class: dict[str, int] = {}
    for klass in classifications.values():
        by_class[klass] = by_class.get(klass, 0) + 1
    return {
        "schema_version": SCHEMA_VERSION,
        "repo_root": str(repo_root),
        "live_root": str(live_root),
        "repo": str(repo_root),
        "live": str(live_root),
        "one_directional": bool(one_directional),
        "union_files": len(keys),
        "classifications": classifications,
        "touch_set": touch,
        "would_touch": list(touch),
        "refused": refused,
        "skipped_identical": identical,
        "by_class": dict(sorted(by_class.items())),
    }


def _atomic_write(dest: Path, data: bytes, mode: int | None = None) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(f".{dest.name}{_TMP_SUFFIX}")
    try:
        tmp.write_bytes(data)
        if mode is not None and os.name == "posix":
            os.chmod(tmp, mode & 0o7777)
        os.replace(tmp, dest)
    finally:
        tmp.unlink(missing_ok=True)


def apply_repair(
    repo: str | Path,
    live: str | Path,
    one_directional: bool = False,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Re-deploy the touch set of :func:`plan_repair` into ``live``; dry run by default.

    Only files the plan classifies ``REPO-AHEAD`` or ``IDENTICAL-MODULO-EOL``
    are written, each as an atomic replace of the live file with the repo
    bytes (repo mode bits preserved).  Refused files are never opened for
    writing.  The returned plan gains ``applied`` (the rels written),
    ``dry_run`` and ``write_errors``.
    """
    plan = plan_repair(repo, live, one_directional=one_directional)
    applied: list[str] = []
    errors: list[dict[str, str]] = []
    if not dry_run:
        repo_root = Path(repo)
        live_root = Path(live)
        for rel in plan["touch_set"]:
            src = repo_root / rel
            dest = live_root / rel
            if dest.is_symlink():
                errors.append(
                    {
                        "path": rel,
                        "error": "live path is a symlink; refusing to write through it",
                    }
                )
                continue
            try:
                src_mode = stat.S_IMODE(src.stat().st_mode)
                _atomic_write(dest, src.read_bytes(), src_mode)
            except OSError as exc:
                errors.append({"path": rel, "error": f"{type(exc).__name__}: {exc}"})
                continue
            applied.append(rel)
    plan["applied"] = applied
    plan["dry_run"] = bool(dry_run)
    plan["write_errors"] = errors
    return plan


# --------------------------------------------------------------------------- payload helpers


def _member_name(name: Any, what: str = "payload member") -> str:
    """Normalise a member/projection path; refuse anything that could leave its root."""
    if not isinstance(name, str):
        raise RepairError(f"{what} must be a string, got {type(name).__name__}")
    text = name.replace("\\", "/")
    if "\x00" in text:
        raise RepairError(f"{what} {name!r} contains a NUL byte")
    if text.startswith("/") or (len(text) > 1 and text[1] == ":" and text[0].isalpha()):
        raise RepairError(f"{what} {name!r} is absolute")
    parts = [part for part in text.split("/") if part not in ("", ".")]
    if not parts:
        raise RepairError(f"{what} {name!r} is empty")
    if any(part == ".." for part in parts):
        raise RepairError(f"{what} {name!r} escapes its root")
    return "/".join(parts)


def _read_payload_bytes(
    blob: bytes, label: str
) -> tuple[dict[str, bytes], dict[str, int]]:
    """Regular-file members of a tar blob as ``({rel: bytes}, {rel: mode})``; links and devices refused."""
    try:
        archive = tarfile.open(fileobj=io.BytesIO(blob), mode="r:*")
    except (tarfile.TarError, EOFError, OSError) as exc:
        raise RepairError(f"{label} is not a readable tar archive: {exc}") from exc
    members: dict[str, bytes] = {}
    modes: dict[str, int] = {}
    total = 0
    with archive:
        infos = archive.getmembers()
        if len(infos) > installer.MAX_MEMBERS:
            raise RepairError(
                f"{label} has {len(infos)} members; limit is {installer.MAX_MEMBERS}"
            )
        for info in infos:
            if info.issym() or info.islnk():
                raise RepairError(f"{label} member {info.name!r} is a link")
            if info.isdev() or info.isfifo():
                raise RepairError(f"{label} member {info.name!r} is a device or fifo")
            if info.isdir():
                continue
            if not info.isfile():
                raise RepairError(
                    f"{label} member {info.name!r} has unsupported type {info.type!r}"
                )
            rel = _member_name(info.name, f"{label} member")
            if info.size > installer.MAX_MEMBER_BYTES:
                raise RepairError(
                    f"{label} member {rel!r} is {info.size} bytes; limit is {installer.MAX_MEMBER_BYTES}"
                )
            total += info.size
            if total > installer.MAX_TOTAL_BYTES:
                raise RepairError(
                    f"{label} exceeds {installer.MAX_TOTAL_BYTES} bytes of payload"
                )
            if rel in members:
                raise RepairError(f"{label} names member {rel!r} twice")
            handle = archive.extractfile(info)
            members[rel] = handle.read() if handle is not None else b""
            modes[rel] = int(info.mode) & 0o7777
    return members, modes


def _read_payload(path: Path) -> tuple[dict[str, bytes], dict[str, int]]:
    if not path.is_file():
        raise RepairSourceError(f"payload sidecar {path} is missing")
    return _read_payload_bytes(path.read_bytes(), path.name)


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_json(path: Path, doc: Mapping[str, Any]) -> None:
    _atomic_write(
        path, (json.dumps(doc, indent=1, sort_keys=True) + "\n").encode("utf-8")
    )


def _release_dir(home: Path, package_id: str) -> Path:
    return home / installer.PLUGINS_DIR / RELEASES_DIR / package_id


def _live_root(home: Path, package_id: str) -> Path:
    return home / installer.PLUGINS_DIR / package_id


# --------------------------------------------------------------------------- install-tree repair


def seed_install(
    home: str | Path,
    blob: str | Path,
    *,
    package_id: str = PACKAGE_NAME,
    version: str = PACKAGE_VERSION,
    files: Mapping[str, Any] | None = None,
    modes: Mapping[str, int] | None = None,
    transaction_id: str | None = None,
    declared_permissions: Iterable[str] = DEFAULT_PERMISSIONS,
) -> dict[str, Any]:
    """Write the demo payload to ``blob``, install it into ``home`` and record the repair source.

    Placement goes through :func:`plugin.installer.install_direct` with a typed
    projection (every payload member to the same relative path), so the live
    root is exactly ``<home>/plugins/<package_id>/``.  The blob is then copied
    to ``plugins/.releases/<package_id>/<txn>.payload`` and described in
    ``repair-source.json`` (digest, projection, per-member sha256 and mode).
    The transaction id is derived from the payload digest unless given, so two
    seeds of the same payload are byte-identical.
    """
    home_path = Path(home)
    blob_path = Path(blob)
    members = (
        {rel: coerce_bytes(data) for rel, data in files.items()}
        if files is not None
        else payload_files_for(version=version, name=package_id)
    )
    member_modes = (
        {rel: int(mode) & 0o7777 for rel, mode in modes.items()}
        if modes is not None
        else {rel: PAYLOAD_MODES.get(rel, 0o644) for rel in members}
    )
    digest = write_deterministic_tar(blob_path, members, member_modes)
    txn = transaction_id or f"seed-{installer.parse_digest(digest)[:16]}"
    projection = {rel: rel for rel in sorted(members)}
    result = installer.install_direct(
        blob_path,
        home_path,
        package_id=package_id,
        projection_map=projection,
        transaction_id=txn,
        digest=digest,
        declared_permissions=list(declared_permissions),
    )
    release_dir = _release_dir(home_path, package_id)
    release_dir.mkdir(parents=True, exist_ok=True)
    payload_path = release_dir / f"{txn}{PAYLOAD_SUFFIX}"
    shutil.copyfile(blob_path, payload_path)
    stored = blob_digest(payload_path.read_bytes())
    if not hmac.compare_digest(stored, digest):
        payload_path.unlink(missing_ok=True)
        raise RepairError(
            f"payload sidecar digest {stored} != installed {digest}; sidecar not recorded"
        )
    meta = {
        "schema_version": SCHEMA_VERSION,
        "kind": "repair-source",
        "package_id": package_id,
        "transaction_id": txn,
        "payload": payload_path.name,
        "digest": digest,
        "installed_digest": digest,
        "projection": projection,
        "members": {
            rel: {
                "sha256": _sha256_hex(members[rel]),
                "mode": member_modes.get(rel, 0o644),
                "size": len(members[rel]),
            }
            for rel in sorted(members)
        },
        "declared_permissions": list(result["declared_permissions"]),
        "placed": list(result["placed"]),
        "dropped_members": [],
    }
    meta_path = release_dir / REPAIR_SOURCE_NAME
    _write_json(meta_path, meta)
    return {
        "ok": True,
        "schema_version": SCHEMA_VERSION,
        "home": str(home_path),
        "package_id": package_id,
        "transaction_id": txn,
        "digest": digest,
        "blob": str(blob_path),
        "live_root": str(_live_root(home_path, package_id)),
        "sidecar": str(payload_path),
        "repair_source": str(meta_path),
        "placed": list(result["placed"]),
        "replaced": bool(result["replaced"]),
        "declared_permissions": list(result["declared_permissions"]),
    }


def load_repair_source(
    home: str | Path, package_id: str = PACKAGE_NAME
) -> dict[str, Any]:
    """Read ``repair-source.json`` for ``package_id``; adds ``_sidecar_path`` (the payload) and friends."""
    home_path = Path(home)
    release_dir = _release_dir(home_path, package_id)
    meta_path = release_dir / REPAIR_SOURCE_NAME
    if not meta_path.is_file():
        raise RepairSourceError(
            f"no repair source recorded for {package_id!r} at {meta_path}"
        )
    try:
        doc = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RepairSourceError(
            f"repair source {meta_path} is unreadable: {exc}"
        ) from exc
    if not isinstance(doc, dict) or doc.get("package_id") != package_id:
        raise RepairSourceError(
            f"repair source {meta_path} does not describe {package_id!r}"
        )
    payload_name = doc.get("payload")
    if (
        not isinstance(payload_name, str)
        or not payload_name
        or "/" in payload_name
        or "\\" in payload_name
    ):
        raise RepairSourceError(
            f"repair source {meta_path} names an invalid payload {payload_name!r}"
        )
    doc["_sidecar_path"] = str(release_dir / payload_name)
    doc["_meta_path"] = str(meta_path)
    doc["_release_dir"] = str(release_dir)
    doc["_live_root"] = str(_live_root(home_path, package_id))
    return doc


def drop_payload_member(sidecar: str | Path, rel: str) -> dict[str, Any]:
    """Rewrite the payload sidecar without member ``rel`` and update ``repair-source.json``.

    This is the fixture hook for the unrepairable case: the live tree loses a
    file *and* the recorded source can no longer supply it.  The sidecar stays
    internally consistent (digest and member table are recomputed) so the
    failure a later repair reports is "member absent", not "sidecar corrupt".
    ``sidecar`` may be the ``.payload`` path (as ``_sidecar_path`` gives it) or
    the ``repair-source.json`` beside it.
    """
    side = Path(sidecar)
    doc: dict[str, Any] | None = None
    if side.name == REPAIR_SOURCE_NAME:
        meta_path = side
        doc = json.loads(meta_path.read_text(encoding="utf-8"))
        payload_path = meta_path.parent / str(doc.get("payload") or "")
    else:
        payload_path = side
        meta_path = side.parent / REPAIR_SOURCE_NAME
        if meta_path.is_file():
            doc = json.loads(meta_path.read_text(encoding="utf-8"))
    members, modes = _read_payload(payload_path)
    member = _member_name(rel)
    if member not in members:
        raise KeyError(
            f"{member!r} is not a member of {payload_path.name}; members: {sorted(members)}"
        )
    del members[member]
    modes.pop(member, None)
    new_digest = write_deterministic_tar(payload_path, members, modes)
    if isinstance(doc, dict):
        doc["digest"] = new_digest
        table = doc.get("members")
        if isinstance(table, dict):
            table.pop(member, None)
        dropped = doc.setdefault("dropped_members", [])
        if isinstance(dropped, list):
            dropped.append(member)
        _write_json(meta_path, doc)
    return {
        "sidecar": str(payload_path),
        "repair_source": str(meta_path) if isinstance(doc, dict) else None,
        "dropped": member,
        "digest": new_digest,
        "remaining": sorted(members),
    }


def _inspect(target: Path, want: bytes, want_mode: int) -> str | None:
    """``None`` when ``target`` already equals the payload member, else the reason it does not."""
    if target.is_symlink():
        return "symlink"
    if not target.exists():
        return "missing"
    if not target.is_file():
        return "not-a-file"
    if target.read_bytes() != want:
        return "content"
    if os.name == "posix" and (stat.S_IMODE(target.stat().st_mode) & 0o777) != (
        want_mode & 0o777
    ):
        return "mode"
    return None


def _restore(target: Path, want: bytes, want_mode: int, reason: str) -> None:
    if reason == "symlink":
        target.unlink()
        reason = "missing"
    if reason == "mode":
        os.chmod(target, want_mode & 0o7777)
        return
    _atomic_write(target, want, want_mode)


def repair_install(
    home: str | Path, package_id: str = PACKAGE_NAME, *, dry_run: bool = False
) -> dict[str, Any]:
    """Restore ``<home>/plugins/<package_id>`` from its recorded repair source.

    Steps: load ``repair-source.json``; verify the payload sidecar's sha256
    equals the recorded digest; read its members; for every projected file
    compare the live bytes and mode with the member and restore (atomically,
    then re-verify) whatever is missing, truncated, altered, a symlink or
    wrongly moded.  A projected file whose member is absent from the payload
    -- or whose member no longer matches the recorded sha256 -- is named under
    ``unrepairable`` and makes ``ok`` false.  Files in the live root that the
    projection does not know are listed under ``unexpected`` and left alone.
    Exit status of the CLI mirrors ``ok``; the report, not the exit code, is
    the evidence.
    """
    home_path = Path(home)
    live_root = _live_root(home_path, package_id)
    report: dict[str, Any] = {
        "ok": False,
        "schema_version": SCHEMA_VERSION,
        "home": str(home_path),
        "package_id": package_id,
        "live_root": str(live_root),
        "dry_run": bool(dry_run),
        "sidecar": None,
        "digest": None,
        "restored": [],
        "verified": [],
        "unrepairable": [],
        "unexpected": [],
        "reasons": [],
    }
    unrepairable: list[str] = report["unrepairable"]
    reasons: list[str] = report["reasons"]
    try:
        meta = load_repair_source(home_path, package_id)
    except RepairSourceError as exc:
        unrepairable.append(f"repair-source:{package_id}")
        reasons.append(str(exc))
        return report
    payload_path = Path(meta["_sidecar_path"])
    report["sidecar"] = str(payload_path)
    if not payload_path.is_file():
        unrepairable.append(f"sidecar:{payload_path.name}")
        reasons.append(f"payload sidecar {payload_path} is missing")
        return report
    blob = payload_path.read_bytes()
    actual = blob_digest(blob)
    report["digest"] = actual
    recorded_digest = str(meta.get("digest") or "")
    if not hmac.compare_digest(actual, recorded_digest):
        unrepairable.append(f"sidecar:{payload_path.name}")
        reasons.append(
            f"payload sidecar digest {actual} != recorded {recorded_digest or '<none>'}"
        )
        return report
    try:
        members, modes = _read_payload_bytes(blob, payload_path.name)
    except RepairError as exc:
        unrepairable.append(f"sidecar:{payload_path.name}")
        reasons.append(str(exc))
        return report
    projection_raw = meta.get("projection")
    projection: dict[str, str] = (
        {str(k): str(v) for k, v in projection_raw.items()}
        if isinstance(projection_raw, dict) and projection_raw
        else {rel: rel for rel in members}
    )
    recorded_members = (
        meta.get("members") if isinstance(meta.get("members"), dict) else {}
    )
    for source, dest in sorted(projection.items(), key=lambda item: item[1]):
        try:
            dest_rel = _member_name(dest, "projection dest")
        except RepairError as exc:
            unrepairable.append(dest)
            reasons.append(str(exc))
            continue
        if source not in members:
            unrepairable.append(dest_rel)
            reasons.append(
                f"{dest_rel}: member {source!r} is absent from {payload_path.name}"
            )
            continue
        want = members[source]
        want_sha = _sha256_hex(want)
        rec = (
            recorded_members.get(source) if isinstance(recorded_members, dict) else None
        )
        if isinstance(rec, dict) and rec.get("sha256") and rec["sha256"] != want_sha:
            unrepairable.append(dest_rel)
            reasons.append(
                f"{dest_rel}: payload member sha256 {want_sha} != recorded {rec['sha256']}"
            )
            continue
        want_mode = int(
            modes.get(
                source, rec.get("mode", 0o644) if isinstance(rec, dict) else 0o644
            )
        )
        target = live_root / dest_rel
        state = _inspect(target, want, want_mode)
        if state is None:
            report["verified"].append(dest_rel)
            continue
        if state == "not-a-file":
            unrepairable.append(dest_rel)
            reasons.append(
                f"{dest_rel}: live path is occupied by a non-file; refusing to remove it"
            )
            continue
        entry = {
            "path": dest_rel,
            "reason": state,
            "sha256": want_sha,
            "mode": f"{want_mode:o}",
        }
        if not dry_run:
            try:
                _restore(target, want, want_mode, state)
            except OSError as exc:
                unrepairable.append(dest_rel)
                reasons.append(
                    f"{dest_rel}: restore failed: {type(exc).__name__}: {exc}"
                )
                continue
            after = _inspect(target, want, want_mode)
            if after is not None:
                unrepairable.append(dest_rel)
                reasons.append(f"{dest_rel}: still {after} after restore")
                continue
        report["restored"].append(entry)
    if live_root.is_dir():
        known = set(projection.values())
        for path in sorted(live_root.rglob("*")):
            if path.is_symlink() or path.is_file():
                rel = path.relative_to(live_root).as_posix()
                if rel not in known and not rel.endswith(_TMP_SUFFIX):
                    report["unexpected"].append(rel)
    report["ok"] = not unrepairable
    return report


def apply_corruption(live: str | Path, mode: str) -> dict[str, Any]:
    """Damage one component of the live tree in the named way; return what was done.

    ``missing_*`` modes delete the component, ``truncated_*`` modes keep only a
    prefix of its bytes (``truncated_skill`` leaves two bytes so the skill is
    present but unreadable; ``truncated_manifest`` cuts ``plugin.json`` in half
    so it no longer parses) and ``wrong_permissions`` strips the shim's
    executable bits.
    """
    root = Path(live)
    if mode not in COMPONENT_FOR_MODE:
        raise ValueError(
            f"unknown corruption mode {mode!r}; known: {sorted(COMPONENT_FOR_MODE)}"
        )
    component = COMPONENT_FOR_MODE[mode]
    target = root / component
    before = target.read_bytes() if target.is_file() else None
    if mode in ("missing_file", "missing_plugin_json", "missing_shim"):
        if target.exists() or target.is_symlink():
            target.unlink()
        kind = "deleted"
    elif mode == "truncated_skill":
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((before or b"")[:2])
        kind = "truncated"
    elif mode == "truncated_manifest":
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((before or b"")[: max(1, len(before or b"") // 2)])
        kind = "truncated"
    else:  # wrong_permissions
        if target.is_file():
            target.chmod(0o644)
        kind = "chmod"
    exists_after = target.exists()
    st = target.stat() if exists_after else None
    return {
        "mode": mode,
        "component": component,
        "path": str(target),
        "kind": kind,
        "bytes_before": len(before) if before is not None else None,
        "bytes_after": st.st_size if st is not None else None,
        "mode_after": f"{stat.S_IMODE(st.st_mode):o}" if st is not None else None,
        "exists_after": exists_after,
        "red_journey": RED_JOURNEY.get(mode),
    }


# --------------------------------------------------------------------------- CLI


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m plugin.repair",
        description="Restore plugins/<package-id> from its recorded payload sidecar.",
    )
    parser.add_argument(
        "--home", required=True, help="profile home that holds plugins/<package-id>"
    )
    parser.add_argument(
        "--package-id",
        default=PACKAGE_NAME,
        help=f"package to repair (default {PACKAGE_NAME})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report what would be restored without writing",
    )
    args = parser.parse_args(argv)
    report = repair_install(args.home, args.package_id, dry_run=args.dry_run)
    verb = "WOULD-RESTORE" if args.dry_run else "RESTORED"
    for entry in report["restored"]:
        print(f"{verb}:{entry['path']} ({entry['reason']})")
    for name in report["unrepairable"]:
        print(f"UNREPAIRABLE:{name}")
    for reason in report["reasons"]:
        print(f"  {reason}", file=sys.stderr)
    print(json.dumps(report, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
