"""Lifecycle commands: install, update, repair, rollback, uninstall — all transactional.

Every mutating command follows the same three-beat shape, which is what makes "a failed install
leaves no partial state" a property of the design rather than a hope:

1. **stage** — unpack into ``state/staging/<txn>/`` and verify it there. Nothing outside staging
   has been touched yet, so a failure at this point is free.
2. **verify** — strict manifest parse, client/OS negotiation, interpreter floors, per-file hash
   check against the archive's own inventory. A staged tree that fails verification is deleted.
3. **activate** — one directory move of the staged tree onto ``versions/<version>/`` (``os.replace``
   where the OS allows it; see ``fsops.move_dir`` for the measured Windows retry path), then an
   atomic ``installed.json`` write. The pointer flip is the only observable moment.

Every step registers its inverse with the journal, so an exception anywhere replays the inverses in
reverse order. ``rollback`` and ``uninstall`` are ordinary commands built from the same primitives —
they are exercised by the test suite precisely because they are the two nobody runs.

Two safety invariants are asserted, not documented:

* ``rollback`` never removes a live file that the target version does not ship (it would delete a
  command the user still has) and never touches ``userdata/``;
* ``uninstall`` requires an explicit user-data decision — there is no default.
"""

from __future__ import annotations

import json
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import deploy as deploy_mod
from .errors import PluginError
from .fsops import (
    atomic_write_bytes,
    content_hash,
    dir_size,
    move_dir,
    rmtree,
    safe_join,
)
from .journal import (
    Prefix,
    PrefixLock,
    Transaction,
    read_installed,
    recover,
    write_installed,
)
from .manifest import MANIFEST_RELPATH, Manifest, load as load_manifest
from .packager import INVENTORY_RELPATH, list_members, read_member, unpack
from .proc import current_os, probe_interpreter

MIN_FREE_BYTES = 32 * 1024 * 1024


@dataclass
class LifecycleResult:
    op: str
    ok: bool
    version: str | None = None
    previous_version: str | None = None
    detail: dict[str, object] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return {
            "artifact": "lifecycle-result",
            "op": self.op,
            "ok": self.ok,
            "version": self.version,
            "previous_version": self.previous_version,
            **self.detail,
        }

    def marker(self) -> str:
        return f"{'SUCCESS' if self.ok else 'FAILED'}:{self.op}"


# --------------------------------------------------------------------------- preflight


def _existing_ancestor(path: Path) -> Path:
    p = path
    while not p.exists() and p != p.parent:
        p = p.parent
    return p


def preflight(
    prefix: Prefix, *, op: str, need_bytes: int = 0, mutate: bool = True
) -> dict[str, object]:
    """Disk, writability, and crash-residue check (IMP-0029). Raises ``E_PREFLIGHT``.

    ``mutate=False`` is the dry-run form: it measures free space against the nearest EXISTING
    ancestor and creates nothing. A dry run that materialises the prefix layout is not a dry run —
    it is a partial install with a reassuring name, and the CLI test caught exactly that.
    """
    if not mutate:
        anchor = _existing_ancestor(prefix.root)
        usage = shutil.disk_usage(str(anchor))
        required = max(need_bytes * 3, MIN_FREE_BYTES)
        if usage.free < required:
            raise PluginError(
                "E_PREFLIGHT",
                f"insufficient free space: {usage.free} bytes free, {required} required",
                context={"measured_at": str(anchor)},
            )
        return {
            "op": op,
            "dry_run": True,
            "free_bytes": usage.free,
            "required_bytes": required,
            "measured_at": str(anchor),
            "created_nothing": True,
        }
    prefix.root.mkdir(parents=True, exist_ok=True)
    prefix.ensure()
    probe = prefix.state / ".writable-probe"
    try:
        atomic_write_bytes(probe, b"ok\n")
        probe.unlink()
    except (PluginError, OSError) as exc:
        raise PluginError(
            "E_PREFLIGHT", f"prefix is not writable: {prefix.root} ({exc})"
        ) from exc
    usage = shutil.disk_usage(str(prefix.root))
    required = max(need_bytes * 3, MIN_FREE_BYTES)
    if usage.free < required:
        raise PluginError(
            "E_PREFLIGHT",
            f"insufficient free space: {usage.free} bytes free, {required} required",
            context={"prefix": str(prefix.root)},
        )
    recovery = recover(prefix)
    return {
        "op": op,
        "free_bytes": usage.free,
        "required_bytes": required,
        "crash_recovery": recovery,
    }


