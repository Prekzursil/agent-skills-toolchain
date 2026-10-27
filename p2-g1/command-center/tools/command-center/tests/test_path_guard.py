"""Both-states tests for tools/command-center/path_guard.py (BLD-0009 residue)."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import path_guard as pg
import pytest


def test_unc_samples_raise_named_error(tmp_path: Path) -> None:
    samples = [
        r"\\bld0009-server\share\catalog.json",
        "//bld0009-server/share/catalog.json",
        r"\\?\UNC\bld0009-server\share\x.json",
        "file://bld0009-server/share/x.json",
    ]
    for sample in samples:
        with pytest.raises(pg.UncRejected) as caught:
            pg.reject_unc(sample)
        assert caught.value.name == "UncRejected"
    local = tmp_path / "ok.json"
    pg.reject_unc(local)
    pg.guarded_write_text(local, "{}\n")
    assert local.is_file()


def test_file_uri_local_is_not_unc(tmp_path: Path) -> None:
    assert not pg.looks_like_unc(str(tmp_path / "x.json"))
    assert not pg.looks_like_unc("/tmp/bld0009-local.json")
    assert pg.looks_like_unc("file:////bld0009-server/share/x.json")


def test_symlink_escape_is_named_not_silent(tmp_path: Path) -> None:
    scratch = tmp_path / "scratch"
    outside = tmp_path / "outside"
    scratch.mkdir()
    outside.mkdir()
    sentinel = outside / "SENTINEL.txt"
    sentinel.write_text("untouched\n", encoding="utf-8")
    (scratch / "ok.json").write_text("{}\n", encoding="utf-8")
    escape = scratch / "escape-link"
    escape.symlink_to(outside)
    with pytest.raises(pg.ContainmentBreach) as caught:
        list(pg.contained_rglob(scratch, "*.json"))
    assert caught.value.name == "ContainmentBreach"
    assert sentinel.read_bytes() == b"untouched\n"


def test_empty_tree_has_no_fixtures(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    assert list(pg.contained_rglob(empty, "*.json")) == []
    assert not (empty / "local-catalog.json").exists()


def test_locked_file_named_error_does_not_partial_write(tmp_path: Path) -> None:
    target = tmp_path / "held.json"
    target.write_text("{}\n", encoding="utf-8")
    holder = subprocess.Popen(
        [
            sys.executable,
            "-c",
            (
                "import fcntl, os, sys, time;"
                "p=sys.argv[1]; fd=os.open(p, os.O_RDWR);"
                "fcntl.flock(fd, fcntl.LOCK_EX);"
                "sys.stdout.write('HOLD\\n'); sys.stdout.flush();"
                "time.sleep(30)"
            ),
            str(target),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert holder.stdout is not None
        assert holder.stdout.readline().strip() == "HOLD"
        time.sleep(0.05)
        with pytest.raises(pg.FileLocked) as caught:
            pg.guarded_write_text(target, '{"over":true}\n')
        assert caught.value.name == "FileLocked"
        assert target.read_text(encoding="utf-8") == "{}\n"
    finally:
        holder.kill()
        holder.wait(timeout=5)


def test_permission_denied_named_when_uid_dropped(tmp_path: Path) -> None:
    locked_dir = tmp_path / "acl-ro"
    locked_dir.mkdir()
    os.chmod(locked_dir, 0o500)
    victim = locked_dir / "denied.json"
    if os.geteuid() != 0:
        pytest.skip("setuid(nobody) requires root")
    pid = os.fork()
    if pid == 0:
        try:
            os.setuid(65534)
        except PermissionError:
            os._exit(4)
        try:
            pg.guarded_write_text(victim, "{}\n")
        except pg.PermissionDenied:
            os._exit(0)
        except Exception:
            os._exit(3)
        os._exit(2)
    _, status = os.waitpid(pid, 0)
    code = os.WEXITSTATUS(status)
    if code == 4:
        pytest.skip("setuid(nobody) refused")
    assert code == 0
    assert not victim.exists()
