"""Tests for apply_registration.py - the apply-when-closed ~/.mcp.json editor.

Every test runs against a TEMP config (tmp_path); the real ~/.mcp.json is never
touched. Proves: dry-run writes nothing, --apply swaps stdio->http and backs up,
the op is idempotent, revert restores, and unrelated entries stay byte-identical.
"""

from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

import apply_registration as reg  # noqa: E402

STDIO_ENTRY = {
    "type": "stdio",
    "command": "C:\\Python314\\python.exe",
    "args": ["C:\\repo\\tools\\mcp\\search-hub\\hub.py"],
    "env": {},
}
OTHER_ENTRY = {"type": "http", "url": "https://mcp.figma.com/mcp"}


@pytest.fixture
def cfg(tmp_path: Path) -> Path:
    target = tmp_path / "mcp.json"
    target.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "search-hub": dict(STDIO_ENTRY),
                    "figma": dict(OTHER_ENTRY),
                }
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return target


def _load(target: Path) -> dict:
    return json.loads(target.read_text(encoding="utf-8"))


def test_http_entry_shape():
    assert reg.http_entry("127.0.0.1", 8900, "/mcp") == {
        "type": "http",
        "url": "http://127.0.0.1:8900/mcp",
    }


def test_dry_run_writes_nothing(cfg: Path):
    before = cfg.read_bytes()
    rc = reg.main(["--target", str(cfg), "--server", "search-hub", "--port", "8900"])
    assert rc == 0
    assert cfg.read_bytes() == before  # untouched


def test_apply_swaps_to_http_and_backs_up(cfg: Path):
    rc = reg.main(
        ["--target", str(cfg), "--server", "search-hub", "--port", "8900", "--apply"]
    )
    assert rc == 0
    data = _load(cfg)
    assert data["mcpServers"]["search-hub"] == {
        "type": "http",
        "url": "http://127.0.0.1:8900/mcp",
    }
    assert data["mcpServers"]["figma"] == OTHER_ENTRY  # unrelated entry untouched
    assert glob.glob(str(cfg) + ".bak-*")  # a backup was written


def test_apply_is_idempotent(cfg: Path):
    reg.main(
        ["--target", str(cfg), "--server", "search-hub", "--port", "8900", "--apply"]
    )
    after_first = cfg.read_bytes()
    rc = reg.main(
        ["--target", str(cfg), "--server", "search-hub", "--port", "8900", "--apply"]
    )
    assert rc == 0
    assert cfg.read_bytes() == after_first  # second apply is a no-op


def test_revert_restores_stdio(cfg: Path):
    reg.main(
        ["--target", str(cfg), "--server", "search-hub", "--port", "8900", "--apply"]
    )
    backup = sorted(glob.glob(str(cfg) + ".bak-*"))[-1]
    rc = reg.main(["--target", str(cfg), "--revert-from", backup])
    assert rc == 0
    assert _load(cfg)["mcpServers"]["search-hub"] == STDIO_ENTRY


def test_no_backup_flag(cfg: Path):
    rc = reg.main(
        [
            "--target",
            str(cfg),
            "--server",
            "search-hub",
            "--port",
            "8900",
            "--apply",
            "--no-backup",
        ]
    )
    assert rc == 0
    assert not glob.glob(str(cfg) + ".bak-*")


def test_server_not_found(cfg: Path):
    rc = reg.main(
        ["--target", str(cfg), "--server", "nope", "--port", "8900", "--apply"]
    )
    assert rc == 1


def test_requires_server_and_port():
    assert reg.main([]) == 2


def test_apply_change_does_not_mutate_input():
    config = {"mcpServers": {"search-hub": dict(STDIO_ENTRY)}}
    snapshot = json.dumps(config, sort_keys=True)
    new = reg.apply_change(
        config, "search-hub", {"type": "http", "url": "http://x/mcp"}
    )
    assert json.dumps(config, sort_keys=True) == snapshot  # original unchanged
    assert new["mcpServers"]["search-hub"]["type"] == "http"


def test_apply_change_unknown_server_raises():
    with pytest.raises(KeyError):
        reg.apply_change(
            {"mcpServers": {}}, "ghost", {"type": "http", "url": "http://x/mcp"}
        )


# --- --transport sse (mcp-proxy also exposes an SSE endpoint) --------------


def test_sse_entry_shape():
    assert reg.sse_entry("127.0.0.1", 8901, "/sse") == {
        "type": "sse",
        "url": "http://127.0.0.1:8901/sse",
    }


def test_build_entry_dispatches_by_transport():
    assert reg.build_entry("http", "127.0.0.1", 8900, "/mcp") == {
        "type": "http",
        "url": "http://127.0.0.1:8900/mcp",
    }
    assert reg.build_entry("sse", "127.0.0.1", 8901, "/sse") == {
        "type": "sse",
        "url": "http://127.0.0.1:8901/sse",
    }


def test_build_entry_unknown_transport_raises():
    with pytest.raises(ValueError, match="unknown transport"):
        reg.build_entry("grpc", "127.0.0.1", 8900, "/mcp")


def test_default_path_per_transport():
    assert reg.default_path("sse") == "/sse"
    assert reg.default_path("http") == "/mcp"


def test_apply_sse_uses_sse_type_and_default_sse_path(cfg: Path):
    rc = reg.main(
        [
            "--target",
            str(cfg),
            "--server",
            "search-hub",
            "--port",
            "8901",
            "--transport",
            "sse",
            "--apply",
        ]
    )
    assert rc == 0
    data = _load(cfg)
    assert data["mcpServers"]["search-hub"] == {
        "type": "sse",
        "url": "http://127.0.0.1:8901/sse",  # default sse path, not /mcp
    }
    assert data["mcpServers"]["figma"] == OTHER_ENTRY  # unrelated entry untouched


def test_apply_sse_honors_explicit_path(cfg: Path):
    rc = reg.main(
        [
            "--target",
            str(cfg),
            "--server",
            "search-hub",
            "--port",
            "8901",
            "--transport",
            "sse",
            "--path",
            "/events",
            "--apply",
        ]
    )
    assert rc == 0
    assert _load(cfg)["mcpServers"]["search-hub"] == {
        "type": "sse",
        "url": "http://127.0.0.1:8901/events",
    }
