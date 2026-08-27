from __future__ import annotations

import importlib.util
import pathlib
import sqlite3
import sys
import uuid


SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "cleanup_stale_codex_threads.py"
SPEC = importlib.util.spec_from_file_location("cleanup_stale_codex_threads", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
cleanup = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = cleanup
SPEC.loader.exec_module(cleanup)


def test_only_missing_rollouts_inside_codex_session_roots_are_candidates(
    tmp_path: pathlib.Path,
) -> None:
    codex_home = tmp_path / ".codex"
    sessions = codex_home / "sessions"
    sessions.mkdir(parents=True)
    existing = sessions / "existing.jsonl"
    existing.write_text("{}\n", encoding="utf-8")
    database = codex_home / "state_5.sqlite"
    connection = sqlite3.connect(database)
    connection.execute(
        "CREATE TABLE threads (id TEXT, rollout_path TEXT, created_at INTEGER)"
    )
    missing_id = str(uuid.uuid4())
    extended_missing_id = str(uuid.uuid4())
    extended_missing = "\\\\?\\" + str(sessions / "extended-missing.jsonl")
    rows = [
        (missing_id, str(sessions / "missing.jsonl"), 1),
        (extended_missing_id, extended_missing, 2),
        (str(uuid.uuid4()), str(existing), 3),
        (str(uuid.uuid4()), str(tmp_path / "outside.jsonl"), 4),
        ("not-a-uuid", str(sessions / "also-missing.jsonl"), 5),
    ]
    connection.executemany("INSERT INTO threads VALUES (?, ?, ?)", rows)
    connection.commit()
    connection.close()

    stale = cleanup.find_stale_threads(database, codex_home)

    assert [item.session_id for item in stale] == [missing_id, extended_missing_id]
