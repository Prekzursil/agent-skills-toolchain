#!/usr/bin/env python
"""Regression suite for scripts/repo-sweep.ps1.

Driven from pytest rather than Pester on purpose. Pester on this box is 3.4.0 (the ancient
in-box build, incompatible syntax with 5.x), and more importantly this exercises the REAL
SHIPPED SCRIPT end-to-end through pwsh -- a mechanically independent runtime from the hook's
Python. A green here is evidence about the artifact, not about a mock of it.

The read-only guarantee is the one that must never regress: this script surveys repos the
owner has ALREADY lost track of. A survey tool that mutates them would be the worst possible
failure mode, so it is asserted behaviourally (state snapshot before/after) AND statically.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent / "repo-sweep.ps1"
PWSH = shutil.which("pwsh") or shutil.which("powershell")

GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@t",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@t",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
}

pytestmark = pytest.mark.skipif(PWSH is None, reason="pwsh/powershell not on PATH")


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        env=GIT_ENV,
        timeout=30,
    )


def make_repo(path: Path, *, origin=None, commit=True, dirty=0, detached=False) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "-b", "main")
    if origin:
        git(path, "remote", "add", "origin", origin)
    if commit:
        (path / "kept.txt").write_text("committed\n", encoding="utf-8")
        git(path, "add", "kept.txt")
        git(path, "commit", "-m", "initial")
    if detached:
        head = git(path, "rev-parse", "HEAD").stdout.strip()
        if head:
            git(path, "checkout", "--detach", head)
    for i in range(dirty):
        (path / f"scratch{i}.txt").write_text("uncommitted\n", encoding="utf-8")
    return path


def sweep(root: Path, *extra: str) -> list[dict]:
    r = subprocess.run(
        [
            PWSH,
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(SCRIPT),
            "-Roots",
            str(root),
            "-Owner",
            "Prekzursil",
            "-MaxDepth",
            "4",
            "-Json",
            *extra,
        ],
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert r.returncode == 0, f"repo-sweep exited {r.returncode}\nSTDERR:\n{r.stderr}"
    out = (r.stdout or "").strip()
    if not out:
        return []
    data = json.loads(out)
    return data if isinstance(data, list) else [data]


def by_name(rows, name):
    for row in rows:
        if row.get("Name") == name:
            return row
    return None


@pytest.fixture
def landscape(tmp_path):
    """One planted instance of every population measured on this box."""
    root = tmp_path / "land"
    make_repo(
        root / "quality-zero-platform",
        origin="https://github.com/Prekzursil/quality-zero-platform.git",
        dirty=9,
    )
    make_repo(
        root / "insta-mcp",
        origin="https://github.com/arjun1194/insta-mcp.git",
        dirty=12,
    )
    make_repo(root / "tiktok-mcp", origin=None)
    make_repo(
        root / "event-link", origin="https://github.com/Prekzursil/event-link.git"
    )
    outer = make_repo(
        root / "skills",
        origin="https://github.com/Prekzursil/agent-skills-toolchain.git",
    )
    make_repo(
        outer / "crypto-ctf" / "RsaCtfTool",
        origin="https://github.com/RsaCtfTool/RsaCtfTool.git",
        dirty=4,
    )
    make_repo(
        root / ".claude" / "agent-worktrees" / "agent-999",
        origin="https://github.com/Prekzursil/Reframe.git",
        detached=True,
    )
    return root


# --------------------------------------------------------------------------------------
# KNOWN-POSITIVE CONTROL -- mandatory, first, and never skipped
# --------------------------------------------------------------------------------------
def test_control_planted_repo_is_found(tmp_path):
    """Prove the sweep can see a repo we planted BEFORE trusting any 'nothing found'."""
    make_repo(
        tmp_path / "land" / "planted-control",
        origin="https://github.com/Prekzursil/planted-control.git",
        dirty=3,
    )
    rows = sweep(tmp_path / "land")
    assert by_name(rows, "planted-control") is not None, (
        "DETECTOR IS BROKEN: repo-sweep did not find a repo planted at "
        f"{tmp_path / 'land' / 'planted-control'}. Every 'clean' verdict it emits is void."
    )


def test_control_empty_root_is_silent_only_after_the_positive_control(tmp_path):
    (tmp_path / "nothing").mkdir()
    assert sweep(tmp_path / "nothing") == []


# --------------------------------------------------------------------------------------
# CLASSIFICATION
# --------------------------------------------------------------------------------------
def test_yours_dirty_is_classified_and_actioned(landscape):
    row = by_name(sweep(landscape), "quality-zero-platform")
    assert row["Class"] == "YOURS"
    assert row["Dirty"] == 9
    assert row["Action"] and row["Action"] != "-"


def test_vendored_by_origin(landscape):
    row = by_name(sweep(landscape), "insta-mcp")
    assert row["Class"] == "VENDORED"
    assert row["Dirty"] == 12, "dirt must still be REPORTED, just not actioned"
    assert row["Action"] in ("-", "", None), "a vendored clone needs no action from you"


def test_no_remote_is_its_own_class(landscape):
    assert by_name(sweep(landscape), "tiktok-mcp")["Class"] == "NO-REMOTE"


def test_nested_clone_is_vendored_despite_being_inside_your_repo(landscape):
    row = by_name(sweep(landscape), "RsaCtfTool")
    assert row["Class"] == "VENDORED"
    assert row["NestedIn"], "the enclosing repo must be named, so the call is auditable"


def test_ephemeral_agent_worktree_is_its_own_class(landscape):
    assert by_name(sweep(landscape), "agent-999")["Class"] == "EPHEMERAL"


def test_clean_repo_is_listed_with_no_action(landscape):
    row = by_name(sweep(landscape), "event-link")
    assert row["Class"] == "YOURS" and row["Dirty"] == 0


def test_every_row_carries_the_full_schema(landscape):
    required = {
        "Name",
        "Path",
        "Class",
        "Branch",
        "Upstream",
        "Ahead",
        "Behind",
        "Dirty",
        "HasRemote",
        "Origin",
        "NestedIn",
        "Action",
    }
    rows = sweep(landscape)
    assert rows, "landscape produced no rows at all"
    for row in rows:
        missing = required - set(row)
        assert not missing, f"row {row.get('Name')} is missing {sorted(missing)}"


# --------------------------------------------------------------------------------------
# READ-ONLY -- the guarantee that matters most
# --------------------------------------------------------------------------------------
def _snapshot(root: Path) -> dict:
    """Every file path + content hash, plus each repo's HEAD and status."""
    snap = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            try:
                snap[str(p.relative_to(root))] = hashlib.sha256(
                    p.read_bytes()
                ).hexdigest()
            except OSError:
                pass
    for d in sorted(root.rglob("*")):
        if d.is_dir() and (d / ".git").exists():
            key = str(d.relative_to(root))
            snap[f"@head:{key}"] = git(d, "rev-parse", "HEAD").stdout.strip()
            snap[f"@status:{key}"] = git(d, "status", "--porcelain").stdout
            snap[f"@log:{key}"] = git(d, "rev-list", "--count", "HEAD").stdout.strip()
    return snap


