#!/usr/bin/env python3
"""Python package manifest/lock inventory helpers for AUD-0020.

Probe 1 parses each manifest into a normalized name/constraint table.
Probe 2 diffs that table against the sibling lockfile. A manifest read
alone cannot see an out-of-range pin. Undecidable PEP 440 forms are
reported, not guessed.
"""
from __future__ import annotations

import configparser
import hashlib
import json
import os
import re
import shutil
import subprocess
import tomllib
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIX_PRESERVE = HERE / "fixtures" / "preservation"
SEED_NAME = "AUD-0020-unique-seed.bin"
COPY_REL = "copied-elsewhere/AUD-0020-seed-copy.bin"

SKIP_DIR_NAMES = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "vendor",
    ".cursor",
}

NAMED_SURVIVING = [
    "ast-integrate",
    "agent-skills-toolchain",
    "ast-harness-reconcile",
    "ast-statusline-capture",
    "cookie-bridge-skill",
    "ast-increment1",
]

REQ = re.compile(
    r"^\s*(?P<name>[A-Za-z0-9._-]+)\s*(?P<extras>\[[^\]]*\])?\s*(?P<spec>.*)$"
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def dump_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )


def norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_spec(s: str) -> str:
    s = (s or "").split(";")[0].strip()
    return s or "*"


def seed_payload() -> bytes:
    return (
        b"AUD-0020-UNIQUE-SEED-NOT-A-PATH-NAME\n"
        + bytes(range(256))
        + b"\nend-aud-0020-seed\n"
    )


def decoy_payload() -> bytes:
    return b"AUD-0020-DECOY-SAME-RELATIVE-NAME-DIFFERENT-BYTES\n"


def git(args: list[str], cwd: Path, timeout: int = 30) -> tuple[int, str]:
    env = os.environ.copy()
    env.update(
        {
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_OPTIONAL_LOCKS": "0",
        }
    )
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return 127, f"{type(exc).__name__}: {exc}"
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()


def candidate_paths(name: str) -> list[str]:
    home = Path.home()
    out = [
        f"/opt/p2/{name}",
        str(home / "source" / name),
        str(home / "Documents" / "GitHub" / name),
        str(home / ".claude" / "agent-worktrees" / name),
        f"C:/Users/Prekzursil/source/{name}",
    ]
    seen: set[str] = set()
    ordered: list[str] = []
    for item in out:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def live_host_scan() -> dict[str, Any]:
    cwd = str(Path.cwd())
    rc, raw = git(["rev-parse", "--is-inside-work-tree"], cwd=REPO)
    git_worktree = rc == 0 and "true" in raw.lower()
    origin_url = None
    origin_raw = raw
    if git_worktree:
        _rc_o, origin_raw = git(["remote", "get-url", "origin"], cwd=REPO)
        if _rc_o == 0 and origin_raw:
            origin_url = origin_raw.splitlines()[0].strip()
    present = 0
    absent = 0
    named: list[dict[str, Any]] = []
    for name in NAMED_SURVIVING:
        cands = candidate_paths(name)
        existing = [p for p in cands if Path(p).exists()]
        git_paths = [p for p in existing if (Path(p) / ".git").exists()]
        if git_paths:
            status = "present-git"
            present += 1
        elif existing:
            status = "present-not-git"
            present += 1
        else:
            status = "absent"
            absent += 1
        named.append(
            {
                "name": name,
                "candidates_checked": cands,
                "existing_paths": existing,
                "git_paths": git_paths,
                "status": status,
            }
        )
    return {
        "cwd": cwd,
        "git_worktree": git_worktree,
        "origin_url": origin_url,
        "named_surviving_present": present,
        "named_surviving_absent": absent,
        "git_rev_parse_raw": raw,
        "origin_raw": origin_raw,
        "named_surviving": named,
    }


def _skip_dir(path: Path) -> bool:
    if set(path.parts) & SKIP_DIR_NAMES:
        return True
    # Skip the preservation-control scratch tree only. Fixture packages
    # under fixtures/packages/ are in-scope inventory.
    if "AUD-0020" in path.parts and "preservation" in path.parts:
        return True
    return False


def find_manifests() -> list[Path]:
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(REPO):
        base = Path(dirpath)
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
        if _skip_dir(base):
            dirnames[:] = []
            continue
        for name in filenames:
            if name in {"pyproject.toml", "setup.cfg"} or (
                name.startswith("requirements") and name.endswith(".txt")
            ):
                found.append(base / name)
    return sorted(found, key=lambda p: p.as_posix())


def parse_requirement_line(line: str) -> tuple[str, str] | None:
    line = line.split("#")[0].strip()
    if not line or line.startswith("-"):
        return None
    m = REQ.match(line)
    if not m:
        return None
    return norm(m.group("name")), parse_spec(m.group("spec"))


