"""TST-0331 evidence-anchor resolver tests.

Catalog tests_required:
  1. Planted bad anchors (nonexistent file, out-of-range line, command never run) DETECTED.
  2. Valid anchors pass (no false positives).
  3. Revision correctness: valid at cited commit but stale at HEAD must PASS.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from evidence_anchor_resolver import (
    AnchorKind,
    line_count_at_revision,
    parse_anchor,
    resolve_anchor,
    validate_receipt_evidence,
)


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed: {proc.stderr.strip() or proc.stdout.strip()}"
        )
    return (proc.stdout or "").strip()


@pytest.fixture()
def rev_repo(tmp_path: Path) -> Path:
    """Tiny git repo with a file that shrinks between commits (revision-correctness fixture)."""
    repo = tmp_path / "revrepo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "tst0331@example.com")
    _git(repo, "config", "user.name", "TST-0331")
    # Disable gpg / template noise.
    _git(repo, "config", "commit.gpgsign", "false")

    target = repo / "doc" / "notes.txt"
    target.parent.mkdir(parents=True)
    # Old revision: 5 lines — line 5 is valid here.
    target.write_text("L1\nL2\nL3\nL4\nL5-only-at-old\n", encoding="utf-8")
    _git(repo, "add", "doc/notes.txt")
    _git(repo, "commit", "-m", "old: five lines")
    old = _git(repo, "rev-parse", "HEAD")

    # HEAD: shrink to 2 lines — line 5 is stale at HEAD.
    target.write_text("L1\nL2\n", encoding="utf-8")
    _git(repo, "add", "doc/notes.txt")
    _git(repo, "commit", "-m", "head: two lines")
    head = _git(repo, "rev-parse", "HEAD")

    # Stash revs for tests.
    (repo / ".tst0331-revs.json").write_text(
        json.dumps({"old": old, "head": head}), encoding="utf-8"
    )
    # Also plant a companion file that exists only at HEAD for positive cases.
    (repo / "doc" / "present.txt").write_text("alpha\nbeta\ngamma\n", encoding="utf-8")
    _git(repo, "add", "doc/present.txt")
    _git(repo, "commit", "-m", "add present.txt")
    head2 = _git(repo, "rev-parse", "HEAD")
    data = json.loads((repo / ".tst0331-revs.json").read_text(encoding="utf-8"))
    data["head"] = head2
    (repo / ".tst0331-revs.json").write_text(json.dumps(data), encoding="utf-8")
    return repo


def _revs(repo: Path) -> dict[str, str]:
    return json.loads((repo / ".tst0331-revs.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def test_parse_rev_pinned_file_line() -> None:
    p = parse_anchor("rev:abc1234:platform/lib/foo.py:12")
    assert p.kind == AnchorKind.FILE
    assert p.path == "platform/lib/foo.py"
    assert p.revision == "abc1234"
    assert p.line == 12


def test_parse_path_at_rev() -> None:
    p = parse_anchor("doc/notes.txt@deadbeef:5")
    assert p.kind == AnchorKind.FILE
    assert p.path == "doc/notes.txt"
    assert p.revision == "deadbeef"
    assert p.line == 5


def test_parse_command_url_inferred() -> None:
    assert parse_anchor("command:pytest -q").kind == AnchorKind.COMMAND
    assert parse_anchor("https://example.com/a").kind == AnchorKind.URL
    assert parse_anchor("inferred-from:CC-0002 receipt").kind == AnchorKind.INFERRED


def test_parse_garbage_is_unparseable() -> None:
    p = parse_anchor("??? not an anchor ???")
    assert p.kind == AnchorKind.UNPARSEABLE


# ---------------------------------------------------------------------------
# Planted bad anchors DETECTED
# ---------------------------------------------------------------------------


def test_planted_nonexistent_file_detected(rev_repo: Path) -> None:
    revs = _revs(rev_repo)
    parsed = parse_anchor(f"rev:{revs['head']}:doc/does-not-exist.txt:1")
    res = resolve_anchor(parsed, repo=rev_repo)
    assert res.status == "unresolved"
    assert res.detail.get("fabricated_citation") is True


def test_planted_out_of_range_line_detected(rev_repo: Path) -> None:
    revs = _revs(rev_repo)
    # present.txt has 3 lines at HEAD; cite line 999.
    parsed = parse_anchor(f"rev:{revs['head']}:doc/present.txt:999")
    res = resolve_anchor(parsed, repo=rev_repo)
    assert res.status == "unresolved"
    assert "only 3 lines" in res.reason
    assert res.detail.get("fabricated_citation") is True


def test_planted_command_never_run_detected(rev_repo: Path) -> None:
    item = {
        "anchor": "command:python -B never_executed_probe.py",
        "probes": [
            {
                "role": "source",
                "method": "command",
                "command": "echo hello",
                "raw_output": "hello\n",
            }
        ],
    }
    parsed = parse_anchor(item["anchor"])
    res = resolve_anchor(parsed, repo=rev_repo, evidence_item=item)
    assert res.status == "unresolved"
    assert "never appears" in res.reason
    assert res.detail.get("fabricated_citation") is True


def test_planted_url_without_archive_detected(rev_repo: Path) -> None:
    item = {
        "anchor": "url:https://example.com/unarchived",
        "probes": [
            {
                "role": "source",
                "method": "file-read",
                "command": "curl https://example.com/unarchived",
                "raw_output": "200 OK body",
            }
        ],
    }
    parsed = parse_anchor(item["anchor"])
    res = resolve_anchor(parsed, repo=rev_repo, evidence_item=item)
    assert res.status == "unresolved"
    assert "archived" in res.reason.lower() or "no archived" in res.reason.lower()


# ---------------------------------------------------------------------------
# Valid anchors pass
# ---------------------------------------------------------------------------


def test_valid_file_line_passes(rev_repo: Path) -> None:
    revs = _revs(rev_repo)
    parsed = parse_anchor(f"rev:{revs['head']}:doc/present.txt:2")
    res = resolve_anchor(parsed, repo=rev_repo)
    assert res.status == "resolved"
    assert res.revision_used == revs["head"]


def test_valid_command_in_transcript_passes(rev_repo: Path) -> None:
    item = {
        "anchor": "command:python -B measure.py",
        "probes": [
            {
                "role": "source",
                "method": "command",
                "command": "python -B measure.py",
                "raw_output": '{"ok": true}\n',
            },
            {
                "role": "verifier",
                "method": "file-read",
                "command": "read measure.out",
                "raw_output": '{"ok": true}\n',
            },
        ],
    }
    parsed = parse_anchor(item["anchor"])
    res = resolve_anchor(parsed, repo=rev_repo, evidence_item=item)
    assert res.status == "resolved"


def test_valid_url_with_archive_passes(rev_repo: Path) -> None:
    item = {
        "anchor": "https://example.com/spec",
        "archive_url": "https://web.archive.org/web/20260101000000/https://example.com/spec",
        "probes": [],
    }
    parsed = parse_anchor(item["anchor"])
    res = resolve_anchor(parsed, repo=rev_repo, evidence_item=item)
    assert res.status == "resolved"


def test_valid_inferred_from_passes(rev_repo: Path) -> None:
    parsed = parse_anchor("inferred-from:CC-0009 ARTIFACT-MANIFEST.json")
    res = resolve_anchor(parsed, repo=rev_repo)
    assert res.status == "resolved"


def test_validate_receipt_mixed_report(rev_repo: Path) -> None:
    revs = _revs(rev_repo)
    receipt = {
        "evidence": [
            {
                "anchor": f"rev:{revs['head']}:doc/present.txt:1",
                "claim": "present",
                "verdict": "CONFIRMED",
                "probes": [
                    {
                        "role": "source",
                        "method": "file-read",
                        "command": "git cat-file",
                        "raw_output": "alpha",
                    }
                ],
            },
            {
                "anchor": f"rev:{revs['head']}:doc/missing.txt:1",
                "claim": "fabricated",
                "verdict": "CONFIRMED",
                "probes": [
                    {
                        "role": "source",
                        "method": "file-read",
                        "command": "x",
                        "raw_output": "y",
                    }
                ],
            },
            {
                "anchor": "not a real grammar !!!",
                "claim": "junk",
                "verdict": "CONFIRMED",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": "x",
                        "raw_output": "y",
                    }
                ],
            },
        ]
    }
    report = validate_receipt_evidence(receipt, repo=rev_repo)
    assert report.anchors_checked == 3
    assert report.resolved == 1
    assert report.unresolved == 1
    assert report.unparseable == 1
    assert len(report.unresolved_list) == 1
    assert report.ok is False


# ---------------------------------------------------------------------------
# Revision correctness — stale at HEAD, valid at cited commit → must PASS
# ---------------------------------------------------------------------------


def test_revision_correctness_stale_at_head_passes_at_cited_rev(rev_repo: Path) -> None:
    revs = _revs(rev_repo)
    old, head = revs["old"], revs["head"]

    # Sanity: line 5 exists at old, not at HEAD.
    assert line_count_at_revision("doc/notes.txt", old, repo=rev_repo) == 5
    assert line_count_at_revision("doc/notes.txt", head, repo=rev_repo) == 2

    # Working-tree naive check would fail (file now has 2 lines). Cited-rev must PASS.
    pinned = parse_anchor(f"rev:{old}:doc/notes.txt:5")
    res_pinned = resolve_anchor(pinned, repo=rev_repo, default_revision=head)
    assert res_pinned.status == "resolved", res_pinned.reason
    assert res_pinned.revision_used == old

    # Same line against HEAD must be unresolved (proves we are not reading worktree/HEAD blindly).
    at_head = parse_anchor(f"rev:{head}:doc/notes.txt:5")
    res_head = resolve_anchor(at_head, repo=rev_repo)
    assert res_head.status == "unresolved"
    assert "only 2 lines" in res_head.reason


def test_path_at_rev_grammar_revision_correctness(rev_repo: Path) -> None:
    revs = _revs(rev_repo)
    parsed = parse_anchor(f"doc/notes.txt@{revs['old']}:5")
    res = resolve_anchor(parsed, repo=rev_repo, default_revision=revs["head"])
    assert res.status == "resolved"
    assert res.revision_used == revs["old"]
