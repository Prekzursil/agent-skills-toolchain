"""Repo-root shim: load production modules from tools/marketplace."""
from pathlib import Path

__path__ = [str(Path(__file__).resolve().parent.parent / "tools" / "marketplace")]
