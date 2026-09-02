#!/usr/bin/env python3
"""Probe 1: git status porcelain v2 with per-path size and mtime.

Runs git status --porcelain=v2 -uall. The live worktree has no .git; the
enumerator still runs against a fixture git repo holding the planted mutants.
A path listed in porcelain that is missing on disk is bytes=0, mtime=null.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from porcelain import (  # noqa: E402
    attach_size_mtime,
    build_fixture_repo,
    live_git_status,
    parse_porcelain_v2,
)

UNIT = "AUD-0006"
SCHEMA = REPO / "command-center" / "schema" / "audit-inventory.schema.json"


def _fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def schema_discriminates() -> dict:
    from jsonschema import Draft7Validator

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = Draft7Validator(schema)
    garbage = list(validator.iter_errors({"totally": "unrelated", "n": 999999}))
    empty = list(validator.iter_errors({}))
    return {
        "schema_exists": SCHEMA.is_file(),
        "garbage_rejected": len(garbage) > 0,
        "empty_rejected": len(empty) > 0,
        "garbage_error_count": len(garbage),
        "empty_error_count": len(empty),
    }


def main() -> int:
    live = live_git_status(REPO)
    tmp = None
    try:
        tmp, entries, raw, rc = build_fixture_repo()
        paths = [e["path"] for e in entries]
        sized = [e for e in entries if e.get("on_disk") and isinstance(e.get("bytes"), int)]
        has_real = any(p.endswith("real_module.py") for p in paths)
        has_junk = any(p.endswith("session_state.py") for p in paths)
        all_sized = all(
            ("bytes" in e and "mtime" in e) for e in entries
        ) and len(entries) >= 2
        schema = schema_discriminates()
        ok = (
            rc == 0
            and has_real
            and has_junk
            and all_sized
            and len(sized) >= 2
            and schema["garbage_rejected"]
            and schema["empty_rejected"]
            and schema["schema_exists"]
        )
        payload = {
            "pass": bool(ok),
            "probe": "probe1-porcelain",
            "unit_id": UNIT,
            "command": "git status --porcelain=v2 -uall",
            "fixture": {
                "exit_code": rc,
                "path_count": len(entries),
                "paths": paths,
                "all_have_bytes_and_mtime": all_sized,
                "planted_real_listed": has_real,
                "planted_junk_listed": has_junk,
                "raw_head": raw[:2000],
            },
            "live_worktree": live,
            "schema": schema,
            "parser_selfcheck": {
                "empty_input_rows": len(parse_porcelain_v2("")),
                "question_mark_row": parse_porcelain_v2("? foo.py")[0]["kind"]
                if parse_porcelain_v2("? foo.py")
                else None,
            },
        }
        print(json.dumps(payload, sort_keys=True, default=str))
        if not ok:
            return _fail(
                f"rc={rc} real={has_real} junk={has_junk} sized={all_sized} schema={schema}"
            )
        print(
            "SUCCESS:AUD-0006-probe1 porcelain v2 ran; per-path size and mtime "
            "recorded; planted mutants listed; schema rejects garbage"
        )
        return 0
    finally:
        if tmp is not None:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