def parse_setup_cfg(p: Path) -> dict[str, str]:
    deps: dict[str, str] = {}
    parser = configparser.ConfigParser()
    try:
        parser.read_string(p.read_text(encoding="utf-8", errors="replace"))
    except (configparser.Error, OSError) as exc:
        return {"__error__": f"{type(exc).__name__}: {exc}"}
    raw = ""
    if parser.has_option("options", "install_requires"):
        raw = parser.get("options", "install_requires")
    for line in raw.splitlines():
        parsed = parse_requirement_line(line)
        if parsed:
            deps[parsed[0]] = parsed[1]
    if parser.has_section("options.extras_require"):
        for _, val in parser.items("options.extras_require"):
            for line in val.splitlines():
                parsed = parse_requirement_line(line)
                if parsed:
                    deps.setdefault(parsed[0], parsed[1])
    return deps


def parse_manifest(p: Path) -> dict[str, str]:
    deps: dict[str, str] = {}
    if p.name == "pyproject.toml":
        try:
            d = tomllib.loads(p.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            return {"__error__": f"{type(exc).__name__}: {exc}"}
        for raw in (d.get("project") or {}).get("dependencies") or []:
            parsed = parse_requirement_line(str(raw))
            if parsed:
                deps[parsed[0]] = parsed[1]
        for group in ((d.get("project") or {}).get("optional-dependencies") or {}).values():
            for raw in group:
                parsed = parse_requirement_line(str(raw))
                if parsed:
                    deps.setdefault(parsed[0], parsed[1])
        poetry = ((d.get("tool") or {}).get("poetry") or {}).get("dependencies") or {}
        for k, v in poetry.items():
            if norm(k) == "python":
                continue
            spec = v if not isinstance(v, dict) else v.get("version", "*")
            deps.setdefault(norm(k), parse_spec(str(spec)))
        return deps
    if p.name == "setup.cfg":
        return parse_setup_cfg(p)
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        parsed = parse_requirement_line(line)
        if parsed:
            deps[parsed[0]] = parsed[1]
    return deps


def parse_uv_lock(p: Path) -> dict[str, str]:
    try:
        d = tomllib.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"__error__": f"{type(exc).__name__}: {exc}"}
    return {
        norm(str(pkg.get("name") or "")): str(pkg.get("version") or "")
        for pkg in d.get("package") or []
        if pkg.get("name")
    }


def parse_poetry_lock(p: Path) -> dict[str, str]:
    try:
        d = tomllib.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"__error__": f"{type(exc).__name__}: {exc}"}
    out: dict[str, str] = {}
    for pkg in d.get("package") or []:
        name = pkg.get("name")
        if name:
            out[norm(str(name))] = str(pkg.get("version") or "")
    return out


def parse_pipfile_lock(p: Path) -> dict[str, str]:
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"__error__": f"{type(exc).__name__}: {exc}"}
    out: dict[str, str] = {}
    for section in ("default", "develop"):
        for name, meta in (d.get(section) or {}).items():
            ver = meta.get("version") if isinstance(meta, dict) else meta
            out[norm(name)] = str(ver or "").lstrip("=") or "*"
    return out


def parse_lock(p: Path) -> dict[str, str]:
    if p.name == "uv.lock":
        return parse_uv_lock(p)
    if p.name == "poetry.lock":
        return parse_poetry_lock(p)
    if p.name == "Pipfile.lock":
        return parse_pipfile_lock(p)
    return {}


def ver_tuple(v: str) -> tuple:
    return tuple(int(x) if x.isdigit() else 0 for x in re.split(r"[.\-+]", v)[:4])


def satisfies(pinned: str, spec: str) -> bool | None:
    spec = (spec or "*").strip()
    if spec in ("", "*"):
        return True
    if not pinned:
        return None
    ok = True
    for clause in spec.split(","):
        clause = clause.strip()
        m = re.match(r"^(==|!=|>=|<=|~=|>|<)\s*([0-9][0-9A-Za-z.\-+*]*)$", clause)
        if not m:
            return None
        op, want = m.group(1), m.group(2)
        if want.endswith("*"):
            base = want.rstrip("*").rstrip(".")
            hit = pinned.startswith(base)
            ok &= hit if op == "==" else (not hit if op == "!=" else True)
            continue
        pv, wv = ver_tuple(pinned), ver_tuple(want)
        ok &= {
            "==": pv == wv,
            "!=": pv != wv,
            ">=": pv >= wv,
            "<=": pv <= wv,
            ">": pv > wv,
            "<": pv < wv,
            "~=": pv >= wv and pv[: max(len(wv) - 1, 1)] == wv[: max(len(wv) - 1, 1)],
        }[op]
    return ok


