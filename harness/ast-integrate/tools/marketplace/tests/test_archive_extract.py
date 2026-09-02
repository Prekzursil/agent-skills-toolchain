"""Unit tests for contained archive extraction."""
from __future__ import annotations

import io
import tarfile
import tempfile
import unittest
from pathlib import Path

from tools.marketplace.archive_extract import (
    ArchiveExtractError,
    census_files,
    extract_import_archive,
    normalize_member_name,
)


def _tar(members: list[tuple[str, bytes]]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        for name, payload in members:
            info = tarfile.TarInfo(name=name)
            info.size = len(payload)
            tf.addfile(info, io.BytesIO(payload))
    return buf.getvalue()


class NormalizeTests(unittest.TestCase):
    def test_nested_dotdot_raises_traversal(self) -> None:
        with self.assertRaises(ArchiveExtractError) as ctx:
            normalize_member_name("pkg/../../escape.beacon")
        self.assertEqual(ctx.exception.code, "TRAVERSAL")

    def test_relative_dotdot_raises(self) -> None:
        with self.assertRaises(ArchiveExtractError) as ctx:
            normalize_member_name("../escape.beacon")
        self.assertEqual(ctx.exception.code, "TRAVERSAL")

    def test_device_con(self) -> None:
        with self.assertRaises(ArchiveExtractError) as ctx:
            normalize_member_name("CON")
        self.assertEqual(ctx.exception.code, "DEVICE_NAME")

    def test_benign_kept(self) -> None:
        self.assertEqual(normalize_member_name("pkg/manifest.json"), "pkg/manifest.json")


class ExtractMatrixTests(unittest.TestCase):
    def test_benign_lands_inside(self) -> None:
        blob = _tar(
            [
                ("pkg/manifest.json", b'{"name":"ok"}'),
                ("pkg/payload.txt", b"hello-benign"),
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "root"
            report = extract_import_archive(blob, dest)
            self.assertTrue(report.ok)
            self.assertEqual(census_files(dest), ["pkg/manifest.json", "pkg/payload.txt"])

    def test_traversal_rejected(self) -> None:
        blob = _tar([("../escape.beacon", b"TRAVERSAL")])
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "root"
            report = extract_import_archive(blob, dest)
            self.assertFalse(report.ok)
            self.assertTrue(report.rejected)
            self.assertEqual(census_files(dest), [])
