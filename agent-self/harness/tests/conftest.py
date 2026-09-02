from __future__ import annotations

import sys
from pathlib import Path

import pytest


AGENTS_ROOT = Path(__file__).resolve().parents[2]
if str(AGENTS_ROOT) not in sys.path:  # pragma: no cover
    sys.path.insert(0, str(AGENTS_ROOT))


@pytest.fixture(autouse=True)
def isolate_basic_memory_vault(tmp_path, monkeypatch):
    """RecallModule records a vault root; tests must never point it at the live
    D:/basic-memory tree (defence in depth — the module never walks the vault,
    which test_recall_vault_digest_never_rglobs_vault_markdown pins)."""
    vault = tmp_path / "_isolated_bm_vault"
    vault.mkdir()
    monkeypatch.setenv("BASIC_MEMORY_VAULT", str(vault))
