"""Deterministic zip packager for ADV-0062 rebuild comparison.

Member bytes come from a path->bytes map so the output directory is not
embedded. SOURCE_DATE_EPOCH, member order, and zlib compresslevel are the
recorded toolchain knobs.
"""
from __future__ import annotations

import hashlib
import io
import json
import time
import zipfile
import zlib
from pathlib import Path
from typing import Iterable, Mapping

CANONICAL_EPOCH = 1_700_000_000
CANONICAL_LEVEL = 6
CANONICAL_ORDER = "sorted"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def epoch_tuple(epoch: int) -> tuple[int, int, int, int, int, int]:
    t = time.gmtime(int(epoch))
    year = max(1980, t.tm_year)
    return (year, t.tm_mon, t.tm_mday, t.tm_hour, t.tm_min, t.tm_sec)


def ordered_names(names: Iterable[str], order: str) -> list[str]:
    items = list(names)
    if order == "reverse":
        return sorted(items, reverse=True)
    if order == "as-given":
        return items
    return sorted(items)


def write_zip(
    members: Mapping[str, bytes],
    *,
    epoch: int = CANONICAL_EPOCH,
    compresslevel: int = CANONICAL_LEVEL,
    order: str = CANONICAL_ORDER,
) -> bytes:
    buf = io.BytesIO()
    dt = epoch_tuple(epoch)
    with zipfile.ZipFile(
        buf,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=int(compresslevel),
        allowZip64=False,
    ) as zf:
        for name in ordered_names(members.keys(), order):
            info = zipfile.ZipInfo(filename=name.replace("\\", "/"), date_time=dt)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.create_version = 20
            info.extract_version = 20
            info.external_attr = 0o100644 << 16
            info.comment = b""
            info.extra = b""
            zf.writestr(info, members[name], compress_type=zipfile.ZIP_DEFLATED)
    return buf.getvalue()


def dump_zip(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def source_revision(members: Mapping[str, bytes]) -> str:
    rows = {k.replace("\\", "/"): sha256_bytes(v) for k, v in members.items()}
    blob = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(blob)


def toolchain(*, epoch: int, compresslevel: int, order: str) -> dict:
    return {
        "language": "python",
        "python_version": __import__("sys").version.split()[0],
        "zlib_version": zlib.ZLIB_VERSION,
        "zipfile_module": "stdlib.zipfile.ZIP_DEFLATED",
        "compresslevel": int(compresslevel),
        "source_date_epoch": int(epoch),
        "member_order": order,
        "create_system": 3,
        "external_attr": "0100644",
        "timestamp_basis": "ZipInfo.date_time from SOURCE_DATE_EPOCH via time.gmtime",
    }


def member_table(data: bytes) -> list[dict]:
    rows = []
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for info in zf.infolist():
            raw = zf.read(info.filename)
            rows.append(
                {
                    "name": info.filename,
                    "crc": info.CRC,
                    "file_size": info.file_size,
                    "compress_size": info.compress_size,
                    "compress_type": info.compress_type,
                    "date_time": list(info.date_time),
                    "content_sha256": sha256_bytes(raw),
                    "deflate_sha256": None,
                }
            )
    # Per-member deflate stream: reconstruct from the central/local records
    # by re-reading the ZipInfo compressed payload via ZipExtFile is not
    # exposed; compare compress_size + CRC + content instead, plus whole-archive
    # sha256 which includes every deflate stream.
    return rows


def compare_archives(left: bytes, right: bytes) -> dict:
    left_sha = sha256_bytes(left)
    right_sha = sha256_bytes(right)
    identical = left_sha == right_sha
    lt = member_table(left)
    rt = member_table(right)
    lnames = [r["name"] for r in lt]
    rnames = [r["name"] for r in rt]
    left_by = {r["name"]: r for r in lt}
    right_by = {r["name"]: r for r in rt}
    only_left = sorted(set(lnames) - set(rnames))
    only_right = sorted(set(rnames) - set(lnames))
    content_diffs = []
    for name in sorted(set(lnames) & set(rnames)):
        a, b = left_by[name], right_by[name]
        if a["content_sha256"] != b["content_sha256"]:
            content_diffs.append(
                {
                    "name": name,
                    "cause_class": "member-content",
                    "left_sha256": a["content_sha256"],
                    "right_sha256": b["content_sha256"],
                }
            )
        elif a["compress_size"] != b["compress_size"] or a["crc"] != b["crc"]:
            content_diffs.append(
                {
                    "name": name,
                    "cause_class": "deflate-stream",
                    "left_compress_size": a["compress_size"],
                    "right_compress_size": b["compress_size"],
                }
            )
        elif a["date_time"] != b["date_time"]:
            content_diffs.append(
                {
                    "name": name,
                    "cause_class": "embedded-timestamp",
                    "left_date_time": a["date_time"],
                    "right_date_time": b["date_time"],
                }
            )
    order_differs = lnames != rnames
    return {
        "byte_identical": identical,
        "left_sha256": left_sha,
        "right_sha256": right_sha,
        "left_bytes": len(left),
        "right_bytes": len(right),
        "member_count_left": len(lt),
        "member_count_right": len(rt),
        "member_order_differs": order_differs,
        "only_left": only_left,
        "only_right": only_right,
        "differing_members": content_diffs,
        "left_member_order": lnames,
        "right_member_order": rnames,
    }
