"""Run every walker, hasher and installer that exists on this worktree."""
from __future__ import annotations

import hashlib
import importlib.util
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any

from fixture import build_hostile_tree, build_manifest_repo
from winpath import (
    is_reserved_component,
    naive_nt_relpath,
    prefix_invocation_count,
    reset_prefix_counter,
    safe_nt_relpath,
    to_extended_length,
    windows_join,
)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
WIN_ROOT = r"C:\cnf0103-fixture"
DEVICE_NUL = r"\\.\NUL"


def _row(
    *,
    id: str,
    kind: str,
    outcome: str,
    fixture_path: str,
    file_count: int | None,
    error: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": id,
        "kind": kind,
        "outcome": outcome,
        "fixture_path": fixture_path,
        "file_count": file_count,
        "error": error,
    }
    if extra:
        out.update(extra)
    return out


def classify_count(count: int, known: int) -> str:
    if count == 0 and known > 0:
        return "silent-zero"
    if count == known:
        return "ok"
    return "explicit-error"


def walk_os_walk(root: Path) -> list[str]:
    found: list[str] = []
    for dirpath, _dirs, filenames in os.walk(root):
        for name in filenames:
            full = Path(dirpath) / name
            found.append(full.relative_to(root).as_posix())
    return sorted(found)


def walk_rglob(root: Path) -> list[str]:
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())


def hash_tree(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for rel in walk_rglob(root):
        raw = (root / rel).read_bytes().replace(b"\r\n", b"\n")
        out[rel] = hashlib.sha256(raw).hexdigest()
    return out


def copytree_install(src: Path, dest: Path) -> list[str]:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)
    return walk_rglob(dest)


def swallowed_zero_walk(root: Path) -> list[str]:
    """Known-broken walker: any reserved name becomes a swallowed empty result."""
    try:
        found: list[str] = []
        for dirpath, _dirs, filenames in os.walk(root):
            for name in filenames:
                if is_reserved_component(name):
                    raise ValueError("path is on mount '\\\\.\\NUL'")
                full = Path(dirpath) / name
                found.append(full.relative_to(root).as_posix())
        return found
    except Exception:
        return []


def honest_walk(root: Path) -> list[str]:
    return walk_os_walk(root)


def _load_mod(rel: str, name: str):
    path = REPO / rel
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise FileNotFoundError(str(path))
    # Match the package's direct-run shim so sibling imports resolve.
    parent = str(path.parent)
    if parent not in sys.path:
        sys.path.insert(0, parent)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_unit_manifest():
    return _load_mod("tools/command-center/unit_manifest.py", "cnf0103_unit_manifest")


def load_path_guard():
    return _load_mod("tools/command-center/path_guard.py", "cnf0103_path_guard")


def walk_contained_rglob(root: Path) -> list[str]:
    pg = load_path_guard()
    found = []
    for child in pg.contained_rglob(root, "*"):
        if child.is_file():
            found.append(child.relative_to(root).as_posix())
    return sorted(found)


def run_unit_manifest(fake_repo: Path) -> dict[str, Any]:
    path = REPO / "tools/command-center/unit_manifest.py"
    if not path.is_file():
        return {
            "ok": False,
            "error": "ABSENT: tools/command-center/unit_manifest.py",
            "rows": 0,
        }
    try:
        mod = load_unit_manifest()
        doc = mod.derive(fake_repo)
        rows = doc.get("artifacts") or []
        return {
            "ok": True,
            "error": None,
            "rows": len(rows),
            "present": doc.get("present"),
            "expected": doc.get("expected"),
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "rows": 0,
        }


def plugin_installer_status() -> dict[str, Any]:
    plugin = REPO / "tools/plugin"
    if not plugin.is_dir():
        return {
            "present": False,
            "error": "ABSENT: tools/plugin directory",
        }
    surface = plugin / "command_surface.py"
    names = []
    for p in (plugin / "__init__.py", surface, plugin / "cli.py"):
        if p.is_file():
            names.append(p.name)
            text = p.read_text(encoding="utf-8")
            if re.search(r"^\s*def install\b", text, re.M):
                return {"present": True, "error": None}
    return {
        "present": False,
        "error": (
            "ABSENT: tools/plugin has no install() (command_surface.COMMANDS="
            "startup/status/log-event/write-cache/write-artifact); nothing to "
            "copy a tree into a destination"
        ),
        "files_seen": names,
    }


