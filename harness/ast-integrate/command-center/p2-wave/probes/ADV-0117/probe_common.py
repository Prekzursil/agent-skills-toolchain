"""ADV-0117 shared fixture matrix, production-component adapters, count oracle.

Probe 1 classifies per-class outcomes (correct / crash / silent skip / wrong
result / explicit refusal). Probe 2 only compares reported item counts against
an independent scandir oracle. Neither oracle calls os.path.relpath.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import platform
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.layout import migrate as layout_migrate  # noqa: E402
from tools.marketplace import census as marketplace_census  # noqa: E402
from tools.plugin import cache_ownership as plugin_own  # noqa: E402
from tools.router.index_build import walk_files  # noqa: E402

UID = "ADV-0117"
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
MAX_PATH = 260
HOSTILE_CLASSES = (
    "reserved-device",
    "long-path",
    "case-collision",
    "spaces",
    "unicode",
    "trailing-dot",
)
ALL_CLASSES = ("ordinary",) + HOSTILE_CLASSES
COMPONENTS = (
    "enumerator",
    "packager",
    "installer",
    "artifact-writer",
    "manifest-hasher",
)
_ORIG_RELPATH = os.path.relpath


def posix(rel: str | Path) -> str:
    text = str(rel).replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return text


def lexical_relpath(path: str | Path, start: str | Path) -> str:
    """OS-free relative path. Never calls os.path.relpath."""
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


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relpath_raises_on_reserved(path: str | os.PathLike[str], start: str = os.curdir) -> str:
    """Windows-faithful relpath: reserved device names raise ValueError (NUL precedent)."""
    name = Path(str(path).replace("\\", "/")).name
    cleaned = name.rstrip(" .")
    stem = cleaned.split(".")[0].upper() if cleaned else ""
    if stem in RESERVED_DEVICE_STEMS or cleaned.upper() in RESERVED_DEVICE_STEMS:
        raise ValueError(f"path is on mount '\\\\.\\{stem or name}': {path}")
    return _ORIG_RELPATH(path, start)


def oracle_list(root: Path) -> list[str]:
    """Independent enumeration via scandir + lexical relpath. Count oracle."""
    root = Path(root)
    files: list[str] = []
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as iterator:
                entries = list(iterator)
        except OSError:
            continue
        for ent in entries:
            try:
                is_dir = ent.is_dir(follow_symlinks=False)
                is_file = ent.is_file(follow_symlinks=False)
            except OSError:
                continue
            if is_dir:
                stack.append(Path(ent.path))
            elif is_file:
                files.append(posix(lexical_relpath(ent.path, root)))
    return sorted(files)


def oracle_hashes(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    root = Path(root)
    for rel in oracle_list(root):
        out[rel] = file_sha256(root / rel)
    return out


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def build_class_tree(root: Path, class_id: str) -> dict[str, Any]:
    """Plant one directory of files for a hostile (or ordinary) class."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    notes: list[str] = []
    if class_id == "ordinary":
        _write(root / "keep.txt", "ordinary-keep\n")
        _write(root / "nested" / "inner.txt", "ordinary-inner\n")
    elif class_id == "reserved-device":
        _write(root / "keep.txt", "reserved-sibling\n")
        _write(root / "NUL", "reserved-device-name-fixture\n")
        _write(root / "CON", "reserved-con-fixture\n")
        notes.append("POSIX files named NUL and CON; Windows CreateFile was not called.")
    elif class_id == "long-path":
        chunk = "p" * 70
        leaf = root / chunk / chunk / chunk / chunk / "leaf.txt"
        _write(leaf, "long-path-payload\n")
        rel = posix(lexical_relpath(leaf, root))
        if len(rel) <= MAX_PATH:
            extra = "q" * (MAX_PATH + 8 - len(rel))
            leaf = root / chunk / chunk / chunk / chunk / f"{extra}.txt"
            _write(leaf, "long-path-payload\n")
            rel = posix(lexical_relpath(leaf, root))
        notes.append(f"relative_len={len(rel)}")
    elif class_id == "case-collision":
        _write(root / "ReadMe.txt", "case-collision-upper\n")
        _write(root / "readme.txt", "case-collision-lower\n")
        notes.append("Two siblings that collide under casefold; distinct bytes.")
    elif class_id == "spaces":
        _write(root / "my file.txt", "spaces-file\n")
        _write(root / "dir with spaces" / "inner.txt", "spaces-inner\n")
    elif class_id == "unicode":
        _write(root / "café.txt", "unicode-nfc-cafe\n")
        _write(root / "日本語.txt", "unicode-jp\n")
    elif class_id == "trailing-dot":
        _write(root / "notes.", "trailing-dot-notes\n")
        _write(root / "readme.txt.", "trailing-dot-readme\n")
        notes.append("Linux preserves trailing dots; Win32 would strip them.")
    else:
        raise ValueError(f"unknown class {class_id}")
    rels = oracle_list(root)
    hashes = oracle_hashes(root)
    longest = max((len(r) for r in rels), default=0)
    return {
        "class_id": class_id,
        "root": str(root),
        "expected_rels": rels,
        "expected_count": len(rels),
        "expected_sha256": hashes,
        "longest_rel": longest,
        "exceeds_max_path": longest > MAX_PATH,
        "notes": notes,
    }


