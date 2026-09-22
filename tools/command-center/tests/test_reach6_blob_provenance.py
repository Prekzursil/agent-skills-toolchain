"""CC-0005 — REACH-6 provenance hashes the git blob, not Windows worktree bytes.

tests_required (catalog):
  - Both-states: FIRE when content genuinely changes.
  - Both-states: SILENT on a pure line-ending difference.
  - Byte-delta control: pre-fix CRLF delta equals that file's line count.
  - Platform parity: blob route yields the same digest on LF and CRLF checkouts.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import catalog as cat  # noqa: E402
import validate as val  # noqa: E402

LF_BODY = b"# register\nalpha\nbeta\ngamma\n"
CRLF_BODY = LF_BODY.replace(b"\n", b"\r\n")
REL = "command-center/sources/REGISTER.md"


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True
    )


def _repo_with_register(tmp_path: Path) -> tuple[Path, Path]:
    """Commit LF REGISTER.md, return (repo_root, register_path)."""
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    reg = root / REL
    reg.parent.mkdir(parents=True)
    reg.write_bytes(LF_BODY)
    _git(root, "add", REL)
    _git(root, "commit", "-q", "-m", "lf-register")
    return root, reg


def _mini_catalog(digest: str, nbytes: int) -> dict:
    return {
        "provenance": {
            "register": REL,
            "register_sha256": digest,
            "register_bytes": nbytes,
        },
        "items": [
            {
                "id": "R-T01",
                "title": "fixture",
                "status": "OPEN",
                "dependencies": [],
                "next_smallest_action": "planted fixture action",
            }
        ],
        "owner_questions": [],
        "defaults": {},
    }


def test_byte_delta_control_crlf_delta_equals_line_count() -> None:
    """Planted CRLF differs from LF by exactly one byte per line (EOL only)."""
    line_count = LF_BODY.count(b"\n")
    assert line_count > 0
    delta = len(CRLF_BODY) - len(LF_BODY)
    assert delta == line_count, (
        f"pre-fix delta {delta} != line_count {line_count} — "
        "fixture is not a pure EOL difference"
    )
    assert CRLF_BODY.replace(b"\r\n", b"\n") == LF_BODY
    assert hashlib.sha256(LF_BODY).hexdigest()[:12] != hashlib.sha256(
        CRLF_BODY
    ).hexdigest()[:12]


def test_silent_on_pure_eol_difference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """REACH-6 SILENT when worktree is CRLF but blob matches recorded digest."""
    root, reg = _repo_with_register(tmp_path)
    monkeypatch.setattr(cat, "repo_root", lambda: root)
    blob_digest = hashlib.sha256(LF_BODY).hexdigest()
    catalog = _mini_catalog(blob_digest, len(LF_BODY))
    reg.write_bytes(CRLF_BODY)
    assert reg.read_bytes() == CRLF_BODY

    raw = val._register_provenance_bytes(reg, catalog)
    assert raw == LF_BODY
    assert hashlib.sha256(raw).hexdigest() == blob_digest

    wt_raw_digest = hashlib.sha256(reg.read_bytes()).hexdigest()
    assert wt_raw_digest != blob_digest, (
        "control: raw worktree MUST differ (else silent both states)"
    )


def test_fires_when_content_genuinely_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """REACH-6 FIRE: dirty content (not just EOL) yields bytes != recorded blob digest."""
    root, reg = _repo_with_register(tmp_path)
    monkeypatch.setattr(cat, "repo_root", lambda: root)
    blob_digest = hashlib.sha256(LF_BODY).hexdigest()
    catalog = _mini_catalog(blob_digest, len(LF_BODY))

    changed = b"# register\nalpha\nbeta\nCHANGED\n"
    reg.write_bytes(changed)
    raw = val._register_provenance_bytes(reg, catalog)
    assert raw == changed
    assert hashlib.sha256(raw).hexdigest() != blob_digest


def test_platform_parity_blob_route_identical_lf_and_crlf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Same commit: blob-route digest identical whether worktree is LF or CRLF."""
    root, reg = _repo_with_register(tmp_path)
    monkeypatch.setattr(cat, "repo_root", lambda: root)
    catalog = _mini_catalog(hashlib.sha256(LF_BODY).hexdigest(), len(LF_BODY))

    reg.write_bytes(CRLF_BODY)
    crlf_raw = val._register_provenance_bytes(reg, catalog)
    reg.write_bytes(LF_BODY)
    lf_raw = val._register_provenance_bytes(reg, catalog)

    assert crlf_raw == lf_raw == LF_BODY
    assert hashlib.sha256(crlf_raw).hexdigest() == hashlib.sha256(lf_raw).hexdigest()


def test_never_uses_working_tree_raw_as_blob(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Control: provenance bytes must not equal raw CRLF worktree when blob is LF."""
    root, reg = _repo_with_register(tmp_path)
    monkeypatch.setattr(cat, "repo_root", lambda: root)
    catalog = _mini_catalog(hashlib.sha256(LF_BODY).hexdigest(), len(LF_BODY))
    reg.write_bytes(CRLF_BODY)
    raw = val._register_provenance_bytes(reg, catalog)
    assert raw != CRLF_BODY
    assert raw == LF_BODY
