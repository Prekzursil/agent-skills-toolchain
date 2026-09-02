"""AUD-0082 Windows path-hazard classifier and enumerators.

Probe 1 classifies path *strings* (git index when available). Probe 2 walks
the filesystem with a lexical relative-path helper so a reserved device name
cannot abort the walk into a silent zero. Neither enumerator calls
os.path.relpath on production paths.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

RESERVED_DEVICE_STEMS = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        "CLOCK$",
        *{f"COM{i}" for i in range(1, 10)},
        *{f"LPT{i}" for i in range(1, 10)},
    }
)

# Harvest-era Windows checkout prefix used to project MAX_PATH risk.
WIN_CHECKOUT_PREFIX = r"C:\Users\Prekzursil\source\ast-integrate"
MAX_PATH = 260
SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".venv",
    }
)
# Receipts this unit writes; including them would make live counts chase the probes.
SELF_OUTPUT_RELS = frozenset(
    {
        "command-center/audit/AUD-0082-windows-path-hazard-census.json",
        "command-center/p2-wave/probes/AUD-0082/probe1-git-index.raw.json",
        "command-center/p2-wave/probes/AUD-0082/probe2-fs-walk.raw.json",
        "command-center/p2-wave/probes/AUD-0082/SUBAGENT-RETURN.json",
        "command-center/p2-wave/probes/AUD-0082/UNIT-ARTIFACT-MANIFEST.json",
    }
)


def posix(path: str | Path) -> str:
    text = str(path).replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return text


def path_components(rel: str) -> list[str]:
    rel = posix(rel)
    return [c for c in rel.split("/") if c and c != "."]


def reserved_stem(name: str) -> str | None:
    cleaned = str(name).rstrip(" .")
    if not cleaned:
        return None
    stem = cleaned.split(".")[0].upper()
    if stem in RESERVED_DEVICE_STEMS:
        return stem
    if cleaned.upper() in RESERVED_DEVICE_STEMS:
        return cleaned.upper()
    return None


def reserved_hits(rel: str) -> list[dict[str, str]]:
    hits = []
    for i, comp in enumerate(path_components(rel)):
        stem = reserved_stem(comp)
        if stem:
            hits.append({"component_index": str(i), "component": comp, "stem": stem})
    return hits


def win_abs(rel: str, prefix: str = WIN_CHECKOUT_PREFIX) -> str:
    rel_win = posix(rel).replace("/", "\\")
    base = prefix.rstrip("\\")
    if not rel_win:
        return base
    return base + "\\" + rel_win


def win_extended(win_path: str) -> str:
    n = win_path.replace("/", "\\")
    if n.startswith("\\\\?\\"):
        return n
    if n.startswith("\\\\"):
        return "\\\\?\\UNC\\" + n[2:]
    return "\\\\?\\" + n


def classify_path(rel: str) -> dict[str, Any]:
    rel_n = posix(rel)
    reserved = reserved_hits(rel_n)
    rel_len = len(rel_n)
    abs_path = win_abs(rel_n)
    abs_len = len(abs_path)
    return {
        "path": rel_n,
        "relative_len": rel_len,
        "windows_abs": abs_path,
        "windows_abs_len": abs_len,
        "windows_extended": win_extended(abs_path),
        "exceeds_260_relative": rel_len > MAX_PATH,
        "exceeds_260_windows_abs": abs_len > MAX_PATH,
        "reserved": reserved,
        "is_reserved": bool(reserved),
        "is_long": rel_len > MAX_PATH or abs_len > MAX_PATH,
    }


def case_collisions(paths: Iterable[str]) -> list[dict[str, Any]]:
    """Sibling names that differ only by case (files or intermediate directories)."""
    children: dict[str, dict[str, set[str]]] = {}
    for raw in paths:
        parts = path_components(raw)
        for i, name in enumerate(parts):
            parent = "/".join(parts[:i])
            bucket = children.setdefault(parent, {})
            folded = name.casefold()
            bucket.setdefault(folded, set()).add(name)
    out: list[dict[str, Any]] = []
    for parent, names in sorted(children.items()):
        for folded, variants in sorted(names.items()):
            if len(variants) < 2:
                continue
            out.append(
                {
                    "parent": parent,
                    "folded": folded,
                    "names": sorted(variants),
                }
            )
    return out


def git_index_paths(repo: Path) -> tuple[list[str], dict[str, Any]]:
    meta: dict[str, Any] = {
        "instrument": "git ls-files -z",
        "git_dir": str(repo / ".git"),
        "git_dir_exists": (repo / ".git").exists(),
    }
    try:
        proc = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=str(repo),
            capture_output=True,
            timeout=120,
        )
    except FileNotFoundError:
        meta.update({"ok": False, "error": "git-executable-absent"})
        return [], meta
    except subprocess.TimeoutExpired:
        meta.update({"ok": False, "error": "git-ls-files-timeout"})
        return [], meta
    meta["returncode"] = proc.returncode
    if proc.returncode != 0:
        err = (proc.stderr or b"").decode("utf-8", "replace")[:800]
        meta.update({"ok": False, "error": err or "git-ls-files-nonzero"})
        return [], meta
    paths = [
        p.decode("utf-8", "surrogateescape").replace("\\", "/")
        for p in proc.stdout.split(b"\0")
        if p
    ]
    meta.update({"ok": True, "count": len(paths)})
    return paths, meta


def _lexical_relpath(path: str | Path, start: str | Path) -> str:
    p = str(path).replace("\\", "/")
    s = str(start).replace("\\", "/")
    if len(s) > 1 and s.endswith("/"):
        s = s[:-1]
    if p == s:
        return "."
    prefix = s + "/"
    if p.startswith(prefix):
        return p[len(prefix) :]
    return p.lstrip("/") or "."


def looks_like_windows_device(path: str | Path) -> bool:
    raw = str(path)
    norm = raw.replace("/", "\\")
    if norm.startswith("\\\\.\\") or norm.startswith("\\\\?\\"):
        return True
    name = Path(raw.replace("\\", "/")).name
    return reserved_stem(name) is not None


def safe_relpath(path: str | Path, start: str | Path) -> str:
    if looks_like_windows_device(path) or looks_like_windows_device(start):
        return _lexical_relpath(path, start)
    p = Path(str(path))
    s = Path(str(start))
    try:
        return p.resolve(strict=False).relative_to(s.resolve(strict=False)).as_posix()
    except (ValueError, OSError, RuntimeError):
        try:
            return Path(os.fspath(p)).relative_to(os.fspath(s)).as_posix()
        except (ValueError, OSError, TypeError):
            return _lexical_relpath(path, start)


@dataclass
class WalkResult:
    files: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    aborted: bool = False
    status: str = "walked"

    @property
    def file_count(self) -> int:
        return len(self.files)


def walk_tree(
    root: Path,
    *,
    skip_dir_names: frozenset[str] | set[str] | None = None,
    relpath_fn: Callable[[str | Path, str | Path], str] | None = None,
) -> WalkResult:
    """Filesystem walk that records per-entry OSError and never swallows a crash as zero."""
    relpath_fn = relpath_fn or safe_relpath
    skip = SKIP_DIR_NAMES if skip_dir_names is None else frozenset(skip_dir_names)
    result = WalkResult()
    root = Path(root)
    try:
        if not root.exists():
            result.status = "missing"
            return result
        if not root.is_dir():
            result.status = "walked"
            result.errors.append(f"not-a-directory:{root}")
            return result
    except OSError as exc:
        result.status = "aborted"
        result.aborted = True
        result.errors.append(f"exists:{root}:{type(exc).__name__}:{exc}")
        return result

    stack: list[Path] = [root]
    try:
        while stack:
            current = stack.pop()
            try:
                with os.scandir(current) as iterator:
                    entries = list(iterator)
            except OSError as exc:
                result.errors.append(f"scandir:{current}:{type(exc).__name__}:{exc}")
                continue
            for ent in entries:
                try:
                    is_dir = ent.is_dir(follow_symlinks=False)
                    is_file = ent.is_file(follow_symlinks=False)
                except OSError as exc:
                    result.errors.append(f"stat:{ent.path}:{type(exc).__name__}:{exc}")
                    continue
                if is_dir:
                    if ent.name in skip:
                        continue
                    stack.append(Path(ent.path))
                    continue
                if not is_file:
                    continue
                try:
                    rel = relpath_fn(ent.path, root)
                except (OSError, ValueError, RuntimeError) as exc:
                    result.errors.append(
                        f"relpath:{ent.path}:{type(exc).__name__}:{exc}"
                    )
                    rel = _lexical_relpath(ent.path, root)
                rel = str(rel).replace("\\", "/")
                if skip is SKIP_DIR_NAMES and rel in SELF_OUTPUT_RELS:
                    continue
                result.files.append(rel)
    except Exception as exc:  # noqa: BLE001 — crash must not become silent zero
        result.aborted = True
        result.status = "aborted"
        result.errors.append(f"walk-abort:{type(exc).__name__}:{exc}")
        return result
    result.status = "walked"
    return result


_ORIG_OS_RELPATH = os.path.relpath


def naive_relpath_raises_on_nul(path: str | Path, start: str | Path = os.curdir) -> str:
    """Windows-shaped relpath failure used only as the RED enumerator."""
    text = str(path).replace("/", "\\")
    leaf = text.rsplit("\\", 1)[-1]
    stem = leaf.split(".")[0].upper()
    if stem == "NUL" or text.startswith("\\\\.\\") or "\\\\.\\NUL" in text:
        raise OSError(22, "Invalid argument — reserved device name", path)
    return _ORIG_OS_RELPATH(os.fspath(path), os.fspath(start))


def naive_walk(root: Path) -> tuple[list[str], str | None]:
    files: list[str] = []
    try:
        for dirpath, _dirnames, filenames in os.walk(root):
            for name in filenames:
                full = os.path.join(dirpath, name)
                rel = os.path.relpath(full, str(root))
                files.append(rel.replace("\\", "/"))
    except OSError as exc:
        return files, f"{type(exc).__name__}:{exc}"
    return files, None


def hazard_tables(paths: Iterable[str]) -> dict[str, Any]:
    reserved: list[dict[str, Any]] = []
    long_paths: list[dict[str, Any]] = []
    classified = 0
    for rel in paths:
        classified += 1
        row = classify_path(rel)
        if row["is_reserved"]:
            reserved.append(row)
        if row["is_long"]:
            long_paths.append(row)
    collisions = case_collisions(paths)
    return {
        "classified": classified,
        "reserved_count": len(reserved),
        "long_path_count": len(long_paths),
        "case_collision_count": len(collisions),
        "reserved": reserved,
        "long_paths": long_paths[:200],
        "long_paths_truncated": max(0, len(long_paths) - 200),
        "case_collisions": collisions[:200],
        "case_collisions_truncated": max(0, len(collisions) - 200),
        "hazard_count": len(reserved) + len(long_paths) + len(collisions),
    }


def plant_control_tree(tmp: Path) -> dict[str, Any]:
    """Fixture: NUL-named file, 300-char relative path, case-colliding siblings."""
    tmp = Path(tmp)
    tmp.mkdir(parents=True, exist_ok=True)
    keep = tmp / "keep.txt"
    keep.write_text("keep\n", encoding="utf-8")
    nul = tmp / "NUL"
    nul.write_text("reserved-device-name-fixture\n", encoding="utf-8")
    # NAME_MAX is 255; nest four 80-char components plus leaf (~330 relative chars).
    chunk = "n" * 80
    long_leaf = tmp / chunk / chunk / chunk / chunk / "leaf.txt"
    long_leaf.parent.mkdir(parents=True, exist_ok=True)
    long_leaf.write_text("long\n", encoding="utf-8")
    (tmp / "ReadMe.txt").write_text("case-a\n", encoding="utf-8")
    (tmp / "readme.txt").write_text("case-b\n", encoding="utf-8")
    long_rel = _lexical_relpath(long_leaf, tmp)
    return {
        "root": str(tmp),
        "nul_rel": "NUL",
        "keep_rel": "keep.txt",
        "long_rel": long_rel,
        "long_rel_len": len(long_rel),
        "case_pair": ["ReadMe.txt", "readme.txt"],
    }


def enumerator_control() -> dict[str, Any]:
    """Required control: non-zero count on NUL + 300-char path; naive walker red."""
    with tempfile.TemporaryDirectory(prefix="aud0082-") as tmp_s:
        tmp = Path(tmp_s)
        planted = plant_control_tree(tmp)
        green = walk_tree(tmp, skip_dir_names=set())
        orig = os.path.relpath
        red_exc = None
        red_count = 0
        os.path.relpath = naive_relpath_raises_on_nul  # type: ignore[method-assign]
        try:
            red_files, red_exc = naive_walk(tmp)
            red_count = len(red_files)
        finally:
            os.path.relpath = orig  # type: ignore[method-assign]
        names = {Path(p).name for p in green.files}
        long_found = any(len(p) >= 300 for p in green.files)
        nul_found = "NUL" in names or any(Path(p).name == "NUL" for p in green.files)
        collisions = case_collisions(green.files)
        synthetic_index = [
            planted["nul_rel"],
            planted["keep_rel"],
            planted["long_rel"],
            "ReadMe.txt",
            "readme.txt",
        ]
        classified = hazard_tables(synthetic_index)
        ok = (
            (not green.aborted)
            and green.file_count > 0
            and nul_found
            and long_found
            and planted["long_rel_len"] >= 300
            and classified["reserved_count"] >= 1
            and classified["long_path_count"] >= 1
            and classified["case_collision_count"] >= 1
            and (red_count == 0 or red_exc is not None)
        )
        return {
            "pass": ok,
            "planted": planted,
            "production_count": green.file_count,
            "production_aborted": green.aborted,
            "production_errors": green.errors,
            "production_names": sorted(names),
            "nul_found": nul_found,
            "long_found": long_found,
            "fixture_collisions": collisions,
            "naive_count": red_count,
            "naive_exception": red_exc,
            "naive_went_red": red_count == 0 or red_exc is not None,
            "classifier": {
                "reserved_count": classified["reserved_count"],
                "long_path_count": classified["long_path_count"],
                "case_collision_count": classified["case_collision_count"],
            },
        }


def index_unavailable_fallback(repo: Path) -> list[str]:
    """Path-string inventory without os.path.relpath when git index cannot be read."""
    walked = walk_tree(repo)
    return walked.files


def probe1_live(repo: Path | None = None) -> dict[str, Any]:
    repo = Path(repo) if repo is not None else REPO
    control = enumerator_control()
    paths, git_meta = git_index_paths(repo)
    source = "git-index"
    if not git_meta.get("ok"):
        paths = index_unavailable_fallback(repo)
        source = "working-tree-strings-git-unavailable"
    tables = hazard_tables(paths)
    return {
        "probe": "probe1-git-index-path-string-classifier",
        "unit_id": "AUD-0082",
        "source": source,
        "git": git_meta,
        "control": {
            "pass": control["pass"],
            "production_count": control["production_count"],
            "nul_found": control["nul_found"],
            "long_found": control["long_found"],
            "naive_went_red": control["naive_went_red"],
            "classifier": control["classifier"],
        },
        "census": tables,
        "pass": bool(control["pass"] and tables["classified"] >= 0 and not (
            control["production_count"] == 0
        )),
    }


def probe2_live(repo: Path | None = None) -> dict[str, Any]:
    repo = Path(repo) if repo is not None else REPO
    control = enumerator_control()
    walked = walk_tree(repo)
    tables = hazard_tables(walked.files)
    index_paths, git_meta = git_index_paths(repo)
    index_set = set(index_paths) if git_meta.get("ok") else set()
    extra = sorted(p for p in walked.files if p not in index_set) if index_set else []
    extra_tables = hazard_tables(extra) if extra else hazard_tables([])
    ok = (
        control["pass"]
        and not walked.aborted
        and walked.file_count > 0
        and tables["classified"] == walked.file_count
    )
    return {
        "probe": "probe2-filesystem-walk-extended-length",
        "unit_id": "AUD-0082",
        "pass": ok,
        "walk": {
            "status": walked.status,
            "aborted": walked.aborted,
            "file_count": walked.file_count,
            "error_count": len(walked.errors),
            "errors_sample": walked.errors[:20],
            "skip_dir_names": sorted(SKIP_DIR_NAMES),
            "self_outputs_excluded": sorted(SELF_OUTPUT_RELS),
        },
        "control": {
            "pass": control["pass"],
            "production_count": control["production_count"],
            "nul_found": control["nul_found"],
            "long_found": control["long_found"],
            "long_rel_len": control["planted"]["long_rel_len"],
            "naive_count": control["naive_count"],
            "naive_exception": control["naive_exception"],
            "naive_went_red": control["naive_went_red"],
        },
        "census": tables,
        "not_in_git_index": {
            "git_ok": bool(git_meta.get("ok")),
            "count": len(extra),
            "hazard_count": extra_tables["hazard_count"],
            "reserved_count": extra_tables["reserved_count"],
            "long_path_count": extra_tables["long_path_count"],
            "case_collision_count": extra_tables["case_collision_count"],
        },
        "extended_length_prefix": "\\\\?\\",
        "linux_note": (
            "This Linux walk does not call Win32 CreateFile. The extended-length "
            "prefix is recorded on classified paths; the production enumerator "
            "uses lexical relpath so NUL cannot abort the walk."
        ),
    }
