#!/usr/bin/env python3
"""Isolated in-place upgrade engine for REL-0005.

Throwaway HOME only. Fails loudly if the profile resolves to the owner's live
home. Migrations are transactional: snapshot, apply the full planned chain,
commit; on any gap or error restore and refuse. A second consecutive upgrade
re-invokes declared migrations but must not increment the ledger or rewrite
files when those migrations are actually idempotent.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

N2, N1, N = "1.0.0", "1.1.0", "1.2.0"
PLUGIN_ID = "ast-canary-plugin"
USER_SKILL_REL = "skills/user/owner-canary/SKILL.md"
USER_SKILL_BODY = (
    "---\n"
    "name: owner-canary-skill\n"
    "---\n"
    "# Owner canary skill\n"
    "User-authored. Must survive upgrade byte-for-byte.\n"
    "token: REL-0005-USER-SKILL-v1\n"
)
RULE_BODY = "# Team rule\nnever log secrets\n"
FRONTMATTER = "---\nmigrated: m122-rule-frontmatter\n---\n"
OWNER_HOME = Path(
    os.environ.get("AST_OWNER_HOME") or os.environ.get("HOME") or str(Path.home())
).resolve()


class IsolationError(RuntimeError):
    pass


class UpgradeRefuse(RuntimeError):
    def __init__(self, reason: str, restored: bool = False):
        super().__init__(reason)
        self.reason = reason
        self.restored = restored


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def assert_isolated(profile: Path) -> dict[str, Any]:
    resolved = Path(profile).resolve()
    owner = OWNER_HOME
    if resolved == owner:
        raise IsolationError(
            f"canary HOME resolves to owner live profile: {resolved}"
        )
    for base in (owner / ".ast", owner / ".cursor", owner / ".claude", owner / "AppData"):
        try:
            resolved.relative_to(base.resolve())
        except (ValueError, OSError):
            continue
        raise IsolationError(
            f"canary HOME {resolved} sits inside owner live tree {base}"
        )
    assertion = (
        f"isolated canary HOME {resolved} is not owner live profile {owner}; "
        "no read or write targeted the owner's live profile"
    )
    return {
        "profile_path": str(resolved),
        "owner_home": str(owner),
        "owner_home_touched": False,
        "isolated": True,
        "assertion": assertion,
    }


def create_profile(parent: Path | None = None) -> Path:
    root = Path(parent) if parent else Path("/tmp")
    root.mkdir(parents=True, exist_ok=True)
    profile = Path(tempfile.mkdtemp(prefix="rel0005-canary-", dir=str(root)))
    assert_isolated(profile)
    (profile / ".ast").mkdir(parents=True, exist_ok=True)
    return profile


def destroy_profile(profile: Path) -> None:
    resolved = Path(profile).resolve()
    if resolved == OWNER_HOME:
        raise IsolationError("refusing to destroy owner live profile")
    shutil.rmtree(resolved, ignore_errors=True)


def ast_root(profile: Path) -> Path:
    return Path(profile) / ".ast"


def tree_hashes(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not root.exists():
        return out
    for path in sorted(root.rglob("*")):
        if path.is_file():
            out[path.relative_to(root).as_posix()] = sha256_file(path)
    return out


def mutations(before: dict[str, str], after: dict[str, str]) -> dict[str, Any]:
    changed = sorted(k for k in before.keys() & after.keys() if before[k] != after[k])
    added = sorted(after.keys() - before.keys())
    removed = sorted(before.keys() - after.keys())
    return {
        "changed": changed,
        "added": added,
        "removed": removed,
        "mutation_count": len(changed) + len(added) + len(removed),
        "measured": True,
    }


def _write_json(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def package_manifest(version: str) -> dict[str, Any]:
    return {
        "id": PLUGIN_ID,
        "version": version,
        "hooks": ["pre-tool"],
        "migrations_declared_idempotent": True,
    }


def write_package(dest: Path, version: str) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    _write_json(dest / "manifest.json", package_manifest(version))
    (dest / "hooks").mkdir(exist_ok=True)
    (dest / "hooks" / "pre-tool.json").write_text(
        json.dumps({"event": "pre-tool", "version": version}, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    skill = dest / "skills" / "bundled" / "hello" / "SKILL.md"
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text(f"# bundled hello {version}\n", encoding="utf-8")
    return dest


def make_packages(root: Path) -> dict[str, Path]:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    return {
        N2: write_package(root / N2, N2),
        N1: write_package(root / N1, N1),
        N: write_package(root / N, N),
    }


def installed_version(profile: Path) -> str | None:
    man = ast_root(profile) / "plugin" / "manifest.json"
    if not man.is_file():
        return None
    return str(_read_json(man).get("version") or "")


def ledger_path(profile: Path) -> Path:
    return ast_root(profile) / "migrations" / "ledger.json"


def load_ledger(profile: Path) -> dict[str, Any]:
    path = ledger_path(profile)
    if not path.is_file():
        return {"executions": {}, "applied": []}
    return _read_json(path)


def save_ledger(profile: Path, ledger: dict[str, Any]) -> None:
    _write_json(ledger_path(profile), ledger)


def execution_count(profile: Path, mig_id: str) -> int:
    return int(load_ledger(profile).get("executions", {}).get(mig_id, 0))


def settings_path(profile: Path) -> Path:
    return ast_root(profile) / "settings.json"


def load_settings(profile: Path) -> dict[str, Any]:
    path = settings_path(profile)
    if not path.is_file():
        return {}
    return _read_json(path)


def save_settings(profile: Path, doc: dict[str, Any]) -> None:
    _write_json(settings_path(profile), doc)


def user_skill_path(profile: Path) -> Path:
    return ast_root(profile) / USER_SKILL_REL


def rule_path(profile: Path) -> Path:
    return ast_root(profile) / "rules" / "team.md"


def inflight_path(profile: Path) -> Path:
    return ast_root(profile) / "ledger" / "in-flight.json"


def populate_user_state(profile: Path, *, from_version: str) -> dict[str, str]:
    settings = {
        "owner.canary": "keep-me",
        "editor.font": "Iosevka",
        "custom.nested": {"a": 1},
    }
    if from_version == N2:
        settings["old.color"] = "obsidian"
    else:
        settings["legacy.color"] = "obsidian"
    save_settings(profile, settings)
    skill = user_skill_path(profile)
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text(USER_SKILL_BODY, encoding="utf-8")
    rule = rule_path(profile)
    rule.parent.mkdir(parents=True, exist_ok=True)
    rule.write_text(RULE_BODY, encoding="utf-8")
    _write_json(
        inflight_path(profile),
        {"entries": [{"id": "job-7", "status": "running", "payload": {"n": 3}}]},
    )
    return {
        "skill_sha256": sha256_file(skill),
        "settings_sha256": sha256_file(settings_path(profile)),
        "rule_sha256": sha256_file(rule),
        "inflight_sha256": sha256_file(inflight_path(profile)),
    }


def _mig_settings_rename(profile: Path, dirty: bool) -> None:
    settings = load_settings(profile)
    if "old.color" in settings and "legacy.color" not in settings:
        settings["legacy.color"] = settings.pop("old.color")
        save_settings(profile, settings)
    elif dirty:
        settings["dirty.stamp"] = int(settings.get("dirty.stamp") or 0) + 1
        save_settings(profile, settings)


def _mig_settings_v3(profile: Path, dirty: bool) -> None:
    settings = load_settings(profile)
    if "legacy.color" in settings and "ui.color" not in settings:
        settings["ui.color"] = settings.pop("legacy.color")
        save_settings(profile, settings)
    elif dirty:
        settings["dirty.stamp"] = int(settings.get("dirty.stamp") or 0) + 1
        save_settings(profile, settings)


def _mig_ledger_schema(profile: Path, dirty: bool) -> None:
    path = inflight_path(profile)
    doc = _read_json(path) if path.is_file() else {"entries": []}
    if doc.get("schema_version") != 2:
        doc["schema_version"] = 2
        _write_json(path, doc)
    elif dirty:
        doc["dirty_stamp"] = int(doc.get("dirty_stamp") or 0) + 1
        _write_json(path, doc)


def _mig_rule_frontmatter(profile: Path, dirty: bool) -> None:
    path = rule_path(profile)
    text = path.read_text(encoding="utf-8") if path.is_file() else RULE_BODY
    if not text.startswith(FRONTMATTER):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(FRONTMATTER + text.lstrip(), encoding="utf-8")
    elif dirty:
        path.write_text(text + "# dirty-stamp\n", encoding="utf-8")


MIGRATIONS: list[dict[str, Any]] = [
    {
        "id": "m110-settings-rename",
        "from_version": N2,
        "to_version": N1,
        "declared_idempotent": True,
        "apply": _mig_settings_rename,
    },
    {
        "id": "m120-settings-v3",
        "from_version": N1,
        "to_version": N,
        "declared_idempotent": True,
        "apply": _mig_settings_v3,
    },
    {
        "id": "m121-ledger-schema",
        "from_version": N1,
        "to_version": N,
        "declared_idempotent": True,
        "apply": _mig_ledger_schema,
    },
    {
        "id": "m122-rule-frontmatter",
        "from_version": N1,
        "to_version": N,
        "declared_idempotent": True,
        "apply": _mig_rule_frontmatter,
    },
]


def hops_needed(src: str, dst: str) -> list[tuple[str, str]]:
    order = [N2, N1, N]
    if src not in order or dst not in order:
        raise UpgradeRefuse(f"unknown version hop {src}->{dst}")
    i, j = order.index(src), order.index(dst)
    if j <= i:
        return []
    return [(order[k], order[k + 1]) for k in range(i, j)]


def plan_migrations(
    src: str,
    dst: str,
    *,
    drop_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    drop_ids = drop_ids or set()
    available = [m for m in MIGRATIONS if m["id"] not in drop_ids]
    hops = hops_needed(src, dst)
    if not hops and src == dst:
        return [m for m in available if m["to_version"] == dst]
    planned: list[dict[str, Any]] = []
    for a, b in hops:
        hop = [m for m in available if m["from_version"] == a and m["to_version"] == b]
        if not hop:
            raise UpgradeRefuse(
                f"skip-version refuse: no migrations cover hop {a}->{b}; "
                "refusing rather than applying a partial chain"
            )
        planned.extend(hop)
    return planned


def _snapshot(profile: Path) -> Path:
    snap = Path(profile).resolve().parent / (Path(profile).name + ".snap")
    if snap.exists():
        shutil.rmtree(snap)
    shutil.copytree(profile, snap)
    return snap


def _restore(profile: Path, snap: Path) -> None:
    resolved = Path(profile).resolve()
    shutil.rmtree(resolved)
    shutil.copytree(snap, resolved)


def _copy_plugin(profile: Path, package_dir: Path) -> None:
    dest = ast_root(profile) / "plugin"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(package_dir, dest)


def chain_status(profile: Path, planned_ids: list[str], target: str) -> str:
    applied = set(load_ledger(profile).get("executions", {}))
    version = installed_version(profile)
    planned = set(planned_ids)
    if version == target and planned <= applied:
        return "complete"
    if applied and version != target:
        return "partial"
    if version == target and planned - applied:
        return "partial"
    if not applied:
        return "not-started"
    return "partial"


def install(profile: Path, package_dir: Path) -> dict[str, Any]:
    iso = assert_isolated(profile)
    man = _read_json(Path(package_dir) / "manifest.json")
    _copy_plugin(profile, Path(package_dir))
    if not ledger_path(profile).is_file():
        save_ledger(profile, {"executions": {}, "applied": []})
    return {
        "command": "install",
        "version": man["version"],
        "isolation": iso,
        "profile": str(Path(profile).resolve()),
    }


def _run_chain(
    profile: Path,
    planned: list[dict[str, Any]],
    *,
    dirty_id: str | None,
) -> tuple[dict[str, Any], bool]:
    ledger = load_ledger(profile)
    executions = dict(ledger.get("executions") or {})
    applied = list(ledger.get("applied") or [])
    changed = False
    for mig in planned:
        mid = str(mig["id"])
        already = mid in executions
        dirty = dirty_id is not None and mid == dirty_id
        if already and not dirty:
            mig["apply"](profile, False)
            continue
        mig["apply"](profile, dirty)
        executions[mid] = int(executions.get(mid, 0)) + 1
        if mid not in applied:
            applied.append(mid)
        changed = True
    new_ledger = {"executions": executions, "applied": applied}
    if changed:
        save_ledger(profile, new_ledger)
    return new_ledger, changed


def upgrade(
    profile: Path,
    package_dir: Path,
    *,
    drop_ids: set[str] | None = None,
    dirty_id: str | None = None,
) -> dict[str, Any]:
    iso = assert_isolated(profile)
    src = installed_version(profile)
    dst = str(_read_json(Path(package_dir) / "manifest.json")["version"])
    if src is None:
        raise UpgradeRefuse("nothing installed")
    before = tree_hashes(ast_root(profile))
    skill_p = user_skill_path(profile)
    skill_before = sha256_file(skill_p) if skill_p.is_file() else None
    try:
        planned = plan_migrations(src, dst, drop_ids=drop_ids)
    except UpgradeRefuse as exc:
        after = tree_hashes(ast_root(profile))
        return {
            "command": "update",
            "outcome": "refused",
            "reason": exc.reason,
            "from_version": src,
            "to_version": dst,
            "partial_apply": False,
            "mutations": mutations(before, after),
            "isolation": iso,
            "planned": [],
            "ledger": load_ledger(profile),
            "user_skill_sha256_before": skill_before,
            "user_skill_sha256_after": skill_before,
        }

    planned_ids = [m["id"] for m in planned]
    snap = _snapshot(profile)
    try:
        _copy_plugin(profile, Path(package_dir))
        ledger, _ = _run_chain(profile, planned, dirty_id=dirty_id)
        status = chain_status(profile, planned_ids, dst)
        if status == "partial":
            raise UpgradeRefuse("partial chain detected after apply")
    except Exception:
        _restore(profile, snap)
        shutil.rmtree(snap, ignore_errors=True)
        raise UpgradeRefuse("upgrade rolled back to snapshot", restored=True) from None
    shutil.rmtree(snap, ignore_errors=True)

    after = tree_hashes(ast_root(profile))
    skill_after = sha256_file(skill_p) if skill_p.is_file() else None
    mut = mutations(before, after)
    undeclared = [rel for rel in mut["changed"] if rel == USER_SKILL_REL]
    outcome = "noop" if mut["mutation_count"] == 0 and src == dst else "completed"
    return {
        "command": "update",
        "outcome": outcome,
        "from_version": src,
        "to_version": installed_version(profile),
        "partial_apply": False,
        "chain_status": chain_status(profile, planned_ids, dst),
        "mutations": mut,
        "isolation": iso,
        "planned": planned_ids,
        "ledger": load_ledger(profile),
        "user_skill_sha256_before": skill_before,
        "user_skill_sha256_after": skill_after,
        "undeclared_user_mutations": undeclared,
        "owner_canary": load_settings(profile).get("owner.canary"),
    }


def apply_partial_unsafe(
    profile: Path, package_dir: Path, stop_after: int = 1
) -> dict[str, Any]:
    """Known-broken helper: bump version then apply only the first K migrations."""
    src = installed_version(profile)
    dst = str(_read_json(Path(package_dir) / "manifest.json")["version"])
    planned = plan_migrations(src, dst)
    _copy_plugin(profile, Path(package_dir))
    _run_chain(profile, planned[:stop_after], dirty_id=None)
    status = chain_status(profile, [m["id"] for m in planned], dst)
    return {
        "outcome": "partial",
        "chain_status": status,
        "partial_apply": status == "partial",
        "from_version": src,
        "to_version": installed_version(profile),
        "applied": load_ledger(profile).get("applied"),
        "planned": [m["id"] for m in planned],
    }


def repair(profile: Path, package_dir: Path) -> dict[str, Any]:
    return upgrade(profile, package_dir)


def rollback(profile: Path, package_dir: Path) -> dict[str, Any]:
    iso = assert_isolated(profile)
    before = tree_hashes(ast_root(profile))
    skill_p = user_skill_path(profile)
    skill_before = sha256_file(skill_p) if skill_p.is_file() else None
    _copy_plugin(profile, Path(package_dir))
    after = tree_hashes(ast_root(profile))
    return {
        "command": "rollback",
        "version": installed_version(profile),
        "isolation": iso,
        "mutations": mutations(before, after),
        "user_skill_sha256_before": skill_before,
        "user_skill_sha256_after": sha256_file(skill_p) if skill_p.is_file() else None,
    }


def uninstall(profile: Path) -> dict[str, Any]:
    iso = assert_isolated(profile)
    plugin = ast_root(profile) / "plugin"
    if plugin.exists():
        shutil.rmtree(plugin)
    return {"command": "uninstall", "isolation": iso, "plugin_present": plugin.exists()}


def double_run_check_fires(second: dict[str, Any]) -> bool:
    return int(second.get("mutations", {}).get("mutation_count") or 0) > 0


def command_lines() -> dict[str, str]:
    engine = "command-center/p2-wave/probes/REL-0005/upgrade.py"
    return {
        "install": f"python3 -B {engine} install --profile $CANARY_HOME --package $PKG_N1",
        "update": f"python3 -B {engine} update --profile $CANARY_HOME --package $PKG_N",
        "repair": f"python3 -B {engine} repair --profile $CANARY_HOME --package $PKG_N",
        "rollback": f"python3 -B {engine} rollback --profile $CANARY_HOME --package $PKG_N1",
        "uninstall": f"python3 -B {engine} uninstall --profile $CANARY_HOME",
    }


def _cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command", choices=["install", "update", "repair", "rollback", "uninstall"]
    )
    parser.add_argument("--profile", required=True)
    parser.add_argument("--package")
    args = parser.parse_args(argv)
    profile = Path(args.profile)
    pkg = Path(args.package) if args.package else None
    if args.command == "install":
        print(json.dumps(install(profile, pkg), indent=2, default=str))
    elif args.command == "update":
        print(json.dumps(upgrade(profile, pkg), indent=2, default=str))
    elif args.command == "repair":
        print(json.dumps(repair(profile, pkg), indent=2, default=str))
    elif args.command == "rollback":
        print(json.dumps(rollback(profile, pkg), indent=2, default=str))
    else:
        print(json.dumps(uninstall(profile), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli(sys.argv[1:]))
