"""Throwaway repo: LF blob, CRLF archive export via gitattributes eol=crlf."""
from __future__ import annotations

import subprocess
from pathlib import Path

ALPHA = "docs/alpha.md"
ALPHA_BODY = b"alpha line one\nalpha line two\n"
BETA = "docs/beta.md"
BETA_BODY = b"beta line one\nbeta line two\n"


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
    )


def make_crlf_export_repo(root: str | Path) -> dict:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
    _git(root, "config", "user.email", "imp0440@example.test")
    _git(root, "config", "user.name", "imp0440")
    _git(root, "config", "core.autocrlf", "false")
    (root / ".gitattributes").write_text(f"{ALPHA} text eol=crlf\n", encoding="utf-8")
    dest = root / ALPHA
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(ALPHA_BODY)
    beta = root / BETA
    beta.parent.mkdir(parents=True, exist_ok=True)
    beta.write_bytes(BETA_BODY)
    (root / ".gitattributes").write_text(
        f"{ALPHA} text eol=crlf\n{BETA} text eol=crlf\n",
        encoding="utf-8",
    )
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "lf blob, crlf export")
    dest.write_bytes(ALPHA_BODY.replace(b"\n", b"\r\n"))
    beta.write_bytes(BETA_BODY.replace(b"\n", b"\r\n"))
    return {"root": root, "alpha": ALPHA, "beta": BETA, "blob": ALPHA_BODY}


__all__ = ["ALPHA", "ALPHA_BODY", "BETA", "BETA_BODY", "make_crlf_export_repo"]
