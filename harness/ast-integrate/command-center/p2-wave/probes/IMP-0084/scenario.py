"""Shared lockfile fixtures for IMP-0084 probes."""
from __future__ import annotations

import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[3] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from marketplace.lockfile import ResolvedPackage  # noqa: E402


def sample_packages() -> list[ResolvedPackage]:
    return [
        ResolvedPackage(
            name="demo-plugin",
            version="1.2.0",
            source_url="mem://demo-plugin/1.2.0",
            blob=b"demo-plugin-payload-v1.2.0\n",
        ),
        ResolvedPackage(
            name="helper-lib",
            version="0.4.1",
            source_url="mem://helper-lib/0.4.1",
            blob=b"helper-lib-payload-v0.4.1\n",
        ),
    ]


def blob_map(packages=None) -> dict[str, bytes]:
    pkgs = packages if packages is not None else sample_packages()
    return {p.source_url: p.blob for p in pkgs}
