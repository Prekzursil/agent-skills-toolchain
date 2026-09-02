#!/usr/bin/env python3
"""Conforming rollback engine plus a naive wipe-and-restore (11347 mutant).

Conforming inverse actions are built only through InversePlan.build(), which
raises ContractViolation if a target is outside CreationSet. There is no
delete-arbitrary-path API. Naive rollback rmtree's the managed root, which
deletes user-owned paths that were never in the installer backup.
"""
from __future__ import annotations

import hashlib
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ledger import (
    ContractViolation,
    CreationSet,
    InverseAction,
    InversePlan,
    Ledger,
    default_ledger,
)
from tree import CONTENTS_V1, apply_install, materialize_base


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def walk_rel(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not root.is_dir():
        return out
    for p in root.rglob("*"):
        if p.is_file():
            rel = p.relative_to(root).as_posix()
            out[rel] = sha256_bytes(p.read_bytes())
    return out


@dataclass
class BackupRecord:
    existed: bool
    sha256: str | None
    data: bytes | None


@dataclass
class Backup:
    recorded_at: float
    files: dict[str, BackupRecord]


@dataclass
class Trace:
    engine: str
    backup_before_first_write: bool
    backup_recorded_at: float | None
    first_write_at: float | None
    inverse_targets: list[str]
    unlinked: list[str]
    restored: list[str]
    verification: dict[str, str]
    claimed_complete: bool
    construction_used: bool
    notes: str = ""
    extra_unlinks: list[str] = field(default_factory=list)


@dataclass
class RunResult:
    engine: str
    complete: bool
    trace: Trace
    before: dict[str, str]
    after: dict[str, str]
    backup_sha: dict[str, str | None]
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "engine": self.engine,
            "complete": self.complete,
            "error": self.error,
            "before": dict(sorted(self.before.items())),
            "after": dict(sorted(self.after.items())),
            "backup_sha": dict(sorted(self.backup_sha.items())),
            "trace": {
                "engine": self.trace.engine,
                "backup_before_first_write": self.trace.backup_before_first_write,
                "backup_recorded_at": self.trace.backup_recorded_at,
                "first_write_at": self.trace.first_write_at,
                "inverse_targets": list(self.trace.inverse_targets),
                "unlinked": list(self.trace.unlinked),
                "restored": list(self.trace.restored),
                "verification": dict(self.trace.verification),
                "claimed_complete": self.trace.claimed_complete,
                "construction_used": self.trace.construction_used,
                "notes": self.trace.notes,
                "extra_unlinks": list(self.trace.extra_unlinks),
            },
        }


def snapshot_creation(root: Path, creation: CreationSet) -> Backup:
    files: dict[str, BackupRecord] = {}
    for rel in creation:
        path = root / rel
        if path.is_file():
            data = path.read_bytes()
            files[rel] = BackupRecord(True, sha256_bytes(data), data)
        else:
            files[rel] = BackupRecord(False, None, None)
    return Backup(recorded_at=time.time(), files=files)


def _write(root: Path, rel: str, data: bytes) -> None:
    dest = root / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)


def prepare_installed_tree(root: Path, ledger: Ledger | None = None) -> Backup:
    """Base tree, backup installer paths, then install mutation + post-install user file."""
    ledger = ledger or default_ledger()
    if root.exists():
        shutil.rmtree(root)
    materialize_base(root)
    backup = snapshot_creation(root, ledger.creation)
    apply_install(root)
    return backup


def plan_from_backup(ledger: Ledger, backup: Backup) -> InversePlan:
    actions: list[InverseAction] = []
    for rel in ledger.creation:
        rec = backup.files[rel]
        if rec.existed:
            actions.append(
                InverseAction(rel, "restore-bytes", rec.sha256)
            )
        else:
            actions.append(InverseAction(rel, "unlink-created", None))
    return InversePlan.build(ledger.creation, actions)


