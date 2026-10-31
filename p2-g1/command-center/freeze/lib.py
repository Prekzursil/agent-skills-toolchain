"""CC-0012 freeze ledger, gate, and versioned migrations."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

LEDGER_REL = "command-center/freeze/FREEZE.json"
RULES_REL = "command-center/freeze/bump_rules.json"
LAUNCHER_VER_REL = "command-center/freeze/launcher-versions.json"
FIXTURE_REL = "command-center/freeze/fixtures/prefreeze_catalog_slice.json"
MIGRATIONS_REL = "command-center/freeze/migrations"
SNAPSHOTS_REL = "command-center/freeze/snapshots"
PROOF_REL = "command-center/freeze/proof"

FROZEN_DEFAULTS: tuple[tuple[str, str], ...] = (
    ("command-center/schema/receipt.schema.json", "schema"),
    ("command-center/schema/test-plan.schema.json", "schema"),
    ("command-center/freeze/launcher-versions.json", "launcher"),
)


def snapshot_rel(rel: str) -> str:
    safe = rel.replace("\\", "/").replace("/", "__")
    return f"{SNAPSHOTS_REL}/{safe}.snap"


def dumps_canon(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def loads_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: Path, obj: Any) -> None:
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(dumps_canon(obj), encoding="utf-8")


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def _git(repo: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


@dataclass
class Migration:
    id: str
    from_version: int
    to_version: int
    targets: list[str]
    up: Callable[[Any], Any]
    down: Callable[[Any], Any]
    path: str


def load_migrations(repo: Path) -> list[Migration]:
    root = Path(repo) / MIGRATIONS_REL
    out: list[Migration] = []
    if not root.is_dir():
        return out
    for path in sorted(root.glob("m*.py")):
        spec = importlib.util.spec_from_file_location(path.stem, path)
        if spec is None or spec.loader is None:
            continue
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        out.append(
            Migration(
                id=str(getattr(mod, "MIGRATION_ID", path.stem)),
                from_version=int(getattr(mod, "FROM_VERSION", 0)),
                to_version=int(getattr(mod, "TO_VERSION", 0)),
                targets=[str(t) for t in (getattr(mod, "TARGETS", None) or [])],
                up=mod.up,
                down=mod.down,
                path=path.relative_to(repo).as_posix(),
            )
        )
    return out


def apply_migration_to_file(
    mig: Migration, before: Path, after: Path, restored: Path
) -> dict[str, Any]:
    original = Path(before).read_bytes()
    doc = json.loads(original.decode("utf-8"))
    up_doc = mig.up(doc)
    after_text = dumps_canon(up_doc)
    Path(after).parent.mkdir(parents=True, exist_ok=True)
    Path(after).write_text(after_text, encoding="utf-8")
    down_doc = mig.down(json.loads(after_text))
    restored_text = dumps_canon(down_doc)
    Path(restored).parent.mkdir(parents=True, exist_ok=True)
    Path(restored).write_text(restored_text, encoding="utf-8")
    original_canon = dumps_canon(json.loads(original.decode("utf-8")))
    after_loaded = json.loads(after_text)
    return {
        "migration_id": mig.id,
        "up_changed": after_text != original_canon,
        "byte_identical": restored_text.encode("utf-8") == original_canon.encode("utf-8"),
        "after_schema_version": after_loaded.get("schema_version"),
        "after_sha256": _sha256_bytes(after_text.encode("utf-8")),
        "restored_sha256": _sha256_bytes(restored_text.encode("utf-8")),
        "before_sha256": _sha256_bytes(original_canon.encode("utf-8")),
    }


def _ensure_support_files(repo: Path) -> None:
    rules = Path(repo) / RULES_REL
    if not rules.is_file():
        write_json(
            rules,
            {
                "unit_id": "CC-0012",
                "rule": "frozen schema/launcher bytes require a version bump and a migration",
                "no_version_bump_reason": "no-version-bump",
            },
        )
    launcher = Path(repo) / LAUNCHER_VER_REL
    if not launcher.is_file():
        write_json(
            launcher,
            {
                "unit_id": "CC-0012",
                "launchers": {"command-center": {"version": 1, "frozen": True}},
            },
        )
    fixture = Path(repo) / FIXTURE_REL
    if not fixture.is_file():
        write_json(
            fixture,
            {
                "schema_version": 2,
                "id": "prefreeze-catalog-slice",
                "work_units": [{"id": "CC-0012", "title": "freeze schemas and launchers"}],
            },
        )


def activate(repo: Path) -> dict[str, Any]:
    repo = Path(repo)
    _ensure_support_files(repo)
    git_rev = _git(repo, ["rev-parse", "HEAD"])
    git_ok = git_rev.returncode == 0 and bool((git_rev.stdout or "").strip())
    commit = (git_rev.stdout or "").strip() if git_ok else None
    frozen_paths = []
    fingerprint = hashlib.sha256()
    for rel, kind in FROZEN_DEFAULTS:
        src = repo / rel
        if not src.is_file():
            continue
        raw = src.read_bytes()
        snap = repo / snapshot_rel(rel)
        snap.parent.mkdir(parents=True, exist_ok=True)
        snap.write_bytes(raw)
        digest = _sha256_bytes(raw)
        fingerprint.update(digest.encode("ascii"))
        frozen_paths.append(
            {
                "path": rel,
                "kind": kind,
                "sha256": digest,
                "bytes": len(raw.replace(b"\r\n", b"\n")),
                "snapshot": snapshot_rel(rel),
            }
        )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    catalog_ver = None
    fixture = repo / FIXTURE_REL
    if fixture.is_file():
        try:
            catalog_ver = loads_json(fixture).get("schema_version")
        except (OSError, json.JSONDecodeError):
            catalog_ver = None
    ledger = {
        "freeze_id": "CC-0012-freeze",
        "unit_id": "CC-0012",
        "activation_timestamp": now,
        "activation_commit": commit,
        "activation_commit_kind": "git-HEAD" if git_ok else "git-unavailable",
        "git": {"available": git_ok, "commit": commit},
        "freeze_fingerprint_sha256": fingerprint.hexdigest(),
        "catalog_schema_version_at_freeze": catalog_ver,
        "frozen_paths": frozen_paths,
        "frozen_count": len(frozen_paths),
        "schema_count": sum(1 for r in frozen_paths if r["kind"] == "schema"),
        "launcher_count": sum(1 for r in frozen_paths if r["kind"] == "launcher"),
        "ledger_path": LEDGER_REL,
        "bump_rules_path": RULES_REL,
    }
    write_json(repo / LEDGER_REL, ledger)
    return ledger


def _schema_version(doc: Any) -> int | None:
    if isinstance(doc, dict) and "schema_version" in doc:
        try:
            return int(doc["schema_version"])
        except (TypeError, ValueError):
            return None
    return None


def evaluate_gate(root: Path) -> dict[str, Any]:
    root = Path(root)
    ledger_path = root / LEDGER_REL
    if not ledger_path.is_file():
        return {"ok": False, "reason": "ledger-missing", "rejections": [], "silent_count": 0}
    ledger = loads_json(ledger_path)
    migrations = load_migrations(root)
    silent = 0
    rejections: list[dict[str, Any]] = []
    admitted: list[dict[str, Any]] = []
    for row in ledger.get("frozen_paths") or []:
        rel = str(row["path"])
        live = root / rel
        snap = root / snapshot_rel(rel)
        if not snap.is_file():
            snap = root / str(row.get("snapshot") or snapshot_rel(rel))
        if not live.is_file() or not snap.is_file():
            rejections.append({"path": rel, "reason": "missing-frozen-bytes"})
            continue
        live_raw = live.read_bytes().replace(b"\r\n", b"\n")
        snap_raw = snap.read_bytes().replace(b"\r\n", b"\n")
        if live_raw == snap_raw:
            silent += 1
            continue
        live_doc = None
        snap_doc = None
        try:
            live_doc = json.loads(live_raw.decode("utf-8"))
            snap_doc = json.loads(snap_raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass
        bumped = False
        if isinstance(live_doc, dict) and isinstance(snap_doc, dict):
            lv = _schema_version(live_doc)
            sv = _schema_version(snap_doc)
            if lv is not None and sv is not None and lv > sv:
                bumped = True
            elif lv is not None and sv is None:
                bumped = True
        matching = [
            m
            for m in migrations
            if rel in m.targets and (not bumped or m.to_version == _schema_version(live_doc) or True)
        ]
        if bumped and matching:
            admitted.append({"path": rel, "reason": "version-bump-with-migration", "migration": matching[0].id})
            continue
        rejections.append({"path": rel, "reason": "no-version-bump"})
    ok = not rejections
    return {
        "ok": ok,
        "reason": "silent" if ok else "rejected",
        "silent_count": silent,
        "rejection_count": len(rejections),
        "rejections": rejections,
        "admitted": admitted,
    }
