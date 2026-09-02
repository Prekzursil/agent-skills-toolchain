"""Fixture table for IMP-0168. Paths are relative to this probe directory."""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"

# (adapter, filename, planted_inexpressible_kinds, expect_empty_ledger)
FIXTURE_ROWS: tuple[tuple[str, str, frozenset[str], bool], ...] = (
    ("claude_mjs", "claude_clean.mjs", frozenset(), True),
    (
        "claude_mjs",
        "claude_inexpressible.mjs",
        frozenset({"background_fire_forget", "eval_call"}),
        False,
    ),
    ("codex_json", "codex_clean.json", frozenset(), True),
    (
        "codex_json",
        "codex_inexpressible.json",
        frozenset({"background_fire_forget"}),
        False,
    ),
    ("dag_json", "dag_clean.json", frozenset(), True),
    (
        "dag_json",
        "dag_inexpressible.json",
        frozenset({"native_while"}),
        False,
    ),
)


def fixture_path(name: str) -> Path:
    return FIXTURES / name