def conforming_rollback(
    root: Path,
    backup: Backup,
    ledger: Ledger | None = None,
    *,
    skip_verify: bool = False,
    force_complete: bool | None = None,
    skip_backup_flag: bool = False,
    corrupt_restore: str | None = None,
    skip_restore: str | None = None,
    extra_unlink: str | None = None,
    clobber_preserve: str | None = None,
) -> RunResult:
    """Execute InversePlan only. Optional knobs produce single-rule mutants."""
    ledger = ledger or default_ledger()
    before = walk_rel(root)
    first_write_at: float | None = None
    restored: list[str] = []
    unlinked: list[str] = []
    extra_unlinks: list[str] = []
    verification: dict[str, str] = {}
    err: str | None = None
    construction_used = True
    try:
        plan = plan_from_backup(ledger, backup)
    except ContractViolation as exc:
        construction_used = False
        err = str(exc)
        trace = Trace(
            engine="conforming",
            backup_before_first_write=not skip_backup_flag,
            backup_recorded_at=backup.recorded_at,
            first_write_at=None,
            inverse_targets=[],
            unlinked=[],
            restored=[],
            verification={},
            claimed_complete=False,
            construction_used=False,
            notes=err,
        )
        return RunResult("conforming", False, trace, before, walk_rel(root), {}, err)

    targets = [a.path for a in plan.actions]
    for act in plan.actions:
        if skip_restore and act.path == skip_restore:
            continue
        rec = backup.files[act.path]
        if first_write_at is None:
            first_write_at = time.time()
        if act.kind == "restore-bytes":
            data = rec.data or b""
            if corrupt_restore == act.path:
                data = data + b"\nCORRUPT-RESTORE\n"
            _write(root, act.path, data)
            restored.append(act.path)
        elif act.kind == "unlink-created":
            path = root / act.path
            if path.is_file():
                path.unlink()
            unlinked.append(act.path)

    if extra_unlink:
        p = root / extra_unlink
        if p.is_file():
            p.unlink()
        extra_unlinks.append(extra_unlink)
        unlinked.append(extra_unlink)

    if clobber_preserve:
        _write(root, clobber_preserve, b"CLOBBERED-BY-ROLLBACK\n")

    if not skip_verify:
        for act in plan.actions:
            if skip_restore and act.path == skip_restore:
                continue
            rec = backup.files[act.path]
            path = root / act.path
            if rec.existed:
                if path.is_file():
                    verification[act.path] = sha256_bytes(path.read_bytes())
                else:
                    verification[act.path] = "MISSING"
            else:
                verification[act.path] = "ABSENT-OK" if not path.exists() else "STILL-PRESENT"

    verify_ok = True
    for act in plan.actions:
        if skip_restore and act.path == skip_restore:
            verify_ok = False
            continue
        rec = backup.files[act.path]
        got = verification.get(act.path)
        if rec.existed:
            if got != rec.sha256:
                verify_ok = False
        else:
            if got != "ABSENT-OK":
                verify_ok = False

    complete = verify_ok if force_complete is None else force_complete
    backup_before = (
        False
        if skip_backup_flag
        else (
            backup.recorded_at is not None
            and (first_write_at is None or backup.recorded_at <= first_write_at)
        )
    )
    trace = Trace(
        engine="conforming" if not extra_unlink and not clobber_preserve else "mutant",
        backup_before_first_write=backup_before,
        backup_recorded_at=backup.recorded_at,
        first_write_at=first_write_at,
        inverse_targets=targets,
        unlinked=unlinked,
        restored=restored,
        verification=verification,
        claimed_complete=complete,
        construction_used=construction_used,
        extra_unlinks=extra_unlinks,
        notes="InversePlan.build restricted to CreationSet",
    )
    backup_sha = {k: v.sha256 for k, v in backup.files.items()}
    return RunResult(
        engine=trace.engine,
        complete=complete,
        trace=trace,
        before=before,
        after=walk_rel(root),
        backup_sha=backup_sha,
        error=err,
    )


def naive_rollback(root: Path, backup: Backup, ledger: Ledger | None = None) -> RunResult:
    """Non-conforming: rmtree the managed root, then restore installer backup only.

    User-owned paths inside the tree are destroyed. This is the :11347 mutant.
    """
    ledger = ledger or default_ledger()
    before = walk_rel(root)
    first_write_at = time.time()
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    restored: list[str] = []
    for rel, rec in backup.files.items():
        if rec.existed and rec.data is not None:
            _write(root, rel, rec.data)
            restored.append(rel)
    after = walk_rel(root)
    verification = {rel: after[rel] for rel in restored if rel in after}
    unlinked = sorted(set(before) - set(after))
    backup_sha = {k: v.sha256 for k, v in backup.files.items()}
    # Naive claims complete after copy, even though preserve paths vanished.
    complete = True
    trace = Trace(
        engine="naive-rmtree",
        backup_before_first_write=backup.recorded_at <= first_write_at,
        backup_recorded_at=backup.recorded_at,
        first_write_at=first_write_at,
        inverse_targets=list(backup.files),
        unlinked=unlinked,
        restored=restored,
        verification=verification,
        claimed_complete=complete,
        construction_used=False,
        notes="rmtree of managed root then installer-only restore",
        extra_unlinks=[p for p in unlinked if p not in ledger.creation],
    )
    return RunResult("naive-rmtree", complete, trace, before, after, backup_sha)


def run_prepared(
    kind: str,
    tmp: Path,
    ledger: Ledger | None = None,
) -> RunResult:
    ledger = ledger or default_ledger()
    backup = prepare_installed_tree(tmp, ledger)
    if kind == "conforming":
        return conforming_rollback(tmp, backup, ledger)
    if kind == "naive":
        return naive_rollback(tmp, backup, ledger)
    raise KeyError(kind)


MUTANT_SPECS: dict[str, dict[str, Any]] = {
    "R1-RESTORE-VERSION": {"corrupt_restore": "plugin.json"},
    "R2-RESTORE-CONFIG": {"corrupt_restore": "config/harness.json"},
    "R3-RESTORE-DEPLOYED-TREE": {"skip_restore": "plugin-extra.json"},
    "R4-PRESERVE-OWNER-EDITS": {"clobber_preserve": "owner/hand-edit.md"},
    "R5-PRESERVE-USER-DATA": {"extra_unlink": "data/user-notes.txt"},
    "R6-PRESERVE-MCP-CURATION": {"clobber_preserve": "mcp/curation.json"},
    "R7-PRESERVE-CREDENTIALS": {"extra_unlink": "credentials/store.synthetic.json"},
    "R8-PRE-CHANGE-BACKUP": {"skip_backup_flag": True},
    "R9-PROOF-OF-RESTORE": {"skip_verify": True},
    "R10-COMPLETE-ONLY-AFTER-VERIFY": {
        "corrupt_restore": "plugin.json",
        "force_complete": True,
    },
    "R11-INVERSE-CREATION-SET": {"extra_unlink": "commands/cmd.user-owned.json"},
    "R12-INVERSE-PREEXISTING": {"extra_unlink": "skills/skill.user.md"},
}


def run_mutant(rule_id: str, tmp: Path, ledger: Ledger | None = None) -> RunResult:
    ledger = ledger or default_ledger()
    spec = MUTANT_SPECS[rule_id]
    backup = prepare_installed_tree(tmp, ledger)
    result = conforming_rollback(tmp, backup, ledger, **spec)
    result.engine = f"mutant:{rule_id}"
    result.trace.engine = result.engine
    return result


# Silence unused import lint for CONTENTS_V1 if tree is the source of truth.
_ = CONTENTS_V1