def negotiate(
    manifest: Manifest, *, client_version: str, os_name: str | None = None
) -> None:
    """Client / platform negotiation. Raises ``E_COMPAT`` with the exact incompatibility."""
    ok, reason = manifest.negotiate(client_version)
    if not ok:
        raise PluginError(
            "E_COMPAT", reason, context={"min_client": manifest.min_client}
        )
    osn = os_name or current_os()
    if osn not in manifest.platforms:
        raise PluginError(
            "E_COMPAT",
            f"platform {osn!r} is not in the manifest's supported set {list(manifest.platforms)}",
        )


def check_interpreters(manifest: Manifest) -> list[dict[str, object]]:
    """Probe every declared interpreter. A missing *required* one is ``E_INTERP``."""
    probes: list[dict[str, object]] = []
    for decl in manifest.interpreters:
        p = probe_interpreter(str(decl["id"]))
        row = p.as_dict()
        row["required"] = bool(decl.get("required", True))
        probes.append(row)
        if row["required"] and (not p.found or not p.meets_floor):
            raise PluginError(
                "E_INTERP",
                f"required interpreter {decl['id']!r}: {p.detail}",
                context={"probe": json.dumps(row, sort_keys=True)},
            )
    return probes


# --------------------------------------------------------------------------- stage / verify


def _stage(archive: Path, prefix: Prefix, txn: Transaction) -> Path:
    staged = prefix.staging / txn.txn_id
    if staged.exists():
        rmtree(staged)
    staged.mkdir(parents=True, exist_ok=True)
    txn.add(
        "stage",
        {"staged_dir": str(staged), "archive": str(archive)},
        lambda: rmtree(staged),
    )
    unpack(archive, staged)
    return staged


def _verify_staged(staged: Path) -> Manifest:
    mpath = staged / MANIFEST_RELPATH
    if not mpath.exists():
        raise PluginError("E_CONFORM", f"package has no {MANIFEST_RELPATH}")
    manifest = load_manifest(mpath)
    inv_path = staged / INVENTORY_RELPATH
    if not inv_path.exists():
        raise PluginError("E_CONFORM", f"package has no {INVENTORY_RELPATH}")
    inventory = json.loads(inv_path.read_text(encoding="utf-8"))
    mismatches: list[str] = []
    for entry in inventory.get("entries", []):
        f = safe_join(staged, entry["path"])
        if not f.exists():
            mismatches.append(f"{entry['path']}: missing from the archive")
            continue
        actual = content_hash(f)
        if actual != entry["sha256"]:
            mismatches.append(f"{entry['path']}: hash mismatch")
    if mismatches:
        raise PluginError(
            "E_CONFORM",
            f"{len(mismatches)} staged file(s) disagree with the package inventory",
            context={"first": mismatches[0]},
        )
    for ep in manifest.entrypoints:
        if not (staged / ep.path).exists():
            raise PluginError(
                "E_CONFORM", f"entrypoint {ep.ident!r} names a missing file: {ep.path}"
            )
    return manifest


def _activate(
    staged: Path, prefix: Prefix, manifest: Manifest, txn: Transaction
) -> Path:
    dest = prefix.version_dir(manifest.version)
    if dest.exists():
        raise PluginError(
            "E_TXN",
            f"version {manifest.version} is already installed at {dest}",
            context={"hint": "use `update` to a new version, or `uninstall` first"},
        )
    dest.parent.mkdir(parents=True, exist_ok=True)
    # The inverse is registered BEFORE the move, so the copy fallback inside move_dir is safe even
    # though it is not atomic: an abort removes `dest` either way.
    txn.add(
        "activate",
        {"created_dir": str(dest), "version": manifest.version},
        lambda: rmtree(dest),
    )
    strategy = move_dir(staged, dest)
    txn.add(
        "activate_strategy", {"version": manifest.version, "strategy": strategy}, None
    )
    return dest


