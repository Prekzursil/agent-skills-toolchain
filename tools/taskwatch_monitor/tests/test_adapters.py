"""Tests for core/adapters.py — the poll() adapters and factory."""

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.adapters import (  # noqa: E402
    AdapterError,
    FileExistsGlobAdapter,
    HttpJsonAdapter,
    LocalFileTailAdapter,
    ProcessPidAdapter,
    RealFileSystem,
    _require_int,
    _require_str,
    adapter_from_spec,
    default_http_get,
    default_pid_alive,
)
from core.models import TaskSpec  # noqa: E402


class FakeFS:
    """In-memory FileSystem stub with optional read failure."""

    def __init__(
        self,
        stats: dict[str, tuple[bool, float | None, int | None]] | None = None,
        texts: dict[str, str] | None = None,
        globs: dict[str, list[str]] | None = None,
        raise_read: bool = False,
    ) -> None:
        self._stats = stats or {}
        self._texts = texts or {}
        self._globs = globs or {}
        self._raise_read = raise_read

    def stat(self, path: str) -> tuple[bool, float | None, int | None]:
        return self._stats.get(path, (False, None, None))

    def read_text(self, path: str) -> str:
        if self._raise_read:
            raise OSError("read failed")
        return self._texts.get(path, "")

    def glob(self, pattern: str) -> list[str]:
        return self._globs.get(pattern, [])


class TestLocalFileTailAdapter:
    def test_missing_file(self):
        a = LocalFileTailAdapter("/x", fs=FakeFS())
        pr = a.poll()
        assert pr.exists is False
        assert pr.liveness is False

    def test_read_error_is_blind(self):
        fs = FakeFS(stats={"/x": (True, 5.0, 10)}, raise_read=True)
        pr = LocalFileTailAdapter("/x", fs=fs).poll()
        assert pr.blind is True
        assert pr.exists is True

    def test_no_pattern_returns_all_lines(self):
        fs = FakeFS(stats={"/x": (True, 5.0, 10)}, texts={"/x": "a\nb\nc"})
        pr = LocalFileTailAdapter("/x", fs=fs).poll()
        assert pr.lines == ["a", "b", "c"]
        assert pr.liveness is True

    def test_pattern_filters_lines(self):
        fs = FakeFS(
            stats={"/x": (True, 5.0, 10)}, texts={"/x": "edge 1\nnoise\nedge 2"}
        )
        pr = LocalFileTailAdapter("/x", r"edge", fs=fs).poll()
        assert pr.lines == ["edge 1", "edge 2"]


class TestFileExistsGlobAdapter:
    def test_empty_glob(self):
        pr = FileExistsGlobAdapter("*.z", fs=FakeFS()).poll()
        assert pr.count == 0
        assert pr.exists is False

    def test_counts_and_newest_mtime(self):
        fs = FakeFS(
            globs={"*.out": ["a.out", "b.out", "c.out"]},
            stats={
                "a.out": (True, 10.0, 1),
                "b.out": (True, 30.0, 1),  # newest
                "c.out": (False, None, None),  # race: gone
            },
        )
        pr = FileExistsGlobAdapter("*.out", fs=fs).poll()
        assert pr.count == 3
        assert pr.mtime == 30.0
        assert pr.liveness is True

    def test_match_with_none_mtime(self):
        fs = FakeFS(
            globs={"*.out": ["a.out"]},
            stats={"a.out": (True, None, 1)},
        )
        pr = FileExistsGlobAdapter("*.out", fs=fs).poll()
        assert pr.mtime is None
        assert pr.exists is True


class TestHttpJsonAdapter:
    def test_transport_error_is_blind(self):
        def boom(_url: str) -> str:
            raise RuntimeError("no network")

        pr = HttpJsonAdapter("http://x", http_get=boom).poll()
        assert pr.blind is True
        assert pr.liveness is False

    def test_invalid_json_is_blind(self):
        pr = HttpJsonAdapter("http://x", http_get=lambda _u: "not json").poll()
        assert pr.blind is True
        assert pr.error is not None and "invalid json" in pr.error

    def test_non_object_root_is_blind(self):
        pr = HttpJsonAdapter("http://x", http_get=lambda _u: "[1, 2]").poll()
        assert pr.blind is True
        assert pr.error is not None and "not an object" in pr.error

    def test_success(self):
        body = json.dumps({"done": 3, "total": 10})
        pr = HttpJsonAdapter(
            "http://x", http_get=lambda _u: body, clock=lambda: 42.0
        ).poll()
        assert pr.liveness is True
        assert pr.mtime == 42.0
        assert pr.raw["done"] == 3


