"""The daemon port move is an executable, dry-run-by-default edit with a rollback.

The fixtures are the tracked copies of the on-box launcher and watchdog
(``scripts/agentic-perfection/``), re-encoded with CRLF the way Windows keeps
them, so the test proves the edit touches port tokens and nothing else.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
LANE = HERE.parent
REPO = LANE.parents[2]
sys.path.insert(0, str(LANE / "deploy"))

import move_daemon_port as mdp  # noqa: E402

TRACKED = REPO / "scripts" / "agentic-perfection"


@pytest.fixture
def bm_dir(tmp_path: Path) -> Path:
    target = tmp_path / ".basic-memory"
    target.mkdir()
    for name in mdp.DEFAULT_FILES:
        text = (TRACKED / name).read_text(encoding="utf-8")
        crlf = text.replace("\r\n", "\n").replace("\n", "\r\n")
        (target / name).write_bytes(
            b"\xef\xbb\xbf" + crlf.encode("utf-8")
        )  # BOM + CRLF
    return target


def test_dry_run_reports_the_edits_without_writing(bm_dir, capsys):
    before = {name: (bm_dir / name).read_bytes() for name in mdp.DEFAULT_FILES}
    rc = mdp.main(["--dir", str(bm_dir)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "DRY RUN" in out
    assert "-$Port = 8765" in out and "+$Port = 8766" in out
    assert "-        Where-Object { $_.CommandLine -like '*basic-memory*8765*' }" in out
    assert "+        Where-Object { $_.CommandLine -like '*basic-memory*8766*' }" in out
    assert "bm-http-server.ps1: 2 replacement(s)" in out  # $Port + kill-stale filter
    assert "bm-watchdog.ps1: 3 replacement(s)" in out  # + the header comment
    assert "DRY RUN: 5 replacement(s) across 2 file(s)" in out
    assert {name: (bm_dir / name).read_bytes() for name in mdp.DEFAULT_FILES} == before
    assert not (bm_dir / "backups").exists()


def test_check_fails_before_the_move_and_names_the_lines(bm_dir, capsys):
    rc = mdp.main(["--dir", str(bm_dir), "--check"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "FAILED" in out and "bm-http-server.ps1" in out and "8765" in out


def test_apply_backs_up_then_rewrites_only_port_tokens_and_check_passes(bm_dir, capsys):
    originals = {name: (bm_dir / name).read_bytes() for name in mdp.DEFAULT_FILES}
    rc = mdp.main(["--dir", str(bm_dir), "--apply"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "APPLIED" in out
    backups = sorted((bm_dir / "backups").iterdir())
    assert [p.name.split(".bak_")[0] for p in backups] == sorted(mdp.DEFAULT_FILES)
    assert all(p.name.endswith("-portmove") for p in backups)
    for name in mdp.DEFAULT_FILES:
        original = originals[name]
        edited = (bm_dir / name).read_bytes()
        assert edited.startswith(b"\xef\xbb\xbf")  # BOM kept
        assert b"\r\n" in edited and b"\n" not in edited.replace(
            b"\r\n", b""
        )  # CRLF kept
        assert edited != original
        assert edited.replace(b"8766", b"8765") == original  # ONLY the port changed
        assert b"8765" not in edited
        backup = next(p for p in backups if p.name.startswith(name))
        assert backup.read_bytes() == original

    assert mdp.main(["--dir", str(bm_dir), "--check"]) == 0
    assert "SUCCESS" in capsys.readouterr().out

    # applying again is a no-op: no edits, no second backup
    assert mdp.main(["--dir", str(bm_dir), "--apply"]) == 0
    assert "0 replacement(s)" in capsys.readouterr().out
    assert len(list((bm_dir / "backups").iterdir())) == 2


def test_rollback_restores_the_original_bytes(bm_dir, capsys):
    originals = {name: (bm_dir / name).read_bytes() for name in mdp.DEFAULT_FILES}
    assert mdp.main(["--dir", str(bm_dir), "--apply"]) == 0
    assert mdp.main(["--dir", str(bm_dir), "--rollback"]) == 0
    assert "ROLLED BACK" in capsys.readouterr().out
    assert {
        name: (bm_dir / name).read_bytes() for name in mdp.DEFAULT_FILES
    } == originals
    assert mdp.main(["--dir", str(bm_dir), "--check"]) == 1  # 8765 is back, as intended


def test_rollback_without_a_backup_is_refused(bm_dir, capsys):
    assert mdp.main(["--dir", str(bm_dir), "--rollback"]) == 1
    assert "no backup" in capsys.readouterr().out


def test_missing_file_is_an_error_not_a_partial_edit(bm_dir, capsys):
    (bm_dir / "bm-watchdog.ps1").unlink()
    rc = mdp.main(["--dir", str(bm_dir), "--apply"])
    assert rc == 2
    assert "missing" in capsys.readouterr().out
    assert (
        b"8765" in (bm_dir / "bm-http-server.ps1").read_bytes()
    )  # nothing was touched


def test_only_whole_port_numbers_are_replaced(tmp_path):
    path = tmp_path / "custom.ps1"
    path.write_bytes(
        b"$Port = 8765\n$Other = 18765\n$Also = 87650\n'*bm*8765*'\n:8765/mcp\n"
    )
    edited, count = mdp.rewrite(path.read_bytes(), 8765, 8766)
    assert count == 3
    assert (
        edited
        == b"$Port = 8766\n$Other = 18765\n$Also = 87650\n'*bm*8766*'\n:8766/mcp\n"
    )


def test_files_can_be_overridden_for_a_hardened_on_box_copy(bm_dir, capsys):
    # The 2026-08-27 on-box watchdog probes with an HTTP GET; the edit rule is the
    # same for that shape, so a custom file list is accepted.
    custom = bm_dir / "bm-watchdog-hardened.ps1"
    custom.write_text(
        "$r = Invoke-WebRequest -Uri 'http://127.0.0.1:8765/mcp' -TimeoutSec 30\n",
        encoding="utf-8",
    )
    rc = mdp.main(["--dir", str(bm_dir), "--files", custom.name, "--apply"])
    assert rc == 0
    assert "http://127.0.0.1:8766/mcp" in custom.read_text(encoding="utf-8")
    shutil.rmtree(bm_dir / "backups")