def _record_installed(
    prefix: Prefix,
    manifest: Manifest,
    *,
    previous: str | None,
    txn: Transaction,
    archive_sha: str,
) -> dict[str, object]:
    before = read_installed(prefix)
    doc = {
        "artifact": "installed-state",
        "name": manifest.name,
        "active_version": manifest.version,
        "previous_version": previous,
        "installed_at": round(time.time(), 3),
        "archive_sha256": archive_sha,
        "history": [*before.get("history", []), manifest.version],  # type: ignore[list-item]
    }

    def _undo() -> None:
        if before:
            write_installed(prefix, before)
        elif prefix.installed.exists():
            prefix.installed.unlink()

    txn.add(
        "record_installed", {"version": manifest.version, "previous": previous}, _undo
    )
    write_installed(prefix, doc)
    return doc


# --------------------------------------------------------------------------- commands


def install(
    archive: Path,
    prefix: Prefix,
    *,
    live_root: Path | None = None,
    client_version: str = "1.0.0",
    deploy: bool = True,
    dry_run: bool = False,
) -> LifecycleResult:
    """Transactional install: stage, verify, activate, then (optionally) deploy live."""
    if not archive.exists():
        raise PluginError("E_USAGE", f"package not found: {archive}")
    need = archive.stat().st_size
    pre = preflight(prefix, op="install", need_bytes=need, mutate=not dry_run)
    if dry_run:
        members = list_members(archive)
        manifest = load_manifest_from_archive(archive)
        negotiate(manifest, client_version=client_version)
        return LifecycleResult(
            "install",
            True,
            manifest.version,
            None,
            {"dry_run": True, "would_stage": len(members), "preflight": pre},
        )
    from .packager import archive_sha256

    sha = archive_sha256(archive)
    with PrefixLock(prefix, op="install"), Transaction(prefix, "install") as txn:
        staged = _stage(archive, prefix, txn)
        manifest = _verify_staged(staged)
        negotiate(manifest, client_version=client_version)
        interp = check_interpreters(manifest)
        version_root = _activate(staged, prefix, manifest, txn)
        state = _record_installed(
            prefix, manifest, previous=None, txn=txn, archive_sha=sha
        )
        synced: dict[str, object] = {"skipped": True}
        if deploy:
            lr = live_root or (prefix.root / "live")
            lr.mkdir(parents=True, exist_ok=True)
            synced = deploy_mod.sync(
                manifest, version_root, lr, prefix, txn=txn
            ).as_dict()
    total, count = dir_size(version_root)
    return LifecycleResult(
        "install",
        True,
        manifest.version,
        None,
        {
            "version_root": str(version_root),
            "installed_bytes": total,
            "installed_files": count,
            "interpreters": interp,
            "deploy": synced,
            "installed_state": state,
            "preflight": pre,
        },
    )


def load_manifest_from_archive(archive: Path) -> Manifest:
    from .manifest import parse

    return parse(read_member(archive, MANIFEST_RELPATH).decode("utf-8"))


def update(
    archive: Path,
    prefix: Prefix,
    *,
    live_root: Path | None = None,
    client_version: str = "1.0.0",
    dry_run: bool = False,
) -> LifecycleResult:
    """Install a new version alongside the current one, preserving live user overrides."""
    state = read_installed(prefix)
    current = state.get("active_version")
    if not current:
        raise PluginError(
            "E_TXN",
            "nothing is installed in this prefix, so there is nothing to update",
            context={"hint": "run `install` first"},
        )
    new_manifest = load_manifest_from_archive(archive)
    if new_manifest.semver <= _semver(str(current)):
        raise PluginError(
            "E_TXN",
            f"refusing to 'update' from {current} to {new_manifest.version}: not an advance",
            context={"hint": "use `rollback` to go backwards"},
        )
    pre = preflight(
        prefix, op="update", need_bytes=archive.stat().st_size, mutate=not dry_run
    )
    if dry_run:
        lr = live_root or (prefix.root / "live")
        staged_preview = deploy_mod.classify(
            new_manifest,
            prefix.version_dir(str(current)),
            lr,
            deploy_mod.Provenance.load(prefix.state / deploy_mod.PROVENANCE_NAME),
        )
        return LifecycleResult(
            "update",
            True,
            new_manifest.version,
            str(current),
            {
                "dry_run": True,
                "preflight": pre,
                "drift_preview": deploy_mod.drift_document(staged_preview)["counts"],
            },
        )
    from .packager import archive_sha256

    sha = archive_sha256(archive)
    with PrefixLock(prefix, op="update"), Transaction(prefix, "update") as txn:
        staged = _stage(archive, prefix, txn)
        manifest = _verify_staged(staged)
        negotiate(manifest, client_version=client_version)
        check_interpreters(manifest)
        version_root = _activate(staged, prefix, manifest, txn)
        _record_installed(
            prefix, manifest, previous=str(current), txn=txn, archive_sha=sha
        )
        lr = live_root or (prefix.root / "live")
        lr.mkdir(parents=True, exist_ok=True)
        sync_res = deploy_mod.sync(manifest, version_root, lr, prefix, txn=txn)
    return LifecycleResult(
        "update",
        True,
        manifest.version,
        str(current),
        {
            "deploy": sync_res.as_dict(),
            "preserved_user_overrides": sync_res.kept,
            "needs_decision": sync_res.needs_decision,
            "preflight": pre,
        },
    )


