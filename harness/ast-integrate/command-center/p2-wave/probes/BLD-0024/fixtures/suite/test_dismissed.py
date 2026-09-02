"""Live reconstructions of the eight dated Phase-0 dismissals plus controls.

These are ordinary assert functions (no pytest). The engine execs them under
two runners and three experimental conditions.
"""
from __future__ import annotations

import os
from pathlib import Path

DATA = Path(os.environ["BLD0024_DATA_DIR"])


def _lines(name: str) -> list[str]:
    return (DATA / name).read_bytes().decode("utf-8").split("\n")


def test_crlf_text_lines() -> None:
    lines = _lines("crlf_a.txt")
    assert all(not ln.endswith("\r") for ln in lines if ln)


def test_crlf_json_rows() -> None:
    for ln in _lines("crlf_b.json"):
        if ln:
            assert "\r" not in ln


def test_crlf_source_bytes() -> None:
    raw = (DATA / "crlf_c.py").read_bytes()
    assert b"\r" not in raw


def test_tdd_feature_alpha() -> None:
    import sibling_still_red as s

    assert s.feature_alpha() == "alpha"


def test_tdd_feature_beta() -> None:
    import sibling_still_red as s

    assert s.feature_beta() == "beta"


def test_tdd_feature_gamma() -> None:
    import sibling_now_green as s

    assert s.feature_gamma() == "gamma"


def test_tdd_feature_delta() -> None:
    import sibling_now_green as s

    assert s.feature_delta() == "delta"


def _isabs(p: str) -> bool:
    if os.environ.get("BLD0024_USE_NTPATH") == "1":
        import ntpath

        return ntpath.isabs(p)
    return os.path.isabs(p)


def test_posix_win_abs_path() -> None:
    assert _isabs("C:\\Users\\baseline\\file.txt")


def test_unfalsifiable_undocumented() -> None:
    raise AssertionError("undocumented failure; no mechanism named")
