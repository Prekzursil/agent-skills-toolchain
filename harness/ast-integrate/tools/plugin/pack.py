"""Allowlist packer CLI + library (IMP-0001 / harvested plugin.pack names)."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tarfile
import unicodedata
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
DEFAULT_ALLOWLIST = HERE / "payload-allowlist.json"
COMPRESSION_LEVEL = 6
NORMALISATION = "lf"

from payload_allowlist import (  # noqa: E402
    _posix,
    glob_to_re,
    is_allowlisted,
    load_allowlist,
    pack_repo as _pack_repo,
    plant_negative_staging,
    select_pairs,
)


def nfc_casefold(path: str) -> str:
    text = str(path).replace("\\", "/").strip().lstrip("./")
    return unicodedata.normalize("NFC", text).casefold()


def collision_groups(paths: list[str]) -> list[list[str]]:
    buckets: dict[str, list[str]] = {}
    for raw in paths:
        key = nfc_casefold(raw)
        buckets.setdefault(key, []).append(raw)
    return [v for v in buckets.values() if len(v) >= 2]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


SHELL_SUFFIXES = (".sh",)


def is_shell_member(rel: str) -> bool:
    return _posix(rel).lower().endswith(SHELL_SUFFIXES)


def cr_shell_members(blobs: dict[str, bytes]) -> list[str]:
    """Shipped ``*.sh`` members whose bytes carry a CR (0x0D); sorted, posix."""
    return sorted(rel for rel, data in blobs.items() if is_shell_member(rel) and b"\r" in data)


def crlf_refusal_message(bad: list[str], where: str = "shipped *.sh blob(s)") -> str:
    return f"CR (0x0D) in {where}: {', '.join(bad)}"


def _is_object_id(token: str) -> bool:
    """True for a full SHA-1 (40) or SHA-256 (64) hex git object id."""
    return len(token) in (40, 64) and all(ch in "0123456789abcdef" for ch in token.lower())


def git_cat_file_blob(repo: Path, rel: str, rev: str = "HEAD") -> bytes:
    """Blob bytes for ``rev:rel``; ``rel`` may also be a blob object id (from ls-tree)."""
    spec = str(rel) if _is_object_id(str(rel)) else f"{rev}:{_posix(rel)}"
    proc = subprocess.run(
        ["git", "-C", str(repo), "cat-file", "-p", spec],
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise FileNotFoundError(rel)
    return proc.stdout


class TreeEntry(str):
    path: str
    sha: str

    def __new__(cls, path: str, sha: str = "") -> "TreeEntry":
        obj = str.__new__(cls, path)
        obj.path = path
        obj.sha = sha
        return obj


def git_ls_tree(repo: Path, rev: str = "HEAD") -> list[TreeEntry]:
    proc = subprocess.run(
        ["git", "-C", str(repo), "ls-tree", "-r", rev],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return []
    rows: list[TreeEntry] = []
    for ln in (proc.stdout or "").splitlines():
        parts = ln.split(None, 3)
        if len(parts) < 4:
            continue
        sha = parts[2]
        path = parts[3]
        if path.startswith("\t"):
            path = path[1:]
        rows.append(TreeEntry(path, sha))
    return rows


def pack_staging(staging: Path, output: Path, doc: dict[str, Any] | None = None) -> dict[str, Any] | int:
    """Pack a staging tree.

    Two call shapes:
    - pack_staging(staging, output, doc=None) — library form, returns dict
    - pack_staging(staging, manifest.json, output.zip) — ADV-0055 probe form, returns 0/1
    """
    staging = Path(staging)
    second = Path(output)
    third = doc
    rc_mode = False
    manifest_files: list[str] | None = None
    if isinstance(third, (str, Path)):
        out_path = Path(third)
        man_path = second
        rc_mode = True
        if man_path.is_file():
            try:
                man = json.loads(man_path.read_text(encoding="utf-8"))
                if isinstance(man, dict) and isinstance(man.get("files"), list):
                    manifest_files = [str(x) for x in man["files"]]
            except Exception:
                manifest_files = None
        cfg = load_allowlist()
        output = out_path
    else:
        output = second
        cfg = third or load_allowlist()
    extras: list[str] = []
    members: list[str] = []
    if manifest_files is not None:
        members = list(manifest_files)
        extras = []
    else:
        for dirpath, dirnames, filenames in os.walk(staging, followlinks=False):
            for name in filenames:
                p = Path(dirpath) / name
                rel = _posix(p.relative_to(staging).as_posix())
                if is_allowlisted(rel, cfg, matcher="a"):
                    members.append(rel)
                else:
                    extras.append(rel)
        extras.sort()
        members.sort()
        if extras:
            print("REFUSED: extras outside allowlist")
            for rel in extras:
                print(rel)
            report = {"ok": False, "extras": extras, "members": members}
            return 1 if rc_mode else report
    staged_shell = {
        rel: (staging / rel).read_bytes()
        for rel in members
        if is_shell_member(rel) and (staging / rel).is_file()
    }
    bad_shell = cr_shell_members(staged_shell)
    if bad_shell:
        message = crlf_refusal_message(bad_shell, "staged *.sh file(s)")
        print(f"REFUSED: {message}")
        report = {
            "ok": False,
            "refused": True,
            "message": message,
            "extras": extras,
            "members": members,
            "crlf_members": bad_shell,
        }
        return 1 if rc_mode else report
    output.parent.mkdir(parents=True, exist_ok=True)
    if str(output).lower().endswith(".zip"):
        import zipfile

        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for rel in members:
                src = staging / rel
                if src.is_file():
                    zf.write(src, arcname=rel)
    else:
        with tarfile.open(output, "w") as tf:
            for rel in members:
                src = staging / rel
                if src.is_file():
                    tf.add(src, arcname=rel)
    report = {"ok": True, "extras": [], "members": members, "archive": str(output)}
    return 0 if rc_mode else report


class PackReport:
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = dict(data)
        self.ok = bool(data.get("ok"))
        self.extras = list(data.get("extras") or [])
        self.members = list(data.get("members") or [])
        self.archive = data.get("archive")
        self.sha256 = str(data.get("sha256") or "")
        self.size = int(data.get("size") or 0)
        self.refused = bool(data.get("refused"))
        self.message = str(data.get("message") or "")
        self.crlf_members = list(data.get("crlf_members") or [])

    def as_dict(self) -> dict[str, Any]:
        return dict(self._data)

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)


class PackResult(PackReport):
    """Alias used by IMP-0002 probes."""


def pack(stage: Path, dest: Path | None = None, **kwargs: Any) -> PackReport:
    if "allowlist" in kwargs:
        return pack_allowlisted(Path(stage), None if dest is None else Path(dest), kwargs["allowlist"])
    dest_path = Path(dest) if dest is not None else Path(kwargs.get("output") or "plugin-pack.tar")
    report = pack_staging(Path(stage), dest_path, kwargs.get("doc"))
    return PackReport(report)


# ----------------------------------------------------------------- TST-0207
# Allowlist-only zip packer: every file under the tree is either named by an
# allowlist glob or reported as an extra; a single extra, or an uncompressed
# payload over the declared ceiling, refuses the pack and emits no archive.


class PackError(ValueError):
    """Allowlist configuration refused before any file is examined."""


class AllowlistPackReport(PackReport):
    """Result of :func:`pack_allowlisted`; ``ok`` only when nothing was left out."""

    def __init__(self, data: dict[str, Any]) -> None:
        super().__init__(data)
        self.reasons = list(data.get("reasons") or [])
        self.extra_paths = list(data.get("extra_paths") or [])
        self.ceiling_exceeded = bool(data.get("ceiling_exceeded"))
        self.uncompressed_bytes = int(data.get("uncompressed_bytes") or 0)
        self.size_ceiling_bytes = int(data.get("size_ceiling_bytes") or 0)
        self.mode = str(data.get("mode") or "")


_UNBOUNDED_GLOBS = {"**", "*", "**/*", "./**", "**/**"}


def _allow_glob_to_re(pattern: str) -> "re.Pattern[str]":
    import re

    parts = pattern.replace("\\", "/").strip("/").split("/")
    out: list[str] = []
    for idx, part in enumerate(parts):
        if part == "**":
            # zero or more whole directories
            out.append("(?:[^/]+/)*" if idx < len(parts) - 1 else "(?:[^/]+/)*[^/]+")
            continue
        seg = ""
        for ch in part:
            if ch == "*":
                seg += "[^/]*"
            elif ch == "?":
                seg += "[^/]"
            else:
                seg += re.escape(ch)
        out.append(seg + ("/" if idx < len(parts) - 1 else ""))
    return re.compile("^" + "".join(out) + "$")


def allowlisted(rel: str, globs: list[str]) -> bool:
    """True when the posix-relative path ``rel`` is named by one of ``globs``."""
    posix = str(rel).replace("\\", "/")
    while posix.startswith("./"):
        posix = posix[2:]
    posix = posix.lstrip("/")
    return any(_allow_glob_to_re(g).match(posix) for g in globs)


def validate_allowlist_config(allowlist: Any) -> dict[str, Any]:
    if not isinstance(allowlist, dict):
        raise PackError("allowlist config must be an object")
    mode = str(allowlist.get("mode") or "").lower()
    if mode != "allowlist":
        raise PackError(
            f"allowlist config mode={mode or 'missing'!r} refused: only mode='allowlist' packs; "
            "a denylist ships every file it forgot to name"
        )
    globs = allowlist.get("globs")
    if not isinstance(globs, list) or not globs or not all(isinstance(g, str) and g.strip() for g in globs):
        raise PackError("allowlist globs must be a non-empty list of strings")
    for g in globs:
        norm = g.replace("\\", "/").strip().strip("/")
        if norm in _UNBOUNDED_GLOBS:
            raise PackError(f"unbounded glob {g!r} refused: the allowlist would become a denylist")
        if ".." in norm.split("/") or g.startswith("/"):
            raise PackError(f"allowlist glob {g!r} escapes the staging root")
    ceiling = allowlist.get("size_ceiling_bytes")
    if not isinstance(ceiling, int) or isinstance(ceiling, bool) or ceiling <= 0:
        raise PackError("size_ceiling_bytes must be a positive integer")
    on_exceed = str(allowlist.get("on_ceiling_exceeded") or "fail")
    if on_exceed != "fail":
        raise PackError(f"on_ceiling_exceeded={on_exceed!r} refused: only 'fail' is a gate")
    return {"mode": mode, "globs": list(globs), "size_ceiling_bytes": int(ceiling), "on_ceiling_exceeded": on_exceed}


def _tree_files(root: Path) -> list[tuple[str, Path]]:
    rows: list[tuple[str, Path]] = []
    for path in root.rglob("*"):
        if path.is_dir() and not path.is_symlink():
            continue
        rows.append((path.relative_to(root).as_posix(), path))
    rows.sort(key=lambda r: r[0])
    return rows


def pack_allowlisted(root: Path, dest: Path | None, allowlist: Any) -> AllowlistPackReport:
    cfg = validate_allowlist_config(allowlist)
    root = Path(root)
    selected: list[tuple[str, Path]] = []
    extras: list[dict[str, Any]] = []
    for rel, path in _tree_files(root):
        if allowlisted(rel, cfg["globs"]):
            selected.append((rel, path))
        else:
            extras.append({"path": rel, "bytes": int(path.lstat().st_size)})
    uncompressed = sum(int(path.stat().st_size) for _rel, path in selected)
    ceiling_exceeded = uncompressed > cfg["size_ceiling_bytes"]
    reasons: list[str] = []
    if extras:
        named = ", ".join(row["path"] for row in extras[:12])
        reasons.append(f"non-allowlisted paths present ({len(extras)}): {named}")
    if ceiling_exceeded:
        reasons.append(
            f"size ceiling exceeded: uncompressed {uncompressed} > {cfg['size_ceiling_bytes']} bytes"
        )
    ok = not reasons
    members = [rel for rel, _ in selected]
    archive: str | None = None
    digest = ""
    size = 0
    if ok and dest is not None:
        import io
        import zipfile

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=COMPRESSION_LEVEL) as zf:
            for rel, path in selected:
                info = zipfile.ZipInfo(rel, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                zf.writestr(info, path.read_bytes())
        data = buf.getvalue()
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        archive = str(dest)
        digest = hashlib.sha256(data).hexdigest()
        size = len(data)
    return AllowlistPackReport(
        {
            "ok": ok,
            "mode": cfg["mode"],
            "policy": "allowlist",
            "members": members,
            "member_count": len(members),
            "extras": [row["path"] for row in extras],
            "extra_paths": extras,
            "reasons": reasons,
            "uncompressed_bytes": uncompressed,
            "size_ceiling_bytes": cfg["size_ceiling_bytes"],
            "ceiling_exceeded": ceiling_exceeded,
            "on_ceiling_exceeded": cfg["on_ceiling_exceeded"],
            "archive": archive,
            "sha256": digest,
            "size": size,
            "refused": not ok,
            "message": "; ".join(reasons),
        }
    )


def independent_zip_members(zip_path: Path) -> list[dict[str, Any]]:
    """Archive listing straight from the zip central directory (not the pack report)."""
    import zipfile

    with zipfile.ZipFile(Path(zip_path)) as zf:
        return [
            {
                "path": info.filename,
                "uncompressed_bytes": int(info.file_size),
                "compressed_bytes": int(info.compress_size),
            }
            for info in zf.infolist()
        ]


def independent_allowlist_expansion(root: Path, globs: list[str]) -> list[str]:
    """Expand ``globs`` with pathlib's own matcher -- independent of :func:`allowlisted`."""
    root = Path(root)
    found: set[str] = set()
    for pattern in globs:
        for path in root.glob(pattern):
            if path.is_file():
                found.add(path.relative_to(root).as_posix())
    return sorted(found)


