"""Repo-root shim: load production modules from tools/workflow_foundry."""
from pathlib import Path

__path__ = [str(Path(__file__).resolve().parent.parent / "tools" / "workflow_foundry")]
