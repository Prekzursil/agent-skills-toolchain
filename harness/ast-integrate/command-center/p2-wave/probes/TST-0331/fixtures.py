"""Hermetic planted receipts, archive index, and revision-pinned git repo."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ARCHIVED_URL = "https://example.test/archived-paper"
MISSING_URL = "https://example.test/no-archive"
RAN_CMD = "python3 -B command-center/p2-wave/probes/TST-0331/probe1_planted_bad.py"
NEVER_CMD = "python3 -B /nonexistent/never-ran-TST-0331.py"
PRESENT_REL = "lib/present.py"
MISSING_REL = "lib/does-not-exist-TST-0331.py"
PINNED_REL = "src/pinned.txt"
TALL_SNIPPET = "PIN-AT-TALL unique-token-tall"


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    env = os.environ.copy()
    env["GIT_AUTHOR_NAME"] = "TST-0331"
    env["GIT_AUTHOR_EMAIL"] = "tst-0331@invalid"
    env["GIT_COMMITTER_NAME"] = "TST-0331"
    env["GIT_COMMITTER_EMAIL"] = "tst-0331@invalid"
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=check,
        capture_output=True,
        env=env,
    )


def write_fixture_tree(root: Path) -> Path:
    """Layout used by planted-bad probe (no git)."""
    lib = root / "lib"
    lib.mkdir(parents=True)
    lines = [f"# present line {i}" for i in range(1, 21)]
    lines[2] = "def present_fn():  # line 3"
    (lib / "present.py").write_text("\n".join(lines) + "\n", encoding="utf-8")
    arch = root / "archives"
    arch.mkdir()
    (arch / "paper.txt").write_text("archived snapshot of example.test paper\n", encoding="utf-8")
    index = {ARCHIVED_URL: "archives/paper.txt"}
    (arch / "index.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    return root


def archive_index(root: Path) -> dict[str, str]:
    path = root / "archives" / "index.json"
    return json.loads(path.read_text(encoding="utf-8"))


def planted_receipt() -> dict[str, Any]:
    """One receipt mixing valid anchors and the three required planted failures."""
    return {
        "unit_id": "TST-0331-planted",
        "tests": [
            {"id": "ran", "command": RAN_CMD, "result": "PASS"},
        ],
        "named_probes": [
            {"id": "probe1", "command": RAN_CMD},
        ],
        "evidence": [
            {
                "id": "valid-file-line",
                "path": PRESENT_REL,
                "line": 3,
                "snippet": "def present_fn()",
                "claim": "known-good file:line",
            },
            {
                "id": "valid-file",
                "path": PRESENT_REL,
                "symbol": "present_fn",
            },
            {
                "id": "valid-command",
                "kind": "command",
                "command": RAN_CMD,
            },
            {
                "id": "valid-url",
                "url": ARCHIVED_URL,
            },
            {
                "id": "valid-inferred",
                "inferred_from": (
                    "probe1 printed DETECTED for nonexistent-file, "
                    "out-of-range-line, and command-never-run"
                ),
            },
            {
                "id": "planted-missing-file",
                "path": MISSING_REL,
                "line": 1,
                "claim": "nonexistent file",
            },
            {
                "id": "planted-oob-line",
                "path": PRESENT_REL,
                "line": 99999,
                "claim": "out-of-range line",
            },
            {
                "id": "planted-command-never-run",
                "kind": "command",
                "command": NEVER_CMD,
                "claim": "command never run",
            },
            {
                "id": "planted-url-no-archive",
                "url": MISSING_URL,
            },
            {
                "id": "unparseable-empty",
                "kind": "mystery",
            },
        ],
    }


def planted_ids() -> dict[str, str]:
    return {
        "missing-file": "planted-missing-file",
        "oob-line": "planted-oob-line",
        "command-never-run": "planted-command-never-run",
    }


def build_revision_repo(root: Path) -> dict[str, str]:
    """Two-commit repo: tall file at sha_tall, truncated at HEAD.

    Line 15 with TALL_SNIPPET exists only in the first commit. After the
    second commit the worktree and HEAD blob are 5 lines, so a worktree
    reader cannot satisfy the cited-revision check.
    """
    repo = root / "rev-repo"
    repo.mkdir(parents=True)
    src = repo / "src"
    src.mkdir()
    tall_lines = [f"LINE-{i:02d}" for i in range(1, 21)]
    tall_lines[14] = f"LINE-15 {TALL_SNIPPET}"
    (src / "pinned.txt").write_text("\n".join(tall_lines) + "\n", encoding="utf-8")
    _git(repo, "init")
    _git(repo, "add", PINNED_REL)
    _git(
        repo,
        "-c",
        "user.name=TST-0331",
        "-c",
        "user.email=tst-0331@invalid",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "-m",
        "tall",
    )
    sha_tall = _git(repo, "rev-parse", "HEAD").stdout.decode().strip()
    short_lines = [f"LINE-{i:02d}" for i in range(1, 6)]
    (src / "pinned.txt").write_text("\n".join(short_lines) + "\n", encoding="utf-8")
    _git(repo, "add", PINNED_REL)
    _git(
        repo,
        "-c",
        "user.name=TST-0331",
        "-c",
        "user.email=tst-0331@invalid",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "-m",
        "short",
    )
    sha_head = _git(repo, "rev-parse", "HEAD").stdout.decode().strip()
    wt = (src / "pinned.txt").read_text(encoding="utf-8").splitlines()
    return {
        "repo": str(repo),
        "sha_tall": sha_tall,
        "sha_head": sha_head,
        "path": PINNED_REL,
        "line": "15",
        "snippet": TALL_SNIPPET,
        "worktree_lines": str(len(wt)),
        "head_is_short": str(len(wt) == 5),
    }
