"""Deterministic packer and unpacker for the distributable artifact.

Determinism rules (IMP-0002, IMP-0011):

* entries are written in sorted payload-relative order;
* every entry carries a fixed timestamp (the zip epoch, 1980-01-01) so two builds of identical
  content are byte-identical;
* text entries are written with LF endings (IMP-0017) — a CRLF working tree must not change the
  archive, which is exactly the class of bug that makes a "reproducible build" check lie;
* external attributes are pinned (0644 / 0755 for declared script entrypoints);
* ``git archive`` is **not** used: on Windows it applies export-time EOL conversion and returns
  CRLF, which is the opposite of the stored blob. Measured on this box in an earlier phase.

Unpacking is containment-checked: a crafted entry name (``../``, absolute, drive-letter, UNC,
reserved device) is refused before any byte lands on disk.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path

from .errors import PluginError
from .fsops import (
    atomic_write_bytes,
    check_relpath,
    looks_binary,
    normalise_eol,
    safe_join,
)
from .manifest import MANIFEST_RELPATH, Manifest, dumps
from .payload import Payload

#: The zip format's minimum representable timestamp. Fixed so builds are reproducible.
ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)

INVENTORY_RELPATH = "PLUGIN-INVENTORY.json"
ALLOWLIST_RELPATH = "PLUGIN-ALLOWLIST.json"


@dataclass
class BuildResult:
    archive: Path
    sha256: str
    size_bytes: int
    file_count: int
    payload_bytes: int
    inventory: dict[str, object]

    def as_dict(self) -> dict[str, object]:
        return {
            "archive": str(self.archive),
            "sha256": self.sha256,
            "archive_bytes": self.size_bytes,
            "entry_count": self.file_count,
            "payload_bytes": self.payload_bytes,
        }


def _normalised_bytes(path: Path) -> bytes:
    data = path.read_bytes()
    return data if looks_binary(data) else normalise_eol(data)


def build_archive(
    payload: Payload,
    manifest: Manifest,
    out_path: Path,
    *,
    allowlist_doc: dict[str, object],
    extra: dict[str, bytes] | None = None,
) -> BuildResult:
    """Write the deterministic archive. Manifest + inventory + allowlist are always included."""
    script_paths = {
        e.path for e in manifest.entrypoints if e.kind in {"script", "hook", "command"}
    }
    members: list[tuple[str, bytes, bool]] = []
    for entry in payload.entries:
        src = payload.root / entry.relpath
        members.append(
            (entry.relpath, _normalised_bytes(src), entry.relpath in script_paths)
        )

    inventory = payload.inventory(name=manifest.name, version=manifest.version)
    members.append((MANIFEST_RELPATH, dumps(manifest).encode("utf-8"), False))
    members.append(
        (
            INVENTORY_RELPATH,
            (json.dumps(inventory, indent=2, sort_keys=True) + "\n").encode(),
            False,
        )
    )
    members.append(
        (
            ALLOWLIST_RELPATH,
            (json.dumps(allowlist_doc, indent=2, sort_keys=True) + "\n").encode(),
            False,
        )
    )
    for rel, blob in sorted((extra or {}).items()):
        members.append((rel, blob, False))

    seen: set[str] = set()
    for rel, _, _ in members:
        check_relpath(rel)
        if rel in seen:
            raise PluginError("E_PAYLOAD", f"duplicate archive member {rel!r}")
        seen.add(rel)
    members.sort(key=lambda m: m[0])

    out_path.parent.mkdir(parents=True, exist_ok=True)
    buf = _write_zip(members)
    atomic_write_bytes(out_path, buf)
    return BuildResult(
        archive=out_path,
        sha256=hashlib.sha256(buf).hexdigest(),
        size_bytes=len(buf),
        file_count=len(members),
        payload_bytes=sum(len(b) for _, b, _ in members),
        inventory=inventory,
    )


def _write_zip(members: list[tuple[str, bytes, bool]]) -> bytes:
    import io

    bio = io.BytesIO()
    with zipfile.ZipFile(
        bio, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as zf:
        for rel, blob, executable in members:
            info = zipfile.ZipInfo(filename=rel, date_time=ZIP_EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = (
                3  # unix, so the mode bits below are meaningful everywhere
            )
            info.external_attr = (0o755 if executable else 0o644) << 16
            zf.writestr(info, blob)
    return bio.getvalue()


def archive_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_member(archive: Path, relpath: str) -> bytes:
    try:
        with zipfile.ZipFile(archive) as zf:
            return zf.read(relpath)
    except KeyError as exc:
        raise PluginError(
            "E_CONFORM", f"archive is missing required member {relpath!r}"
        ) from exc
    except (OSError, zipfile.BadZipFile) as exc:
        raise PluginError("E_CONFORM", f"cannot read {archive}: {exc}") from exc


def list_members(archive: Path) -> list[str]:
    try:
        with zipfile.ZipFile(archive) as zf:
            return sorted(i.filename for i in zf.infolist() if not i.is_dir())
    except (OSError, zipfile.BadZipFile) as exc:
        raise PluginError("E_CONFORM", f"cannot read {archive}: {exc}") from exc


def unpack(archive: Path, dest: Path) -> list[str]:
    """Extract with per-entry containment checks. Returns the extracted relative paths."""
    written: list[str] = []
    try:
        zf = zipfile.ZipFile(archive)
    except (OSError, zipfile.BadZipFile) as exc:
        raise PluginError(
            "E_CONFORM", f"not a readable archive: {archive} ({exc})"
        ) from exc
    with zf:
        for info in sorted(zf.infolist(), key=lambda i: i.filename):
            if info.is_dir():
                continue
            target = safe_join(
                dest, info.filename
            )  # raises E_IO on escape / reserved name
            atomic_write_bytes(target, zf.read(info))
            written.append(info.filename)
    return written
