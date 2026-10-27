"""Repo-root shim: load production modules from tools/selfimprove."""
from pathlib import Path

__path__ = [str(Path(__file__).resolve().parent.parent / "tools" / "selfimprove")]
