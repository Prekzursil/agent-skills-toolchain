#!/usr/bin/env python3
"""Fail-open contract tests for the sec-corpora-update refresher.

No network: the behavioral tests run the Python twin against a fake ``$Root``
with fake git repos and missing directories, using a POSIX ``git`` shim, and
assert the OK/FAILED/SKIP reporting and ``exit 0`` guarantee. A parse test keeps
the PowerShell ``$corpora`` list and the Python ``CORPORA`` list in sync so the
dual-write copies cannot drift.

Run (from the repo root; the ``skills/`` mirror is a byte-identical copy, so pass
``--import-mode=importlib`` if you collect both copies in one invocation):
    python3 -m pytest .agents/skills/sec-corpora-update/tests -q
"""

from __future__ import annotations

import importlib.util
import os
import re
import stat
from pathlib import Path

import pytest

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
MODULE_PATH = SCRIPTS / "sec_corpora_update.py"
PS1_PATH = SCRIPTS / "sec-corpora-update.ps1"

EXISTING = (
    "payloadsallthethings",
    "gtfobins",
    "lolbas",
    "owasp-wstg",
    "owasp-cheatsheets",
    "atomic-red-team",
)
ADDED = (
    "seclists",
    "exploitdb",
    "attack-stix-data",
    "misp-galaxy",
    "misp-warninglists",
    "signature-base",
    "adversary-emulation-library",
    "control-validation-compass",
    "sysmon-modular",
    "loldrivers",
)


def _load_module():
    spec = importlib.util.spec_from_file_location("sec_corpora_update", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MOD = _load_module()


def _strip_ps1_line_comments(text: str) -> str:
    """Drop `# ...` comments while leaving single-quoted strings untouched.

    A `)` inside an inline comment must not terminate the `@( ... )` array early.
    """
    return re.sub(
        r"'[^']*'|#[^\n]*",
        lambda m: m.group(0) if m.group(0).startswith("'") else "",
        text,
    )


def _ps1_corpora() -> tuple[str, ...]:
    text = _strip_ps1_line_comments(PS1_PATH.read_text(encoding="utf-8"))
    match = re.search(r"\$corpora\s*=\s*@\((.*?)\)", text, re.DOTALL)
    assert match, "could not find `$corpora = @(...)` in sec-corpora-update.ps1"
    return tuple(re.findall(r"'([^']+)'", match.group(1)))


def test_existing_corpora_kept_first_in_order() -> None:
    assert MOD.CORPORA[: len(EXISTING)] == EXISTING


def test_all_added_corpora_present_no_dupes() -> None:
    names = MOD.CORPORA
    for name in ADDED:
        assert name in names, f"{name} missing from CORPORA"
    assert len(names) == len(set(names)) == len(EXISTING) + len(ADDED)


def test_ps1_comment_stripper_ignores_parens_in_comments() -> None:
    snippet = "$corpora = @(\n  'a', # note (with parens) and a 'quote\n  'b#not-a-comment'\n)\n"
    stripped = _strip_ps1_line_comments(snippet)
    match = re.search(r"\$corpora\s*=\s*@\((.*?)\)", stripped, re.DOTALL)
    assert match is not None
    assert re.findall(r"'([^']+)'", match.group(1)) == ["a", "b#not-a-comment"]


def test_ps1_and_python_lists_stay_in_sync() -> None:
    assert _ps1_corpora() == tuple(MOD.CORPORA)


def test_ps1_keeps_fail_open_contract() -> None:
    """pwsh is absent in cloud CI, so pin the PowerShell contract statically."""
    text = PS1_PATH.read_text(encoding="utf-8")
    assert "pull --depth 1" in text  # shallow
    assert "try {" in text and "} catch {" in text  # per-repo try/catch
    # one failure never aborts the loop; the script always exits 0
    assert "$ErrorActionPreference = 'Continue'" in text
    assert text.rstrip().splitlines()[-1].strip() == "exit 0"


def test_default_root_prefers_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEC_CORPORA_ROOT", "/tmp/xyz-corpora")
    assert MOD._default_root() == "/tmp/xyz-corpora"
    monkeypatch.delenv("SEC_CORPORA_ROOT", raising=False)
    assert MOD._default_root() == r"D:\knowledge"


def _write_fake_git(bin_dir: Path) -> None:
    """A POSIX git shim: exit 1 if the -C repo holds a `.fail` marker, else exit 0."""
    bin_dir.mkdir(parents=True, exist_ok=True)
    git = bin_dir / "git"
    git.write_text(
        "#!/usr/bin/env bash\n"
        'path=""\n'
        'prev=""\n'
        'for arg in "$@"; do\n'
        '  if [ "$prev" = "-C" ]; then path="$arg"; fi\n'
        '  prev="$arg"\n'
        "done\n"
        'if [ -f "$path/.fail" ]; then\n'
        '  echo "fatal: fake pull failure" >&2\n'
        "  exit 1\n"
        "fi\n"
        'echo "Already up to date."\n'
        "exit 0\n",
        encoding="utf-8",
    )
    git.chmod(git.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


@pytest.mark.skipif(os.name == "nt", reason="POSIX bash git shim")
def test_fail_open_ok_failed_skip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "knowledge"
    (root / "seclists" / ".git").mkdir(parents=True)  # OK: git returns 0
    (root / "exploitdb" / ".git").mkdir(parents=True)  # FAILED: sentinel forces rc!=0
    (root / "exploitdb" / ".fail").write_text("x", encoding="utf-8")
    (root / "gtfobins").mkdir(parents=True)  # SKIP: dir but no .git
    # every other corpus directory is absent -> SKIP

    bin_dir = tmp_path / "bin"
    _write_fake_git(bin_dir)
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ.get("PATH", ""))

    rc = MOD.main(["--root", str(root)])
    out = capsys.readouterr().out

    assert rc == 0  # always exit 0
    assert "OK     seclists" in out
    assert "FAILED exploitdb" in out
    assert "SKIP   gtfobins" in out
    assert "ok=1 failed=1 skipped=14" in out
    # one repo failing never aborted the rest: all 16 corpora were reported
    reported = out.count("OK     ") + out.count("FAILED ") + out.count("SKIP   ")
    assert reported == len(MOD.CORPORA)


@pytest.mark.skipif(os.name == "nt", reason="POSIX PATH manipulation")
def test_fail_open_when_git_binary_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "knowledge"
    (root / "seclists" / ".git").mkdir(parents=True)
    empty_bin = tmp_path / "empty-bin"
    empty_bin.mkdir()
    monkeypatch.setenv("PATH", str(empty_bin))  # `git` cannot be resolved

    rc = MOD.main(["--root", str(root)])
    out = capsys.readouterr().out

    assert rc == 0  # FileNotFoundError is caught, not raised
    assert "FAILED seclists" in out
    assert "ok=0 failed=1 skipped=15" in out


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