def ntpath_naive_device() -> dict[str, Any]:
    try:
        naive_nt_relpath(DEVICE_NUL, WIN_ROOT)
        return {"raised": False, "error": None, "result": "no-raise"}
    except Exception as exc:
        return {
            "raised": True,
            "error": f"{type(exc).__name__}: {exc}",
            "result": None,
        }


def ntpath_prefixed_reserved(inventory: dict[str, Any]) -> dict[str, Any]:
    recovered: list[str] = []
    errors: list[str] = []
    for rel in inventory["reserved_relpaths"]:
        parts = rel.split("/")
        win = windows_join(WIN_ROOT, parts)
        try:
            got = safe_nt_relpath(win, WIN_ROOT)
            recovered.append(got.replace("/", "\\"))
            to_extended_length(win)
        except Exception as exc:
            errors.append(f"{rel}: {type(exc).__name__}: {exc}")
    long_rel = inventory["long_rel"]
    long_win = windows_join(WIN_ROOT, long_rel.split("/"))
    try:
        got_long = safe_nt_relpath(long_win, WIN_ROOT)
        recovered.append(got_long)
        to_extended_length(long_win)
    except Exception as exc:
        errors.append(f"long: {type(exc).__name__}: {exc}")
    return {
        "recovered": recovered,
        "errors": errors,
        "count": len(recovered),
        "prefix_used": prefix_invocation_count(),
    }


