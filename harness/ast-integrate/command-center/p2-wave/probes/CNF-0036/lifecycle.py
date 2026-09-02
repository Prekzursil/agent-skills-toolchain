"""Mutating operations against a disposable snapshot.

Forward: install, deploy, migrate, sync, repair.
Reverse: uninstall, undeploy, unmigrate, unsync, unrepair.

Second apply is a no-op that reports already-applied. Journals never carry
wall-clock timestamps, so a true no-op stays byte-identical.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from scenario import USER_NOTES


def _write_json(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _iter_files(root: Path):
    for path in sorted(root.rglob("*")):
        if path.is_file():
            yield path


def _mirror_package(pkg: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for src in _iter_files(pkg):
        rel = src.relative_to(pkg)
        out = dest / rel
        data = src.read_bytes()
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.is_file() and out.read_bytes() == data:
            continue
        out.write_bytes(data)


def _package_matches(pkg: Path, dest: Path) -> bool:
    if not dest.is_dir():
        return False
    for src in _iter_files(pkg):
        out = dest / src.relative_to(pkg)
        if not out.is_file() or out.read_bytes() != src.read_bytes():
            return False
    return True


def create_if_missing(path: Path, content: bytes) -> dict:
    if path.exists():
        return {"exit_code": 0, "message": "already-applied", "wrote": False}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return {"exit_code": 0, "message": "applied", "wrote": True}


def force_create_truncate(path: Path, content: bytes) -> dict:
    """Analogue of Windows New-Item -Force: open-for-write truncates first."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        handle.write(content)
    return {"exit_code": 0, "message": "applied", "wrote": True}


def non_idempotent_append(path: Path) -> tuple[int, str]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab") as handle:
        handle.write(b"tick\n")
    return 0, "applied"


def do_install(root: Path) -> tuple[int, str]:
    dest = root / "target" / "installed"
    marker = dest / ".install-marker.json"
    payload = {"status": "installed", "version": "1"}
    pkg = root / "package"
    if marker.is_file() and _read_json(marker) == payload and _package_matches(pkg, dest):
        return 0, "already-applied"
    _mirror_package(pkg, dest)
    _write_json(marker, payload)
    return 0, "applied"


def do_uninstall(root: Path) -> tuple[int, str]:
    dest = root / "target" / "installed"
    if not dest.exists():
        return 0, "already-applied"
    shutil.rmtree(dest)
    return 0, "applied"


def do_deploy(root: Path) -> tuple[int, str]:
    live = root / "target" / "live"
    prov_path = live / ".provenance.json"
    pkg = root / "package"
    planned: list[tuple[Path, str, bytes]] = []
    all_same = True
    for src in _iter_files(pkg):
        rel = src.relative_to(pkg).as_posix()
        dest = live / rel
        data = src.read_bytes()
        planned.append((dest, rel, data))
        if not dest.is_file() or dest.read_bytes() != data:
            all_same = False
    if prov_path.is_file() and all_same:
        return 0, "already-applied"
    live.mkdir(parents=True, exist_ok=True)
    written = []
    for dest, rel, data in planned:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        written.append(rel)
    _write_json(prov_path, {"files": written, "version": "1"})
    return 0, "applied"


def do_undeploy(root: Path) -> tuple[int, str]:
    live = root / "target" / "live"
    prov_path = live / ".provenance.json"
    if not prov_path.is_file():
        return 0, "already-applied"
    listed = _read_json(prov_path).get("files") or []
    for rel in listed:
        path = live / str(rel)
        if path.is_file():
            path.unlink()
            parent = path.parent
            while parent != live and parent.is_dir() and not any(parent.iterdir()):
                parent.rmdir()
                parent = parent.parent
    prov_path.unlink()
    return 0, "applied"


def do_migrate(root: Path) -> tuple[int, str]:
    version_path = root / "target" / ".layout-version"
    current = root / "target" / "current"
    legacy = root / "target" / "legacy"
    if version_path.is_file() and version_path.read_text(encoding="utf-8").strip() == "v2":
        return 0, "already-applied"
    current.mkdir(parents=True, exist_ok=True)
    if legacy.exists():
        for src in _iter_files(legacy):
            dest = current / src.relative_to(legacy)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(src.read_bytes())
        shutil.rmtree(legacy)
    version_path.write_text("v2\n", encoding="utf-8", newline="\n")
    return 0, "applied"


