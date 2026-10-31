"""Both-states controls for the vendored-copy drift gate.

Every "the gate is quiet" assertion here is paired with a case that makes the SAME gate fire, so
the quiet reading means something. A probe that is silent in the broken state measures nothing.

`core.autocrlf` is forced OFF in every throwaway repo, and that is a detector control rather than
tidiness: this box has `core.autocrlf=true` globally (measured), which normalises CRLF to LF at
`git add`. Without the override the CRLF fixture would be committed as LF, both blobs would carry
the SAME OID, and `test_crlf_only_is_its_own_class` would pass while classifying nothing at all.
It therefore asserts the OIDs really diverge before it reads the verdict.

Nothing here touches this repository. `commit_all` uses `git add -A`, which is banned against the
shared worktree and fine here: every call targets a fresh repo under `tmp_path`.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import vendordrift as vd  # noqa: E402
from conftest import commit_all as _commit  # noqa: E402
from conftest import make_git_repo  # noqa: E402

SRC = "tools/monitorcore/monitorcore"
COPY = "skills/workflow-monitor/monitorcore"
BODY = b"def poll():\n    return 1\n"


def _repo(tmp_path: Path) -> Path:
    root = make_git_repo(tmp_path / "r")
    subprocess.run(
        ["git", "-C", str(root), "config", "core.autocrlf", "false"],
        check=True,
        capture_output=True,
    )
    return root


def _plant(root: Path, rel: str, files: dict[str, bytes]) -> None:
    directory = root / rel
    directory.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        (directory / name).write_bytes(data)


def _vendored(tmp_path: Path, copies: tuple[str, ...] = (COPY,)) -> Path:
    """A repo whose every vendored copy is byte-identical to the source of truth."""
    root = _repo(tmp_path)
    files = {"__init__.py": b'"""pkg."""\n', "stall.py": BODY}
    for rel in (SRC, *copies):
        _plant(root, rel, files)
    _commit(root)
    return root


def _oid(root: Path, path: str) -> str:
    out = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-s", "--", path],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return out.split()[1]


def _entries(report: dict[str, object]) -> list[dict[str, object]]:
    copies = report["copies"]
    assert isinstance(copies, list)
    return copies


def _paths(report: dict[str, object]) -> list[str]:
    return sorted(str(c["path"]) for c in _entries(report))


def _only(report: dict[str, object], path: str) -> dict[str, object]:
    match = [c for c in _entries(report) if c["path"] == path]
    assert match, f"{path} was never discovered; copies={_paths(report)}"
    return match[0]


# --------------------------------------------------------------------------------------------
# the quiet state, and the control that proves the quiet means something
# --------------------------------------------------------------------------------------------


def test_identical_copies_are_clean(tmp_path: Path) -> None:
    report = vd.scan(_vendored(tmp_path), source=SRC)
    assert report["total_drift"] == 0
    assert report["source_files"] == 2
    assert _paths(report) == [COPY]


def test_one_changed_byte_fires_and_names_the_file(tmp_path: Path) -> None:
    """THE control for the test above: same fixture, one byte moved, gate must go red."""
    root = _vendored(tmp_path)
    (root / COPY / "stall.py").write_bytes(BODY.replace(b"return 1", b"return 2"))
    _commit(root, "drift")

    report = vd.scan(root, source=SRC)
    assert report["total_drift"] == 1
    entry = _only(report, COPY)
    assert entry["content"] == ["stall.py"]
    assert entry["crlf_only"] == []


def test_main_reports_a_terminal_state_in_both_directions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """AGENTS.md 4: the CLI must end on SUCCESS:<id> or FAILED:<id>, never open-ended prose."""
    root = _vendored(tmp_path)
    monkeypatch.setattr(vd, "REPO", root)

    assert vd.main(["--source", SRC]) == 0
    clean = capsys.readouterr().out
    assert clean.strip().startswith("SUCCESS:vendordrift")

    (root / COPY / "stall.py").write_bytes(b"def poll():\n    return 7\n")
    _commit(root, "drift")

    assert vd.main(["--source", SRC]) == 1
    dirty = capsys.readouterr().out
    assert "CONTENT" in dirty and f"{COPY}/stall.py" in dirty
    assert dirty.strip().splitlines()[-1].startswith("FAILED:vendordrift")


# --------------------------------------------------------------------------------------------
# classification: a line-ending phantom is drift, but it is not a logic change
# --------------------------------------------------------------------------------------------


def test_crlf_only_is_its_own_class(tmp_path: Path) -> None:
    root = _vendored(tmp_path)
    (root / COPY / "stall.py").write_bytes(BODY.replace(b"\n", b"\r\n"))
    _commit(root, "crlf")

    # Detector control: if autocrlf had normalised the fixture the OIDs would match and the
    # classification below would be vacuous.
    assert _oid(root, f"{SRC}/stall.py") != _oid(root, f"{COPY}/stall.py")

    entry = _only(vd.scan(root, source=SRC), COPY)
    assert entry["crlf_only"] == ["stall.py"]
    assert entry["content"] == []


def test_crlf_only_still_fails_the_gate(tmp_path: Path) -> None:
    """Different committed bytes are different in a fresh Linux clone; classify, do not exempt."""
    root = _vendored(tmp_path)
    (root / COPY / "stall.py").write_bytes(BODY.replace(b"\n", b"\r\n"))
    _commit(root, "crlf")
    assert vd.scan(root, source=SRC)["total_drift"] == 1


# --------------------------------------------------------------------------------------------
# set differences
# --------------------------------------------------------------------------------------------


def test_a_file_missing_from_a_copy_fires(tmp_path: Path) -> None:
    root = _vendored(tmp_path)
    (root / COPY / "stall.py").unlink()
    _commit(root, "drop")
    entry = _only(vd.scan(root, source=SRC), COPY)
    assert entry["missing"] == ["stall.py"]
    assert entry["extra"] == []


def test_a_file_only_in_the_copy_fires(tmp_path: Path) -> None:
    root = _vendored(tmp_path)
    (root / COPY / "orphan.py").write_bytes(b"x = 1\n")
    _commit(root, "add")
    entry = _only(vd.scan(root, source=SRC), COPY)
    assert entry["extra"] == ["orphan.py"]
    assert entry["missing"] == []


# --------------------------------------------------------------------------------------------
# discovery: the reason this is not two hardcoded paths
# --------------------------------------------------------------------------------------------


def test_a_third_copy_is_gated_with_no_configuration_change(tmp_path: Path) -> None:
    """The hole in the shipped CI step: it names one pair, so copy number three arrives ungated."""
    third = ".agents/skills/workflow-monitor/monitorcore"
    root = _vendored(tmp_path, copies=(COPY, third))
    assert _paths(vd.scan(root, source=SRC)) == sorted([COPY, third])

    (root / third / "stall.py").write_bytes(b"def poll():\n    return 99\n")
    _commit(root, "drift the ungated copy")

    report = vd.scan(root, source=SRC)
    assert report["total_drift"] == 1
    assert _only(report, third)["content"] == ["stall.py"]
    assert _only(report, COPY)["content"] == []


def test_find_copies_matches_a_repo_root_package(tmp_path: Path) -> None:
    """A copy vendored at the repo root has no leading slash and must still be discovered."""
    paths = {"monitorcore/__init__.py", f"{SRC}/__init__.py", "notes/monitorcore.md"}
    assert vd.find_copies(paths, "monitorcore", SRC) == ["monitorcore"]


# --------------------------------------------------------------------------------------------
# the index/HEAD trap named in the module docstring
# --------------------------------------------------------------------------------------------


def test_staged_but_uncommitted_drift_is_caught(tmp_path: Path) -> None:
    """Kills the `cat-file -p HEAD:<path>` regression.

    HEAD still holds two identical copies; the INDEX does not. A gate that discovered the
    difference from `ls-files` and then read bytes from HEAD would classify this as clean.
    """
    root = _vendored(tmp_path)
    (root / COPY / "stall.py").write_bytes(b"def poll():\n    return 3\n")
    subprocess.run(
        ["git", "-C", str(root), "add", f"{COPY}/stall.py"],
        check=True,
        capture_output=True,
    )
    # Control: HEAD is genuinely still clean, so a HEAD-reading gate really would say 0.
    head = subprocess.run(
        ["git", "-C", str(root), "cat-file", "-p", f"HEAD:{COPY}/stall.py"],
        capture_output=True,
        check=True,
    ).stdout
    assert head == BODY

    entry = _only(vd.scan(root, source=SRC), COPY)
    assert entry["content"] == ["stall.py"]


# --------------------------------------------------------------------------------------------
# fail closed: "0 drift" must never come from having found nothing
# --------------------------------------------------------------------------------------------


def test_empty_walk_fails_closed(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    with pytest.raises(vd.VendorDriftError, match="ls-files returned nothing"):
        vd.scan(root, source=SRC)


def test_absent_source_of_truth_fails_closed(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _plant(root, COPY, {"__init__.py": b"\n"})
    _commit(root)
    with pytest.raises(vd.VendorDriftError, match="no tracked files"):
        vd.scan(root, source=SRC)


def test_zero_discovered_copies_fails_closed(tmp_path: Path) -> None:
    """A source of truth with no consumers is discovery breaking, not a clean bill of health."""
    root = _repo(tmp_path)
    _plant(root, SRC, {"__init__.py": b"\n"})
    _commit(root)
    with pytest.raises(vd.VendorDriftError, match="below the floor"):
        vd.scan(root, source=SRC)


def test_unreadable_blob_degrades_to_the_louder_class() -> None:
    """Cannot prove "line endings only" => report CONTENT. Never the quieter verdict."""
    oids = {
        f"{SRC}/stall.py": "0" * 40,
        f"{COPY}/stall.py": "1" * 40,
    }
    entry = vd.compare(Path("."), oids, SRC, COPY)
    assert entry["content"] == ["stall.py"]
    assert entry["crlf_only"] == []


# --------------------------------------------------------------------------------------------
# the CI invocation shape
# --------------------------------------------------------------------------------------------


def test_cli_entry_runs_in_the_shape_ci_uses() -> None:
    """`python tools/measure-guard/vendordrift.py` from the repo root must resolve `blobread`.

    Scoped deliberately: this asserts the ENTRY POINT works, not that this repository is
    drift-free. Asserting the latter here would duplicate the CI step and paint an unrelated
    lane's test run red for a reason the test name does not explain.
    """
    repo = Path(__file__).resolve().parents[3]
    proc = subprocess.run(
        [sys.executable, "tools/measure-guard/vendordrift.py"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode in (0, 1), proc.stderr
    assert "Traceback" not in proc.stderr, proc.stderr
    assert (
        proc.stdout.strip()
        .splitlines()[-1]
        .startswith(("SUCCESS:vendordrift", "FAILED:vendordrift"))
    )