def run_all(tmp: Path) -> dict[str, Any]:
    reset_prefix_counter()
    hostile = tmp / "hostile"
    fake = tmp / "manifest-repo"
    inv = build_hostile_tree(hostile)
    man_inv = build_manifest_repo(fake)
    known = int(inv["known_count"])

    rows: list[dict[str, Any]] = []

    def add_count_row(*, id: str, kind: str, found: list[str], extra=None):
        got = set(found)
        want = set(inv["by_rel"])
        if got == want:
            outcome, err = "ok", None
        elif not found:
            outcome, err = "silent-zero", "zero files over known-non-empty fixture"
        else:
            outcome, err = "explicit-error", f"set-mismatch got={sorted(got)}"
        rows.append(
            _row(
                id=id,
                kind=kind,
                outcome=outcome,
                fixture_path=str(hostile),
                file_count=len(found),
                error=err,
                extra=extra,
            )
        )

    add_count_row(id="walker-os-walk", kind="walker", found=walk_os_walk(hostile))
    add_count_row(id="walker-pathlib-rglob", kind="walker", found=walk_rglob(hostile))
    try:
        cg_found = walk_contained_rglob(hostile)
        add_count_row(
            id="walker-path-guard-contained-rglob",
            kind="walker",
            found=cg_found,
            extra={"module": "tools/command-center/path_guard.py"},
        )
    except Exception as exc:
        rows.append(
            _row(
                id="walker-path-guard-contained-rglob",
                kind="walker",
                outcome="explicit-error",
                fixture_path=str(hostile),
                file_count=None,
                error=f"{type(exc).__name__}: {exc}",
                extra={"module": "tools/command-center/path_guard.py"},
            )
        )

    hashes = hash_tree(hostile)
    long_hashed = inv["long_rel"] in hashes
    rows.append(
        _row(
            id="hasher-sha256",
            kind="hasher",
            outcome="ok"
            if len(hashes) == known and long_hashed
            else ("silent-zero" if not hashes else "explicit-error"),
            fixture_path=str(hostile),
            file_count=len(hashes),
            error=None
            if len(hashes) == known and long_hashed
            else f"long_hashed={long_hashed} count={len(hashes)}",
            extra={"long_hashed": long_hashed, "digest_len": 64 if hashes else 0},
        )
    )

    dest = tmp / "installed"
    try:
        installed = copytree_install(hostile, dest)
        inst_ok = set(installed) == set(inv["by_rel"])
        rows.append(
            _row(
                id="installer-copytree",
                kind="installer",
                outcome="ok"
                if inst_ok
                else ("silent-zero" if not installed else "explicit-error"),
                fixture_path=str(hostile),
                file_count=len(installed),
                error=None if inst_ok else f"set-mismatch got={installed}",
            )
        )
    except Exception as exc:
        rows.append(
            _row(
                id="installer-copytree",
                kind="installer",
                outcome="explicit-error",
                fixture_path=str(hostile),
                file_count=None,
                error=f"{type(exc).__name__}: {exc}",
            )
        )

    plug = plugin_installer_status()
    rows.append(
        _row(
            id="installer-plugin",
            kind="installer",
            outcome="explicit-error",
            fixture_path="tools/plugin",
            file_count=None,
            error=plug["error"],
            extra={"implementation_present": plug["present"]},
        )
    )

    man = run_unit_manifest(fake)
    want = int(man_inv["known_artifact_count"])
    if man["ok"] and man["rows"] == want:
        man_outcome = "ok"
        man_err = None
    elif man["ok"] and man["rows"] == 0:
        man_outcome = "silent-zero"
        man_err = "derive returned zero rows over a known-non-empty fake repo"
    else:
        man_outcome = "explicit-error"
        man_err = man["error"] or f"rows={man['rows']} want={want}"
    rows.append(
        _row(
            id="walker-hasher-unit-manifest-derive",
            kind="walker",
            outcome=man_outcome,
            fixture_path=str(fake),
            file_count=man["rows"] if man["ok"] else None,
            error=man_err,
            extra={
                "known_artifact_count": want,
                "long_receipt_chars": man_inv["long_receipt_chars"],
            },
        )
    )

    naive = ntpath_naive_device()
    rows.append(
        _row(
            id="relpath-ntpath-device-naive",
            kind="relpath",
            outcome="explicit-error" if naive["raised"] else "ok",
            fixture_path=DEVICE_NUL,
            file_count=None,
            error=naive["error"] or "naive ntpath.relpath did not raise on \\\\.\\NUL",
            extra={
                "precedent_reproduced": bool(naive["raised"] and "\\\\.\\NUL" in (naive["error"] or "")),
            },
        )
    )
    # The naive crash is the measured defect, not a toolchain success. Keep it
    # as explicit-error. If it did NOT raise, that is a discrepancy.

    prefixed = ntpath_prefixed_reserved(inv)
    want_pref = len(inv["reserved_relpaths"]) + 1  # reserved + long
    pref_ok = not prefixed["errors"] and prefixed["count"] == want_pref
    rows.append(
        _row(
            id="relpath-ntpath-extended-length",
            kind="relpath",
            outcome="ok" if pref_ok else ("silent-zero" if prefixed["count"] == 0 else "explicit-error"),
            fixture_path=WIN_ROOT,
            file_count=prefixed["count"],
            error=None if pref_ok else "; ".join(prefixed["errors"]) or "count shortfall",
            extra={
                "recovered": prefixed["recovered"],
                "prefix_invocations_at_step": prefixed["prefix_used"],
            },
        )
    )

    swallowed = swallowed_zero_walk(hostile)
    honest = honest_walk(hostile)
    detector = {
        "id": "swallowed-zero-vs-known-count",
        "fired_on_bad": len(swallowed) == 0 and known > 0,
        "silent_on_good": len(honest) == known,
        "bad_file_count": len(swallowed),
        "good_file_count": len(honest),
        "known_fixture_count": known,
    }

    silent = [r for r in rows if r["outcome"] == "silent-zero"]
    # Naive relpath is an explicit error by design; it is not a silent zero.
    toolchain = [
        r
        for r in rows
        if r["id"]
        not in {"relpath-ntpath-device-naive"}
    ]
    return {
        "inventory": inv,
        "manifest_inventory": man_inv,
        "results": rows,
        "toolchain_results": toolchain,
        "detector": detector,
        "prefix_invocation_count": prefix_invocation_count(),
        "silent_zero_ids": [r["id"] for r in silent],
        "naive_device": naive,
        "plugin": plug,
    }


def both_states(tmp: Path) -> dict[str, Any]:
    """Detector control: fire on swallowed-zero, silent on honest walk."""
    hostile = tmp / "both-states"
    inv = build_hostile_tree(hostile)
    known = int(inv["known_count"])
    bad = swallowed_zero_walk(hostile)
    good = honest_walk(hostile)
    empty_root = tmp / "empty"
    empty_root.mkdir(parents=True, exist_ok=True)
    empty_count = len(honest_walk(empty_root))
    return {
        "known_fixture_count": known,
        "bad_file_count": len(bad),
        "good_file_count": len(good),
        "empty_tree_count": empty_count,
        "fired_on_bad": len(bad) == 0 and known > 0,
        "silent_on_good": len(good) == known,
        "zero_from_empty_is_correct": empty_count == 0,
        "zero_from_swallowed_is_failure": len(bad) == 0 and known > 0,
        "distinguished": (len(bad) == 0 and known > 0) and (empty_count == 0),
    }