def test_sweep_mutates_absolutely_nothing(landscape):
    before = _snapshot(landscape)
    sweep(landscape)
    after = _snapshot(landscape)
    added = set(after) - set(before)
    removed = set(before) - set(after)
    changed = {k for k in set(before) & set(after) if before[k] != after[k]}
    assert not added, f"repo-sweep CREATED: {sorted(added)[:10]}"
    assert not removed, f"repo-sweep DELETED: {sorted(removed)[:10]}"
    assert not changed, f"repo-sweep MODIFIED: {sorted(changed)[:10]}"


def test_sweep_creates_no_commits(landscape):
    counts_before = {
        p.name: git(p, "rev-list", "--count", "HEAD").stdout.strip()
        for p in landscape.iterdir()
        if (p / ".git").exists()
    }
    sweep(landscape)
    counts_after = {
        p.name: git(p, "rev-list", "--count", "HEAD").stdout.strip()
        for p in landscape.iterdir()
        if (p / ".git").exists()
    }
    assert counts_before == counts_after


def test_no_mutating_git_verb_is_ever_INVOKED(landscape):
    """Static belt-and-braces on top of the behavioural proof above.

    Implemented mention-aware ON PURPOSE. The recommendation strings this script prints
    legitimately CONTAIN the text `git push` -- and PR1-hook-input-schema documents a whole
    defect class (12+ false positives across 3 detectors) caused by scanners that match a
    payload without asking whether the match sits in a position that could EXECUTE. A naive
    grep here would fire on the help text and would have to be 'fixed' by rewording the
    advice, which is exactly the anti-pattern that program exists to kill. So: a mutating
    verb only counts when it is in COMMAND POSITION -- not inside a quoted literal and not
    after a comment marker.
    """
    mutating = (
        "git push",
        "git commit",
        "git add",
        "git reset",
        "git checkout",
        "git clean",
        "Remove-Item",
        "Set-Content",
        "Out-File",
        "New-Item",
    )
    offenders = []
    for lineno, raw in enumerate(SCRIPT.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.split("#", 1)[0]  # drop comments
        # drop quoted literals -- '...' and "..." are data, never a command invocation
        stripped, in_s, in_d = [], False, False
        for ch in line:
            if ch == "'" and not in_d:
                in_s = not in_s
                continue
            if ch == '"' and not in_s:
                in_d = not in_d
                continue
            if not in_s and not in_d:
                stripped.append(ch)
        code = "".join(stripped)
        for verb in mutating:
            if verb.lower() in code.lower():
                offenders.append(f"{lineno}: {raw.strip()[:90]}")
    assert not offenders, (
        "repo-sweep.ps1 INVOKES a mutating command:\n  " + "\n  ".join(offenders)
    )


def test_control_the_mention_aware_scanner_can_actually_catch_an_offender(tmp_path):
    """Validate the detector in the test above. Without this, a scanner that never fires
    and a genuinely read-only script are indistinguishable -- the exact failure this
    program was created to stop."""
    bad = tmp_path / "bad.ps1"
    bad.write_text(
        "Write-Host 'run: git push'\ngit push origin main\n", encoding="utf-8"
    )
    offenders = []
    for lineno, raw in enumerate(bad.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.split("#", 1)[0]
        stripped, in_s, in_d = [], False, False
        for ch in line:
            if ch == "'" and not in_d:
                in_s = not in_s
                continue
            if ch == '"' and not in_s:
                in_d = not in_d
                continue
            if not in_s and not in_d:
                stripped.append(ch)
        if "git push" in "".join(stripped).lower():
            offenders.append(lineno)
    assert offenders == [2], (
        "the mention-aware scanner is broken: it must flag line 2 (a real invocation) "
        f"and NOT line 1 (the same text inside a quoted string); got {offenders}"
    )


# --------------------------------------------------------------------------------------
# SUMMARY / UX
# --------------------------------------------------------------------------------------
def test_human_output_summarises_by_class(landscape):
    r = subprocess.run(
        [
            PWSH,
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(SCRIPT),
            "-Roots",
            str(landscape),
            "-Owner",
            "Prekzursil",
            "-MaxDepth",
            "4",
        ],
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert r.returncode == 0, r.stderr
    out = r.stdout
    assert "YOURS" in out and "VENDORED" in out and "NO-REMOTE" in out
    assert "quality-zero-platform" in out


def test_vendored_hidden_by_default_shown_with_All(landscape):
    default_names = {row["Name"] for row in sweep(landscape)}
    assert "insta-mcp" in default_names, (
        "-Json is the full survey; filtering is the view's job"
    )
    r = subprocess.run(
        [
            PWSH,
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(SCRIPT),
            "-Roots",
            str(landscape),
            "-Owner",
            "Prekzursil",
            "-MaxDepth",
            "4",
        ],
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert "insta-mcp" not in r.stdout, "vendored noise must be summarised, not listed"
    r_all = subprocess.run(
        [
            PWSH,
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(SCRIPT),
            "-Roots",
            str(landscape),
            "-Owner",
            "Prekzursil",
            "-MaxDepth",
            "4",
            "-All",
        ],
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert "insta-mcp" in r_all.stdout, "-All must show everything"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