def pack_repository(
    root: Path,
    output: Path,
    doc: dict[str, Any] | None = None,
    allowlist_path: Path | str | None = None,
) -> PackResult:
    root = Path(root)
    output = Path(output)
    if allowlist_path is not None:
        cfg = load_allowlist(Path(allowlist_path))
    elif doc is not None:
        cfg = doc
    else:
        local = root / "payload-allowlist.json"
        cfg = load_allowlist(local if local.is_file() else None)
    pairs = select_pairs(root, cfg)
    # Read every member from its git blob (git cat-file -p), never the worktree,
    # so CRLF that only lives in a checkout cannot leak into the archive; a *.sh
    # blob that itself carries CR is refused instead of silently normalised.
    blobs: dict[str, bytes] = {}
    for rel, src in pairs:
        try:
            blobs[rel] = git_cat_file_blob(root, rel)
        except FileNotFoundError:
            blobs[rel] = src.read_bytes()
    bad_shell = cr_shell_members(blobs)
    if bad_shell:
        message = crlf_refusal_message(bad_shell)
        print(f"REFUSED: {message}")
        return PackResult(
            {
                "ok": False,
                "refused": True,
                "message": message,
                "members": [],
                "extras": [],
                "crlf_members": bad_shell,
                "archive": None,
            }
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    import io
    import tarfile as _tarfile

    buf = io.BytesIO()
    with _tarfile.open(fileobj=buf, mode="w") as tf:
        for rel, _src in pairs:
            payload = blobs[rel].replace(b"\r\n", b"\n")
            info = _tarfile.TarInfo(name=rel)
            info.size = len(payload)
            info.mtime = 0
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.mode = 0o644
            tf.addfile(info, io.BytesIO(payload))
    data = buf.getvalue()
    output.write_bytes(data)
    members = [rel for rel, _ in pairs]
    digest = hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()
    row = {
        "ok": True,
        "members": members,
        "archive": str(output),
        "sha256": digest,
        "size": len(data),
        "extras": [],
    }
    return PackResult(row)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--staging", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allowlist", type=Path, default=DEFAULT_ALLOWLIST)
    parser.add_argument("--manifest", type=Path, default=None)
    args = parser.parse_args(argv)
    files: list[str] = []
    if args.manifest and args.manifest.is_file():
        man = json.loads(args.manifest.read_text(encoding="utf-8"))
        files = [str(x) for x in (man.get("files") or [])]
        groups = collision_groups(files)
        if groups:
            print("CASEFOLD-COLLISION", file=sys.stderr)
            for group in groups:
                print("colliding paths: " + " ".join(group), file=sys.stderr)
                for p in group:
                    print(p, file=sys.stderr)
            return 2
    if files:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(args.output, "w") as tf:
            for rel in files:
                src = args.staging / rel
                if src.is_file():
                    tf.add(src, arcname=rel)
        return 0
    doc = json.loads(args.allowlist.read_text(encoding="utf-8")) if args.allowlist.is_file() else load_allowlist()
    report = pack_staging(args.staging, args.output, doc)
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