def do_unmigrate(root: Path) -> tuple[int, str]:
    version_path = root / "target" / ".layout-version"
    current = root / "target" / "current"
    legacy = root / "target" / "legacy"
    version = (
        version_path.read_text(encoding="utf-8").strip()
        if version_path.is_file()
        else "v1"
    )
    if version == "v1" and not current.exists():
        return 0, "already-applied"
    legacy.mkdir(parents=True, exist_ok=True)
    if current.exists():
        for src in _iter_files(current):
            dest = legacy / src.relative_to(current)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(src.read_bytes())
        shutil.rmtree(current)
    version_path.write_text("v1\n", encoding="utf-8", newline="\n")
    return 0, "applied"


def do_sync(root: Path) -> tuple[int, str]:
    pkg = root / "package"
    live = root / "target" / "live"
    journal_path = live / ".sync-journal.json"
    live.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    for src in _iter_files(pkg):
        rel = src.relative_to(pkg).as_posix()
        dest = live / rel
        result = create_if_missing(dest, src.read_bytes())
        if result["wrote"]:
            created.append(rel)
    if not created and journal_path.is_file():
        return 0, "already-applied"
    prev = []
    if journal_path.is_file():
        prev = list(_read_json(journal_path).get("created") or [])
    merged = sorted(set(prev) | set(created))
    if journal_path.is_file() and merged == prev and not created:
        return 0, "already-applied"
    _write_json(journal_path, {"created": merged})
    return 0, "applied"


def do_unsync(root: Path) -> tuple[int, str]:
    live = root / "target" / "live"
    journal_path = live / ".sync-journal.json"
    if not journal_path.is_file():
        return 0, "already-applied"
    created = list(_read_json(journal_path).get("created") or [])
    for rel in created:
        path = live / str(rel)
        if path.is_file():
            path.unlink()
    journal_path.unlink()
    return 0, "applied"


def _classify(pkg_bytes: bytes, dest_bytes: bytes | None) -> str:
    if dest_bytes is None:
        return "REPO-AHEAD"
    if dest_bytes == pkg_bytes:
        return "IDENTICAL"
    dest_lines = set(dest_bytes.splitlines())
    pkg_lines = set(pkg_bytes.splitlines())
    dest_only = dest_lines - pkg_lines
    pkg_only = pkg_lines - dest_lines
    if dest_only and pkg_only:
        return "DIVERGED"
    if pkg_only:
        return "REPO-AHEAD"
    if dest_only:
        return "LIVE-AHEAD"
    return "IDENTICAL"


def do_repair(root: Path) -> tuple[int, str]:
    live = root / "target" / "live"
    src = root / "package" / "skills" / "hello.md"
    dest = live / "hello.md"
    journal_path = live / ".repair-journal.json"
    diverged = live / "user-edit.md"
    if not diverged.is_file():
        return 2, "detector-failure: diverged fixture missing"
    pkg_bytes = src.read_bytes()
    dest_bytes = dest.read_bytes() if dest.is_file() else None
    cls = _classify(pkg_bytes, dest_bytes)
    if cls == "DIVERGED":
        return 2, "refused-diverged"
    if cls != "REPO-AHEAD":
        return 0, "already-applied"
    live.mkdir(parents=True, exist_ok=True)
    _write_json(
        journal_path,
        {
            "backups": [
                {
                    "path": "hello.md",
                    "previous": None if dest_bytes is None else dest_bytes.hex(),
                }
            ]
        },
    )
    dest.write_bytes(pkg_bytes)
    return 0, "applied"


def do_unrepair(root: Path) -> tuple[int, str]:
    live = root / "target" / "live"
    journal_path = live / ".repair-journal.json"
    if not journal_path.is_file():
        return 0, "already-applied"
    for item in _read_json(journal_path).get("backups") or []:
        path = live / str(item.get("path") or "")
        previous = item.get("previous")
        if previous is None:
            if path.is_file():
                path.unlink()
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(bytes.fromhex(previous))
    journal_path.unlink()
    return 0, "applied"


FUNCS = {
    "install": do_install,
    "uninstall": do_uninstall,
    "deploy": do_deploy,
    "undeploy": do_undeploy,
    "migrate": do_migrate,
    "unmigrate": do_unmigrate,
    "sync": do_sync,
    "unsync": do_unsync,
    "repair": do_repair,
    "unrepair": do_unrepair,
}

PAIRS = (
    ("install", "uninstall"),
    ("deploy", "undeploy"),
    ("migrate", "unmigrate"),
    ("sync", "unsync"),
    ("repair", "unrepair"),
)


def apply_named(root: Path, name: str) -> tuple[int, str]:
    fn = FUNCS.get(name)
    if fn is None:
        return 2, f"unknown-operation:{name}"
    notes = root / USER_NOTES
    before = notes.read_bytes() if notes.is_file() else None
    code, message = fn(root)
    after = notes.read_bytes() if notes.is_file() else None
    if before is not None and after != before:
        return 3, f"data-loss:{name}: truncated {USER_NOTES}"
    return code, message