def _semver(text: str) -> tuple[int, int, int]:
    from .manifest import parse_semver

    return parse_semver(text, where="installed version")


def repair(
    prefix: Prefix, *, live_root: Path | None = None, dry_run: bool = False
) -> LifecycleResult:
    """Restore live files that hold no unique content. Live overrides are reported, never clobbered."""
    state = read_installed(prefix)
    version = state.get("active_version")
    if not version:
        raise PluginError("E_TXN", "nothing is installed in this prefix")
    version_root = prefix.version_dir(str(version))
    manifest = load_manifest(version_root / MANIFEST_RELPATH)
    lr = live_root or (prefix.root / "live")
    preflight(prefix, op="repair", mutate=not dry_run)
    with PrefixLock(prefix, op="repair"):
        res = deploy_mod.repair(manifest, version_root, lr, prefix, dry_run=dry_run)
    return LifecycleResult(
        "repair",
        True,
        str(version),
        None,
        {
            "restored": res.written,
            "kept_live_override": res.kept,
            "needs_decision": res.needs_decision,
            "dry_run": dry_run,
        },
    )


def rollback(
    prefix: Prefix, *, live_root: Path | None = None, dry_run: bool = False
) -> LifecycleResult:
    """Activate the previous version. Cannot remove an existing live command or any user data."""
    state = read_installed(prefix)
    current = state.get("active_version")
    target = state.get("previous_version")
    if not current:
        raise PluginError("E_TXN", "nothing is installed in this prefix")
    if not target:
        raise PluginError(
            "E_TXN",
            f"version {current} has no recorded previous version to roll back to",
            context={"hint": "the install history is in state/installed.json"},
        )
    target_root = prefix.version_dir(str(target))
    if not target_root.exists():
        raise PluginError(
            "E_TXN",
            f"previous version {target} is recorded but its files are gone ({target_root})",
        )
    manifest = load_manifest(target_root / MANIFEST_RELPATH)
    lr = live_root or (prefix.root / "live")
    preflight(prefix, op="rollback", mutate=not dry_run)
    if dry_run:
        return LifecycleResult(
            "rollback", True, str(target), str(current), {"dry_run": True}
        )

    live_before = _live_snapshot(lr)
    userdata_before = _live_snapshot(prefix.userdata)
    with PrefixLock(prefix, op="rollback"), Transaction(prefix, "rollback") as txn:
        before_state = dict(state)

        def _undo_state() -> None:
            write_installed(prefix, before_state)

        txn.add(
            "rollback_pointer", {"from": str(current), "to": str(target)}, _undo_state
        )
        new_state = {
            **state,
            "active_version": str(target),
            "previous_version": None,
            "rolled_back_from": str(current),
            "installed_at": round(time.time(), 3),
        }
        write_installed(prefix, new_state)
        # Deploy the target version's files. force_source=False keeps user overrides.
        sync_res = deploy_mod.sync(manifest, target_root, lr, prefix, txn=txn)

    live_after = _live_snapshot(lr)
    removed = sorted(set(live_before) - set(live_after))
    userdata_after = _live_snapshot(prefix.userdata)
    if removed:
        raise PluginError(
            "E_TXN",
            f"rollback removed {len(removed)} live file(s); this violates the no-removal invariant",
            context={"first_removed": removed[0]},
        )
    if userdata_before != userdata_after:
        raise PluginError(
            "E_TXN", "rollback modified userdata/, which it must never touch"
        )
    return LifecycleResult(
        "rollback",
        True,
        str(target),
        str(current),
        {
            "deploy": sync_res.as_dict(),
            "live_files_before": len(live_before),
            "live_files_after": len(live_after),
            "live_files_removed": removed,
            "userdata_untouched": True,
            "versions_retained": sorted(
                p.name for p in prefix.versions.iterdir() if p.is_dir()
            ),
        },
    )