def diff(manifest: dict[str, str], lock: dict[str, str]) -> dict[str, Any]:
    rows, violations, undecidable, missing = [], [], [], []
    for name, spec in sorted(manifest.items()):
        if name.startswith("__"):
            continue
        pinned = lock.get(name)
        verdict = satisfies(pinned, spec) if pinned is not None else None
        status = (
            "MISSING-FROM-LOCK"
            if pinned is None
            else "OK"
            if verdict is True
            else "OUT-OF-RANGE"
            if verdict is False
            else "UNDECIDABLE-CONSTRAINT"
        )
        row = {
            "name": name,
            "declared": spec,
            "locked": pinned,
            "satisfies": verdict,
            "status": status,
        }
        rows.append(row)
        if status == "OUT-OF-RANGE":
            violations.append(row)
        elif status == "UNDECIDABLE-CONSTRAINT":
            undecidable.append(row)
        elif status == "MISSING-FROM-LOCK":
            missing.append(row)
    return {
        "rows": rows,
        "violations": violations,
        "undecidable": undecidable,
        "missing_from_lock": missing,
    }


def pin_control() -> dict[str, Any]:
    fx_manifest = {"requests": ">=2.31,<3", "rich": ">=13.0"}
    fx_lock_good = {"requests": "2.32.3", "rich": "13.7.1"}
    fx_lock_bad = {"requests": "1.2.3", "rich": "13.7.1"}
    d_bad = diff(fx_manifest, fx_lock_bad)
    d_good = diff(fx_manifest, fx_lock_good)
    fires = len(d_bad["violations"]) == 1 and d_bad["violations"][0]["name"] == "requests"
    silent = len(d_good["violations"]) == 0
    return {
        "fixture_manifest": fx_manifest,
        "bad_lock": fx_lock_bad,
        "good_lock": fx_lock_good,
        "bad_result": d_bad,
        "good_result": d_good,
        "fires_on_out_of_range": fires,
        "silent_on_in_range": silent,
        "ok": fires and silent,
    }


def _hash_index(root: Path) -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    if not root.is_dir():
        return index
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
        for name in filenames:
            path = Path(dirpath) / name
            if path.is_file() and not path.is_symlink():
                digest = sha256_bytes(path.read_bytes())
                rel = path.relative_to(root).as_posix()
                index.setdefault(digest, []).append(rel)
    return index


def run_preservation_control() -> dict[str, Any]:
    if FIX_PRESERVE.exists():
        shutil.rmtree(FIX_PRESERVE)
    seed_dir = FIX_PRESERVE / "only-here"
    decoy_dir = FIX_PRESERVE / "decoy-same-name"
    seed_dir.mkdir(parents=True)
    decoy_dir.mkdir(parents=True)
    seed_path = seed_dir / SEED_NAME
    decoy_path = decoy_dir / SEED_NAME
    seed_path.write_bytes(seed_payload())
    decoy_path.write_bytes(decoy_payload())
    digest = sha256_bytes(seed_payload())
    before_idx = _hash_index(FIX_PRESERVE)
    before_hits = list(before_idx.get(digest) or [])
    path_name_rejected = (
        decoy_path.is_file()
        and seed_path.is_file()
        and sha256_bytes(decoy_path.read_bytes()) != digest
    )
    copy_path = FIX_PRESERVE / COPY_REL
    copy_path.parent.mkdir(parents=True, exist_ok=True)
    copy_path.write_bytes(seed_payload())
    after_idx = _hash_index(FIX_PRESERVE)
    after_hits = list(after_idx.get(digest) or [])
    unpreserved_before = len(before_hits) == 1
    preserved_after = any(h.endswith("AUD-0020-seed-copy.bin") for h in after_hits)
    flipped = unpreserved_before and preserved_after
    return {
        "seed_path": seed_path.relative_to(REPO).as_posix(),
        "copy_path": copy_path.relative_to(REPO).as_posix(),
        "seed_sha256": digest,
        "unpreserved_before_copy": unpreserved_before,
        "preserved_after_copy": preserved_after,
        "path_name_match_rejected": path_name_rejected,
        "flipped": flipped,
        "before_hits": before_hits,
        "after_hits": after_hits,
        "decoy_path": decoy_path.relative_to(REPO).as_posix(),
    }


def sibling_lock(pkgdir: Path) -> Path | None:
    for name in ("uv.lock", "poetry.lock", "Pipfile.lock"):
        cand = pkgdir / name
        if cand.is_file():
            return cand
    return None


def inventory_name(rel_dir: str) -> str:
    last = Path(rel_dir).name or rel_dir
    if len(last) >= 3:
        return last
    slug = rel_dir.replace("/", "--") or "pkg"
    return slug if len(slug) >= 3 else f"pkg-{slug}"