def build_fixture_forest(base: Path) -> dict[str, dict[str, Any]]:
    forest: dict[str, dict[str, Any]] = {}
    for class_id in ALL_CLASSES:
        forest[class_id] = build_class_tree(base / class_id, class_id)
    return forest


def classify_outcome(
    *,
    expected_count: int,
    reported_count: int,
    expected_rels: list[str] | None = None,
    reported_rels: list[str] | None = None,
    expected_sha: dict[str, str] | None = None,
    reported_sha: dict[str, str] | None = None,
    exception: str | None,
    aborted: bool,
    errors: list[str] | None,
    explicit_refusal: bool = False,
    swallowed_zero: bool = False,
) -> str:
    """Closed set: correct | crash | silent_skip | wrong_result | explicit_refusal | swallowed_zero."""
    if explicit_refusal:
        return "explicit_refusal"
    if swallowed_zero:
        return "swallowed_zero"
    if exception and aborted:
        return "crash"
    if exception and reported_count == 0 and not errors:
        return "swallowed_zero"
    if exception:
        return "crash"
    if reported_count == expected_count:
        if expected_rels is not None and reported_rels is not None:
            if sorted(reported_rels) != sorted(expected_rels):
                return "wrong_result"
        if expected_sha and reported_sha:
            for rel, digest in expected_sha.items():
                if reported_sha.get(rel) != digest:
                    return "wrong_result"
        return "correct"
    if reported_count < expected_count and not exception:
        return "silent_skip"
    return "wrong_result"


def outcome_to_verdict(outcome: str) -> str:
    """Hypothesis: component fails/corrupts/silently-skips on this class."""
    if outcome == "correct":
        return "REFUTED"
    if outcome in {"silent_skip", "wrong_result", "crash", "swallowed_zero"}:
        return "CONFIRMED"
    if outcome == "explicit_refusal":
        return "REFUTED"
    return "PARTIAL"


def _capture(fn: Callable[[], Any]) -> tuple[Any, str | None]:
    try:
        return fn(), None
    except Exception as exc:  # noqa: BLE001 — classify, do not swallow as zero
        return None, f"{type(exc).__name__}:{exc}"


def run_enumerator(root: Path) -> dict[str, Any]:
    result, err = _capture(lambda: walk_files(root))
    if err or result is None:
        return {
            "component": "enumerator",
            "reported_count": 0,
            "rels": [],
            "errors": [err or "none"],
            "aborted": True,
            "exception": err,
            "source": "tools.router.index_build.walk_files",
        }
    rels = sorted({posix(f.rel) for f in result.files})
    return {
        "component": "enumerator",
        "reported_count": int(result.file_count),
        "rels": rels,
        "errors": list(result.errors),
        "aborted": bool(result.aborted),
        "exception": None,
        "status": result.status,
        "source": "tools.router.index_build.walk_files",
    }


def run_packager(root: Path) -> dict[str, Any]:
    """Stdlib zip of every regular file found by pathlib rglob (program packager shape)."""

    def _pack() -> tuple[list[str], int]:
        members: list[str] = []
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(root.rglob("*")):
                if not path.is_file() or path.is_symlink():
                    continue
                rel = path.relative_to(root).as_posix()
                zf.write(path, arcname=rel)
                members.append(rel)
        return sorted(members), len(buf.getvalue())

    packed, err = _capture(_pack)
    if err or packed is None:
        return {
            "component": "packager",
            "reported_count": 0,
            "rels": [],
            "errors": [err or "none"],
            "aborted": True,
            "exception": err,
            "source": "zipfile.ZipFile.write + Path.rglob",
        }
    members, nbytes = packed
    return {
        "component": "packager",
        "reported_count": len(members),
        "rels": members,
        "errors": [],
        "aborted": False,
        "exception": None,
        "zip_bytes": nbytes,
        "source": "zipfile.ZipFile.write + Path.rglob",
    }


def run_installer(root: Path) -> dict[str, Any]:
    """Production tree copy used by plugin rollback/install restore."""

    def _install() -> list[str]:
        dest = Path(tempfile.mkdtemp(prefix="adv0117-install-"))
        try:
            written = plugin_own._copy_tree_files(root, dest)
            return sorted(posix(r) for r in written)
        finally:
            shutil.rmtree(dest, ignore_errors=True)

    written, err = _capture(_install)
    if err or written is None:
        return {
            "component": "installer",
            "reported_count": 0,
            "rels": [],
            "errors": [err or "none"],
            "aborted": True,
            "exception": err,
            "source": "tools.plugin.cache_ownership._copy_tree_files",
        }
    return {
        "component": "installer",
        "reported_count": len(written),
        "rels": written,
        "errors": [],
        "aborted": False,
        "exception": None,
        "source": "tools.plugin.cache_ownership._copy_tree_files",
    }


