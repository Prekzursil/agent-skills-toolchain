"""Run the merge contracts against the unpacked CRCP subject tree."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path


def _default_source_root() -> Path:
    # Prefer local package layout: scripts/ → tools/crcp
    here = Path(__file__).resolve()
    local = here.parents[1]
    if (local / "crcp").is_dir():
        return local
    env = os.environ.get("CRCP_SOURCE_ROOT")
    if env:
        return Path(env)
    # Databricks job-node unpack path (merge batch)
    remote = Path("/local_disk0/codexwork/bundle")
    if remote.is_dir():
        return remote
    return local


def configure_import_path() -> Path:
    source_root = Path(os.environ.get("CRCP_SOURCE_ROOT", _default_source_root())).resolve()
    package_dir = source_root / "crcp"
    if not package_dir.is_dir():
        raise FileNotFoundError(
            f"CRCP package directory not found: {package_dir}; "
            "set CRCP_SOURCE_ROOT to the tools/crcp root"
        )
    # The root supports package imports; crcp/ supports legacy flat imports.
    for path in (package_dir, source_root):
        value = str(path)
        if value not in sys.path:
            sys.path.insert(0, value)
    return source_root


def main() -> int:
    configure_import_path()
    # tests live next to package root, not under scripts/
    root = Path(__file__).resolve().parents[1]
    test_dir = root / "tests"
    suite = unittest.defaultTestLoader.discover(
        start_dir=str(test_dir),
        pattern="test_merge_*.py",
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
