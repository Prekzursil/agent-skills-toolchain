"""Both-states controls for the tracked-JSON parse gate.

Every test builds a throwaway git repo and plants the exact shape. Nothing reads or mutates this
repository except the two live assertions at the bottom, which are read-only.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import jsonparse as jp  # noqa: E402
from conftest import commit_all as _commit  # noqa: E402
from conftest import make_git_repo  # noqa: E402


def test_fires_on_a_terminal_marker_after_the_closing_brace(tmp_path: Path) -> None:
    """THE defect: a probe printed its JSON and its SUCCESS: marker to the same stdout.

    Measured on two committed artifacts - PROOF-e2e.json (line 209) and
    _wave1audit_mutation_selfcheck.json (line 155).
    """
    root = make_git_repo(tmp_path / "r")
    (root / "p.json").write_text('{"ok": true}\nSUCCESS:some-probe\n', encoding="utf-8")
    _commit(root)
    report = jp.scan(root)
    assert [f for f, _ in report["unparseable"]] == ["p.json"]
    assert "Extra data" in report["unparseable"][0][1]


def test_silent_once_the_marker_is_folded_into_the_document(tmp_path: Path) -> None:
    """Both-states pair: the fix must clear the finding and nothing else."""
    root = make_git_repo(tmp_path / "r")
    (root / "p.json").write_text(
        '{"ok": true, "marker": "SUCCESS:some-probe"}', encoding="utf-8"
    )
    _commit(root)
    assert jp.scan(root)["unparseable"] == []


def test_fires_on_a_utf8_bom(tmp_path: Path) -> None:
    root = make_git_repo(tmp_path / "r")
    (root / "b.json").write_bytes(b"\xef\xbb\xbf{}")
    _commit(root)
    report = jp.scan(root)
    assert [f for f, _ in report["unparseable"]] == ["b.json"]


def test_a_git_crypt_encrypted_file_is_EXCLUDED_not_flagged(tmp_path: Path) -> None:
    """The guard that matters most: two live accounts.json files are git-crypt ciphertext.

    They carry the \\x00GITCRYPT\\x00 magic and `filter: git-crypt`. They are ENCRYPTED, not broken.
    Flagging them would be a permanent false positive, and "repairing" one would destroy encrypted
    credential material. Exclusion is by the git filter ATTRIBUTE, with the magic bytes as a second
    independent signal.
    """
    root = make_git_repo(tmp_path / "r")
    (root / ".gitattributes").write_text(
        "secret.json filter=git-crypt diff=git-crypt\n", encoding="utf-8"
    )
    (root / "secret.json").write_bytes(b"\x00GITCRYPT\x00\xe9\x35\xd7not-json-at-all")
    _commit(root)
    report = jp.scan(root)
    assert report["unparseable"] == [], (
        "an encrypted file must never be reported as malformed"
    )
    assert report["encrypted_skipped"] == 1, "the skip must be COUNTED, never silent"


def test_the_magic_bytes_alone_also_exclude(tmp_path: Path) -> None:
    """Second signal, independent of .gitattributes: a checkout without the attribute still skips."""
    root = make_git_repo(tmp_path / "r")
    (root / "s.json").write_bytes(b"\x00GITCRYPT\x00\xff\xfe garbage")
    _commit(root)
    report = jp.scan(root)
    assert report["unparseable"] == []
    assert report["encrypted_skipped"] == 1


def test_the_ATTRIBUTE_branch_excludes_on_its_own(tmp_path: Path) -> None:
    """Attribute-only: git-crypt attribute set, but NO magic bytes. The other two exclusion tests
    supply BOTH signals or magic-only, so neither can detect an inoperative attribute branch --
    and it WAS inoperative. `check-attr --stdin -z` expects NUL-separated INPUT as well as output;
    sending newline-joined paths made git see one enormous path and match nothing, silently
    collapsing "two independent signals" to one. This test fails if that regresses.
    """
    root = make_git_repo(tmp_path / "r")
    (root / ".gitattributes").write_text(
        "marked.json filter=git-crypt diff=git-crypt\n", encoding="utf-8"
    )
    # Deliberately NOT git-crypt bytes: plain broken JSON. Only the attribute can exclude it.
    (root / "marked.json").write_text("this is not json at all", encoding="utf-8")
    # MULTIPLE tracked .json files are REQUIRED to expose the defect. With a single path,
    # "\n".join(rels) and "\0".join(rels) are indistinguishable -- there is no separator to get
    # wrong -- so a one-file fixture passes under the broken implementation and proves nothing.
    # Verified by mutation: with one file the mutant survives; with these siblings it dies.
    for n in range(3):
        (root / f"sibling{n}.json").write_text('{"n": %d}' % n, encoding="utf-8")
    _commit(root)
    report = jp.scan(root)
    assert report["unparseable"] == [], (
        "the attribute branch alone must exclude it; if this fails, --stdin -z is mis-fed again"
    )
    assert report["encrypted_skipped"] == 1
    assert report["parsed"] == 3, "the sibling files must still be parsed normally"


def test_a_plain_binary_file_is_STILL_flagged(tmp_path: Path) -> None:
    """Discrimination: the exclusion must key on git-crypt, not on 'undecodable'.

    Without this, the encrypted-file guard would silently swallow every genuinely corrupt file.
    """
    root = make_git_repo(tmp_path / "r")
    (root / "junk.json").write_bytes(b"\xe9\x35\xd7\x00 not encrypted, just broken")
    _commit(root)
    assert [f for f, _ in jp.scan(root)["unparseable"]] == ["junk.json"]


def test_scan_fails_closed_when_git_returns_nothing(tmp_path: Path) -> None:
    root = make_git_repo(tmp_path / "r")
    with pytest.raises(ValueError, match="fail closed"):
        jp.scan(root)


def test_a_valid_repo_reports_the_count_it_actually_parsed(tmp_path: Path) -> None:
    root = make_git_repo(tmp_path / "r")
    for n in range(3):
        (root / f"{n}.json").write_text('{"n": %d}' % n, encoding="utf-8")
    _commit(root)
    report = jp.scan(root)
    assert report["parsed"] == 3 and report["unparseable"] == []


# --- live repo, read-only ---


def test_the_live_repo_has_no_unparseable_tracked_json() -> None:
    report = jp.scan()
    assert report["unparseable"] == [], (
        f"unparseable tracked JSON: {report['unparseable']}"
    )


def test_the_live_walk_did_not_collapse() -> None:
    """`0 unparseable` from having parsed nothing is a no-op wearing a green badge."""
    report = jp.scan()
    assert report["parsed"] >= jp.MIN_FILES, (
        f"parsed only {report['parsed']}, below floor {jp.MIN_FILES}"
    )
    # 2026-10-22: the git-crypt accounts.json pair (tools/mcp/cloud-hub,
    # tools/mcp/search-hub) was left plaintext by #376 (b898382e4) and now
    # PARSES like any other tracked JSON. The old `>= 2` floor pinned the
    # pre-#376 state; this pins the post-#376 state instead: the walk must
    # hand every tracked JSON to the parser (0 encrypted skips). If this
    # ever goes > 0 again, git-crypt content returned to the tree -- a state
    # change worth a loud failure, not a silent skip.
    assert report["encrypted_skipped"] == 0, (
        f"git-crypt-skip count changed: {report['encrypted_skipped']} tracked JSON "
        "file(s) are encrypted again; the tree state moved -- update this pin deliberately"
    )