def run_hasher(root: Path) -> dict[str, Any]:
    def _hash() -> tuple[dict[str, str], dict[str, str]]:
        market = marketplace_census.census(root)
        layout = {row["path"]: row["sha256"] for row in layout_migrate.census(root)}
        return market, layout

    hashed, err = _capture(_hash)
    if err or hashed is None:
        return {
            "component": "manifest-hasher",
            "reported_count": 0,
            "rels": [],
            "sha256": {},
            "errors": [err or "none"],
            "aborted": True,
            "exception": err,
            "source": "tools.marketplace.census + tools.layout.migrate.census",
        }
    market, layout = hashed
    rels = sorted(set(market) | set(layout))
    disagree = sorted(k for k in set(market) | set(layout) if market.get(k) != layout.get(k))
    return {
        "component": "manifest-hasher",
        "reported_count": len(market),
        "rels": sorted(market),
        "sha256": dict(market),
        "layout_count": len(layout),
        "layout_rels": sorted(layout),
        "hasher_disagreement": disagree,
        "errors": [],
        "aborted": False,
        "exception": None,
        "source": "tools.marketplace.census + tools.layout.migrate.census",
    }


WRITER_EXTRA = {
    "ordinary": "receipt.json",
    "reserved-device": "AUX",
    "long-path": "receipt.json",
    "case-collision": "README.TXT",
    "spaces": "writer receipt.json",
    "unicode": "ünicode-receipt.json",
    "trailing-dot": "receipt.json.",
}


def run_writer(root: Path, class_id: str) -> dict[str, Any]:
    attempted: list[str] = ["ownership-manifest.json"]
    written: list[str] = []
    errors: list[str] = []
    exception = None
    extra = WRITER_EXTRA[class_id]
    attempted.append(extra)

    dest, err = _capture(lambda: plugin_own.write_manifest(root))
    if err or dest is None:
        exception = err
        errors.append(err or "write_manifest")
    else:
        written.append(posix(dest.relative_to(root).as_posix()))

    extra_path = root / extra

    def _extra() -> None:
        extra_path.parent.mkdir(parents=True, exist_ok=True)
        extra_path.write_text(
            json.dumps({"unit_id": UID, "class_id": class_id}, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    _, extra_err = _capture(_extra)
    if extra_err:
        errors.append(extra_err)
        if exception is None:
            exception = extra_err
    else:
        written.append(posix(extra))

    parseable = False
    if extra_path.is_file():
        try:
            json.loads(extra_path.read_text(encoding="utf-8"))
            parseable = True
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            parseable = False

    return {
        "component": "artifact-writer",
        "reported_count": len(written),
        "attempted_count": len(attempted),
        "rels": sorted(written),
        "attempted": attempted,
        "errors": errors,
        "aborted": bool(exception) and not written,
        "exception": exception,
        "extra_parseable": parseable,
        "source": "tools.plugin.cache_ownership.write_manifest + Path.write_text",
    }


def naive_relpath_walk(root: Path) -> list[str]:
    files: list[str] = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, str(root))
            files.append(posix(rel))
    return files


def swallowing_zero_walk(root: Path) -> dict[str, Any]:
    """Defect class: crash rewritten as count=0 with an empty error list."""
    try:
        files = naive_relpath_walk(root)
        return {"count": len(files), "rels": files, "swallowed": False, "exception": None}
    except Exception as exc:  # noqa: BLE001
        return {
            "count": 0,
            "rels": [],
            "swallowed": True,
            "exception": f"{type(exc).__name__}:{exc}",
        }


def mutant_casefold_hasher(root: Path) -> dict[str, str]:
    """Bad hasher: casefold keys silently drop a case-only sibling."""
    out: dict[str, str] = {}
    for rel, digest in marketplace_census.census(root).items():
        out[rel.casefold()] = digest
    return out


def run_component(name: str, root: Path, class_id: str) -> dict[str, Any]:
    if name == "enumerator":
        return run_enumerator(root)
    if name == "packager":
        return run_packager(root)
    if name == "installer":
        return run_installer(root)
    if name == "artifact-writer":
        return run_writer(root, class_id)
    if name == "manifest-hasher":
        return run_hasher(root)
    raise ValueError(name)


def run_component_isolated(name: str, src_root: Path, class_id: str) -> dict[str, Any]:
    """Copy the class tree so writers cannot pollute hasher/enumerator counts."""
    tmp = Path(tempfile.mkdtemp(prefix="adv0117-comp-"))
    try:
        dest = tmp / "tree"
        shutil.copytree(src_root, dest)
        return run_component(name, dest, class_id)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def copy_tree(src: Path, dest: Path) -> None:
    shutil.copytree(src, dest)


def platform_info() -> dict[str, Any]:
    return {
        "system": platform.system(),
        "release": platform.release(),
        "python": platform.python_version(),
        "windows_createfile_executed": False,
        "extended_length_prefix": "\\\\?\\",
        "max_path": MAX_PATH,
        "note": (
            "Linux substrate: reserved names are POSIX files. Win32 CreateFile "
            "and the \\\\?\\ prefix are recorded as path-shape, not executed."
        ),
    }
