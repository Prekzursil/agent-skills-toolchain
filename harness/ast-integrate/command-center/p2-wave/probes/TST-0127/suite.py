"""In-process fixture suite for TST-0127 order-dependence census.

Independents share no state. Planted pairs share one named channel each:
module-level flag, or a run-scoped temp file. An always-fail test is a
negative control — always-red is not order dependence.
"""
from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


@dataclass
class RunState:
    module_flag: bool = False
    tmpdir: Path | None = None
    leaked_path: Path | None = None
    _scratch: list[Path] = field(default_factory=list)

    def reset(self) -> None:
        self.cleanup()
        self.module_flag = False
        self.tmpdir = Path(tempfile.mkdtemp(prefix="tst0127-run-"))
        self.leaked_path = self.tmpdir / "leaked-shared.txt"
        self._scratch = [self.tmpdir]

    def cleanup(self) -> None:
        for path in self._scratch:
            shutil.rmtree(path, ignore_errors=True)
        self._scratch = []
        self.tmpdir = None
        self.leaked_path = None
        self.module_flag = False


NODE_IDS: list[str] = [
    "test_independent_arithmetic",
    "test_independent_reversal",
    "test_independent_copy",
    "test_always_broken_independent",
    "test_planted_writer_module_flag",
    "test_planted_writer_shared_file",
    "test_planted_reader_module_flag",
    "test_planted_reader_shared_file",
]

PLANT_CHANNELS: dict[str, dict[str, str]] = {
    "test_planted_reader_module_flag": {
        "channel": "module-level mutable flag",
        "symbol": "RunState.module_flag",
        "writer": "test_planted_writer_module_flag",
        "kind": "module-level-state",
    },
    "test_planted_reader_shared_file": {
        "channel": "run-scoped shared temp file",
        "symbol": "RunState.leaked_path",
        "writer": "test_planted_writer_shared_file",
        "kind": "shared-temp-dir",
    },
}

PLANTED_READERS = tuple(PLANT_CHANNELS)
PLANTED_WRITERS = (
    "test_planted_writer_module_flag",
    "test_planted_writer_shared_file",
)
INDEPENDENTS_PASS = (
    "test_independent_arithmetic",
    "test_independent_reversal",
    "test_independent_copy",
)
ALWAYS_FAIL = "test_always_broken_independent"


def bind_tests(state: RunState) -> dict[str, Callable[[], None]]:
    def test_independent_arithmetic() -> None:
        assert 6 * 7 == 42

    def test_independent_reversal() -> None:
        assert list(reversed("abc")) == ["c", "b", "a"]

    def test_independent_copy() -> None:
        src = [1, 2, 3]
        dst = list(src)
        dst.append(4)
        assert src == [1, 2, 3]
        assert dst[-1] == 4

    def test_always_broken_independent() -> None:
        raise AssertionError("planted always-fail; not order dependent")

    def test_planted_writer_module_flag() -> None:
        state.module_flag = True

    def test_planted_writer_shared_file() -> None:
        assert state.leaked_path is not None
        state.leaked_path.write_text("leaked-from-writer\n", encoding="utf-8")

    def test_planted_reader_module_flag() -> None:
        assert state.module_flag is True, (
            "reader saw module_flag=False; writer did not run first "
            "(module-level state leak)"
        )

    def test_planted_reader_shared_file() -> None:
        path = state.leaked_path
        assert path is not None and path.is_file(), (
            "reader saw no leaked shared file; writer did not run first "
            "(shared temp dir leak)"
        )
        assert path.read_text(encoding="utf-8") == "leaked-from-writer\n"

    tests = {
        "test_independent_arithmetic": test_independent_arithmetic,
        "test_independent_reversal": test_independent_reversal,
        "test_independent_copy": test_independent_copy,
        "test_always_broken_independent": test_always_broken_independent,
        "test_planted_writer_module_flag": test_planted_writer_module_flag,
        "test_planted_writer_shared_file": test_planted_writer_shared_file,
        "test_planted_reader_module_flag": test_planted_reader_module_flag,
        "test_planted_reader_shared_file": test_planted_reader_shared_file,
    }
    missing = [n for n in NODE_IDS if n not in tests]
    extra = [n for n in tests if n not in NODE_IDS]
    if missing or extra:
        raise RuntimeError(f"NODE_IDS mismatch missing={missing} extra={extra}")
    return tests
