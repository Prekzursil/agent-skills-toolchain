#!/usr/bin/env python3
"""Live crafted-archive matrix through the marketplace import path."""
from __future__ import annotations

import io
import json
import os
import platform
import sys
import tarfile
import tempfile
import warnings
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.marketplace.archive_extract import (  # noqa: E402
    census_files,
)
from tools.marketplace.offline_import import (  # noqa: E402
    import_offline_bundle_archive,
)


def _tar_bytes(members: list[tuple[str, bytes | None, str]]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        for name, payload, kind in members:
            info = tarfile.TarInfo(name=name)
            if kind == "sym":
                info.type = tarfile.SYMTYPE
                info.linkname = (
                    payload.decode("utf-8") if isinstance(payload, bytes) else str(payload)
                )
                tf.addfile(info)
            elif kind == "lnk":
                info.type = tarfile.LNKTYPE
                info.linkname = (
                    payload.decode("utf-8") if isinstance(payload, bytes) else str(payload)
                )
                tf.addfile(info)
            else:
                data = payload or b""
                info.size = len(data)
                tf.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def craft_ratio_bomb_zip(
    name: str = "bomb.bin",
    declared_uncompressed: int = 2_000_000,
    payload: bytes = b"\x00" * 200,
) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(name, payload)
    raw = bytearray(buf.getvalue())
    declared = declared_uncompressed.to_bytes(4, "little")
    idx = 0
    while True:
        loc = raw.find(b"PK\x03\x04", idx)
        if loc < 0:
            break
        raw[loc + 22 : loc + 26] = declared
        idx = loc + 4
    idx = 0
    while True:
        cen = raw.find(b"PK\x01\x02", idx)
        if cen < 0:
            break
        raw[cen + 24 : cen + 28] = declared
        idx = cen + 4
    return bytes(raw)


def _outside_files(sandbox: Path, dest: Path) -> list[str]:
    found: list[str] = []
    for path in sandbox.rglob("*"):
        if not (path.is_file() or path.is_symlink()):
            continue
        try:
            # Resolve both sides: on Windows the rglob path may carry the 8.3
            # short temp-name while resolve() returns the long form, which
            # made every inside file look 'outside'.
            path.resolve().relative_to(dest.resolve())
        except ValueError:
            found.append(str(path))
    return sorted(found)


def _run_one(sandbox: Path, dest: Path, blob: bytes, label: str) -> dict:
    dest.mkdir(parents=True, exist_ok=True)
    before_out = set(_outside_files(sandbox, dest))
    report = import_offline_bundle_archive(blob, dest)
    after_out = set(_outside_files(sandbox, dest))
    new_out = sorted(after_out - before_out)
    inside = census_files(dest)
    return {
        "label": label,
        "ok": report.ok,
        "error": report.error,
        "rejected": report.rejected,
        "written": report.written,
        "inside": inside,
        "outside_new": new_out,
        "escaped": bool(new_out),
    }


def run_matrix() -> dict:
    """Execute the catalog member matrix in an isolated sandbox."""
    with tempfile.TemporaryDirectory(prefix="adv0027-matrix-") as tmp:
        sandbox = Path(tmp)
        dest = sandbox / "extract-root"
        dest.mkdir()

        benign = _run_one(
            sandbox,
            dest / "benign",
            _tar_bytes(
                [
                    ("pkg/manifest.json", b'{"name":"ok"}', "reg"),
                    ("pkg/payload.txt", b"hello-benign", "reg"),
                ]
            ),
            "control-benign",
        )

        rel = _run_one(
            sandbox,
            dest / "rel",
            _tar_bytes([("../escape.beacon", b"TRAVERSAL", "reg")]),
            "relative-traversal",
        )
        nested = _run_one(
            sandbox,
            dest / "nested",
            _tar_bytes([("pkg/../../nested-escape.beacon", b"NEST", "reg")]),
            "nested-dotdot",
        )
        abs_path = sandbox / "abs.beacon"
        absolute = _run_one(
            sandbox,
            dest / "abs",
            _tar_bytes([(str(abs_path), b"ABS", "reg")]),
            "absolute-path",
        )
        symlink = _run_one(
            sandbox,
            dest / "sym",
            _tar_bytes([("link", b"../outside.beacon", "sym")]),
            "external-symlink",
        )
        outside = sandbox / "hardlink-target.txt"
        outside.write_text("OUT", encoding="utf-8")
        hardlink = _run_one(
            sandbox,
            dest / "lnk",
            _tar_bytes([("linked.txt", str(outside).encode("utf-8"), "lnk")]),
            "hardlink",
        )
        device = _run_one(
            sandbox,
            dest / "dev",
            _tar_bytes([("CON", b"device", "reg")]),
            "device-con",
        )
        device_nul = _run_one(
            sandbox,
            dest / "nul",
            _tar_bytes([("NUL", b"nul", "reg")]),
            "device-nul",
        )
        bomb_blob = craft_ratio_bomb_zip()
        with zipfile.ZipFile(io.BytesIO(bomb_blob)) as zf:
            info = zf.getinfo("bomb.bin")
            ratio = info.file_size / max(info.compress_size, 1)
        ratio_row = _run_one(
            sandbox,
            dest / "ratio",
            bomb_blob,
            "compression-ratio",
        )

        naive_dest = dest / "naive"
        naive_dest.mkdir()
        naive_blob = _tar_bytes([("../naive.beacon", b"RED", "reg")])
        naive_filter_refused = False
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            with tarfile.open(fileobj=io.BytesIO(naive_blob), mode="r:") as tf:
                try:
                    tf.extractall(naive_dest)
                except tarfile.FilterError:
                    # python >= 3.14: the 'data' filter is the DEFAULT and
                    # refuses ../ members. Record this world explicitly; the
                    # naive bad state is unrepresentable on this runtime.
                    naive_filter_refused = True
        naive_landed = (dest / "naive.beacon").is_file()
        naive_body = (
            (dest / "naive.beacon").read_bytes() if naive_landed else b""
        )
        naive_import = import_offline_bundle_archive(naive_blob, dest / "naive-import")
        naive_import_inside = census_files(dest / "naive-import")
        naive_import_closed = naive_import.ok is False and naive_import_inside == []

        benign_ok = (
            benign["ok"] is True
            and benign["inside"] == ["pkg/manifest.json", "pkg/payload.txt"]
            and not benign["escaped"]
        )
        attacks = {
            "T1-relative-traversal": rel,
            "T2-absolute-path": absolute,
            "T3-external-symlink": symlink,
            "T4-hardlink": hardlink,
            "T5-device-name": device,
            "T6-compression-ratio": ratio_row,
        }
        nested_ok = nested["ok"] is False and not nested["escaped"]
        nul_ok = device_nul["ok"] is False and not device_nul["escaped"]
        all_refuted = all(
            row["ok"] is False and not row["escaped"] and not row["written"]
            for row in attacks.values()
        )
        naive_red = naive_landed and naive_body == b"RED"

        targets = []
        for tid, row in attacks.items():
            escaped = row["escaped"]
            verdict = "CONFIRMED" if escaped or row["ok"] else "REFUTED"
            if row["ok"] and not escaped:
                # Accepted into dest (sanitise-and-write) is still accept.
                verdict = "CONFIRMED"
            if not row["ok"] and not escaped:
                verdict = "REFUTED"
            targets.append(
                {
                    "id": tid,
                    "verdict": verdict,
                    "import_ok": row["ok"],
                    "escaped": escaped,
                    "written": row["written"],
                    "outside_new": row["outside_new"],
                    "rejected": row["rejected"],
                    "error": row["error"],
                    "lands": (
                        "outside-root" if escaped else ("inside-root" if row["written"] else "nowhere")
                    ),
                }
            )
        # Nested bypass of pre-normalisation startswith('..') is the same T1 class.
        targets.append(
            {
                "id": "T1b-nested-dotdot-pre-normalize-bypass",
                "verdict": "REFUTED" if nested_ok else "CONFIRMED",
                "import_ok": nested["ok"],
                "escaped": nested["escaped"],
                "written": nested["written"],
                "outside_new": nested["outside_new"],
                "rejected": nested["rejected"],
                "error": nested["error"],
                "lands": "nowhere" if nested_ok else "escaped-or-accepted",
                "note": "pkg/../../escape bypasses startswith('..'); post-normpath rejects it.",
            }
        )

        passed = (
            benign_ok
            and all_refuted
            and nested_ok
            and nul_ok
            and (naive_red or (naive_filter_refused and naive_import_closed))
            and naive_import_closed
            and ratio > 10000.0
        )
        return {
            "pass": passed,
            "platform": {
                "system": platform.system(),
                "release": platform.release(),
                "python": platform.python_version(),
            },
            "benign": benign,
            "nested": nested,
            "device_nul": device_nul,
            "ratio_observed": ratio,
            "ratio_file_size": info.file_size,
            "ratio_compress_size": info.compress_size,
            "naive_tar_extractall_landed_outside": naive_red,
            "naive_tar_extractall_refused_by_stdlib_filter": naive_filter_refused,
            "naive_beacon_bytes": len(naive_body),
            "naive_import_fail_closed": naive_import_closed,
            "targets": targets,
            "tests": [
                {
                    "id": "T-CONTROL-BENIGN-ARCHIVE",
                    "result": "PASS" if benign_ok else "FAIL",
                    "command": "tools.marketplace.offline_import.import_offline_bundle_archive (in-process matrix run)",
                    "output_tail": "written inside dest: " + json.dumps(benign["inside"]),
                },
                {
                    "id": "T-DEVICE-NAME-EXPLICIT",
                    "result": "PASS" if (not device["ok"] and not device["escaped"]) else "FAIL",
                    "command": "tools.marketplace.offline_import.import_offline_bundle_archive (in-process matrix run)",
                    "output_tail": json.dumps(
                        {
                            "handling": "EXPLICIT-REJECT",
                            "crash": False,
                            "platform": platform.system(),
                            "note": (
                                "Linux will create a regular file named CON; an unhandled "
                                "open is not a crash here. The import path rejects DEVICE_NAME "
                                "before any create, which is distinct from a successful traversal."
                            ),
                        }
                    ),
                },
            ],
            "negative_controls": [
                {
                    "id": "NC-NESTED-DOTDOT-BYPASS",
                    "kind": "adversarial-payload",
                    "description": (
                        "pkg/../../escape.beacon bypasses a naive "
                        "startswith('..') pre-normalisation check. The production "
                        "import path must reject it post-normpath while the benign "
                        "control still extracts. Fires on every python: the "
                        "crafted adversarial member is runtime-independent, unlike "
                        "the stdlib-naive extractall world (py < 3.12 only), which "
                        "is recorded in naive_tar_extractall_* fields and the "
                        "residual_unknowns entry instead."
                    ),
                    "fired_on_bad_state": nested_ok,
                    "silent_on_good_state": benign_ok,
                    "bad_state_output": json.dumps(
                        {
                            "bypass_member": "pkg/../../escape.beacon",
                            "import_ok": nested["ok"],
                            "escaped": nested["escaped"],
                            "written": nested["written"],
                            "rejected": nested["rejected"],
                        }
                    ),
                }
            ],
            "sandbox_cleaned": True,
            "host_pid": os.getpid(),
        }
