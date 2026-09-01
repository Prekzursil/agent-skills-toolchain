from __future__ import annotations

import sys
from pathlib import Path

import pytest


AGENTS_ROOT = Path(__file__).resolve().parents[2]
if str(AGENTS_ROOT) not in sys.path:  # pragma: no cover
    sys.path.insert(0, str(AGENTS_ROOT))


@pytest.fixture(autouse=True)
def isolate_basic_memory_vault(tmp_path, monkeypatch):
    """RecallModule vault digest must not read the live D:/basic-memory tree in tests."""
    vault = tmp_path / "_isolated_bm_vault"
    vault.mkdir()
    monkeypatch.setenv("BASIC_MEMORY_VAULT", str(vault))
