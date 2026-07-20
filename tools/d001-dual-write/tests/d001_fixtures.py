"""Synthetic filtered-repository fixtures for the D-001 applier suite.

The filter is SYNTHETIC.  It has the one property that matters for this lane --
stored form != working-tree form, related by a non-identity invertible pair --
and its ``clean`` side is deliberately NOT idempotent, so re-cleaning already
stored bytes produces a DIFFERENT blob.  That is the double-encryption hazard,
reproduced without git-crypt, without a key, and without any real credential
file: the only payload anywhere in these fixtures is the literal
``SYNTHETIC_LANE03_FIXTURE_NOT_A_REAL_SECRET``.

Uniquely named module (not ``conftest``/``fixtures``) so a pytest session that
also collects ``ci/tests`` cannot import the wrong sibling off ``sys.path``.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

MAGIC = b"\x00FAKECRYPT\x00"
MAGIC_HEX = MAGIC.hex()
SYNTHETIC_PAYLOAD = '{"token": "SYNTHETIC_LANE03_FIXTURE_NOT_A_REAL_SECRET"}\n'
PROTECTED = "secrets/protected.json"

FAKECRYPT = '''\
"""Synthetic non-identity content filter (stdin -> stdout)."""

import base64
import sys

MAGIC = b"\\x00FAKECRYPT\\x00"


def main() -> int:
    mode = sys.argv[1]
    data = sys.stdin.buffer.read()
    if mode == "clean":
        # Deliberately NOT idempotent: cleaning stored bytes re-encodes them,
        # which is exactly how a corrupted working tree becomes a
        # double-encrypted blob on commit.
        out = MAGIC + base64.b64encode(data)
    elif mode == "smudge":
        out = base64.b64decode(data[len(MAGIC) :]) if data.startswith(MAGIC) else data
    else:
        sys.stderr.write("usage: fakecrypt.py clean|smudge\\n")
        return 2
    sys.stdout.buffer.write(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def git(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        raise AssertionError(
            f"git {' '.join(args)} -> {proc.returncode}\n{proc.stderr}"
        )
    return proc.stdout


def write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def signature(path: Path) -> tuple[str, int, int]:
    """(sha256, size, mtime_ns) -- the byte-identity + metadata probe."""
    data = path.read_bytes()
    stat = path.stat()
    return hashlib.sha256(data).hexdigest(), stat.st_size, stat.st_mtime_ns


@dataclass
class Fixture:
    root: Path
    script: Path
    protected: Path

    def git(self, *args: str) -> str:
        return git(self.root, *args)

    def neutralize(self) -> None:
        """The 07:03 state: identity filter installed in the SHARED config."""
        self.git("config", "filter.fakecrypt.smudge", "cat")
        self.git("config", "filter.fakecrypt.clean", "cat")
        self.git("config", "filter.fakecrypt.required", "false")

    def restore(self) -> None:
        quoted = f'"{sys.executable}" "{self.script.as_posix()}"'
        self.git("config", "filter.fakecrypt.smudge", f"{quoted} smudge")
        self.git("config", "filter.fakecrypt.clean", f"{quoted} clean")
        self.git("config", "filter.fakecrypt.required", "true")

    def stored_bytes(self, rev: str = "HEAD", path: str = PROTECTED) -> bytes:
        proc = subprocess.run(
            ["git", "-C", str(self.root), "cat-file", "blob", f"{rev}:{path}"],
            capture_output=True,
        )
        assert proc.returncode == 0, proc.stderr
        return proc.stdout


def build(tmp_path: Path) -> Fixture:
    root = tmp_path / "filtered-repo"
    root.mkdir(parents=True)
    script = tmp_path / "fakecrypt.py"
    script.write_text(FAKECRYPT, encoding="utf-8", newline="\n")

    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.name", "fixture")
    git(root, "config", "user.email", "fixture@example.invalid")
    git(root, "config", "core.autocrlf", "false")
    git(root, "config", "commit.gpgsign", "false")

    fixture = Fixture(root=root, script=script, protected=root / PROTECTED)
    fixture.restore()

    write(root, ".gitattributes", f"{PROTECTED} filter=fakecrypt diff=fakecrypt\n")
    write(root, PROTECTED, SYNTHETIC_PAYLOAD)
    write(root, "skills/alpha/SKILL.md", "# alpha\n\nprojection copy\n")
    write(root, ".agents/skills/alpha/SKILL.md", "# alpha\n\ncanonical copy\n")
    write(root, "skills/beta/SKILL.md", "# beta\n\nprojection-only skill\n")
    git(root, "add", "--", ".gitattributes", "secrets", "skills", ".agents")
    git(root, "commit", "-q", "-m", "base")

    # The fixture is only valid if the two forms actually differ.
    stored = fixture.stored_bytes()
    assert stored.startswith(MAGIC), "clean filter did not run; fixture is invalid"
    assert fixture.protected.read_bytes() == SYNTHETIC_PAYLOAD.encode()
    assert git(root, "status", "--porcelain") == ""
    return fixture


@pytest.fixture
def filtered(tmp_path: Path) -> Fixture:
    return build(tmp_path)
