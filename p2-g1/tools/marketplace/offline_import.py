"""Offline bundle import that reuses the contained archive extractor."""
from __future__ import annotations

from pathlib import Path

from .archive_extract import ExtractReport, extract_import_archive


def import_offline_bundle_archive(blob: bytes, dest: Path) -> ExtractReport:
    return extract_import_archive(blob, Path(dest))
