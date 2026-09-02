#!/usr/bin/env python3
"""Reference rollback engine for the ARC-0094 contract.

Fail-closed: if restoring the pre-change backup by full protected-tree sync
would DELETE an owner-authored path that exists only on the live tree, the
rollback is REFUSED and no mutations are applied.

Proof-of-restore is a content hash per protected path. Rollback is not
complete until that verification passes. A second apply on an already
restored tree is a no-op (idempotence).
"""
from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SHA_LEN = 64
ZERO_SHA = "0" * SHA_LEN

RESTORE_EXACT = {
    "version.json": "previous_version",
    "config/harness.json": "previous_configuration",
}
RESTORE_PREFIXES = {
    "deploy/": "previous_deployed_tree_state",
}
MCP_EXACT = {
    "mcp/enable-disable.json": "curated_mcp_enable_disable_state",
}
PRESERVE_PREFIXES = {
    "owner/": "owner_authored_edits",
    "userdata/": "user_data",
    "credentials/": "credential_stores",
}
OWNER_PREFIX = "owner/"
RESTORE_ROLES = {
    "previous_version",
    "previous_configuration",
    "previous_deployed_tree_state",
    "curated_mcp_enable_disable_state",
}


def rel_of(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def iter_files(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    out = [p for p in root.rglob("*") if p.is_file()]
    out.sort(key=lambda p: rel_of(root, p))
    return out


def classify(rel: str) -> str | None:
    if rel in RESTORE_EXACT:
        return RESTORE_EXACT[rel]
    if rel in MCP_EXACT:
        return MCP_EXACT[rel]
    for prefix, role in RESTORE_PREFIXES.items():
        if rel.startswith(prefix):
            return role
    for prefix, role in PRESERVE_PREFIXES.items():
        if rel.startswith(prefix):
            return role
    return None


def is_restore_target(rel: str) -> bool:
    return classify(rel) in RESTORE_ROLES


def is_owner_authored(rel: str) -> bool:
    return rel.startswith(OWNER_PREFIX)


def tree_digest(files: dict[str, str]) -> str:
    lines = [f"{k}\0{files[k]}" for k in sorted(files)]
    return sha256_bytes("\n".join(lines).encode("utf-8"))


def live_protected(root: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    for path in iter_files(root):
        rel = rel_of(root, path)
        if classify(rel) is None:
            continue
        files[rel] = sha256_file(path)
    return files


def snapshot(root: Path) -> dict[str, Any]:
    files: dict[str, str] = {}
    roles: dict[str, str] = {}
    for path in iter_files(root):
        rel = rel_of(root, path)
        role = classify(rel)
        if role is None:
            continue
        files[rel] = sha256_file(path)
        roles[rel] = role
    digest = tree_digest(files)
    return {
        "backup_id": f"backup-{digest[:16]}",
        "captured_before_mutation": True,
        "files": files,
        "roles": roles,
        "tree_digest": digest,
    }


def copy_tree(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)


def naive_tree_sync_deletes(live_root: Path, backup: dict[str, Any]) -> list[str]:
    """Deletes a full tree-sync (backup as the whole protected tree) would apply.

    Witness only. Not the contract engine.
    """
    backup_files = set(backup.get("files") or {})
    deletes: list[str] = []
    for path in iter_files(live_root):
        rel = rel_of(live_root, path)
        if classify(rel) is None:
            continue
        if rel not in backup_files:
            deletes.append(rel)
    return sorted(deletes)


def apply_naive_tree_sync(
    live_root: Path, backup_root: Path, backup: dict[str, Any]
) -> list[str]:
    """Execute the forbidden full sync so the probe can prove a planted file dies."""
    deleted: list[str] = []
    for rel in naive_tree_sync_deletes(live_root, backup):
        path = live_root / rel
        if path.is_file():
            path.unlink()
            deleted.append(rel)
    for rel in backup.get("files") or {}:
        src = backup_root / rel
        dest = live_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(src.read_bytes())
    return deleted


@dataclass
class RollbackResult:
    outcome: str
    complete: bool
    mutations_applied: bool
    would_destroy_owner_authored: bool
    owner_paths_that_would_be_deleted: list[str] = field(default_factory=list)
    owner_file_still_present: bool | None = None
    planted_rel: str | None = None
    first_tree_digest: str = ""
    second_tree_digest: str = ""
    path_proofs: list[dict[str, Any]] = field(default_factory=list)
    backup: dict[str, Any] = field(default_factory=dict)
    verification_passed: bool = False
    reason: str = ""


def _copy_from_backup(live_root: Path, backup_root: Path, rel: str) -> None:
    src = backup_root / rel
    dest = live_root / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(src.read_bytes())


def _plan_owner_deletes(live_root: Path, backup: dict[str, Any]) -> list[str]:
    return [
        rel
        for rel in naive_tree_sync_deletes(live_root, backup)
        if is_owner_authored(rel)
    ]


def _apply_restore(live_root: Path, backup_root: Path, backup: dict[str, Any]) -> None:
    backup_files = backup.get("files") or {}
    for rel in backup_files:
        if is_restore_target(rel):
            _copy_from_backup(live_root, backup_root, rel)
    for path in list(iter_files(live_root)):
        rel = rel_of(live_root, path)
        if classify(rel) == "previous_deployed_tree_state" and rel not in backup_files:
            path.unlink()
    for rel, role in (backup.get("roles") or {}).items():
        if role in {"owner_authored_edits", "user_data", "credential_stores"}:
            dest = live_root / rel
            if not dest.is_file():
                _copy_from_backup(live_root, backup_root, rel)


def _proofs(live_root: Path, backup: dict[str, Any]) -> list[dict[str, Any]]:
    proofs: list[dict[str, Any]] = []
    for rel, pre in sorted((backup.get("files") or {}).items()):
        role = (backup.get("roles") or {}).get(rel) or classify(rel) or "unknown"
        dest = live_root / rel
        if not dest.is_file():
            post = ZERO_SHA
            matched = False
        else:
            post = sha256_file(dest)
            if is_restore_target(rel):
                matched = post == pre
            else:
                matched = True
        proofs.append(
            {
                "path": rel,
                "role": role,
                "pre_change_sha256": pre,
                "post_rollback_sha256": post,
                "matched": matched,
            }
        )
    return proofs


def _restore_ok(proofs: list[dict[str, Any]]) -> bool:
    for item in proofs:
        role = item.get("role")
        if role in RESTORE_ROLES:
            if not item.get("matched"):
                return False
            if item["pre_change_sha256"] != item["post_rollback_sha256"]:
                return False
        if role in {"owner_authored_edits", "user_data", "credential_stores"}:
            if not item.get("matched"):
                return False
    return True


def rollback_once(
    live_root: Path,
    backup_root: Path,
    backup: dict[str, Any],
    planted_rel: str | None = None,
) -> RollbackResult:
    if not backup.get("captured_before_mutation") or not (backup.get("files") or {}):
        return RollbackResult(
            outcome="MISSING_BACKUP",
            complete=False,
            mutations_applied=False,
            would_destroy_owner_authored=False,
            reason="pre-change backup was not captured before mutation",
            backup=backup,
            first_tree_digest=tree_digest(live_protected(live_root)) or ZERO_SHA,
        )
    owner_deletes = _plan_owner_deletes(live_root, backup)
    if owner_deletes:
        planted_present = None
        if planted_rel:
            planted_present = (live_root / planted_rel).is_file()
        return RollbackResult(
            outcome="REFUSED_WOULD_DESTROY_OWNER_AUTHORED",
            complete=False,
            mutations_applied=False,
            would_destroy_owner_authored=True,
            owner_paths_that_would_be_deleted=owner_deletes,
            owner_file_still_present=planted_present,
            planted_rel=planted_rel,
            backup=backup,
            reason="tree-sync rollback would delete owner-authored path(s)",
            first_tree_digest=tree_digest(live_protected(live_root)),
        )
    _apply_restore(live_root, backup_root, backup)
    proofs = _proofs(live_root, backup)
    passed = _restore_ok(proofs)
    digest = tree_digest(live_protected(live_root))
    planted_present = None
    if planted_rel:
        planted_present = (live_root / planted_rel).is_file()
    return RollbackResult(
        outcome="COMPLETE" if passed else "INCOMPLETE_VERIFICATION_FAILED",
        complete=passed,
        mutations_applied=True,
        would_destroy_owner_authored=False,
        owner_file_still_present=planted_present,
        planted_rel=planted_rel,
        first_tree_digest=digest,
        path_proofs=proofs,
        backup=backup,
        verification_passed=passed,
        reason=(
            "post-restore content-hash verification passed"
            if passed
            else "post-restore verification failed"
        ),
    )


def rollback_twice(
    live_root: Path,
    backup_root: Path,
    backup: dict[str, Any],
    planted_rel: str | None = None,
) -> RollbackResult:
    first = rollback_once(live_root, backup_root, backup, planted_rel=planted_rel)
    second_digest = tree_digest(live_protected(live_root))
    if not first.complete:
        first.second_tree_digest = second_digest or ZERO_SHA
        return first
    second = rollback_once(live_root, backup_root, backup, planted_rel=planted_rel)
    first.second_tree_digest = second.first_tree_digest or ZERO_SHA
    if first.first_tree_digest != first.second_tree_digest:
        first.complete = False
        first.outcome = "INCOMPLETE_VERIFICATION_FAILED"
        first.reason = "second rollback changed the first rollback result"
        first.verification_passed = False
    return first


def _placeholder_proofs(backup: dict[str, Any]) -> list[dict[str, Any]]:
    proofs = []
    for rel, sha in sorted((backup.get("files") or {}).items()):
        proofs.append(
            {
                "path": rel,
                "role": (backup.get("roles") or {}).get(rel) or classify(rel) or "unknown",
                "pre_change_sha256": sha,
                "post_rollback_sha256": sha,
                "matched": False,
            }
        )
    if not proofs:
        proofs.append(
            {
                "path": "version.json",
                "role": "previous_version",
                "pre_change_sha256": ZERO_SHA,
                "post_rollback_sha256": ZERO_SHA,
                "matched": False,
            }
        )
    return proofs


def record_from_result(result: RollbackResult) -> dict[str, Any]:
    backup = result.backup or {}
    hashes = [
        {
            "path": rel,
            "sha256": sha,
            "role": (backup.get("roles") or {}).get(rel) or classify(rel),
        }
        for rel, sha in sorted((backup.get("files") or {}).items())
    ]
    if not hashes:
        hashes = [
            {"path": "version.json", "sha256": ZERO_SHA, "role": "previous_version"}
        ]
    first = result.first_tree_digest or ZERO_SHA
    second = result.second_tree_digest or first
    proofs = result.path_proofs or _placeholder_proofs(backup)
    owner_present = result.owner_file_still_present
    if owner_present is None:
        owner_present = not result.would_destroy_owner_authored
    return {
        "contract_id": "ARC-0094",
        "restore_obligations": {
            "previous_version": True,
            "previous_configuration": True,
            "previous_deployed_tree_state": True,
        },
        "never_destroy": {
            "owner_authored_edits": {
                "class": "owner_authored_edits",
                "must_not_destroy": True,
            },
            "user_data": {"class": "user_data", "must_not_destroy": True},
            "curated_mcp_enable_disable_state": {
                "class": "curated_mcp_enable_disable_state",
                "must_not_destroy": True,
            },
            "credential_stores": {
                "class": "credential_stores",
                "must_not_destroy": True,
            },
        },
        "pre_change_backup": {
            "backup_id": backup.get("backup_id") or "backup-missing",
            "captured_before_mutation": bool(backup.get("captured_before_mutation")),
            "protected_path_hashes": hashes,
        },
        "post_restore_verification": {
            "method": "content_hash_per_protected_path",
            "passed": bool(result.verification_passed),
            "path_proofs": proofs,
        },
        "complete": bool(result.complete),
        "outcome": result.outcome,
        "destruction_control": {
            "would_destroy_owner_authored": bool(result.would_destroy_owner_authored),
            "owner_paths_that_would_be_deleted": list(
                result.owner_paths_that_would_be_deleted
            ),
            "owner_file_still_present": bool(owner_present),
            "mutations_applied": bool(result.mutations_applied),
        },
        "idempotence": {
            "second_pass_digest_equals_first": first == second and len(first) == SHA_LEN,
            "first_tree_digest": first,
            "second_tree_digest": second,
        },
        "reason": result.reason or "rollback-record",
    }


# Probe-facing aliases (same functions, stable names).
copy_tree = copy_tree
naive_tree_sync_deletes = naive_tree_sync_deletes
apply_naive_tree_sync = apply_naive_tree_sync
record_from_result = record_from_result
sha256_file = sha256_file
