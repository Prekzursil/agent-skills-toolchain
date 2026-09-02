"""Live measurement: which ZIP metadata axes break byte-identity for asset packages."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from recipe import (
    DEFINITION_PATH,
    RECIPE_CREATE_SYSTEM,
    RECIPE_DATE,
    RECIPE_MODE,
    normalize_members,
    pack_stored,
    pack_zipfile,
)

HERE = Path(__file__).resolve().parent

CAFE_NFC = "notes/caf\u00e9.md"
CAFE_NFD = "notes/cafe\u0301.md"

CANON = {
    "README.md": b"# asset pack\nhello\n",
    "data.json": b'{"ok": true, "n": 1}\n',
    "scripts/hello.py": b"print('hello')\n",
    CAFE_NFC: b"note: cafe\n",
}

JUNK = {
    ".git/HEAD": b"ref: refs/heads/main\n",
    "__pycache__/hello.cpython-312.pyc": b"\0PYCjunk",
}

AXES = [
    "archive-member-order",
    "mtimes",
    "path-separators",
    "crlf-vs-lf",
    "unicode-path-casing",
    "zip-create-system",
]


def sha256_bytes(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def definition_sha256() -> str:
    return sha256_file(DEFINITION_PATH)


def _packers():
    return (("zipfile-deflate", pack_zipfile), ("stored-struct", pack_stored))


def _naive_linux(members: dict[str, bytes]) -> list[tuple[str, bytes]]:
    return list(members.items())


def _naive_windows(members: dict[str, bytes]) -> list[tuple[str, bytes]]:
    items: list[tuple[str, bytes]] = []
    for name, body in members.items():
        win_name = name.replace("/", "\\")
        if name == CAFE_NFC:
            win_name = CAFE_NFD.replace("/", "\\")
        payload = body.replace(b"\n", b"\r\n")
        items.append((win_name, payload))
    items.reverse()
    return items


def _axis_pair(axis: str):
    base = list(CANON.items())
    kw_a = {
        "date_time": RECIPE_DATE,
        "create_system": RECIPE_CREATE_SYSTEM,
        "external_attr": RECIPE_MODE << 16,
        "normalize": False,
    }
    kw_b = dict(kw_a)
    a = list(base)
    b = list(base)
    if axis == "archive-member-order":
        b = list(reversed(base))
    elif axis == "mtimes":
        kw_b["date_time"] = (2024, 8, 24, 12, 0, 0)
    elif axis == "path-separators":
        b = [(n.replace("/", "\\"), body) for n, body in base]
    elif axis == "crlf-vs-lf":
        b = [(n, body.replace(b"\n", b"\r\n")) for n, body in base]
    elif axis == "unicode-path-casing":
        b = []
        for n, body in base:
            if n == CAFE_NFC:
                b.append((CAFE_NFD, body))
            elif n == "README.md":
                b.append(("Readme.md", body))
            else:
                b.append((n, body))
    elif axis == "zip-create-system":
        kw_b["create_system"] = 0
    else:
        raise KeyError(axis)
    return a, b, kw_a, kw_b


def _digest_pair(packer, a, b, kw_a, kw_b) -> tuple[str, str, bool]:
    extra_a = extra_b = {}
    if packer is pack_zipfile:
        extra_a = {"compresslevel": 9}
        extra_b = {"compresslevel": 9}
    da = sha256_bytes(packer(a, **kw_a, **extra_a))
    db = sha256_bytes(packer(b, **kw_b, **extra_b))
    return da, db, da != db


def measure() -> dict:
    defn_hash = definition_sha256()
    defn = json.loads(DEFINITION_PATH.read_text(encoding="utf-8"))

    per_packer_breaks: dict[str, list[str]] = {}
    axis_rows = []
    for axis in AXES:
        a, b, kw_a, kw_b = _axis_pair(axis)
        row = {"vendor_id": axis, "items": []}
        broke_any = False
        for packer_id, packer in _packers():
            da, db, differ = _digest_pair(packer, a, b, kw_a, kw_b)
            row["items"].append(
                {
                    "packer": packer_id,
                    "digest_a": da,
                    "digest_b": db,
                    "broke_identity": differ,
                }
            )
            per_packer_breaks.setdefault(packer_id, [])
            if differ:
                broke_any = True
                per_packer_breaks[packer_id].append(axis)
        row["broke_identity"] = broke_any
        axis_rows.append(row)

    linux_members = dict(CANON)
    linux_members.update(JUNK)
    win_src = dict(CANON)
    win_src.update(JUNK)
    linux_naive = _naive_linux(linux_members)
    win_naive = _naive_windows(win_src)

    off_linux = pack_zipfile(
        linux_naive,
        date_time=(2026, 1, 15, 8, 30, 0),
        create_system=3,
        external_attr=0o644 << 16,
        normalize=False,
    )
    off_win = pack_zipfile(
        win_naive,
        date_time=(2024, 8, 24, 12, 0, 0),
        create_system=0,
        external_attr=0,
        normalize=False,
    )
    on_linux = pack_zipfile(linux_naive, normalize=True)
    on_win = pack_zipfile(win_naive, normalize=True)
    on_linux_b = pack_stored(linux_naive, normalize=True)
    on_win_b = pack_stored(win_naive, normalize=True)

    recipe_norm = normalize_members(linux_members)
    recipe_norm_win = normalize_members(dict(win_naive))
    hygiene_ok = all(
        not n.startswith(".git/") and "__pycache__" not in n for n, _ in recipe_norm
    )

    pass_a = per_packer_breaks["zipfile-deflate"]
    pass_b = per_packer_breaks["stored-struct"]
    n_a, n_b = len(pass_a), len(pass_b)
    rel = 0.0 if max(n_a, n_b) == 0 else abs(n_a - n_b) / max(n_a, n_b)

    off_l = sha256_bytes(off_linux)
    off_w = sha256_bytes(off_win)
    on_l = sha256_bytes(on_linux)
    on_w = sha256_bytes(on_win)
    on_lb = sha256_bytes(on_linux_b)
    on_wb = sha256_bytes(on_win_b)

    return {
        "definition_id": defn["id"],
        "definition_sha256": defn_hash,
        "definition_locked_hash_before_enumerate": True,
        "window_start": "2026-08-24",
        "window_end": "2026-08-24",
        "window_days": 1,
        "axes": axis_rows,
        "per_packer_breaks": per_packer_breaks,
        "two_pass": {
            "vendor_id": "asset-zip-nondeterminism",
            "pass_a": "zipfile-deflate",
            "pass_b": "stored-struct",
            "pass_a_count": n_a,
            "pass_b_count": n_b,
            "relative_delta": rel,
            "within_10_percent": rel <= 0.10,
            "pass_a_items": pass_a,
            "pass_b_items": pass_b,
        },
        "two_platform": {
            "linux_recipe_off_sha256": off_l,
            "windows_recipe_off_sha256": off_w,
            "linux_recipe_on_sha256": on_l,
            "windows_recipe_on_sha256": on_w,
            "linux_recipe_on_stored_sha256": on_lb,
            "windows_recipe_on_stored_sha256": on_wb,
            "recipe_off_digests_differ": off_l != off_w,
            "recipe_on_zipfile_equal": on_l == on_w,
            "recipe_on_stored_equal": on_lb == on_wb,
            "normalized_names_equal": recipe_norm == recipe_norm_win,
            "normalized_members": [n for n, _ in recipe_norm],
            "host_os": "linux",
            "windows_side": (
                "in-process Windows ZIP/NTFS behavior simulation, not native Win32 zip.exe"
            ),
        },
        "hygiene_excludes_git_and_pyc": hygiene_ok,
        "cafe_nfc": CAFE_NFC,
        "cafe_nfd": CAFE_NFD,
        "maintenance_implication": (
            "Ship asset packages with this pinned ZIP recipe (sorted POSIX NFC "
            "names, LF text, DOS time 1980-01-01, create_system=3, 0o644, no extra, "
            "allowlist suffixes, drop .git/__pycache__). Do not use raw zip -r or "
            "ZipFile.write() of a live tree: mtimes, member order, CRLF, backslashes, "
            "and ZipInfo.create_system (0 on win32, 3 elsewhere) each change the digest. "
            "tools/plugin/pack.py already pins time/order/mode but must also pin "
            "create_system, NFC, and LF to survive a Windows packer."
        ),
    }