def _live_snapshot(root: Path) -> dict[str, str]:
    from .fsops import iter_files, relposix

    if not root.exists():
        return {}
    return {relposix(root, f): content_hash(f) for f in iter_files(root)}


def uninstall(
    prefix: Prefix,
    *,
    live_root: Path | None = None,
    user_data: str | None = None,
    dry_run: bool = False,
) -> LifecycleResult:
    """Remove versions and provenance-tracked live files. ``user_data`` MUST be chosen explicitly."""
    if user_data not in {"retain", "purge"}:
        raise PluginError(
            "E_USAGE",
            "uninstall requires an explicit user-data decision",
            context={"choose": "--retain-user-data | --purge-user-data"},
        )
    state = read_installed(prefix)
    if not state:
        raise PluginError("E_TXN", "nothing is installed in this prefix")
    lr = live_root or (prefix.root / "live")
    provenance = deploy_mod.Provenance.load(prefix.state / deploy_mod.PROVENANCE_NAME)
    removable: list[str] = []
    kept: list[str] = []
    for live_rel, rec in sorted(provenance.records.items()):
        f = lr / live_rel
        if not f.exists():
            continue
        if content_hash(f) == rec.content_sha256:
            removable.append(live_rel)
        else:
            kept.append(live_rel)  # user-edited: never deleted by an uninstall
    versions = (
        sorted(p.name for p in prefix.versions.iterdir() if p.is_dir())
        if prefix.versions.exists()
        else []
    )
    if dry_run:
        return LifecycleResult(
            "uninstall",
            True,
            str(state.get("active_version")),
            None,
            {
                "dry_run": True,
                "would_remove_live": removable,
                "would_keep_live_edited": kept,
                "would_remove_versions": versions,
                "user_data": user_data,
            },
        )
    with PrefixLock(prefix, op="uninstall"), Transaction(prefix, "uninstall") as txn:
        for live_rel in removable:
            f = lr / live_rel
            blob = f.read_bytes()
            txn.add(
                "remove_live",
                {"live_path": live_rel},
                lambda p=f, b=blob: atomic_write_bytes(p, b),
            )
            f.unlink()
        for v in versions:
            txn.add("remove_version", {"version": v}, None)
            rmtree(prefix.version_dir(v))
        if user_data == "purge":
            txn.add("purge_userdata", {"path": str(prefix.userdata)}, None)
            rmtree(prefix.userdata)
        prov_path = prefix.state / deploy_mod.PROVENANCE_NAME
        if prov_path.exists():
            prov_path.unlink()
        if prefix.installed.exists():
            prefix.installed.unlink()
    return LifecycleResult(
        "uninstall",
        True,
        str(state.get("active_version")),
        None,
        {
            "removed_live": removable,
            "kept_live_edited": kept,
            "removed_versions": versions,
            "user_data": user_data,
            "userdata_retained": user_data == "retain" and prefix.userdata.exists(),
        },
    )


def prefix_residue(prefix: Prefix) -> dict[str, object]:
    """What a prefix still holds. Used by the failed-install test to prove nothing partial remains."""
    versions = (
        sorted(p.name for p in prefix.versions.iterdir() if p.is_dir())
        if prefix.versions.exists()
        else []
    )
    staged = (
        sorted(p.name for p in prefix.staging.iterdir())
        if prefix.staging.exists()
        else []
    )
    return {
        "artifact": "prefix-residue",
        "versions": versions,
        "staged_dirs": staged,
        "installed_json_exists": prefix.installed.exists(),
        "lock_held": prefix.lock.exists(),
        "live_files": sorted(_live_snapshot(prefix.root / "live")),
    }