class TestProcessPidAdapter:
    def test_alive(self):
        pr = ProcessPidAdapter(123, pid_alive=lambda _p: True, clock=lambda: 7.0).poll()
        assert pr.exists is True
        assert pr.mtime == 7.0

    def test_dead(self):
        pr = ProcessPidAdapter(123, pid_alive=lambda _p: False).poll()
        assert pr.exists is False
        assert pr.mtime is None


class TestRealDefaults:
    def test_real_fs_stat_and_read(self, tmp_path: Path):
        fs = RealFileSystem()
        p = tmp_path / "f.txt"
        _ = p.write_text("hello", encoding="utf-8")
        exists, mtime, size = fs.stat(str(p))
        assert exists is True
        assert mtime is not None and size == 5
        assert fs.read_text(str(p)) == "hello"

    def test_real_fs_stat_missing(self, tmp_path: Path):
        assert RealFileSystem().stat(str(tmp_path / "nope")) == (False, None, None)

    def test_real_fs_glob(self, tmp_path: Path):
        for name in ("b.log", "a.log"):
            _ = (tmp_path / name).write_text("x", encoding="utf-8")
        matches = RealFileSystem().glob(str(tmp_path / "*.log"))
        assert len(matches) == 2
        assert matches == sorted(matches)

    def test_default_http_get_file_url(self, tmp_path: Path):
        p = tmp_path / "data.json"
        _ = p.write_text('{"ok": true}', encoding="utf-8")
        body = default_http_get(p.as_uri())
        assert json.loads(body) == {"ok": True}

    def test_default_pid_alive_self(self):
        assert default_pid_alive(os.getpid()) is True

    def test_default_pid_alive_nonpositive(self):
        assert default_pid_alive(0) is False

    def test_default_pid_alive_bogus(self):
        assert default_pid_alive(2**31 - 1) is False


class TestRequireHelpers:
    def test_require_str_ok(self):
        assert _require_str({"k": "v"}, "k", "t") == "v"

    def test_require_str_missing(self):
        with pytest.raises(AdapterError, match="non-empty string"):
            _require_str({}, "k", "t")

    def test_require_str_empty(self):
        with pytest.raises(AdapterError, match="non-empty string"):
            _require_str({"k": ""}, "k", "t")

    def test_require_int_ok(self):
        assert _require_int({"k": 5}, "k", "t") == 5

    def test_require_int_missing(self):
        with pytest.raises(AdapterError, match="must be an integer"):
            _require_int({}, "k", "t")

    def test_require_int_bool_rejected(self):
        with pytest.raises(AdapterError, match="must be an integer"):
            _require_int({"k": True}, "k", "t")


class TestAdapterFromSpec:
    def test_local_file_tail_with_pattern(self):
        spec = TaskSpec(
            id="a",
            adapter="local-file-tail",
            config={"path": "/x", "pattern": "edge"},
        )
        a = adapter_from_spec(spec, fs=FakeFS())
        assert isinstance(a, LocalFileTailAdapter)
        assert a.pattern is not None

    def test_local_file_tail_empty_pattern_is_none(self):
        spec = TaskSpec(
            id="a", adapter="local-file-tail", config={"path": "/x", "pattern": ""}
        )
        a = adapter_from_spec(spec, fs=FakeFS())
        assert isinstance(a, LocalFileTailAdapter)
        assert a.pattern is None

    def test_local_file_tail_nonstr_pattern_is_none(self):
        spec = TaskSpec(
            id="a", adapter="local-file-tail", config={"path": "/x", "pattern": 5}
        )
        a = adapter_from_spec(spec, fs=FakeFS())
        assert isinstance(a, LocalFileTailAdapter)
        assert a.pattern is None

    def test_file_exists_glob(self):
        spec = TaskSpec(id="a", adapter="file-exists-glob", config={"pattern": "*.z"})
        assert isinstance(adapter_from_spec(spec), FileExistsGlobAdapter)

    def test_http_json(self):
        spec = TaskSpec(id="a", adapter="http-json", config={"url": "http://x"})
        assert isinstance(adapter_from_spec(spec), HttpJsonAdapter)

    def test_process_pid(self):
        spec = TaskSpec(id="a", adapter="process-pid", config={"pid": 5})
        assert isinstance(adapter_from_spec(spec), ProcessPidAdapter)

    def test_unknown_adapter(self):
        spec = TaskSpec(id="a", adapter="mystery")
        with pytest.raises(AdapterError, match="unknown adapter"):
            adapter_from_spec(spec)