def scan_packages() -> list[dict[str, Any]]:
    manifests = find_manifests()
    by_dir: dict[str, list[Path]] = {}
    for mp in manifests:
        rel_dir = mp.parent.relative_to(REPO).as_posix() or "."
        by_dir.setdefault(rel_dir, []).append(mp)

    packages: list[dict[str, Any]] = []
    for rel_dir, mps in sorted(by_dir.items()):
        pkgdir = REPO / rel_dir
        declared: dict[str, str] = {}
        manifest_rows: list[dict[str, Any]] = []
        errors: list[str] = []
        for mp in sorted(mps, key=lambda p: p.name):
            rel = mp.relative_to(REPO).as_posix()
            deps = parse_manifest(mp)
            err = deps.get("__error__")
            if err:
                errors.append(f"{rel}: {err}")
            clean = {k: v for k, v in deps.items() if not k.startswith("__")}
            for k, v in clean.items():
                declared.setdefault(k, v)
            manifest_rows.append(
                {
                    "manifest": rel,
                    "declared": clean,
                    "declared_dep_count": len(clean),
                    "manifest_error": err,
                }
            )
        lock_p = sibling_lock(pkgdir)
        lock: dict[str, str] = {}
        lock_kind = None
        lock_rel = None
        if lock_p is not None:
            lock_kind = lock_p.name
            lock_rel = lock_p.relative_to(REPO).as_posix()
            lock = parse_lock(lock_p)
        lock_err = lock.get("__error__") if lock else None
        lock_clean = {k: v for k, v in lock.items() if not k.startswith("__")}
        if lock_p is not None and lock_clean and not lock_err:
            recon = diff(declared, lock_clean)
            note = None
        elif lock_p is None:
            recon = None
            note = (
                "NOT-CHECKED: no lockfile for this package, so whether the lock "
                "resolves declared constraints has no answer here — absence is "
                "reported, not passed."
            )
        elif lock_err:
            recon = None
            note = f"NOT-CHECKED: lock parse error: {lock_err}"
        else:
            recon = None
            note = (
                "NOT-CHECKED: lockfile format not parsed by this differ "
                f"({lock_kind})."
            )
        missing_n = len((recon or {}).get("missing_from_lock") or [])
        viol_n = len((recon or {}).get("violations") or [])
        packages.append(
            {
                "name": inventory_name(rel_dir),
                "package_dir": rel_dir,
                "source": "live-host",
                "origin_url": None,
                "dirty_tracked": 0,
                "dirty_untracked": 0,
                "unique_file_count": len(mps) + (1 if lock_p else 0),
                "unpreserved_count": missing_n + viol_n,
                "manifests": manifest_rows,
                "declared": declared,
                "declared_dep_count": len(declared),
                "manifest_errors": errors,
                "lockfile": lock_rel,
                "lockfile_kind": lock_kind,
                "locked_package_count": len(lock_clean),
                "reconciliation": recon,
                "reconciliation_note": note,
            }
        )
    return packages


def headline(packages: list[dict[str, Any]]) -> dict[str, Any]:
    with_lock = [p for p in packages if p["reconciliation"] is not None]
    without_lock = [p for p in packages if p["reconciliation"] is None]
    viol = [
        {"package_dir": p["package_dir"], **v}
        for p in with_lock
        for v in p["reconciliation"]["violations"]
    ]
    missing = [
        {"package_dir": p["package_dir"], "name": r["name"]}
        for p in with_lock
        for r in p["reconciliation"]["missing_from_lock"]
    ]
    undec = [
        {"package_dir": p["package_dir"], "name": r["name"], "declared": r["declared"]}
        for p in with_lock
        for r in p["reconciliation"]["undecidable"]
    ]
    return {
        "python_packages": len(packages),
        "python_manifests": sum(len(p["manifests"]) for p in packages),
        "declared_direct_dependencies": sum(p["declared_dep_count"] for p in packages),
        "packages_with_parsed_lock": len(with_lock),
        "packages_without_parsed_lock": len(without_lock),
        "out_of_range_pins": len(viol),
        "declared_missing_from_lock": len(missing),
        "undecidable_constraints": len(undec),
        "violations": viol,
        "missing_from_lock": missing,
        "undecidable": undec,
        "poetry_lock_files": sum(
            1 for p in packages if p["lockfile_kind"] == "poetry.lock"
        ),
        "pipfile_lock_files": sum(
            1 for p in packages if p["lockfile_kind"] == "Pipfile.lock"
        ),
        "uv_lock_files": sum(1 for p in packages if p["lockfile_kind"] == "uv.lock"),
        "setup_cfg_files": sum(
            1
            for p in packages
            for m in p["manifests"]
            if Path(m["manifest"]).name == "setup.cfg"
        ),
    }
