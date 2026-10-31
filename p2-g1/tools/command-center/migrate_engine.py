"""Versioned schema/launcher migration engine with a freeze marker.

Spec line 10660: once the first implementation wave starts, launchers and
schemas are frozen; any change requires a numbered migration with an
executable down-step. An in-place edit of a frozen path is refused.

This module is the live engine IMP-0477's probes drive. It never writes
outside the supplied workspace root.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

MARKER_NAME = ".schema-freeze.json"
REFUSE_INPLACE = "post-freeze-inplace-edit"
REFUSE_NO_DOWN = "irreversible-migration"
ROUNDTRIP_FAIL = "roundtrip-bytes-diverge"
FROZEN = "FROZEN"
ACCEPTED = "ACCEPTED"
ROUNDTRIP_OK = "ROUNDTRIP_OK"
WRITTEN = "WRITTEN"
LOADED = "LOADED"
PATH_ESCAPE = "path-escape"
MISSING_TARGET = "missing-frozen-target"
MISSING_MANIFEST = "missing-migration-manifest"
UP_FAIL = "up-step-failed"
DOWN_FAIL = "down-step-failed"
STEP_MISSING = "migration-step-missing"

INPLACE_DETAIL = (
    "in-place edit of a frozen schema/launcher is refused; submit a numbered "
    "migration with an executable down-step"
)
INPLACE_FIX = "numbered-migration-with-down-step"
NO_DOWN_DETAIL = (
    "migration has no executable down-step and is refused as irreversible"
)
NO_DOWN_FIX = "add-nonempty-down-step"
ROUNDTRIP_DETAIL = "down-step did not restore original corpus bytes"
ROUNDTRIP_OK_DETAIL = "up then down restored original corpus bytes"

CORPUS_DIRS = ("schemas", "launchers")


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def _ok(**kwargs: Any) -> dict[str, Any]:
    out = {"ok": True}
    out.update(kwargs)
    return out


def _err(code: str, detail: str, **kwargs: Any) -> dict[str, Any]:
    out = {"ok": False, "code": code, "detail": detail}
    out.update(kwargs)
    return out


def _as_root(root: Path | str) -> Path:
    return Path(root).resolve()


def resolve_rel(root: Path, rel: str) -> Path | dict[str, Any]:
    """Map a relative path into root. Refuse absolute paths and escapes."""
    root = _as_root(root)
    if not isinstance(rel, str) or not rel.strip():
        return _err(PATH_ESCAPE, "relative path is empty", path=rel)
    candidate = Path(rel)
    if candidate.is_absolute() or ".." in candidate.parts:
        return _err(
            PATH_ESCAPE,
            "path must be relative to the workspace root and may not climb",
            path=rel,
        )
    dest = (root / candidate).resolve()
    if dest != root and root not in dest.parents:
        return _err(PATH_ESCAPE, "resolved path escapes the workspace root", path=rel)
    return dest


def load_marker(root: Path | str) -> dict[str, Any] | None:
    path = _as_root(root) / MARKER_NAME
    if not path.is_file():
        return None
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return doc if isinstance(doc, dict) else None


def _write_marker(root: Path, marker: dict[str, Any]) -> None:
    path = root / MARKER_NAME
    path.write_text(
        json.dumps(marker, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def freeze(
    root: Path | str,
    frozen_rels: list[str] | tuple[str, ...],
    schema_version: int = 1,
) -> dict[str, Any]:
    """Record sha256 of each frozen path and set the freeze marker."""
    root = _as_root(root)
    paths: dict[str, Any] = {}
    for rel in frozen_rels:
        dest = resolve_rel(root, rel)
        if isinstance(dest, dict):
            return dest
        if not dest.is_file():
            return _err(
                MISSING_TARGET,
                f"cannot freeze missing path {rel}",
                path=rel,
            )
        sha, size = digest_file(dest)
        paths[rel.replace("\\", "/")] = {"sha256": sha, "bytes": size}
    marker = {
        "frozen": True,
        "schema_version": int(schema_version),
        "paths": paths,
    }
    _write_marker(root, marker)
    return _ok(code=FROZEN, schema_version=int(schema_version), paths=paths)


def write_bytes(root: Path | str, rel: str, data: bytes) -> dict[str, Any]:
    """Write `data` at `rel` unless the path is frozen and the bytes change."""
    root = _as_root(root)
    dest = resolve_rel(root, rel)
    if isinstance(dest, dict):
        return dest
    rel_n = rel.replace("\\", "/")
    if not isinstance(data, (bytes, bytearray)):
        data = bytes(data)
    marker = load_marker(root)
    frozen_paths = (marker or {}).get("paths") or {}
    if (marker or {}).get("frozen") and rel_n in frozen_paths:
        current = dest.read_bytes() if dest.is_file() else b""
        if bytes(data) != current:
            return _err(
                REFUSE_INPLACE,
                INPLACE_DETAIL,
                required_fix=INPLACE_FIX,
                path=rel_n,
            )
        return _ok(code=WRITTEN, path=rel_n, noop=True)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(bytes(data))
    return _ok(code=WRITTEN, path=rel_n, noop=False)


def snapshot_corpus(root: Path | str) -> dict[str, str]:
    """Hash files under schemas/ and launchers/. Ignores the freeze marker."""
    root = _as_root(root)
    snap: dict[str, str] = {}
    for dirname in CORPUS_DIRS:
        base = root / dirname
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            sha, _ = digest_file(path)
            snap[rel] = sha
    return snap


def _read_manifest(mig: Path) -> dict[str, Any] | dict[str, Any]:
    man_path = Path(mig) / "MANIFEST.json"
    if not man_path.is_file():
        return _err(
            MISSING_MANIFEST,
            "migration directory has no MANIFEST.json",
            migration_dir=str(mig),
        )
    try:
        doc = json.loads(man_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return _err(
            MISSING_MANIFEST,
            f"MANIFEST.json unparseable: {type(exc).__name__}",
            migration_dir=str(mig),
        )
    if not isinstance(doc, dict):
        return _err(
            MISSING_MANIFEST,
            "MANIFEST.json is not an object",
            migration_dir=str(mig),
        )
    return doc


def _down_executable(mig: Path, manifest: dict[str, Any]) -> tuple[bool, Path | None]:
    down_name = manifest.get("down")
    if not isinstance(down_name, str) or not down_name.strip():
        return False, None
    dest = resolve_rel(mig, down_name.strip())
    if isinstance(dest, dict):
        return False, None
    if not dest.is_file() or dest.stat().st_size <= 0:
        return False, dest
    return True, dest


def load_migration(mig: Path | str) -> dict[str, Any]:
    """Accept a numbered migration only when a non-empty down-step is present."""
    mig = Path(mig)
    manifest = _read_manifest(mig)
    if manifest.get("ok") is False:
        return manifest
    ok_down, down_path = _down_executable(mig, manifest)
    if not ok_down:
        return _err(
            REFUSE_NO_DOWN,
            NO_DOWN_DETAIL,
            required_fix=NO_DOWN_FIX,
            down_present=False,
            migration_id=manifest.get("id"),
            migration_dir=str(mig),
        )
    up_name = manifest.get("up")
    if not isinstance(up_name, str) or not up_name.strip():
        return _err(
            STEP_MISSING,
            "migration has no up-step",
            required_fix="add-up-step",
            migration_id=manifest.get("id"),
        )
    up_dest = resolve_rel(mig, up_name.strip())
    if isinstance(up_dest, dict) or not up_dest.is_file() or up_dest.stat().st_size <= 0:
        return _err(
            STEP_MISSING,
            "migration up-step is missing or empty",
            required_fix="add-nonempty-up-step",
            migration_id=manifest.get("id"),
        )
    return _ok(
        code=LOADED,
        manifest=manifest,
        migration_id=manifest.get("id"),
        up=str(up_dest),
        down=str(down_path),
        down_present=True,
    )


def _run_step(script: Path, root: Path) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        proc = subprocess.run(
            [sys.executable, "-B", str(script), "--root", str(root)],
            cwd=str(root),
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        return _err("TIMEOUT", f"{script.name} exceeded 60s")
    tail = ((proc.stdout or "") + (proc.stderr or "")).strip()[-2000:]
    if proc.returncode != 0:
        return _err(
            "STEP_FAIL",
            f"{script.name} exited {proc.returncode}",
            rc=proc.returncode,
            output_tail=tail,
        )
    return _ok(code="OK", rc=0, output_tail=tail)


def _targets(manifest: dict[str, Any], root: Path) -> list[str]:
    raw = manifest.get("targets")
    if isinstance(raw, list) and raw:
        out = []
        for item in raw:
            if isinstance(item, str) and item.strip():
                out.append(item.replace("\\", "/"))
        if out:
            return out
    marker = load_marker(root) or {}
    paths = marker.get("paths") or {}
    if isinstance(paths, dict) and paths:
        return sorted(str(k).replace("\\", "/") for k in paths)
    return sorted(snapshot_corpus(root))


def _hash_targets(root: Path, targets: list[str]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for rel in targets:
        dest = resolve_rel(root, rel)
        if isinstance(dest, dict) or not dest.is_file():
            out[rel] = {"sha256": "", "bytes": 0, "missing": True}
            continue
        sha, size = digest_file(dest)
        out[rel] = {"sha256": sha, "bytes": size, "missing": False}
    return out


def round_trip(root: Path | str, mig: Path | str) -> dict[str, Any]:
    """Run up then down. Succeeds only when original corpus bytes return."""
    root = _as_root(root)
    mig = Path(mig)
    loaded = load_migration(mig)
    if not loaded.get("ok"):
        return loaded
    manifest = loaded["manifest"]
    targets = _targets(manifest, root)
    before = _hash_targets(root, targets)
    original_sha256 = {rel: rec["sha256"] for rel, rec in before.items()}

    up = _run_step(Path(loaded["up"]), root)
    if not up.get("ok"):
        return _err(UP_FAIL, up.get("detail") or "up-step failed", up=up)

    after_up = _hash_targets(root, targets)
    up_changed = [
        {
            "path": rel,
            "before_bytes": before[rel]["bytes"],
            "before_sha256": before[rel]["sha256"],
            "after_bytes": after_up[rel]["bytes"],
            "after_sha256": after_up[rel]["sha256"],
        }
        for rel in sorted(targets)
    ]

    down = _run_step(Path(loaded["down"]), root)
    restored = _hash_targets(root, targets)
    restored_sha256 = {rel: rec["sha256"] for rel, rec in restored.items()}
    identical = (
        bool(down.get("ok"))
        and original_sha256 == restored_sha256
        and all(not before[rel].get("missing") for rel in targets)
    )
    common = {
        "up": up,
        "down": down,
        "original_sha256": original_sha256,
        "restored_sha256": restored_sha256,
        "files_compared": len(targets),
        "up_changed": up_changed,
        "migration_id": manifest.get("id"),
    }
    if not identical:
        # A crashing down-step is still a round-trip failure: original bytes
        # were not restored. Probe1's no-op control keys on this code.
        return _err(ROUNDTRIP_FAIL, ROUNDTRIP_DETAIL, **common)
    return _ok(code=ROUNDTRIP_OK, detail=ROUNDTRIP_OK_DETAIL, **common)


def apply_accepted(root: Path | str, mig: Path | str) -> dict[str, Any]:
    """Apply a reversible numbered migration and refresh freeze hashes."""
    root = _as_root(root)
    mig = Path(mig)
    loaded = load_migration(mig)
    if not loaded.get("ok"):
        return loaded
    manifest = loaded["manifest"]
    up = _run_step(Path(loaded["up"]), root)
    if not up.get("ok"):
        return _err(UP_FAIL, up.get("detail") or "up-step failed", up=up)

    marker = load_marker(root) or {"frozen": True, "paths": {}}
    if not isinstance(marker.get("paths"), dict):
        marker["paths"] = {}
    targets = _targets(manifest, root)
    for rel in targets:
        dest = resolve_rel(root, rel)
        if isinstance(dest, dict) or not dest.is_file():
            continue
        sha, size = digest_file(dest)
        marker["paths"][rel] = {"sha256": sha, "bytes": size}
    to_version = manifest.get("to_version")
    try:
        marker["schema_version"] = int(to_version)
    except (TypeError, ValueError):
        marker["schema_version"] = int(marker.get("schema_version") or 1) + 1
    marker["frozen"] = True
    marker["last_migration"] = manifest.get("id")
    _write_marker(root, marker)
    return _ok(
        code=ACCEPTED,
        migration_id=manifest.get("id"),
        schema_version=marker["schema_version"],
        up=up,
    )


def _cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Freeze schemas/launchers; refuse in-place edits; apply numbered migrations."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_freeze = sub.add_parser("freeze", help="set the freeze marker")
    p_freeze.add_argument("--root", required=True)
    p_freeze.add_argument("--path", action="append", dest="paths", required=True)
    p_freeze.add_argument("--schema-version", type=int, default=1)

    p_write = sub.add_parser("write", help="write bytes through the freeze gate")
    p_write.add_argument("--root", required=True)
    p_write.add_argument("--path", required=True)
    p_write.add_argument("--file", required=True, help="local file whose bytes to write")

    p_rt = sub.add_parser("round-trip", help="run up then down and compare bytes")
    p_rt.add_argument("--root", required=True)
    p_rt.add_argument("--migration", required=True)

    p_apply = sub.add_parser("apply", help="apply an accepted reversible migration")
    p_apply.add_argument("--root", required=True)
    p_apply.add_argument("--migration", required=True)

    p_load = sub.add_parser("load", help="validate a migration directory")
    p_load.add_argument("--migration", required=True)

    args = parser.parse_args(argv)
    if args.cmd == "freeze":
        rec = freeze(args.root, args.paths, schema_version=args.schema_version)
    elif args.cmd == "write":
        data = Path(args.file).read_bytes()
        rec = write_bytes(args.root, args.path, data)
    elif args.cmd == "round-trip":
        rec = round_trip(args.root, args.migration)
    elif args.cmd == "apply":
        rec = apply_accepted(args.root, args.migration)
    else:
        rec = load_migration(args.migration)
    print(json.dumps(rec, indent=2, sort_keys=True, default=str))
    return 0 if rec.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(_cli())
