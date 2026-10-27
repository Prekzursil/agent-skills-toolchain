"""Platform-parity tests for blob-route provenance hashing (IMP-0439).

Runnable as a script (`python tests/test_blob_provenance.py`) and as pytest.
The control that the working-tree route DIFFERS is load-bearing: identical
hashes on both routes would be silence in both states.
"""

from __future__ import annotations

import hashlib
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import blob  # noqa: E402
import render  # noqa: E402


def test_manifest_filenames_match_render_contract() -> None:
    assert blob.MANIFEST_FILENAMES == render.CONTRACTED_ARTIFACTS
    assert len(blob.MANIFEST_FILENAMES) == 14


def test_helper_uses_cat_file_and_refuses_archive_argv() -> None:
    src = Path(blob.__file__).read_text(encoding="utf-8")
    assert "cat-file" in src
    assert '", "archive"' not in src
    assert "', 'archive'" not in src


def test_known_file_blob_equals_show(tmp_path: Path) -> None:
    repo = blob.init_manifest_fixture(tmp_path)
    rel = "command-center/PROGRAM-CHARTER.md"
    cat = blob.blob_bytes(repo, rel)
    shown = blob.show_bytes(repo, rel)
    assert cat == shown
    assert b"\r\n" not in cat
    assert cat == blob._fixture_body("PROGRAM-CHARTER.md")


def test_blob_route_identical_on_crlf_vs_lf_and_worktree_differs(
    tmp_path: Path,
) -> None:
    result = blob.parity_experiment(tmp_path)
    assert result["n_entries"] == 14
    assert result["n_crlf_rewritten"] == 14
    assert result["blob_route_identical_crlf_vs_lf"] is True
    assert result["blob_equals_recorded_for_all_14"] is True
    assert result["working_tree_route_differs_for_all_14"] is True
    assert result["independent_git_show_matches_cat_file"] is True


def test_untracked_path_falls_back_to_lf_normalised(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    lf = b"# register\nline two\n"
    path = tmp_path / "REGISTER.md"
    path.write_bytes(lf.replace(b"\n", b"\r\n"))
    got = blob.provenance_bytes(path)
    assert got == lf
    assert blob.sha256_hex(got) == hashlib.sha256(lf).hexdigest()


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0439-tests-") as td:
        root = Path(td)
        test_manifest_filenames_match_render_contract()
        test_helper_uses_cat_file_and_refuses_archive_argv()
        test_known_file_blob_equals_show(root / "known")
        test_blob_route_identical_on_crlf_vs_lf_and_worktree_differs(root / "parity")
        test_untracked_path_falls_back_to_lf_normalised(root / "fallback")
    print("SUCCESS:test_blob_provenance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
