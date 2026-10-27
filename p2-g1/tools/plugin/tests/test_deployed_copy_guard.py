#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
REPO = PLUGIN.parents[1]
sys.path.insert(0, str(PLUGIN))
import deployed_copy_guard as g  # noqa: E402

SOURCE = "skills/known/SKILL.md"
BLOB = "b" * 40


def plant(root: Path) -> dict[str, Path]:
    repo = root / "repo"
    live = root / "live"
    repo.mkdir()
    live.mkdir()
    known_repo = repo / SOURCE
    known_live = live / SOURCE
    known_repo.parent.mkdir(parents=True)
    known_live.parent.mkdir(parents=True)
    known_repo.write_text("source\n", encoding="utf-8")
    known_live.write_text("deployed\n", encoding="utf-8")
    scratch = live / "scratch.md"
    scratch.write_text("scratch\n", encoding="utf-8")
    ledger = root / "ledger.json"
    ledger.write_text(
        json.dumps(
            {
                "records": [
                    {
                        "live_path": str(known_live),
                        "repo_path": SOURCE,
                        "blob": BLOB,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return {
        "repo": repo,
        "live": live,
        "known_repo": known_repo,
        "known_live": known_live,
        "scratch": scratch,
        "ledger": ledger,
    }


def _handle(path: Path, ledger: Path, extra: dict | None = None) -> dict:
    env = os.environ.copy()
    env["DEPLOY_PROVENANCE_LEDGER"] = str(ledger)
    env.pop(g.FORCE_ERROR_ENV, None)
    if extra:
        env.update(extra)
    old = os.environ.copy()
    os.environ.update(env)
    try:
        return g.handle_event(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Edit",
                "tool_input": {"file_path": str(path)},
            }
        )
    finally:
        os.environ.clear()
        os.environ.update(old)


def test_deployed_path_warns() -> None:
    with tempfile.TemporaryDirectory() as td:
        planted = plant(Path(td))
        payload = _handle(planted["known_live"], planted["ledger"])
        ctx = (payload.get("hookSpecificOutput") or {}).get("additionalContext") or ""
        assert g.ADVISORY_MARK in ctx
        assert SOURCE in ctx
        assert not g.blocks(payload)


def test_live_only_path_silent() -> None:
    with tempfile.TemporaryDirectory() as td:
        planted = plant(Path(td))
        payload = _handle(planted["scratch"], planted["ledger"])
        ctx = (payload.get("hookSpecificOutput") or {}).get("additionalContext") or ""
        assert g.ADVISORY_MARK not in ctx
        assert not g.blocks(payload)


def test_repo_path_silent() -> None:
    with tempfile.TemporaryDirectory() as td:
        planted = plant(Path(td))
        payload = _handle(planted["known_repo"], planted["ledger"])
        ctx = (payload.get("hookSpecificOutput") or {}).get("additionalContext") or ""
        assert g.ADVISORY_MARK not in ctx


def test_negative_control_record_not_prefix() -> None:
    with tempfile.TemporaryDirectory() as td:
        planted = plant(Path(td))
        planted["ledger"].write_text(json.dumps({"records": []}), encoding="utf-8")
        payload = _handle(planted["known_live"], planted["ledger"])
        ctx = (payload.get("hookSpecificOutput") or {}).get("additionalContext") or ""
        assert g.ADVISORY_MARK not in ctx


def test_inject_never_block() -> None:
    with tempfile.TemporaryDirectory() as td:
        planted = plant(Path(td))
        payload = _handle(planted["known_live"], planted["ledger"])
        assert payload.get("continue") is True
        assert not g.blocks(payload)


def test_fail_open_on_forced_exception() -> None:
    with tempfile.TemporaryDirectory() as td:
        planted = plant(Path(td))
        payload = _handle(
            planted["known_live"], planted["ledger"], {g.FORCE_ERROR_ENV: "1"}
        )
        assert payload.get("continue") is True
        spec = payload.get("hookSpecificOutput") or {}
        assert spec.get("permissionDecision") == "allow"


def main() -> int:
    tests = [
        test_deployed_path_warns,
        test_live_only_path_silent,
        test_repo_path_silent,
        test_negative_control_record_not_prefix,
        test_inject_never_block,
        test_fail_open_on_forced_exception,
    ]
    for fn in tests:
        fn()
        print(f"{fn.__name__} ... ok")
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
