#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN))
import drift as D  # noqa: E402

SHARED = b"# shared prefix\ncommon line\n"


def test_identical() -> None:
    assert D.classify_pair(b"a\n", b"a\n") == D.IDENTICAL


def test_identical_modulo_eol() -> None:
    assert D.classify_pair(b"a\n", b"a\r\n") == D.IDENTICAL_MODULO_EOL


def test_repo_ahead() -> None:
    live = SHARED
    repo = SHARED + b"repo extra\n"
    assert D.classify_pair(repo, live) == D.REPO_AHEAD


def test_live_ahead() -> None:
    repo = SHARED
    live = SHARED + b"live extra\n"
    assert D.classify_pair(repo, live) == D.LIVE_AHEAD


def test_diverged_not_repo_ahead() -> None:
    live = SHARED + b"LIVE-UNIQUE\n"
    repo = SHARED + b"REPO-UNIQUE A\nREPO-UNIQUE B\n"
    assert D.classify_pair(repo, live) == D.DIVERGED
    one = D.classify_pair(repo, live, one_directional=True)
    assert one == D.REPO_AHEAD


def main() -> int:
    tests = [
        test_identical,
        test_identical_modulo_eol,
        test_repo_ahead,
        test_live_ahead,
        test_diverged_not_repo_ahead,
    ]
    for fn in tests:
        fn()
        print(f"{fn.__name__} ... ok")
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
